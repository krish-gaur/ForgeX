"""Evidence service: SHA-256 before write, immutability, anchoring, embedding, graph linking."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.embeddings import embed_text, evidence_to_text
from app.core.logging import get_logger
from app.db.models import (
    CollectorType,
    EvidenceEmbedding,
    EvidenceItem,
    EvidenceType,
    Investigation,
    Provenance,
    User,
)
from app.graph.builder import build_graph_for_evidence
from app.services.blockchain_service import anchor_evidence_hash

log = get_logger("evidence")

COLLECTOR_EVIDENCE_TYPE = {
    CollectorType.PROCESS: EvidenceType.PROCESS,
    CollectorType.FILE: EvidenceType.FILE,
    CollectorType.NETWORK: EvidenceType.NETWORK_CONNECTION,
    CollectorType.USER: EvidenceType.USER_ACCOUNT,
    CollectorType.EVENT: EvidenceType.SYSTEM_EVENT,
}


def compute_hash(data: dict) -> str:
    """SHA-256 of the canonical JSON rendering (architecture §16 rule)."""
    return hashlib.sha256(json.dumps(data, sort_keys=True, default=str).encode("utf-8")).hexdigest()


async def store_items(
    db: AsyncSession,
    investigation: Investigation,
    execution_id: str | None,
    collector_type: CollectorType,
    items: list[dict],
    user: User,
    provenance: Provenance,
) -> tuple[int, int]:
    etype = COLLECTOR_EVIDENCE_TYPE[collector_type]
    stored = 0
    duplicates = 0
    new_items: list[EvidenceItem] = []
    for item in items:
        data_hash = compute_hash(item)
        existing = await db.execute(
            select(EvidenceItem.id).where(EvidenceItem.investigation_id == investigation.id, EvidenceItem.data_hash == data_hash)
        )
        if existing.scalar_one_or_none():
            duplicates += 1
            continue
        ev = EvidenceItem(
            investigation_id=investigation.id,
            execution_id=execution_id,
            evidence_type=etype.value,
            target_host=investigation.target_host,
            data=item,
            data_hash=data_hash,
            provenance=provenance.value,
            collected_by=user.id,
        )
        db.add(ev)
        new_items.append(ev)
        stored += 1
    await db.flush()
    for ev in new_items:
        await anchor_evidence_hash(db, ev)
        text = evidence_to_text(ev)
        db.add(EvidenceEmbedding(evidence_id=ev.id, embedding=embed_text(text), text_content=text))
        await build_graph_for_evidence(db, ev)
    if new_items:
        await db.flush()
    log.info("evidence_stored", investigation=investigation.id, collector=collector_type.value, stored=stored, duplicates=duplicates)
    return stored, duplicates
