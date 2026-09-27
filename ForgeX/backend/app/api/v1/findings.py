"""Findings endpoints (human verification workflow)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.scripts import _finding_dict
from app.core import audit
from app.core.auth import CurrentUser, require_min_role
from app.core.errors import NotFound
from app.db.models import Finding, Role, User
from app.db.session import get_db
from app.schemas.requests import FindingUpdate
from app.services import investigation_service

router = APIRouter(tags=["findings"])


@router.get("/investigations/{inv_id}/findings")
async def list_findings(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db), severity: str | None = None, status: str | None = None):
    await investigation_service.get_for_user(db, inv_id, user)
    stmt = select(Finding).where(Finding.investigation_id == inv_id)
    if severity:
        stmt = stmt.where(Finding.severity == severity)
    if status:
        stmt = stmt.where(Finding.status == status)
    rows = (await db.execute(stmt.order_by(Finding.created_at.desc()))).scalars().all()
    return {"data": [_finding_dict(f) for f in rows]}


@router.patch("/findings/{finding_id}")
async def update_finding(finding_id: str, body: FindingUpdate, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    finding = await db.get(Finding, finding_id)
    if not finding:
        raise NotFound(f"No finding {finding_id}")
    await investigation_service.get_for_user(db, finding.investigation_id, user)
    finding.status = body.status
    if body.status == "VERIFIED":
        finding.verified_by = user.id
    await audit.audit(db, "FINDING_STATUS_CHANGED", actor=user, resource_type="finding", resource_id=finding.id, metadata={"status": body.status}, request=request)
    await db.commit()
    return _finding_dict(finding)
