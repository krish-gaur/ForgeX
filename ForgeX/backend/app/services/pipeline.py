"""Job runners: FQL collection pipeline, AI analysis, report generation."""
from __future__ import annotations

import asyncio
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.base import CollectContext
from app.collectors.event_collector import EventCollector
from app.collectors.file_collector import FileCollector
from app.collectors.network_collector import NetworkCollector
from app.collectors.process_collector import ProcessCollector
from app.collectors.user_collector import UserCollector
from app.core.logging import get_logger
from app.db.models import (
    CollectorExecution,
    CollectorStatus,
    CollectorType,
    FqlQuery,
    Investigation,
    Job,
    JobStatus,
    Provenance,
    User,
)
from app.jobs.executor import register_runner
from app.services.evidence_service import store_items
from app.services.timeline_service import build_timeline, parse_ts

log = get_logger("pipeline")

COLLECTORS = {
    CollectorType.PROCESS: ProcessCollector,
    CollectorType.FILE: FileCollector,
    CollectorType.NETWORK: NetworkCollector,
    CollectorType.USER: UserCollector,
    CollectorType.EVENT: EventCollector,
}


@register_runner("COLLECT")
async def runner_collect(session: AsyncSession, job: Job) -> None:
    from app.config import get_settings

    settings = get_settings()
    payload = job.payload or {}
    fql = await session.get(FqlQuery, payload["fql_query_id"])
    investigation = await session.get(Investigation, job.investigation_id)
    user = await session.get(User, fql.submitted_by)
    rules = payload.get("policy_rules") or {}
    collectors_spec = payload.get("collectors") or []
    provenance = Provenance(investigation.provenance)

    total_stored = 0
    completed = 0
    failures = 0
    per_collector: dict[str, str] = {}
    for spec in collectors_spec:
        ctype = CollectorType(spec["type"])
        params = spec.get("params") or {}
        execution = CollectorExecution(
            fql_query_id=fql.id,
            collector_type=ctype.value,
            status=CollectorStatus.RUNNING.value,
            raw_params=params,
        )
        session.add(execution)
        await session.flush()
        job.progress = {"completed": completed, "total": len(collectors_spec), "current": ctype.value}
        try:
            if ctype == CollectorType.TIMELINE:
                entries = await build_timeline(session, investigation.id, parse_ts(params.get("from")), parse_ts(params.get("to")))
                execution.status = CollectorStatus.COMPLETED.value
                execution.items_collected = len(entries)
                total_stored += 0
            else:
                collector = COLLECTORS[ctype]()
                ctx = CollectContext(
                    investigation=investigation,
                    params=params,
                    rules=rules,
                    provenance=provenance,
                    deadline=asyncio.get_event_loop().time() + settings.collector_timeout_sec,
                )
                items = await asyncio.wait_for(collector.collect(ctx), timeout=settings.collector_timeout_sec)
                stored, _dups = await store_items(session, investigation, execution.id, ctype, items, user, provenance)
                execution.status = CollectorStatus.COMPLETED.value
                execution.items_collected = stored
                total_stored += stored
            completed += 1
        except TimeoutError:
            execution.status = CollectorStatus.TIMEOUT.value
            execution.error_message = f"Collector exceeded {settings.collector_timeout_sec}s timeout; partial results kept."
            failures += 1
        except Exception as e:  # noqa: BLE001 — per-collector isolation
            execution.status = CollectorStatus.FAILED.value
            execution.error_message = f"{type(e).__name__}: {str(e)[:300]}"
            log.warning("collector_failed", collector=ctype.value, error=str(e)[:200])
            failures += 1
        execution.completed_at = datetime.now(UTC)
        per_collector[ctype.value] = execution.status
        job.progress = {"completed": completed, "total": len(collectors_spec)}
        await session.flush()
        from app.core.websocket import manager

        await manager.broadcast(investigation.id, {"type": "JOB_STATUS", "job_id": job.id, "status": "RUNNING", "progress": job.progress, "collectors": per_collector})

    if failures == 0:
        fql.status = JobStatus.COMPLETED.value
        job.status = JobStatus.COMPLETED.value
    elif completed > 0:
        fql.status = JobStatus.PARTIAL.value
        job.status = JobStatus.PARTIAL.value
    else:
        fql.status = JobStatus.FAILED.value
        job.status = JobStatus.FAILED.value
        first_err = next((e.error_message for e in [execution] if e.error_message), None)
        fql.error_message = first_err or "All collectors failed"
        job.error_message = fql.error_message
    fql.completed_at = datetime.now(UTC)
    job.completed_at = datetime.now(UTC)
    job.result = {"evidence_count": total_stored, "collectors": per_collector}


@register_runner("AI")
async def runner_ai(session: AsyncSession, job: Job) -> None:
    from app.services.ai_service import run_analysis_job

    await run_analysis_job(session, job)


@register_runner("REPORT")
async def runner_report(session: AsyncSession, job: Job) -> None:
    from app.services.report_service import run_report_job

    await run_report_job(session, job)
