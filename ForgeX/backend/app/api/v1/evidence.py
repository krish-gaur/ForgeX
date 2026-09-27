"""Evidence browsing, integrity verification, export, and artifact ingestion (pcap/zeek/evtx/json)."""
from __future__ import annotations

import csv
import io
import json
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Request, UploadFile
from fastapi.responses import Response as FastResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.collectors.event_collector import parse_evtx
from app.collectors.network_collector import parse_zeek_conn_log
from app.collectors.pcap_parser import parse_pcap
from app.config import get_settings
from app.core import audit
from app.core.auth import CurrentUser, require_min_role
from app.core.errors import NotFound, UnsupportedArtifact, ValidationError
from app.db.models import CollectorExecution, CollectorStatus, CollectorType, EvidenceItem, Provenance, Role, User
from app.db.session import get_db
from app.services import investigation_service
from app.services.evidence_service import compute_hash, store_items
from app.services.timeline_service import parse_ts, timestamp_for

router = APIRouter(tags=["evidence"])
settings = get_settings()

_ALLOWED_EXT = {".pcap", ".cap", ".log", ".json", ".evtx"}


@router.get("/investigations/{inv_id}/evidence")
async def list_evidence(
    inv_id: str,
    user: CurrentUser,
    db: AsyncSession = Depends(get_db),
    type: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
    search: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=500),
):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    stmt = select(EvidenceItem).where(EvidenceItem.investigation_id == inv.id)
    if type:
        stmt = stmt.where(EvidenceItem.evidence_type == type)
    items = list((await db.execute(stmt)).scalars().all())
    ft, tt = parse_ts(from_time), parse_ts(to_time)
    if ft:
        items = [i for i in items if (timestamp_for(i) or i.collected_at) >= ft]
    if tt:
        items = [i for i in items if (timestamp_for(i) or i.collected_at) <= tt]
    if search:
        s = search.lower()
        items = [i for i in items if s in json.dumps(i.data, default=str).lower()]
    total = len(items)
    page_items = items[(page - 1) * per_page : page * per_page]
    return {
        "data": [
            {
                "id": e.id,
                "evidence_type": e.evidence_type,
                "collected_at": e.collected_at.isoformat() if e.collected_at else None,
                "data_hash": e.data_hash,
                "data": e.data,
                "provenance": e.provenance,
                "blockchain_status": e.blockchain_status,
                "blockchain_tx": e.blockchain_tx,
                "raw_file_path": e.raw_file_path,
            }
            for e in page_items
        ],
        "pagination": {"page": page, "per_page": per_page, "total": total},
    }


@router.get("/investigations/{inv_id}/evidence/export")
async def export_evidence(inv_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db), format: str = "json"):
    inv = await investigation_service.get_for_user(db, inv_id, user)
    items = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == inv.id))).scalars().all()
    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "type", "collected_at", "sha256", "data"])
        for e in items:
            writer.writerow([e.id, e.evidence_type, e.collected_at.isoformat() if e.collected_at else "", e.data_hash, json.dumps(e.data, default=str)])
        return FastResponse(buf.getvalue(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{inv.name}-evidence.csv"'})
    payload = [{"id": e.id, "type": e.evidence_type, "collected_at": e.collected_at.isoformat() if e.collected_at else None, "sha256": e.data_hash, "data": e.data} for e in items]
    return FastResponse(json.dumps(payload, indent=2, default=str), media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{inv.name}-evidence.json"'})


@router.get("/investigations/{inv_id}/evidence/{evidence_id}")
async def get_evidence(inv_id: str, evidence_id: str, user: CurrentUser, db: AsyncSession = Depends(get_db), verify: bool = False):
    await investigation_service.get_for_user(db, inv_id, user)
    item = await db.get(EvidenceItem, evidence_id)
    if not item or item.investigation_id != inv_id:
        raise NotFound(f"No evidence item {evidence_id} in this investigation.")
    out = {
        "id": item.id,
        "evidence_type": item.evidence_type,
        "collected_at": item.collected_at.isoformat() if item.collected_at else None,
        "target_host": item.target_host,
        "data": item.data,
        "data_hash": item.data_hash,
        "provenance": item.provenance,
        "blockchain_status": item.blockchain_status,
        "blockchain_tx": item.blockchain_tx,
    }
    if verify:
        recomputed = compute_hash(item.data)
        out["integrity"] = {"recomputed_sha256": recomputed, "matches_stored": recomputed == item.data_hash}
    return out


@router.post("/investigations/{inv_id}/evidence/ingest", status_code=201)
async def ingest_artifact(inv_id: str, request: Request, file: UploadFile, user: User = Depends(require_min_role(Role.INVESTIGATOR)), db: AsyncSession = Depends(get_db)):
    """Ingest a forensic artifact file (pcap / zeek conn.log / events json / evtx) as evidence."""
    inv = await investigation_service.get_for_user(db, inv_id, user)
    suffix = Path(file.filename or "artifact.bin").suffix.lower()
    if suffix not in _ALLOWED_EXT:
        raise UnsupportedArtifact(f"Unsupported artifact type '{suffix}'. Allowed: {sorted(_ALLOWED_EXT)}")
    content = await file.read()
    if len(content) > 200 * 1024 * 1024:
        raise ValidationError("Artifact exceeds 200 MB limit.")
    store_dir = Path(settings.file_store_dir) / "ingest" / inv.id
    store_dir.mkdir(parents=True, exist_ok=True)
    digest = compute_hash({"name": file.filename, "size": len(content)})
    path = store_dir / f"{digest}{suffix}"
    path.write_bytes(content)

    execution = CollectorExecution(collector_type=CollectorType.NETWORK.value, status=CollectorStatus.RUNNING.value, raw_params={"ingest": file.filename})
    db.add(execution)
    await db.flush()

    items: list[dict] = []
    etype = CollectorType.NETWORK
    if suffix in (".pcap", ".cap"):
        packets = parse_pcap(content)
        items = [
            {
                "src_ip": p.src_ip, "src_port": p.src_port, "dst_ip": p.dst_ip, "dst_port": p.dst_port,
                "protocol": p.protocol, "state": "CAPTURED", "pid": None, "process_name": None,
                "bytes_sent": p.length, "bytes_recv": None, "dns_query": p.dns_query, "source": "pcap", "captured_at": p.ts,
            }
            for p in packets
        ]
    elif suffix == ".log":
        items = parse_zeek_conn_log(content.decode("utf-8", "replace"))
    elif suffix == ".json":
        try:
            data = json.loads(content.decode("utf-8"))
        except json.JSONDecodeError as e:
            raise ValidationError(f"Invalid JSON artifact: {e}") from e
        items = data if isinstance(data, list) else data.get("items", [])
        etype = CollectorType.EVENT if items and isinstance(items[0], dict) and "event_type" in items[0] else CollectorType.NETWORK
    elif suffix == ".evtx":
        items = parse_evtx(path)
        etype = CollectorType.EVENT

    stored, dups = await store_items(db, inv, execution.id, etype, items, user, Provenance(investigation_provenance(inv)))
    execution.status = CollectorStatus.COMPLETED.value
    execution.items_collected = stored
    for e in (await db.execute(select(EvidenceItem).where(EvidenceItem.execution_id == execution.id))).scalars().all():
        e.raw_file_path = str(path)
    await audit.audit(db, "EVIDENCE_INGESTED", actor=user, resource_type="investigation", resource_id=inv.id, metadata={"file": file.filename, "stored": stored, "duplicates": dups}, request=request)
    await db.commit()
    return {"stored": stored, "duplicates_skipped": dups, "file": str(path), "execution_id": execution.id}


def investigation_provenance(inv) -> str:
    return inv.provenance
