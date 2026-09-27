"""FQL execution service: parse → policy → job enqueue (architecture WF-02)."""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.errors import PolicyDenied
from app.db.models import AuditResult, FqlQuery, Investigation, JobStatus, User
from app.fql.parser import parse_fql
from app.fql.to_collector_params import ast_to_collector_params
from app.jobs.executor import executor
from app.policy import engine as policy_engine
from app.policy.loader import get_active_policy


async def validate(db: AsyncSession, investigation: Investigation, user: User, fql_text: str) -> dict:
    prog = parse_fql(fql_text)  # FqlParseError with line/col on bad syntax
    policy = await get_active_policy(db)
    decision = policy_engine.evaluate(user, investigation, prog.collectors, policy.rules, check_rate_limit=False)
    return {
        "valid": True,
        "ast": prog.to_dict(),
        "estimated_collectors": [c.upper() for c in prog.collectors],
        "policy_preview": decision.to_dict(),
    }


async def execute(db: AsyncSession, investigation: Investigation, user: User, fql_text: str, policy_id: str | None, request=None) -> tuple[FqlQuery, dict]:
    prog = parse_fql(fql_text)
    policy = await get_active_policy(db, policy_id)
    decision = policy_engine.evaluate(user, investigation, prog.collectors, policy.rules, check_rate_limit=True)
    query = FqlQuery(
        investigation_id=investigation.id,
        raw_fql=fql_text,
        parsed_ast=prog.to_dict(),
        status=JobStatus.VALIDATED.value,
        policy_decision=decision.to_dict(),
        submitted_by=user.id,
    )
    db.add(query)
    await db.flush()

    if decision.status == "DENIED":
        query.status = JobStatus.POLICY_DENIED.value
        query.error_message = "; ".join(decision.reasons)
        await audit.audit(db, "FQL_POLICY_DENIED", actor=user, resource_type="fql_query", resource_id=query.id, metadata={"reasons": decision.reasons}, result=AuditResult.DENIED, request=request)
        await db.commit()
        raise PolicyDenied(decision.reasons[0] if decision.reasons else "Policy denied this execution.", details=decision.to_dict())

    specs = [{"type": ctype.value, "params": params} for ctype, params in ast_to_collector_params(prog)]
    job = await executor.submit(db, "COLLECT", investigation.id, query.id, {"fql_query_id": query.id, "collectors": specs, "policy_rules": policy.rules})
    query.status = JobStatus.QUEUED.value
    await audit.audit(db, "FQL_EXECUTED", actor=user, resource_type="fql_query", resource_id=query.id, metadata={"collectors": prog.collectors, "job_id": job.id}, request=request)
    await db.commit()
    return query, {
        "job_id": job.id,
        "fql_query_id": query.id,
        "collectors": [s["type"] for s in specs],
        "estimated_duration_sec": 15,
        "status_endpoint": f"/api/v1/jobs/{job.id}/status",
    }
