"""Investigation (case) service."""
from __future__ import annotations

import ipaddress
import re
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Conflict, NotFound, ValidationError
from app.db.models import EvidenceItem, FqlQuery, Investigation, InvestigationStatus, Role, User

_DNS_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$")
_BLOCKED_IPS = {"169.254.169.254", "169.254.170.2", "fd00:ec2::254"}  # cloud metadata endpoints (SSRF)


def validate_target(target_host: str) -> str:
    t = target_host.strip()
    if not t or len(t) > 255:
        raise ValidationError("target_host is required (IP or hostname).", details={"field": "target_host"})
    try:
        ip = ipaddress.ip_address(t)
        if ip.is_link_local or ip.is_loopback and t not in ("127.0.0.1", "::1"):
            raise ValidationError(f"Target {t} is not routable for forensic collection.", details={"field": "target_host"})
        if t in _BLOCKED_IPS:
            raise ValidationError("Cloud metadata endpoints cannot be forensic targets.", details={"field": "target_host"})
        return t
    except ValueError:
        pass
    if t in ("localhost",):
        return t
    if not _DNS_RE.match(t):
        raise ValidationError(f"'{t}' is not a valid hostname or IP.", details={"field": "target_host"})
    return t


async def create(db: AsyncSession, user: User, name: str, target_host: str, description: str | None, target_os: str, source_mode: str, source_path: str | None, provenance: str) -> Investigation:
    existing = await db.execute(select(Investigation).where(Investigation.name == name))
    if existing.scalar_one_or_none():
        raise Conflict(f"An investigation named '{name}' already exists.", details={"name": name})
    inv = Investigation(
        name=name,
        description=description,
        target_host=validate_target(target_host),
        target_os=target_os,
        source_mode=source_mode,
        source_path=source_path,
        provenance=provenance,
        status=InvestigationStatus.ACTIVE.value,
        created_by=user.id,
        lead_investigator=user.id if user.role in (Role.LEAD_INVESTIGATOR.value, Role.ADMIN.value) else None,
    )
    db.add(inv)
    await db.flush()
    return inv


async def get_for_user(db: AsyncSession, inv_id: str, user: User) -> Investigation:
    inv = await db.get(Investigation, inv_id)
    if not inv:
        raise NotFound(f"No investigation with id {inv_id}.")
    if inv.created_by != user.id and user.role not in (Role.LEAD_INVESTIGATOR.value, Role.ADMIN.value, Role.AUDITOR.value):
        raise NotFound(f"No investigation with id {inv_id}.")  # IDOR: do not leak existence
    return inv


async def summary(db: AsyncSession, inv: Investigation) -> dict:
    total = (await db.execute(select(func.count(EvidenceItem.id)).where(EvidenceItem.investigation_id == inv.id))).scalar() or 0
    by_type_rows = (await db.execute(select(EvidenceItem.evidence_type, func.count(EvidenceItem.id)).where(EvidenceItem.investigation_id == inv.id).group_by(EvidenceItem.evidence_type))).all()
    recent = (await db.execute(select(FqlQuery).where(FqlQuery.investigation_id == inv.id).order_by(FqlQuery.submitted_at.desc()).limit(5))).scalars().all()
    last_ev = (await db.execute(select(func.max(EvidenceItem.collected_at)).where(EvidenceItem.investigation_id == inv.id))).scalar()
    return {
        "total": total,
        "by_type": dict(by_type_rows),
        "recent_jobs": [
            {"id": q.id, "status": q.status, "fql": q.raw_fql[:120], "completed_at": q.completed_at.isoformat() if q.completed_at else None}
            for q in recent
        ],
        "last_activity": last_ev.isoformat() if last_ev else None,
    }


async def set_status(db: AsyncSession, inv: Investigation, status: str) -> Investigation:
    inv.status = status
    if status in (InvestigationStatus.COMPLETED.value, InvestigationStatus.ARCHIVED.value):
        inv.closed_at = datetime.now(UTC)
    await db.flush()
    return inv
