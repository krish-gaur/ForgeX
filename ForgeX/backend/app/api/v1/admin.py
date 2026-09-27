"""Admin endpoints: users, policies, audit log. Plus demo seeding trigger."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import audit
from app.core.auth import CurrentUser, hash_password, require_roles
from app.core.errors import Conflict, NotFound, ValidationError
from app.db.models import AuditLog, Policy, Role, User
from app.db.session import get_db
from app.policy.loader import invalidate_cache, parse_policy_yaml
from app.schemas.requests import PolicyCreate, UserCreate, UserUpdate

router = APIRouter(tags=["admin"])


# ---------------------------------------------------------------- users
@router.get("/admin/users")
async def list_users(_: User = Depends(require_roles(Role.ADMIN)), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(User).order_by(User.created_at))).scalars().all()
    return {"data": [{"id": u.id, "username": u.username, "email": u.email, "role": u.role, "is_active": u.is_active, "created_at": u.created_at.isoformat() if u.created_at else None} for u in rows]}


@router.post("/admin/users", status_code=201)
async def create_user(body: UserCreate, request: Request, admin: User = Depends(require_roles(Role.ADMIN)), db: AsyncSession = Depends(get_db)):
    dup = (await db.execute(select(User).where((User.username == body.username) | (User.email == body.email)))).scalar_one_or_none()
    if dup:
        raise Conflict("Username or email already exists.")
    user = User(username=body.username, email=body.email, password_hash=hash_password(body.password), role=body.role)
    db.add(user)
    await audit.audit(db, "USER_CREATED", actor=admin, resource_type="user", metadata={"username": body.username, "role": body.role}, request=request)
    await db.commit()
    return {"id": user.id, "username": user.username, "role": user.role}


@router.patch("/admin/users/{user_id}")
async def update_user(user_id: str, body: UserUpdate, request: Request, admin: User = Depends(require_roles(Role.ADMIN)), db: AsyncSession = Depends(get_db)):
    user = await db.get(User, user_id)
    if not user:
        raise NotFound(f"No user {user_id}")
    if body.role:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.password_hash = hash_password(body.password)
    await audit.audit(db, "USER_UPDATED", actor=admin, resource_type="user", resource_id=user.id, metadata={"role": user.role, "is_active": user.is_active}, request=request)
    await db.commit()
    return {"id": user.id, "username": user.username, "role": user.role, "is_active": user.is_active}


# ---------------------------------------------------------------- policies
@router.get("/admin/policies")
async def list_policies(_: User = Depends(require_roles(Role.ADMIN, Role.LEAD_INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(select(Policy).order_by(Policy.created_at))).scalars().all()
    return {"data": [{"id": p.id, "name": p.name, "description": p.description, "rules": p.rules, "is_default": p.is_default, "is_active": p.is_active} for p in rows]}


@router.post("/admin/policies", status_code=201)
async def create_policy(body: PolicyCreate, request: Request, admin: User = Depends(require_roles(Role.ADMIN)), db: AsyncSession = Depends(get_db)):
    try:
        rules = parse_policy_yaml(body.yaml)
    except ValueError as e:
        raise ValidationError(str(e), details={"yaml": body.yaml[:200]}) from e
    if (await db.execute(select(Policy).where(Policy.name == body.name))).scalar_one_or_none():
        raise Conflict(f"Policy '{body.name}' already exists.")
    if body.is_default:
        for p in (await db.execute(select(Policy).where(Policy.is_default.is_(True)))).scalars().all():
            p.is_default = False
    policy = Policy(name=body.name, description=body.description, rules=rules, is_default=body.is_default, created_by=admin.id)
    db.add(policy)
    invalidate_cache()
    await audit.audit(db, "POLICY_CREATED", actor=admin, resource_type="policy", metadata={"name": body.name}, request=request)
    await db.commit()
    return {"id": policy.id, "name": policy.name, "rules": policy.rules}


@router.post("/admin/policies/validate")
async def validate_policy_yaml(body: PolicyCreate, _: User = Depends(require_roles(Role.ADMIN))):
    try:
        rules = parse_policy_yaml(body.yaml)
    except ValueError as e:
        return {"valid": False, "error": str(e)}
    return {"valid": True, "rules": rules}


# ---------------------------------------------------------------- audit
@router.get("/admin/audit")
async def audit_log(
    _: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR)),
    db: AsyncSession = Depends(get_db),
    action: str | None = None,
    actor: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if actor:
        stmt = stmt.where(AuditLog.actor_email.ilike(f"%{actor}%"))
    total = (await db.execute(select(func.count()).select_from(stmt.subquery()))).scalar() or 0
    rows = (await db.execute(stmt.order_by(AuditLog.created_at.desc()).offset((page - 1) * per_page).limit(per_page))).scalars().all()
    return {
        "data": [
            {
                "id": a.id, "actor_email": a.actor_email, "action": a.action, "resource_type": a.resource_type,
                "resource_id": a.resource_id, "metadata": a.metadata_, "ip_address": a.ip_address,
                "result": a.result, "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in rows
        ],
        "pagination": {"page": page, "per_page": per_page, "total": total},
    }


@router.get("/admin/audit/export")
async def audit_export(_: User = Depends(require_roles(Role.ADMIN, Role.AUDITOR)), db: AsyncSession = Depends(get_db)):
    import csv
    import io

    from fastapi.responses import Response as FastResponse

    rows = (await db.execute(select(AuditLog).order_by(AuditLog.created_at))).scalars().all()
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "created_at", "actor", "action", "resource_type", "resource_id", "result", "ip"])
    for a in rows:
        w.writerow([a.id, a.created_at.isoformat() if a.created_at else "", a.actor_email, a.action, a.resource_type, a.resource_id, a.result, a.ip_address])
    return FastResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": 'attachment; filename="forgex-audit.csv"'})


# ---------------------------------------------------------------- demo
demo_router = APIRouter(tags=["demo"])


@demo_router.post("/demo/seed", status_code=201)
async def seed(request: Request, user: User = Depends(require_roles(Role.ADMIN, Role.LEAD_INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    from app.services.demo_service import seed_demo

    result = await seed_demo(db, user)
    return result


@demo_router.get("/demo/fql-examples")
async def demo_examples(user: CurrentUser):
    from app.services.demo_service import DEMO_FQL_QUERIES

    return {"queries": DEMO_FQL_QUERIES}


@demo_router.get("/datasets")
async def list_datasets(user: CurrentUser):
    """List forensic datasets available for DATASET-mode investigations (new-case picker)."""
    from pathlib import Path

    from app.config import get_settings

    root = Path(get_settings().dataset_dir)
    out = []
    if root.exists():
        for d in sorted(root.iterdir()):
            if not d.is_dir():
                continue
            files = sorted(p.name for p in d.iterdir() if p.is_file())
            size = sum(p.stat().st_size for p in d.iterdir() if p.is_file())
            out.append({"id": d.name, "files": files, "size_bytes": size})
    return {"datasets": out}
