"""ForgeX backend entrypoint (FastAPI application factory)."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import func, select

from app.api.v1.router import api_router
from app.config import get_settings
from app.core.auth import hash_password
from app.core.errors import ForgeXError
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestIdMiddleware, SecurityHeadersMiddleware
from app.core.websocket import router as ws_router
from app.db.models import AuditResult, User
from app.db.session import SessionLocal, create_schema, engine
from app.policy.loader import ensure_default_policy

settings = get_settings()
log = get_logger("main")

BOOTSTRAP_USERS = [
    ("admin", "admin@forgex.local", "ForgeX-Admin-2026!", "ADMIN"),
    ("lead", "lead@forgex.local", "ForgeX-Lead-2026!", "LEAD_INVESTIGATOR"),
    ("investigator", "investigator@forgex.local", "ForgeX-Investigator-2026!", "INVESTIGATOR"),
    ("auditor", "auditor@forgex.local", "ForgeX-Auditor-2026!", "AUDITOR"),
]


async def _bootstrap() -> None:
    async with SessionLocal() as db:
        count = (await db.execute(select(func.count(User.id)))).scalar() or 0
        if count == 0:
            for username, email, password, role in BOOTSTRAP_USERS:
                db.add(User(username=username, email=email, password_hash=hash_password(password), role=role))
            await db.commit()
            log.info("bootstrap_users_created", users=[u[0] for u in BOOTSTRAP_USERS])
        async with SessionLocal() as db2:
            admin = (await db2.execute(select(User).where(User.role == "ADMIN").order_by(User.created_at))).scalars().first()
            if admin:
                await ensure_default_policy(db2, admin.id)
                await db2.commit()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging(settings.log_level)
    if settings.auto_create_schema:
        await create_schema()
    await _bootstrap()
    if settings.demo_seed_on_boot:
        from app.services.demo_service import seed_demo

        async with SessionLocal() as db:
            admin = (await db.execute(select(User).where(User.role == "ADMIN").order_by(User.created_at))).scalars().first()
            if admin:
                try:
                    await seed_demo(db, admin)
                except Exception:  # noqa: BLE001
                    log.exception("demo_seed_failed")
    log.info("forgex_backend_ready", env=settings.environment, db=settings.database_url.split("://")[0])
    if settings.task_backend != "celery":
        # Self-healing: pick up jobs orphaned in QUEUED by a previous process
        # (restart/crash). Celery workers own their own queue instead.
        try:
            await recover_orphaned_jobs()
        except Exception:  # noqa: BLE001
            log.exception("orphaned_job_recovery_failed")
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(
        title="ForgeX API",
        version="1.0.0",
        description="ForgeX — controlled forensic analysis platform (SIH26148). Intent → Execution → Evidence → Correlation → Answer.",
        lifespan=lifespan,
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origin_list, allow_credentials=True, allow_methods=["*"], allow_headers=["*"], expose_headers=["X-Request-ID"])
    app.add_middleware(RequestIdMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(ForgeXError)
    async def forgex_error_handler(request: Request, exc: ForgeXError):
        return JSONResponse(
            status_code=exc.status,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details, "request_id": getattr(request.state, "request_id", None)}},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content={"error": {"code": "VALIDATION_ERROR", "message": "Request validation failed.", "details": {"errors": exc.errors()[:10]}, "request_id": getattr(request.state, "request_id", None)}},
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        log.exception("unhandled_error", path=request.url.path, error=str(exc)[:200])
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An internal error occurred. The incident has been logged for the platform team.", "details": {}, "request_id": getattr(request.state, "request_id", None)}},
        )

    @app.get("/health", tags=["health"])
    async def health():
        try:
            async with engine.connect() as conn:
                await conn.execute(select(1))
            db_ok = True
        except Exception:  # noqa: BLE001
            db_ok = False
        return {"status": "ok" if db_ok else "degraded", "database": db_ok, "service": "forgex-backend", "version": "1.0.0"}

    @app.get("/api/v1/health", tags=["health"])
    async def health_v1():
        return await health()

    app.include_router(api_router)
    app.include_router(ws_router)
    return app


app = create_app()

# ensure runners are registered (pipeline imports executor registry)
from app.jobs.executor import recover_orphaned_jobs  # noqa: E402
from app.services import pipeline  # noqa: E402,F401

_ = AuditResult  # re-export guard
