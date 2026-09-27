"""FQL validate/execute + job status endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import CurrentUser, require_min_role
from app.core.errors import NotFound
from app.db.models import CollectorExecution, Job, Role, User
from app.db.session import get_db
from app.schemas.requests import FqlRequest
from app.services import fql_service, investigation_service

router = APIRouter(tags=["fql"])


@router.post("/investigations/{inv_id}/fql/validate")
async def validate_fql(inv_id: str, body: FqlRequest, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    return await fql_service.validate(db, inv, user, body.fql)


@router.post("/investigations/{inv_id}/fql/execute", status_code=202)
async def execute_fql(inv_id: str, body: FqlRequest, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    _query, info = await fql_service.execute(db, inv, user, body.fql, body.policy_id, request)
    return info


@router.get("/jobs/{job_id}/status")
async def job_status(job_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise NotFound(f"No job with id {job_id}")
    await investigation_service.get_for_user(db, job.investigation_id, user)
    executions = (await db.execute(select_executions(job))).scalars().all() if job.kind == "COLLECT" else []
    return {
        "job_id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": job.progress or {},
        "collectors": {e.collector_type: e.status for e in executions},
        "items_collected_so_far": sum(e.items_collected or 0 for e in executions),
        "error": job.error_message,
        "result": job.result,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
    }


def select_executions(job: Job):
    from sqlalchemy import select

    from app.db.models import FqlQuery

    return select(CollectorExecution).where(CollectorExecution.fql_query_id == FqlQuery.id).where(FqlQuery.id == job.ref_id)
