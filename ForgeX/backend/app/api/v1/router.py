"""Aggregate API v1 router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import admin, ai, auth, evidence, findings, fql, investigations, reports, scripts

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(investigations.router)
api_router.include_router(fql.router)
api_router.include_router(evidence.router)
api_router.include_router(scripts.router)
api_router.include_router(findings.router)
api_router.include_router(ai.router)
api_router.include_router(reports.router)
api_router.include_router(admin.router)
api_router.include_router(admin.demo_router)
