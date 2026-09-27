"""AI intelligence endpoints: correlate (async job), RAG Q&A (sync), analyses, promote."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.scripts import _finding_dict
from app.core import audit
from app.core.auth import CurrentUser, require_min_role
from app.db.models import AiAnalysis, AnalysisType, JobStatus, Role, User
from app.db.session import get_db
from app.jobs.executor import executor
from app.schemas.requests import PromoteRequest, QueryRequest
from app.services import ai_service, investigation_service

router = APIRouter(tags=["ai"])


@router.post("/investigations/{inv_id}/ai/correlate", status_code=202)
async def correlate(inv_id: str, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    job = await executor.submit(db, "AI", inv.id, None, {"analysis_type": AnalysisType.CORRELATION.value, "user_id": user.id})
    await audit.audit(db, "AI_CORRELATION_REQUESTED", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"job_id": job.id}, request=request)
    await db.commit()
    return {"analysis_id": None, "job_id": job.id, "status": "RUNNING", "estimated_sec": 30}


@router.post("/investigations/{inv_id}/ai/query")
async def query(inv_id: str, body: QueryRequest, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    job = await executor.submit(db, "AI", inv.id, None, {"analysis_type": AnalysisType.QUERY_RESPONSE.value, "question": body.question, "user_id": user.id})
    await db.commit()
    # Synchronous convenience: wait for the inline job to settle (bounded).
    import asyncio

    for _ in range(120):
        await asyncio.sleep(0.5)
        await db.refresh(job)
        if job.status in (JobStatus.COMPLETED.value, JobStatus.FAILED.value, JobStatus.PARTIAL.value):
            break
    if job.status == JobStatus.FAILED.value:
        from app.core.errors import AiProcessingError

        raise AiProcessingError(job.error_message or "AI query failed.")
    analysis = await db.get(AiAnalysis, job.ref_id) if job.ref_id else None
    if not analysis:
        from app.core.errors import AiProcessingError

        raise AiProcessingError("Analysis did not produce a result.")
    await audit.audit(db, "AI_QUERY", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"question": body.question[:200]}, request=request)
    await db.commit()
    return {**(analysis.result or {}), "analysis_id": analysis.id, "engine": analysis.engine, "model": analysis.model_used}


@router.get("/investigations/{inv_id}/ai/analyses")
async def analyses(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    rows = (await db.execute(select(AiAnalysis).where(AiAnalysis.investigation_id == inv_id).order_by(AiAnalysis.created_at.desc()))).scalars().all()
    return {
        "data": [
            {
                "id": a.id, "analysis_type": a.analysis_type, "engine": a.engine, "model_used": a.model_used,
                "confidence_score": a.confidence_score, "result": a.result, "input_evidence_ids": a.input_evidence_ids,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ]
    }


@router.post("/ai/analyses/{analysis_id}/promote", status_code=201)
async def promote(analysis_id: str, body: PromoteRequest, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    finding = await ai_service.promote_indicator_to_finding(db, analysis_id, body.indicator_index, user)
    await audit.audit(db, "AI_INDICATOR_PROMOTED", actor=user, resource_type="finding", resource_id=finding.id, metadata={"analysis_id": analysis_id}, request=request)
    await db.commit()
    return _finding_dict(finding)
