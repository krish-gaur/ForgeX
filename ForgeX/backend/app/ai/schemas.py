"""Strict output schemas for AI results (hallucination control: invalid → discarded)."""
from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class Stage(BaseModel):
    stage: str
    description: str
    evidence_ids: list[str] = Field(default_factory=list)


class Indicator(BaseModel):
    indicator: str
    severity: str = Field(pattern="^(INFO|LOW|MEDIUM|HIGH|CRITICAL)$")
    evidence_ids: list[str] = Field(default_factory=list)


class MitreTechnique(BaseModel):
    technique_id: str
    name: str
    evidence_ids: list[str] = Field(default_factory=list)


class CorrelationResult(BaseModel):
    what_happened: str
    attack_stages: list[Stage] = Field(default_factory=list)
    suspicious_indicators: list[Indicator] = Field(default_factory=list)
    mitre_techniques: list[MitreTechnique] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    gaps: list[str] = Field(default_factory=list)

    @field_validator("attack_stages", "suspicious_indicators", "mitre_techniques", mode="before")
    @classmethod
    def _coerce(cls, v):
        return v if isinstance(v, list) else []


class QueryResponse(BaseModel):
    answer: str
    evidence_refs: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0)
    caveat: str | None = None
