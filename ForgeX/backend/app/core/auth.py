"""JWT issuance/validation, password hashing, RBAC dependencies (architecture §10)."""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.errors import AccountDisabled, AuthError, PermissionDenied
from app.db.models import ROLE_RANK, Role, User
from app.db.session import get_db

settings = get_settings()
_bearer = HTTPBearer(auto_error=False)

REFRESH_COOKIE = "forgex_refresh"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _issue(subject: str, role: str, ttl: timedelta, kind: str) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "role": role,
        "kind": kind,
        "jti": uuid.uuid4().hex,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user: User) -> str:
    return _issue(user.id, user.role, timedelta(minutes=settings.access_token_ttl_minutes), "access")


def create_refresh_token(user: User) -> str:
    return _issue(user.id, user.role, timedelta(days=settings.refresh_token_ttl_days), "refresh")


def decode_token(token: str, kind: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("Token expired. Please sign in again.") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("Invalid authentication token.") from e
    if payload.get("kind") != kind:
        raise AuthError(f"Wrong token kind: expected {kind}.")
    return payload


async def current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    token = creds.credentials if creds else None
    if not token:
        # Allow WS / cookie fallback
        token = request.query_params.get("token") or request.cookies.get("forgex_access")
    if not token:
        raise AuthError("Missing bearer token.")
    payload = decode_token(token, "access")
    user = (await db.execute(select(User).where(User.id == payload["sub"]))).scalar_one_or_none()
    if user is None:
        raise AuthError("Account no longer exists.")
    if not user.is_active:
        raise AccountDisabled("This account has been disabled. Contact your platform administrator.")
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_roles(*roles: Role):
    """RBAC dependency factory: endpoint requires one of the given roles."""

    async def _check(user: CurrentUser) -> User:
        if user.role not in {r.value for r in roles}:
            raise PermissionDenied(
                f"Role {user.role} is not allowed here. Required: {', '.join(r.value for r in roles)}.",
                details={"required_roles": [r.value for r in roles], "actual_role": user.role},
            )
        return user

    return _check


def require_min_role(role: Role):
    async def _check(user: CurrentUser) -> User:
        if ROLE_RANK[Role(user.role)] < ROLE_RANK[role]:
            raise PermissionDenied(
                f"Requires at least role {role.value}; current role {user.role}.",
                details={"required_role": role.value, "actual_role": user.role},
            )
        return user

    return _check
