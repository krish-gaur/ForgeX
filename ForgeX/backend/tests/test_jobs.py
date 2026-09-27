"""Job executor regression tests.

Covers the commit-visibility race: `executor.submit()` flushes the Job row inside
the *request* transaction, which commits a few statements later (audit row +
`db.commit()`). The inline task therefore starts before the row is visible to its
own DB connection. Before the fix the task silently dropped the job, leaving it
QUEUED forever (intermittent "collection job never completes" under load).
"""
from __future__ import annotations

import asyncio

from app.db.models import Investigation, InvestigationStatus, Job, JobStatus, SourceMode, TargetOS
from app.db.session import SessionLocal
from app.jobs.executor import JOB_VISIBILITY_TIMEOUT_SEC, execute_job
from tests.test_api_integration import _wait_job, auth, login


async def _make_investigation(users) -> str:
    async with SessionLocal() as s:
        inv = Investigation(
            name="job-race-case",
            target_host="ws-race.lab",
            target_os=TargetOS.WINDOWS,
            source_mode=SourceMode.DATASET,
            status=InvestigationStatus.ACTIVE,
            created_by=users["LEAD_INVESTIGATOR"].id,
        )
        s.add(inv)
        await s.commit()
        return inv.id


async def test_execute_job_waits_for_uncommitted_row(client, users, policy):
    """A task started before the creating transaction commits must still run the job."""
    inv_id = await _make_investigation(users)

    async with SessionLocal() as s:
        job = Job(kind="NO_RUNNER", investigation_id=inv_id, status=JobStatus.QUEUED.value, payload={}, progress={})
        s.add(job)
        await s.flush()
        job_id = job.id

        # Mimic the endpoint ordering: the task is created at submit() time and the
        # transaction commits only later (audit row + commit).
        task = asyncio.create_task(execute_job(job_id))
        await asyncio.sleep(0.25)  # let the task start while the row is still invisible
        await s.commit()

        found = await asyncio.wait_for(task, timeout=JOB_VISIBILITY_TIMEOUT_SEC + 10)

    assert found is True, "execute_job dropped a job whose row was not yet committed"

    async with SessionLocal() as s:
        stored = await s.get(Job, job_id)
        assert stored is not None
        # No runner registered for NO_RUNNER → the job is failed explicitly, never orphaned.
        assert stored.status == JobStatus.FAILED.value
        assert "No runner registered" in (stored.error_message or "")


async def test_execute_job_returns_false_for_missing_row(client, users, policy):
    """A genuinely absent job id returns False (Celery retry signal) instead of hanging."""
    found = await asyncio.wait_for(execute_job("00000000-0000-0000-0000-000000000000"), timeout=JOB_VISIBILITY_TIMEOUT_SEC + 10)
    assert found is False


async def test_fql_execute_job_reaches_terminal_state(client, users, policy):
    """End-to-end: the real FQL execute path (submit → audit → commit) must complete."""
    token = await login(client, "lead")
    h = auth(token)

    r = await client.post(
        "/api/v1/investigations",
        headers=h,
        json={"name": "job-race-e2e", "target_host": "ws-race2.lab", "target_os": "WINDOWS", "source_mode": "DATASET", "source_path": "synthetic-corp-breach"},
    )
    assert r.status_code == 201, r.text
    inv = r.json()["id"]

    r = await client.post(f"/api/v1/investigations/{inv}/fql/execute", headers=h, json={"fql": "INVESTIGATE processes WHERE user = 'svc_backup'"})
    assert r.status_code == 202, r.text
    job_id = r.json()["job_id"]

    st = await _wait_job(client, h, job_id)
    # The regression is an orphaned job stuck in QUEUED forever; any terminal state
    # proves the executor picked the row up. (The test DB ships no synthetic dataset,
    # so a DATASET collector legitimately fails with EvidenceUnavailable.)
    assert st["status"] in ("COMPLETED", "FAILED", "PARTIAL"), f"job {job_id} stuck in {st['status']}"
    assert st["status"] != "QUEUED"
