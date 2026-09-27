"""Timeline construction + severity heuristics over real stored evidence."""
from __future__ import annotations

import re
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvidenceItem

_ENC_CMD_RE = re.compile(r"(-enc(odedcommand)?\s+[A-Za-z0-9+/=]{16,}|base64\s+-d|frombase64string)", re.I)
_EXFIL_RE = re.compile(r"(curl|wget|nc|netcat|scp|ftp)\b", re.I)


def parse_ts(value) -> datetime | None:
    if not value:
        return None
    try:
        if isinstance(value, (int, float)):
            dt = datetime.fromtimestamp(value, tz=UTC)
        else:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (ValueError, OSError, OverflowError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    return dt


def severity_for(item: EvidenceItem) -> str:
    d = item.data or {}
    t = item.evidence_type
    if t == "PROCESS":
        cmd = d.get("cmdline") or ""
        if _ENC_CMD_RE.search(cmd):
            return "HIGH"
        if _EXFIL_RE.search(cmd) and re.search(r"\d{1,3}(\.\d{1,3}){3}", cmd):
            return "HIGH"
        return "INFO"
    if t == "SYSTEM_EVENT":
        et = d.get("event_type")
        if et == "login_failure":
            return "MEDIUM"
        if et in ("persistence", "privilege_use"):
            return "HIGH"
        if et == "login_success":
            return "LOW"
        return "INFO"
    if t == "NETWORK_CONNECTION":
        sent = d.get("bytes_sent") or 0
        if isinstance(sent, (int, float)) and sent > 1_000_000:
            return "HIGH"
        if d.get("dst_port") in (4444, 1337, 31337):
            return "HIGH"
        return "INFO"
    if t == "FILE":
        if d.get("is_executable") and (d.get("path") or "").startswith(("/tmp", "/var/tmp", "/dev/shm", "C:\\Temp")):
            return "MEDIUM"
        return "INFO"
    if t == "REGISTRY":
        if "Run" in str(d.get("key")):
            return "HIGH"
        return "INFO"
    return "INFO"


def label_for(item: EvidenceItem) -> str:
    d = item.data or {}
    t = item.evidence_type
    if t == "PROCESS":
        return f"{d.get('name')} (PID {d.get('pid')}) spawned by {d.get('parent_name') or '?'} ({d.get('user')})"
    if t == "FILE":
        return f"{d.get('path')} written/observed ({d.get('size')} bytes)"
    if t == "NETWORK_CONNECTION":
        return f"{d.get('src_ip')}:{d.get('src_port')} → {d.get('dst_ip')}:{d.get('dst_port')} ({d.get('protocol')})" + (f" dns={d.get('dns_query')}" if d.get("dns_query") else "")
    if t in ("SYSTEM_EVENT", "LOG_ENTRY"):
        return f"[{d.get('event_type')}] {d.get('description', '')[:120]}"
    if t == "USER_ACCOUNT":
        return f"User account {d.get('username')} (last login {d.get('last_login') or 'unknown'})"
    if t == "REGISTRY":
        return f"Registry {d.get('key')} = {str(d.get('value'))[:60]}"
    if t == "BROWSER_ARTIFACT":
        return f"Browser {d.get('kind')}: {d.get('url')}"
    return f"{t} evidence item"


def timestamp_for(item: EvidenceItem):
    d = item.data or {}
    for key in ("timestamp", "started_at", "created_at", "modified_at", "visited_at", "captured_at"):
        ts = parse_ts(d.get(key))
        if ts:
            return ts
    ts = item.collected_at
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


async def build_timeline(db: AsyncSession, investigation_id: str, from_ts: datetime | None = None, to_ts: datetime | None = None) -> list[dict]:
    items = (await db.execute(select(EvidenceItem).where(EvidenceItem.investigation_id == investigation_id))).scalars().all()
    entries = []
    for item in items:
        ts = timestamp_for(item)
        if ts is None:
            continue
        if from_ts and ts < from_ts:
            continue
        if to_ts and ts > to_ts:
            continue
        entries.append(
            {
                "timestamp": ts.isoformat(),
                "type": item.evidence_type,
                "label": label_for(item),
                "evidence_id": item.id,
                "severity": severity_for(item),
                "provenance": item.provenance,
            }
        )
    entries.sort(key=lambda e: e["timestamp"])
    return entries
