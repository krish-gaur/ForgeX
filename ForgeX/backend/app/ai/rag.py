"""RAG retrieval over evidence embeddings (local cosine similarity)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import cosine, embed_text
from app.db.models import EvidenceEmbedding, EvidenceItem

SIMILARITY_THRESHOLD = 0.08  # local hashed embeddings are sparse; threshold tuned accordingly


async def retrieve(db: AsyncSession, investigation_id: str, question: str, top_k: int = 12) -> list[tuple[EvidenceItem, float]]:
    q = embed_text(question)
    rows = (
        await db.execute(
            select(EvidenceEmbedding, EvidenceItem)
            .join(EvidenceItem, EvidenceItem.id == EvidenceEmbedding.evidence_id)
            .where(EvidenceItem.investigation_id == investigation_id)
        )
    ).all()
    scored = []
    for emb, item in rows:
        sim = cosine(q, emb.embedding or [])
        scored.append((item, sim))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [(i, s) for i, s in scored[:top_k] if s > SIMILARITY_THRESHOLD]


def extractive_answer(question: str, hits: list[tuple[EvidenceItem, float]]) -> dict:
    if not hits:
        return {
            "answer": "The collected evidence does not contain information answering this question. Collect more evidence (e.g. INVESTIGATE events / processes / network) and retry.",
            "evidence_refs": [],
            "confidence": 0.0,
            "caveat": "No evidence above similarity threshold.",
        }
    top = hits[:5]
    lines = []
    for item, sim in top:
        d = item.data or {}
        label = d.get("name") or d.get("path") or d.get("description") or d.get("url") or d.get("username") or item.evidence_type
        lines.append(f"- [{item.evidence_type}] {str(label)[:140]} (similarity {sim:.2f})")
    avg = sum(s for _, s in top) / len(top)
    return {
        "answer": f"Based on {len(hits)} retrieved evidence item(s), the most relevant are:\n" + "\n".join(lines),
        "evidence_refs": [i.id for i, _ in top],
        "confidence": round(min(0.9, 0.3 + avg), 2),
        "caveat": "Extractive retrieval answer (offline engine).",
    }
