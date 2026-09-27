"""Unit tests: AI validation, heuristic correlation citations, RAG (architecture §12 CRITICAL)."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.ai import heuristic, rag
from app.ai.schemas import CorrelationResult, QueryResponse
from app.db.models import EvidenceItem


def _ev(id_, etype, data, inv="inv"):
    import hashlib
    import json as _json
    return EvidenceItem(id=id_, investigation_id=inv, evidence_type=etype, data=data, data_hash=hashlib.sha256(_json.dumps(data, sort_keys=True, default=str).encode()).hexdigest(), target_host="h", collected_by="u")


BRUTE = [_ev(f"ev{i}", "SYSTEM_EVENT", {"event_type": "login_failure", "user": "svc", "timestamp": f"2026-09-26T10:{i:02d}:00+00:00", "description": "fail"}) for i in range(2, 9)]
SUCCESS = _ev("evok", "SYSTEM_EVENT", {"event_type": "login_success", "user": "svc", "timestamp": "2026-09-26T10:12:00+00:00", "description": "ok"})
ENCPROC = _ev("evp", "PROCESS", {"pid": 5, "name": "powershell.exe", "cmdline": "powershell -enc AAAABBBBCCCCDDDDEEEE", "user": "svc", "parent_name": "winword.exe", "started_at": "2026-09-26T10:14:00+00:00"})
EXFIL = _ev("evn", "NETWORK_CONNECTION", {"src_ip": "10.0.0.5", "dst_ip": "203.0.113.9", "dst_port": 4444, "bytes_sent": 5_000_000, "protocol": "TCP"})


def test_heuristic_detects_bruteforce_and_cites():
    res = heuristic.correlate(BRUTE + [SUCCESS, ENCPROC, EXFIL])
    ids = {e.id for e in BRUTE + [SUCCESS, ENCPROC, EXFIL]}
    all_cited = [i for ind in res["suspicious_indicators"] for i in ind["evidence_ids"]]
    assert all_cited and set(all_cited) <= ids  # never fabricates evidence ids
    sevs = {ind["severity"] for ind in res["suspicious_indicators"]}
    assert "CRITICAL" in sevs and "HIGH" in sevs
    stages = [s["stage"] for s in res["attack_stages"]]
    assert "Execution" in stages and ("Exfiltration" in stages or "Command and Control" in stages)
    mitre = {m["technique_id"] for m in res["mitre_techniques"]}
    assert {"T1110", "T1059.001"} <= mitre
    assert 0.0 <= res["confidence"] <= 1.0


def test_heuristic_empty_evidence_no_claims():
    res = heuristic.correlate([])
    assert res["suspicious_indicators"] == []
    assert res["attack_stages"] == []
    assert res["gaps"]


def test_correlation_schema_rejects_invalid():
    with pytest.raises(ValidationError):
        CorrelationResult.model_validate({"what_happened": "x", "confidence": 4.2})
    with pytest.raises(ValidationError):
        CorrelationResult.model_validate({"what_happened": "x", "confidence": 0.5, "suspicious_indicators": [{"indicator": "i", "severity": "ULTRA"}]})


def test_query_response_schema():
    ok = QueryResponse.model_validate({"answer": "a", "evidence_refs": ["x"], "confidence": 0.4, "caveat": None})
    assert ok.evidence_refs == ["x"]


def test_extractive_answer_without_hits():
    ans = rag.extractive_answer("who?", [])
    assert ans["confidence"] == 0.0 and ans["evidence_refs"] == []
    assert "does not contain" in ans["answer"]


async def test_rag_retrieval_ranks_relevant(db, users):
    from app.ai.embeddings import embed_text, evidence_to_text
    from app.db.models import EvidenceEmbedding, Investigation

    db.add(Investigation(id="inv", name="rag", target_host="h", created_by="u"))

    items = [
        _ev("r1", "PROCESS", {"pid": 1, "name": "powershell.exe", "cmdline": "powershell -enc AAAA", "user": "svc"}),
        _ev("r2", "FILE", {"path": "/etc/hosts", "size": 10}),
    ]
    for it in items:
        db.add(it)
    await db.commit()
    for it in items:
        text = evidence_to_text(it)
        db.add(EvidenceEmbedding(evidence_id=it.id, embedding=embed_text(text), text_content=text))
    await db.commit()
    hits = await rag.retrieve(db, "inv", "powershell encoded command process", top_k=5)
    assert hits and hits[0][0].id == "r1"
