"""Investigation CRUD, timeline, graph, dashboard stats, anchor-chain verification."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser, require_min_role
from app.db.models import EvidenceItem, Finding, Investigation, Job, Role, ScriptExecution, User
from app.db.session import get_db
from app.graph import engine as graph_engine
from app.schemas.requests import InvestigationCreate, StatusUpdate
from app.services import blockchain_service, investigation_service
from app.services.timeline_service import build_timeline, parse_ts

router = APIRouter(tags=["investigations"])


@router.get("/investigations")
async def list_investigations(
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    status: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    stmt = select(Investigation)
    if user.role not in (Role.LEAD_INVESTIGATOR.value, Role.ADMIN.value, Role.AUDITOR.value):
        stmt = stmt.where(Investigation.created_by == user.id)
    if status:
        stmt = stmt.where(Investigation.status == status)
    if search:
        stmt = stmt.where(Investigation.name.ilike(f"%{search}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.order_by(Investigation.created_at.desc()).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    data = []
    for inv in rows:
        ev_count = (await db.execute(select(func.count(EvidenceItem.id)).where(EvidenceItem.investigation_id == inv.id))).scalar() or 0
        open_jobs = (await db.execute(select(func.count(Job.id)).where(Job.investigation_id == inv.id, Job.status.in_(["PENDING", "QUEUED", "RUNNING"])))).scalar() or 0
        data.append(
            {
                "id": inv.id,
                "name": inv.name,
                "description": inv.description,
                "target_host": inv.target_host,
                "target_os": inv.target_os,
                "source_mode": inv.source_mode,
                "provenance": inv.provenance,
                "status": inv.status,
                "created_by": inv.created_by,
                "created_at": inv.created_at.isoformat() if inv.created_at else None,
                "evidence_count": ev_count,
                "open_jobs": open_jobs,
            }
        )
    return {"data": data, "pagination": {"page": page, "per_page": per_page, "total": total}}


@router.post("/investigations", status_code=201)
async def create_investigation(body: InvestigationCreate, request: Request, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.create(db, user, body.name, body.target_host, body.description, body.target_os, body.source_mode, body.source_path, "SYNTHETIC" if body.source_mode == "DATASET" else "LIVE")
    await audit.audit(db, "INVESTIGATION_CREATED", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"name": inv.name, "target": inv.target_host}, request=request)
    await db.commit()
    return _inv_dict(inv)


@router.get("/investigations/{inv_id}")
async def get_investigation(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    summary = await investigation_service.summary(db, inv)
    return {**_inv_dict(inv), "evidence_summary": {"total": summary["total"], "by_type": summary["by_type"]}, "last_activity": summary["last_activity"], "recent_jobs": summary["recent_jobs"]}


@router.patch("/investigations/{inv_id}/status")
async def update_status(inv_id: str, body: StatusUpdate, request: Request, user: User = Depends(require_min_role(Role.LEAD_INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    await investigation_service.set_status(db, inv, body.status)
    await audit.audit(db, "INVESTIGATION_STATUS_CHANGED", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"status": body.status}, request=request)
    await db.commit()
    return _inv_dict(inv)


@router.get("/investigations/{inv_id}/timeline")
async def timeline(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db), from_time: str | None = None, to_time: str | None = None, granularity: str = "minute"):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    entries = await build_timeline(db, inv.id, parse_ts(from_time), parse_ts(to_time))
    return {"timeline": entries}


@router.get("/investigations/{inv_id}/graph")
async def graph(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    return await graph_engine.get_graph(db, inv.id)


@router.get("/investigations/{inv_id}/anchor-chain/verify")
async def verify_chain(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db)):
    await investigation_service.get_for_user(db, inv_id, user)
    return await blockchain_service.verify_chain(db)


@router.get("/stats/overview")
async def stats_overview(user: CurrentUser, db: AsyncSession = Depends(get_db)):
    scope = select(Investigation.id)
    if user.role not in (Role.LEAD_INVESTIGATOR.value, Role.ADMIN.value, Role.AUDITOR.value):
        scope = scope.where(Investigation.created_by == user.id)
    inv_ids = (await db.execute(scope)).scalars().all()
    if not inv_ids:
        return {"active_cases": 0, "evidence_items": 0, "executions": 0, "findings": 0, "high_severity_findings": 0, "severity_distribution": {}, "execution_history": [], "artifact_categories": {}}
    active = (await db.execute(select(func.count(Investigation.id)).where(Investigation.id.in_(inv_ids), Investigation.status == "ACTIVE"))).scalar() or 0
    evidence = (await db.execute(select(func.count(EvidenceItem.id)).where(EvidenceItem.investigation_id.in_(inv_ids)))).scalar() or 0
    executions = (await db.execute(select(func.count(ScriptExecution.id)).where(ScriptExecution.investigation_id.in_(inv_ids)))).scalar() or 0
    fql_runs = (await db.execute(select(func.count(Job.id)).where(Job.investigation_id.in_(inv_ids), Job.kind == "COLLECT"))).scalar() or 0
    findings = (await db.execute(select(func.count(Finding.id)).where(Finding.investigation_id.in_(inv_ids)))).scalar() or 0
    high = (await db.execute(select(func.count(Finding.id)).where(Finding.investigation_id.in_(inv_ids), Finding.severity.in_(["HIGH", "CRITICAL"])))).scalar() or 0
    sev_rows = (await db.execute(select(Finding.severity, func.count(Finding.id)).where(Finding.investigation_id.in_(inv_ids)).group_by(Finding.severity))).all()
    cat_rows = (await db.execute(select(EvidenceItem.evidence_type, func.count(EvidenceItem.id)).where(EvidenceItem.investigation_id.in_(inv_ids)).group_by(EvidenceItem.evidence_type))).all()
    hist_rows = (
        await db.execute(
            select(func.date(Job.created_at), func.count(Job.id)).where(Job.investigation_id.in_(inv_ids)).group_by(func.date(Job.created_at)).order_by(func.date(Job.created_at)).limit(30)
        )
    ).all()
    return {
        "active_cases": active,
        "evidence_items": evidence,
        "executions": executions + fql_runs,
        "findings": findings,
        "high_severity_findings": high,
        "severity_distribution": dict(sev_rows),
        "artifact_categories": dict(cat_rows),
        "execution_history": [{"date": str(d), "count": c} for d, c in hist_rows],
    }


def _inv_dict(inv: Investigation) -> dict:
    return {
        "id": inv.id,
        "name": inv.name,
        "description": inv.description,
        "target_host": inv.target_host,
        "target_os": inv.target_os,
        "source_mode": inv.source_mode,
        "source_path": inv.source_path,
        "provenance": inv.provenance,
        "status": inv.status,
        "created_by": inv.created_by,
        "lead_investigator": inv.lead_investigator,
        "created_at": inv.created_at.isoformat() if inv.created_at else None,
        "closed_at": inv.closed_at.isoformat() if inv.closed_at else None,
    }
