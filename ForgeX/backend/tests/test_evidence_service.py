"""Unit tests: evidence hashing, dedupe, anchor chain, embeddings (architecture §12 CRITICAL)."""
from __future__ import annotations

import hashlib
import json

from sqlalchemy import select

from app.db.models import AnchorRecord, CollectorType, EvidenceEmbedding, EvidenceItem, Investigation, Provenance
from app.services import blockchain_service
from app.services.evidence_service import compute_hash, store_items


def test_compute_hash_canonical_and_stable():
    a = {"b": 1, "a": {"z": 2, "y": 3}}
    b = {"a": {"y": 3, "z": 2}, "b": 1}
    assert compute_hash(a) == compute_hash(b)
    assert compute_hash(a) == hashlib.sha256(json.dumps(a, sort_keys=True, default=str).encode()).hexdigest()
    assert compute_hash(a) != compute_hash({"b": 1, "a": {"z": 2}})


async def test_store_items_hashes_dedupes_and_embeds(db, users):
    inv = Investigation(name="ev-case", target_host="10.0.0.9", created_by=users["INVESTIGATOR"].id)
    db.add(inv)
    await db.commit()
    items = [{"pid": 1, "name": "a"}, {"pid": 2, "name": "b"}]
    stored, dups = await store_items(db, inv, None, CollectorType.PROCESS, items, users["INVESTIGATOR"], Provenance.LIVE)
    await db.commit()
    assert (stored, dups) == (2, 0)
    rows = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == inv.id))).scalars().all()
    assert all(r.data_hash == compute_hash(r.data) for r in rows)
    emb = (
        await db.execute(
            select(EvidenceEmbedding).where(EvidenceEmbedding.evidence_id.in_(select(EvidenceItem.id).where(EvidenceItem.investigation_id == inv.id)))
        )
    ).scalars().all()
    assert len(emb) == 2 and all(len(e.embedding) > 0 for e in emb)
    # duplicates skipped on second pass
    stored2, dups2 = await store_items(db, inv, None, CollectorType.PROCESS, items, users["INVESTIGATOR"], Provenance.LIVE)
    await db.commit()
    assert (stored2, dups2) == (0, 2)


async def test_anchor_chain_links_and_verifies(db, users):
    inv = Investigation(name="chain-case", target_host="10.0.0.9", created_by=users["INVESTIGATOR"].id)
    db.add(inv)
    await db.commit()
    before = len((await db.execute(select(AnchorRecord))).scalars().all())
    items = [{"i": i} for i in range(5)]
    await store_items(db, inv, None, CollectorType.FILE, items, users["INVESTIGATOR"], Provenance.LIVE)
    await db.commit()
    recs = (await db.execute(select(AnchorRecord).order_by(AnchorRecord.id))).scalars().all()
    assert len(recs) == before + 5
    mine = recs[before:]
    if before == 0:
        assert mine[0].prev_hash == "0" * 64
    for prev, cur in zip(mine, mine[1:]):
        assert cur.prev_hash == prev.record_hash
    result = await blockchain_service.verify_chain(db)
    assert result["valid"] is True and result["records"] == before + 5


async def test_tampered_chain_detected(db, users):
    inv = Investigation(name="tamper-case", target_host="10.0.0.9", created_by=users["INVESTIGATOR"].id)
    db.add(inv)
    await db.commit()
    await store_items(db, inv, None, CollectorType.FILE, [{"x": 1}, {"x": 2}], users["INVESTIGATOR"], Provenance.LIVE)
    await db.commit()
    rec = (await db.execute(select(AnchorRecord).order_by(AnchorRecord.id).limit(1))).scalar_one()
    rec.record_hash = "f" * 64  # simulate DB-level tampering
    await db.commit()
    result = await blockchain_service.verify_chain(db)
    assert result["valid"] is False
    assert result["broken_at_record_id"] == rec.id
