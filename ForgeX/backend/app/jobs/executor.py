"""Async job execution. Inline asyncio executor by default; Celery/Redis in production.

Both executors drive the same runner coroutines in app.services.pipeline, so
business logic lives in exactly one place.
"""
from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.core.websocket import manager
from app.db.models import Job, JobStatus
from app.db.session import SessionLocal

settings = get_settings()
log = get_logger("jobs")

RUNNERS: dict[str, Callable[[AsyncSession, Job], Awaitable[None]]] = {}


def register_runner(kind: str):
    def deco(fn):
        RUNNERS[kind] = fn
        return fn

    return deco


async def _create_job(db: AsyncSession, kind: str, investigation_id: str, ref_id: str | None, payload: dict) -> Job:
    job = Job(kind=kind, investigation_id=investigation_id, ref_id=ref_id, status=JobStatus.QUEUED.value, payload=payload, progress={})
    db.add(job)
    await db.flush()
    return job


# `submit()` flushes the job inside the *request* transaction, which commits a
# few statements later (audit row + commit). An inline task or a Celery worker can
# therefore start before the row is visible to its own DB connection. Without this
# wait the job is silently orphaned in QUEUED forever (observed as an intermittent
# "collection job never completes" under load).
JOB_VISIBILITY_TIMEOUT_SEC = 20.0


async def _await_job_row(job_id: str, timeout: float = JOB_VISIBILITY_TIMEOUT_SEC) -> Job | None:
    """Poll (fresh session per attempt) until the job row is committed & visible."""
    deadline = time.monotonic() + timeout
    while True:
        async with SessionLocal() as probe:
            job = await probe.get(Job, job_id)
        if job is not None:
            return job
        if time.monotonic() >= deadline:
            return None
        await asyncio.sleep(0.05)


async def execute_job(job_id: str) -> bool:
    """Run one queued job: runner dispatch, status transitions, WS fan-out.

    Single code path shared by the inline asyncio executor and Celery workers.
    Returns False when the job row never became visible — Celery retries then.
    """
    job = await _await_job_row(job_id)
    if job is None:
        log.error("job_row_not_visible", job=job_id, timeout_sec=JOB_VISIBILITY_TIMEOUT_SEC)
        return False

    async with SessionLocal() as session:
        job = await session.get(Job, job_id)
        if not job:  # pragma: no cover - row vanished between polls
            return False
        runner = RUNNERS.get(job.kind)
        if runner is None:
            job.status = JobStatus.FAILED.value
            job.error_message = f"No runner registered for job kind {job.kind}"
            await session.commit()
            return True
        job.status = JobStatus.RUNNING.value
        job.started_at = datetime.now(UTC)
        await session.commit()
        await manager.broadcast(job.investigation_id, {"type": "JOB_STATUS", "job_id": job.id, "status": "RUNNING", "progress": job.progress})
        try:
            await runner(session, job)
            await session.commit()
            await manager.broadcast(
                job.investigation_id,
                {"type": "JOB_COMPLETE", "job_id": job.id, "kind": job.kind, "result": job.result or {}},
            )
        except Exception as e:  # noqa: BLE001 — job boundary
            await session.rollback()
            async with SessionLocal() as err_session:
                j2 = await err_session.get(Job, job_id)
                if j2:
                    j2.status = JobStatus.FAILED.value
                    j2.error_message = f"{type(e).__name__}: {str(e)[:300]}"
                    await err_session.commit()
            log.exception("job_failed", job=job_id, kind=job.kind, error=str(e)[:200])
            await manager.broadcast(job.investigation_id, {"type": "JOB_FAILED", "job_id": job_id, "error": str(e)[:300]})
    return True


async def recover_orphaned_jobs() -> int:
    """Re-enqueue jobs left QUEUED by a previous process (crash/restart safety net).

    Only meaningful for the inline executor: Celery workers own their own queue.
    """
    requeued = 0
    async with SessionLocal() as session:
        rows = (await session.execute(select(Job).where(Job.status == JobStatus.QUEUED.value))).scalars().all()
        for job in rows:
            task = asyncio.create_task(executor._run(job.id))  # noqa: SLF001 - same class, recovery path
            executor._tasks.add(task)  # noqa: SLF001
            task.add_done_callback(executor._tasks.discard)  # noqa: SLF001
            requeued += 1
    if requeued:
        log.warning("orphaned_jobs_requeued", count=requeued)
    return requeued


class InlineExecutor:
    def __init__(self) -> None:
        self._sem = asyncio.Semaphore(settings.max_concurrent_jobs)
        self._tasks: set[asyncio.Task] = set()

    async def submit(self, db: AsyncSession, kind: str, investigation_id: str, ref_id: str | None, payload: dict) -> Job:
        job = await _create_job(db, kind, investigation_id, ref_id, payload)
        job_id = job.id
        task = asyncio.create_task(self._run(job_id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return job

    async def _run(self, job_id: str) -> None:
        async with self._sem:
            await execute_job(job_id)


class CeleryExecutor(InlineExecutor):
    """Enqueues jobs to Celery (TASK_BACKEND=celery); workers run the SAME
    execute_job code path, so behavior is identical to inline execution."""

    async def submit(self, db: AsyncSession, kind: str, investigation_id: str, ref_id: str | None, payload: dict) -> Job:
        job = await _create_job(db, kind, investigation_id, ref_id, payload)
        from app.workers.celery_app import run_job_task

        run_job_task.delay(job.id)
        log.info("job_enqueued_celery", job=job.id, kind=kind)
        return job


def get_executor() -> InlineExecutor:
    if settings.task_backend == "celery":
        try:
            from app.workers.celery_app import celery_app  # noqa: F401

            return CeleryExecutor()
        except ImportError:
            log.warning("celery_unavailable_falling_back_inline")
    return InlineExecutor()


executor = get_executor()
