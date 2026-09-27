"""Typed request schemas (architecture §06)."""
from __future__ import annotations

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str | None = None


class InvestigationCreate(BaseModel):
    name: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    target_host: str = Field(min_length=1, max_length=255)
    target_os: str = Field(default="UNKNOWN", pattern="^(WINDOWS|LINUX|UNKNOWN)$")
    source_mode: str = Field(default="LIVE_LOCAL", pattern="^(LIVE_LOCAL|DATASET)$")
    source_path: str | None = Field(default=None, max_length=500)


class StatusUpdate(BaseModel):
    status: str = Field(pattern="^(ACTIVE|COMPLETED|ARCHIVED|SUSPENDED)$")


class FqlRequest(BaseModel):
    fql: str = Field(min_length=1, max_length=20000)
    policy_id: str | None = None


class ScriptCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    template_id: str | None = None
    code: str | None = Field(default=None, max_length=100000)
    language: str = Field(default="PYFUNC", pattern="^(PYFUNC|FQL)$")


class ScriptUpdate(BaseModel):
    code: str = Field(min_length=1, max_length=100000)
    note: str | None = Field(default=None, max_length=300)
    bump_version: bool = True


class ValidateCodeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=100000)


class RunScriptRequest(BaseModel):
    investigation_id: str
    code: str | None = Field(default=None, max_length=100000)  # run unsaved edits


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)


class ReportRequest(BaseModel):
    type: str = Field(default="FULL", pattern="^(FULL|SUMMARY|CHAIN_OF_CUSTODY)$")
    title: str | None = Field(default=None, max_length=255)


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=100)
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(pattern="^(ADMIN|LEAD_INVESTIGATOR|INVESTIGATOR|AUDITOR)$")


class UserUpdate(BaseModel):
    role: str | None = Field(default=None, pattern="^(ADMIN|LEAD_INVESTIGATOR|INVESTIGATOR|AUDITOR)$")
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8, max_length=200)


class PolicyCreate(BaseModel):
    name: str = Field(min_length=3, max_length=100)
    description: str | None = None
    yaml: str = Field(min_length=10, max_length=20000)
    is_default: bool = False


class FindingUpdate(BaseModel):
    status: str = Field(pattern="^(OPEN|VERIFIED|DISMISSED)$")


class PromoteRequest(BaseModel):
    indicator_index: int = Field(ge=0)
