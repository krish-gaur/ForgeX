"""Celery worker entrypoint (optional production task backend).

Activated only when TASK_BACKEND=celery AND celery+redis are installed
(requirements-extra.txt). Workers execute the SAME `execute_job` code path as
the inline asyncio executor, so job semantics are identical in both modes.
"""
from __future__ import annotations

from celery import Celery

from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "forgex",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
)

# Importing the pipeline module registers the COLLECT / AI / REPORT runners in
# app.jobs.executor.RUNNERS inside the worker process.
from app.services import pipeline  # noqa: E402,F401  (registration side effects)


@celery_app.task(name="forgex.run_job", bind=True, max_retries=5, default_retry_delay=2)
def run_job_task(self, job_id: str) -> dict:
    """Execute one queued job. Retries briefly while the API transaction that
    created the job row is still committing (submit → enqueue → commit race)."""
    import asyncio

    from app.jobs.executor import execute_job

    found = asyncio.run(execute_job(job_id))
    if not found:
        raise self.retry(exc=RuntimeError(f"job {job_id} not visible yet"))
    return {"job_id": job_id, "executed": True}
