"""Policy loading: DB-backed with a 60s in-process cache (architecture §03/§11)."""
from __future__ import annotations

import time

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Policy
from app.policy.models import DEFAULT_POLICY_NAME, DEFAULT_POLICY_RULES

_cache: dict[str, tuple[float, dict]] = {}
_TTL = 60.0


def invalidate_cache() -> None:
    _cache.clear()


async def ensure_default_policy(db: AsyncSession, created_by: str) -> Policy:
    existing = (await db.execute(select(Policy).where(Policy.name == DEFAULT_POLICY_NAME))).scalar_one_or_none()
    if existing:
        return existing
    policy = Policy(
        name=DEFAULT_POLICY_NAME,
        description="Shipped ForgeX default policy. Network collection requires lead approval.",
        rules=DEFAULT_POLICY_RULES,
        is_default=True,
        is_active=True,
        created_by=created_by,
    )
    db.add(policy)
    await db.flush()
    return policy


async def get_active_policy(db: AsyncSession, policy_id: str | None = None) -> Policy:
    key = policy_id or "default"
    now = time.monotonic()
    if key in _cache and now - _cache[key][0] < _TTL:
        pid, rules = _cache[key]
        stmt = select(Policy).where(Policy.id == pid) if pid else select(Policy).where(Policy.is_default.is_(True), Policy.is_active.is_(True))
        pol = (await db.execute(stmt)).scalar_one_or_none()
        if pol:
            return pol
    if policy_id:
        stmt = select(Policy).where(Policy.id == policy_id, Policy.is_active.is_(True))
    else:
        stmt = select(Policy).where(Policy.is_default.is_(True), Policy.is_active.is_(True))
    policy = (await db.execute(stmt)).scalar_one_or_none()
    if policy is None:
        policy = (await db.execute(select(Policy).where(Policy.is_active.is_(True)).order_by(Policy.created_at))).scalars().first()
    if policy is None:
        raise RuntimeError("No active policy configured")
    _cache[key] = (now, policy.rules)
    return policy


def parse_policy_yaml(text: str) -> dict:
    """Validate + parse admin-supplied policy YAML into the rules dict."""
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError("Policy YAML must be a mapping")
    required = {"allowed_collectors"}
    missing = required - set(data)
    if missing:
        raise ValueError(f"Policy YAML missing keys: {sorted(missing)}")
    known_collectors = {"processes", "files", "network", "users", "events", "timeline"}
    for c in data.get("allowed_collectors", []):
        if c not in known_collectors:
            raise ValueError(f"Unknown collector in allowed_collectors: {c}")
    for c in data.get("restricted_collectors", {}) or {}:
        if c not in known_collectors:
            raise ValueError(f"Unknown collector in restricted_collectors: {c}")
    return data
