"""Auth endpoints: login / refresh / logout / me."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core import audit
from app.core.auth import (
    REFRESH_COOKIE,
    CurrentUser,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.errors import AccountDisabled, AuthError
from app.core.ratelimit import limit
from app.db.models import AuditResult, User
from app.db.session import get_db
from app.schemas.requests import LoginRequest, RefreshRequest

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.is_production,
        max_age=settings.refresh_token_ttl_days * 86400,
        path="/api/v1/auth",
    )


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    limit("login", request.client.host if request.client else "unknown", settings.rate_limit_login_per_min, 60)
    user = (await db.execute(select(User).where(or_(User.username == body.username, User.email == body.username)))).scalars().first()
    if user is None or not verify_password(body.password, user.password_hash):
        await audit.audit(db, "LOGIN_FAILED", actor=None, resource_type="auth", metadata={"username": body.username}, result=AuditResult.FAILURE, request=request)
        await db.commit()
        raise AuthError("Invalid username or password.")
    if not user.is_active:
        raise AccountDisabled("This account is disabled. Contact your platform administrator.")
    access = create_access_token(user)
    refresh = create_refresh_token(user)
    _set_refresh_cookie(response, refresh)
    await audit.audit(db, "LOGIN", actor=user, resource_type="auth", request=request)
    await db.commit()
    return {
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": settings.access_token_ttl_minutes * 60,
        "token_type": "bearer",
        "user": {"id": user.id, "username": user.username, "email": user.email, "role": user.role},
    }


@router.post("/refresh")
async def refresh(body: RefreshRequest, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = body.refresh_token or request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise AuthError("No refresh token provided.")
    payload = decode_token(token, "refresh")
    user = (await db.execute(select(User).where(User.id == payload["sub"]))).scalar_one_or_none()
    if not user or not user.is_active:
        raise AuthError("Account unavailable.")
    access = create_access_token(user)
    await audit.audit(db, "TOKEN_REFRESH", actor=user, resource_type="auth", request=request)
    await db.commit()
    return {"access_token": access, "expires_in": settings.access_token_ttl_minutes * 60, "token_type": "bearer"}


@router.post("/logout")
async def logout(user: CurrentUser, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    await audit.audit(db, "LOGOUT", actor=user, resource_type="auth", request=request)
    await db.commit()
    return {"status": "logged_out"}


@router.get("/me")
async def me(user: CurrentUser):
    return {"id": user.id, "username": user.username, "email": user.email, "role": user.role, "is_active": user.is_active}


# helper used by bootstrap scripts
async def create_user(db: AsyncSession, username: str, email: str, password: str, role: str) -> User:
    user = User(username=username, email=email, password_hash=hash_password(password), role=role)
    db.add(user)
    await db.flush()
    return user
