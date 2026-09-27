"""Report generation + download."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser
from app.core.errors import NotFound
from app.db.models import InvestigationReport, ReportStatus
from app.db.session import get_db
from app.jobs.executor import executor
from app.schemas.requests import ReportRequest
from app.services import investigation_service

router = APIRouter(tags=["reports"])


@router.post("/investigations/{inv_id}/reports", status_code=202)
async def generate_report(inv_id: str, body: ReportRequest, request: Request, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    report = InvestigationReport(
        investigation_id=inv.id,
        title=body.title or f"{inv.name} — {body.type.lower()} report",
        report_type=body.type,
        status=ReportStatus.GENERATING.value,
        created_by=user.id,
    )
    db.add(report)
    await db.flush()
    job = await executor.submit(db, "REPORT", inv.id, report.id, {"report_id": report.id})
    await audit.audit(db, "REPORT_REQUESTED", actor=user, resource_type="report", resource_id=report.id, metadata={"type": body.type, "job_id": job.id}, request=request)
    await db.commit()
    return {"report_id": report.id, "status": ReportStatus.GENERATING.value, "estimated_sec": 20}


@router.get("/investigations/{inv_id}/reports")
async def list_reports(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    rows = (await db.execute(select(InvestigationReport).where(InvestigationReport.investigation_id == inv_id).order_by(InvestigationReport.created_at.desc()))).scalars().all()
    return {
        "data": [
            {
                "id": r.id, "title": r.title, "report_type": r.report_type, "status": r.status,
                "file_size_bytes": r.file_size_bytes,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            }
            for r in rows
        ]
    }


@router.get("/investigations/{inv_id}/reports/{report_id}/download")
async def download_report(inv_id: str, report_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    report = await db.get(InvestigationReport, report_id)
    if not report or report.investigation_id != inv_id:
        raise NotFound(f"No report {report_id}")
    if report.status != ReportStatus.READY.value or not report.file_path:
        raise NotFound(f"Report {report_id} is not ready (status={report.status}).")
    path = Path(report.file_path)
    if not path.exists():
        raise NotFound("Report file missing from file store.")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
