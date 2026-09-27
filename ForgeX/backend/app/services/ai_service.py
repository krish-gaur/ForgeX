"""AI orchestration: correlation ("What Happened?"), RAG Q&A, provider fallback, validation."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai import heuristic, rag
from app.ai.providers import Message, llm_available, llm_complete
from app.ai.schemas import CorrelationResult, QueryResponse
from app.core.errors import NotFound, ValidationError
from app.core.logging import get_logger
from app.core.websocket import manager
from app.db.models import AiAnalysis, AnalysisType, EvidenceItem, Finding, FindingSource, FindingStatus, Investigation, Job, JobStatus, User
from app.graph import engine as graph_engine

log = get_logger("ai")

CORRELATION_SYSTEM = """You are a digital forensics AI assistant. You analyze collected forensic evidence
and produce structured incident reconstructions. You ONLY reason about evidence explicitly
provided. You do NOT speculate beyond the data. Every claim MUST cite an evidence_id.
Output ONLY valid JSON matching the schema below. No prose outside the JSON."""

QA_SYSTEM = """You are a forensic evidence analyst. You answer investigator questions strictly
based on the collected evidence provided. Cite evidence_ids for every factual claim.
If the evidence does not contain the answer, say so explicitly — do not guess."""


def _escape_evidence(items: list[EvidenceItem]) -> str:
    blocks = []
    for e in items[:50]:
        payload = json.dumps(e.data, default=str)
        payload = payload.replace("<", "&lt;").replace(">", "&gt;")
        blocks.append(f'<evidence id="{e.id}" type="{e.evidence_type}">{payload}</evidence>')
    return "\n".join(blocks)


async def _llm_correlate(investigation: Investigation, items: list[EvidenceItem], graph_summary: dict) -> tuple[dict, str, int, int] | None:
    if not llm_available():
        return None
    user_msg = f"""Investigation: {investigation.name}
Target: {investigation.target_host} ({investigation.target_os})

EVIDENCE:
{_escape_evidence(items)}

CORRELATION GRAPH SUMMARY:
{json.dumps(graph_summary)}

Produce a CorrelationResult JSON:
{{"what_happened": str, "attack_stages": [{{"stage": str, "description": str, "evidence_ids": [uuid]}}],
"suspicious_indicators": [{{"indicator": str, "severity": "HIGH|MED|LOW", "evidence_ids": [uuid]}}],
"mitre_techniques": [{{"technique_id": "T1059.001", "name": str, "evidence_ids": [uuid]}}],
"confidence": 0.0-1.0, "gaps": [str]}}"""
    try:
        data, model, pt, ct = await llm_complete([Message(role="system", content=CORRELATION_SYSTEM), Message(role="user", content=user_msg)])
        validated = CorrelationResult.model_validate(data)
    except Exception as e:  # noqa: BLE001 — invalid LLM output is discarded by design
        log.warning("llm_correlation_invalid", error=str(e)[:200])
        return None
    valid_ids = {e.id for e in items}
    result = validated.model_dump()
    for key in ("attack_stages", "suspicious_indicators", "mitre_techniques"):
        for entry in result[key]:
            entry["evidence_ids"] = [i for i in entry["evidence_ids"] if i in valid_ids]
    return result, model, pt, ct


async def run_analysis_job(session: AsyncSession, job: Job) -> None:
    payload = job.payload or {}
    analysis_type = payload.get("analysis_type", AnalysisType.CORRELATION.value)
    investigation = await session.get(Investigation, job.investigation_id)
    items = (await session.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == investigation.id))).scalars().all()
    if not items:
        job.status = JobStatus.FAILED.value
        job.error_message = "Collect evidence first: this investigation has no evidence items yet."
        return
    user = await session.get(User, payload.get("user_id")) if payload.get("user_id") else None

    if analysis_type in (AnalysisType.CORRELATION.value, AnalysisType.MITRE_MAPPING.value, AnalysisType.EXPLANATION.value):
        base = heuristic.correlate(list(items))
        engine = "HEURISTIC"
        model = "forgex-correlation-engine-v1"
        pt = ct = 0
        gsum = await graph_engine.graph_summary(session, investigation.id)
        llm_out = await _llm_correlate(investigation, list(items), gsum)
        if llm_out:
            base, model, pt, ct = llm_out
            engine = "LLM"
        result = base
        confidence = result.get("confidence", 0.5)
        input_ids = sorted({i for entry in result.get("attack_stages", []) + result.get("suspicious_indicators", []) + result.get("mitre_techniques", []) for i in entry.get("evidence_ids", [])}) or [e.id for e in items[:50]]
    else:  # QUERY_RESPONSE
        question = payload.get("question", "")
        if not question:
            job.status = JobStatus.FAILED.value
            job.error_message = "question is required for QUERY_RESPONSE analysis"
            return
        hits = await rag.retrieve(session, investigation.id, question)
        engine, model, pt, ct = "HEURISTIC_RETRIEVAL", "forgex-local-embed-v1", 0, 0
        answer = rag.extractive_answer(question, hits)
        if llm_available() and hits:
            ctx = "\n".join(f'<evidence id="{i.id}" type="{i.evidence_type}">{json.dumps(i.data, default=str)[:800]}</evidence>' for i, _ in hits)
            try:
                data, model, pt, ct = await llm_complete(
                    [Message(role="system", content=QA_SYSTEM), Message(role="user", content=f"Question: {question}\n\nRelevant Evidence (retrieved via semantic search):\n{ctx}\n\nAnswer in JSON: {{\"answer\": str, \"evidence_refs\": [uuid], \"confidence\": 0.0-1.0, \"caveat\": str|null}}")]
                )
                validated = QueryResponse.model_validate(data)
                allowed = {i.id for i, _ in hits}
                refs = [r for r in validated.evidence_refs if r in allowed]
                answer = {"answer": validated.answer, "evidence_refs": refs, "confidence": validated.confidence, "caveat": validated.caveat}
                engine = "LLM_RAG"
            except Exception as e:  # noqa: BLE001
                log.warning("llm_qa_invalid", error=str(e)[:150])
        result = answer
        confidence = answer.get("confidence", 0.0)
        input_ids = [i.id for i, _ in hits]

    analysis = AiAnalysis(
        investigation_id=investigation.id,
        analysis_type=analysis_type,
        engine=engine,
        prompt_tokens=pt or None,
        completion_tokens=ct or None,
        model_used=model,
        input_evidence_ids=input_ids,
        result=result,
        confidence_score=confidence,
        created_by=(user.id if user else (payload.get("user_id") or "")),
    )
    session.add(analysis)
    await session.flush()
    job.ref_id = analysis.id
    job.status = JobStatus.COMPLETED.value
    job.completed_at = datetime.now(UTC)
    job.result = {"analysis_id": analysis.id, "engine": engine, "confidence": confidence}
    await manager.broadcast(investigation.id, {"type": "AI_COMPLETE", "analysis_id": analysis.id, "engine": engine})


async def promote_indicator_to_finding(db: AsyncSession, analysis_id: str, index: int, user: User) -> Finding:
    analysis = await db.get(AiAnalysis, analysis_id)
    if not analysis:
        raise NotFound(f"No analysis {analysis_id}")
    indicators = (analysis.result or {}).get("suspicious_indicators", [])
    if not (0 <= index < len(indicators)):
        raise ValidationError(f"Indicator index {index} out of range (0..{len(indicators) - 1}).")
    ind = indicators[index]
    valid = set((await db.execute(select(EvidenceItem.id).where(EvidenceItem.investigation_id == analysis.investigation_id))).scalars().all())
    finding = Finding(
        investigation_id=analysis.investigation_id,
        analysis_id=analysis.id,
        source=FindingSource.AI.value,
        severity=ind.get("severity", "MEDIUM") if ind.get("severity") in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL") else "MEDIUM",
        title=ind.get("indicator", "AI indicator")[:300],
        description="Promoted from AI correlation analysis (human-verified).",
        evidence_ids=[i for i in ind.get("evidence_ids", []) if i in valid],
        mitre_techniques=[],
        status=FindingStatus.VERIFIED.value,
        verified_by=user.id,
    )
    db.add(finding)
    await db.flush()
    return finding
