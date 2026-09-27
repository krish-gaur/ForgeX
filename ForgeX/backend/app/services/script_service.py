"""Script Lab service: snapshot assembly, sandboxed execution, findings persistence."""
from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import audit
from app.core.errors import NotFound, PermissionDenied
from app.core.websocket import manager
from app.db.models import (
    AnchorRecord,
    EvidenceItem,
    Finding,
    FindingSource,
    FindingStatus,
    GraphEdge,
    Investigation,
    Role,
    ScriptExecStatus,
    ScriptExecution,
    User,
)
from app.execution import sandbox
from app.execution.validation import validate_function
from app.services.blockchain_service import iso_norm
from app.services.timeline_service import build_timeline

settings = get_settings()

ROLE_ALLOWED = {Role.ADMIN.value, Role.LEAD_INVESTIGATOR.value, Role.INVESTIGATOR.value}


async def build_snapshot(db: AsyncSession, investigation: Investigation) -> dict:
    evidence = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == investigation.id))).scalars().all()
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.investigation_id == investigation.id))).scalars().all()
    ev_ids = {e.id for e in evidence}
    custody = (
        await db.execute(select(AnchorRecord).where(AnchorRecord.evidence_id.in_(ev_ids)).order_by(AnchorRecord.id))
    ).scalars().all() if ev_ids else []
    timeline = await build_timeline(db, investigation.id)
    return {
        "investigation": {
            "id": investigation.id,
            "name": investigation.name,
            "target_host": investigation.target_host,
            "target_os": investigation.target_os,
            "provenance": investigation.provenance,
        },
        "evidence": [
            {
                "id": e.id,
                "evidence_type": e.evidence_type,
                "data": e.data,
                "data_hash": e.data_hash,
                "collected_at": e.collected_at.isoformat() if e.collected_at else None,
                "provenance": e.provenance,
            }
            for e in evidence
        ],
        "timeline": timeline,
        "graph": {
            "edges": [{"source": e.src_node, "target": e.dst_node, "label": e.rel_type} for e in edges],
        },
        "custody": [
            {"evidence_id": c.evidence_id, "data_hash": c.data_hash, "prev_hash": c.prev_hash, "record_hash": c.record_hash, "created_at": iso_norm(c.created_at)}
            for c in custody
        ],
    }


async def run_script(
    db: AsyncSession,
    investigation: Investigation,
    script_id: str | None,
    code: str,
    user: User,
    request=None,
) -> ScriptExecution:
    if user.role not in ROLE_ALLOWED:
        raise PermissionDenied(f"Role {user.role} cannot execute forensic functions.", details={"required_roles": sorted(ROLE_ALLOWED)})
    validate_function(code)  # raises ScriptValidationError with actionable problems
    execution = ScriptExecution(
        script_id=script_id,
        investigation_id=investigation.id,
        status=ScriptExecStatus.RUNNING.value,
        triggered_by=user.id,
    )
    db.add(execution)
    await db.flush()
    exec_id = execution.id
    snapshot = await build_snapshot(db, investigation)
    result = await sandbox.run_function(exec_id, code, snapshot, settings.script_timeout_sec)
    now = datetime.now(UTC)
    status_map = {
        "COMPLETED": ScriptExecStatus.COMPLETED,
        "FAILED": ScriptExecStatus.FAILED,
        "TIMEOUT": ScriptExecStatus.TIMEOUT,
        "SANDBOX_VIOLATION": ScriptExecStatus.SANDBOX_VIOLATION,
    }
    execution.status = status_map.get(result.get("status"), ScriptExecStatus.FAILED).value
    execution.completed_at = now
    execution.console_log = "\n".join(result.get("console", []))[:200_000]
    execution.resource_usage = result.get("metrics") or {}
    if result.get("error"):
        execution.error_message = f"{result['error'].get('type')}: {result['error'].get('message')}"[:2000]
    findings = result.get("findings", [])
    valid_ids = {e["id"] for e in snapshot["evidence"]}
    stored = 0
    for f in findings:
        ev_ids = [i for i in f.get("evidence_ids", []) if i in valid_ids]
        db.add(
            Finding(
                investigation_id=investigation.id,
                execution_id=exec_id,
                source=FindingSource.SCRIPT.value,
                severity=f.get("severity", "INFO"),
                title=f.get("title", "Untitled finding")[:300],
                description=f.get("description"),
                evidence_ids=ev_ids,
                mitre_techniques=f.get("mitre_techniques", []),
                status=FindingStatus.OPEN.value,
            )
        )
        stored += 1
    execution.findings_count = stored
    await audit.audit(
        db,
        "SCRIPT_EXECUTED",
        actor=user,
        resource_type="script_execution",
        resource_id=exec_id,
        metadata={"script_id": script_id, "status": execution.status, "findings": stored},
        request=request,
    )
    await db.commit()
    await manager.broadcast(investigation.id, {"type": "SCRIPT_COMPLETE", "execution_id": exec_id, "status": execution.status, "findings": stored})
    return execution


async def stop_script(db: AsyncSession, execution_id: str, user: User, request=None) -> bool:
    execution = await db.get(ScriptExecution, execution_id)
    if not execution:
        raise NotFound(f"No execution with id {execution_id}")
    stopped = await sandbox.stop_function(execution_id)
    if stopped:
        execution.status = ScriptExecStatus.STOPPED.value
        execution.completed_at = datetime.now(UTC)
        execution.error_message = "Stopped by user."
        await audit.audit(db, "SCRIPT_STOPPED", actor=user, resource_type="script_execution", resource_id=execution_id, request=request)
        await db.commit()
    return stopped
