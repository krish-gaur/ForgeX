"""Shared fixtures: isolated SQLite DB + ASGI client + seeded roles."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

TMP = tempfile.mkdtemp(prefix="forgex_test_")
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{TMP}/test.db"
os.environ["SECRET_KEY"] = "test-secret-key-0123456789abcdef0123456789abcdef"
os.environ["DATASET_DIR"] = TMP + "/datasets"
os.environ["DATA_DIR"] = TMP + "/data"
os.environ["FILE_STORE_DIR"] = TMP + "/data/files"
os.environ["ENVIRONMENT"] = "test"

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()
settings = get_settings()

from app.core.auth import hash_password  # noqa: E402
from app.db.models import Base, User  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402
from app.policy.loader import ensure_default_policy  # noqa: E402

engine = create_async_engine(settings.database_url, connect_args={"check_same_thread": False})
TestSession = async_sessionmaker(engine, expire_on_commit=False)


@pytest_asyncio.fixture(scope="session")
async def _schema():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="session")
async def db(_schema):
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(autouse=True)
async def _clean_session(db):
    yield
    if not db.is_active or db.new or db.dirty or db.deleted:
        await db.rollback()


@pytest_asyncio.fixture
async def client(_schema):

    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    # avoid lifespan bootstrap touching the real engine
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


async def _override_db():
    async with TestSession() as session:
        yield session


@pytest_asyncio.fixture(scope="session")
async def users(db):
    out = {}
    for username, role in (("admin", "ADMIN"), ("lead", "LEAD_INVESTIGATOR"), ("investigator", "INVESTIGATOR"), ("auditor", "AUDITOR")):
        u = User(username=username, email=f"{username}@test.local", password_hash=hash_password("Passw0rd!-test"), role=role)
        db.add(u)
        out[role] = u
    await db.commit()
    for v in out.values():
        await db.refresh(v)
    # return detached copies: attribute access never triggers lazy IO,
    # so session rollbacks/expirations in later tests can't break them
    return {k: User(id=v.id, username=v.username, email=v.email, role=v.role, password_hash=v.password_hash) for k, v in out.items()}


@pytest_asyncio.fixture(scope="session")
async def policy(db, users):
    p = await ensure_default_policy(db, users["ADMIN"].id)
    await db.commit()
    return p


async def login(client, username="lead", password="Passw0rd!-test"):
    r = await client.post("/api/v1/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _reset_limiter():
    from app.core.ratelimit import limiter

    limiter.reset()
    yield
    limiter.reset()
