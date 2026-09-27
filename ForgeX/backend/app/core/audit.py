"""Immutable audit trail writer — synchronous write in the caller's transaction."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import AuditLog, AuditResult, User

_SENSITIVE = {"password", "password_hash", "token", "refresh_token", "access_token", "secret", "api_key", "authorization", "code"}


def _scrub(value):
    if isinstance(value, dict):
        return {k: ("***" if k.lower() in _SENSITIVE else _scrub(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    return value


async def audit(
    db: AsyncSession,
    action: str,
    actor: User | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    metadata: dict | None = None,
    result: AuditResult = AuditResult.SUCCESS,
    request: Request | None = None,
) -> AuditLog:
    entry = AuditLog(
        actor_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        metadata_=_scrub(metadata or {}),
        ip_address=(request.client.host if request and request.client else None),
        user_agent=(request.headers.get("user-agent") if request else None),
        result=result.value,
    )
    db.add(entry)
    await db.flush()
    return entry
