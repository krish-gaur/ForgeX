"""Evidence anchoring: append-only SHA-256 hash chain (default) or Ethereum Sepolia.

The local chain is a genuine tamper-evident ledger: every record binds
(prev_hash, evidence_id, data_hash, timestamp). Auditors can re-verify the
whole chain via GET /investigations/:id/anchor-chain/verify.
"""
from __future__ import annotations

import hashlib
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.logging import get_logger
from app.db.models import AnchorChain, AnchorRecord, BlockchainStatus, EvidenceItem

log = get_logger("anchor")
GENESIS = "0" * 64
settings = get_settings()


def _record_hash(prev: str, evidence_id: str, data_hash: str, ts: str) -> str:
    return hashlib.sha256(f"{prev}|{evidence_id}|{data_hash}|{ts}".encode()).hexdigest()


def iso_norm(dt) -> str:
    """UTC-aware ISO string; SQLite round-trips drop the offset, so re-attach UTC."""
    if dt is None:
        return ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt.isoformat()


async def anchor_evidence_hash(db: AsyncSession, evidence: EvidenceItem) -> AnchorRecord:
    last = (await db.execute(select(AnchorRecord).order_by(AnchorRecord.id.desc()).limit(1))).scalar_one_or_none()
    prev = last.record_hash if last else GENESIS
    dt = datetime.now(UTC)
    ts = dt.isoformat()
    rec_hash = _record_hash(prev, evidence.id, evidence.data_hash, ts)
    tx_hash = None
    chain = AnchorChain.LOCAL_HASH_CHAIN
    if settings.blockchain_anchor == "sepolia" and settings.sepolia_private_key:
        tx_hash = await _submit_sepolia(evidence, rec_hash)
        chain = AnchorChain.SEPOLIA
        evidence.blockchain_status = BlockchainStatus.PENDING.value if tx_hash else BlockchainStatus.FAILED.value
    else:
        evidence.blockchain_status = BlockchainStatus.CONFIRMED.value
    evidence.blockchain_tx = tx_hash or f"local:{rec_hash[:32]}"
    rec = AnchorRecord(
        evidence_id=evidence.id,
        data_hash=evidence.data_hash,
        prev_hash=prev,
        record_hash=rec_hash,
        chain=chain.value,
        tx_hash=tx_hash,
        created_at=dt,
    )
    db.add(rec)
    await db.flush()
    return rec


async def _submit_sepolia(evidence: EvidenceItem, rec_hash: str) -> str | None:
    """Best-effort Sepolia anchoring via web3 (requirements-extra). Never blocks collection."""
    try:
        from web3 import Web3  # type: ignore

        w3 = Web3(Web3.HTTPProvider(settings.sepolia_rpc_url, request_kwargs={"timeout": 10}))
        acct = w3.eth.account.from_key(settings.sepolia_private_key)
        nonce = w3.eth.get_transaction_count(acct.address)
        tx = {
            "nonce": nonce,
            "to": acct.address,
            "value": 0,
            "gas": 100_000,
            "gasPrice": w3.eth.gas_price,
            "chainId": 11155111,
            "data": rec_hash.encode(),
        }
        signed = acct.sign_transaction(tx)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        return tx_hash.hex()
    except Exception as e:  # noqa: BLE001 — anchoring is fire-and-forget by design
        log.warning("sepolia_anchor_failed", evidence=evidence.id, error=str(e)[:200])
        return None


async def verify_chain(db: AsyncSession) -> dict:
    records = (await db.execute(select(AnchorRecord).order_by(AnchorRecord.id.asc()))).scalars().all()
    prev = GENESIS
    broken_at: int | None = None
    for rec in records:
        if rec.prev_hash != prev:
            broken_at = rec.id
            break
        expect = _record_hash(prev, rec.evidence_id, rec.data_hash, iso_norm(rec.created_at))
        if expect != rec.record_hash:
            broken_at = rec.id
            break
        prev = rec.record_hash
    return {"records": len(records), "valid": broken_at is None, "broken_at_record_id": broken_at, "chain": "SHA-256 append-only ledger (full per-record recompute)"}
