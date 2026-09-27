"""System event collector: Linux syslog/auth.log/journalctl, Windows .evtx, dataset replay."""
from __future__ import annotations

import asyncio
import json
import platform
import re
from datetime import UTC, datetime
from pathlib import Path

from app.collectors.base import BaseCollector, CollectContext, apply_filters, apply_limit
from app.core.errors import UnsupportedArtifact
from app.db.models import CollectorType

_SYSLOG_CANDIDATES = ("/var/log/auth.log", "/var/log/secure", "/var/log/syslog", "/var/log/messages")

_SYSLOG_RE = re.compile(r"^(?P<month>\w{3})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2})\s+(?P<host>\S+)\s+(?P<process>\S+?)(?:\[(?P<pid>\d+)\])?:\s+(?P<msg>.*)$")

_FAILED_RE = re.compile(r"failed password|authentication failure|invalid user", re.I)
_SUCCESS_RE = re.compile(r"accepted (password|publickey)|session opened", re.I)
_SUDO_RE = re.compile(r"sudo:", re.I)


def _classify(process: str, msg: str) -> tuple[str, str]:
    if _FAILED_RE.search(msg):
        return "login_failure", msg
    if _SUDO_RE.search(process + " " + msg):
        return "privilege_use", msg
    if _SUCCESS_RE.search(msg):
        return "login_success", msg
    return "system", msg


def _user_from_msg(msg: str) -> str | None:
    m = re.search(r"(?:for|user)\s+(?:invalid user\s+)?(\S+?)\s+(?:from|:|$)", msg, re.I)
    return m.group(1) if m else None


class EventCollector(BaseCollector):
    type = CollectorType.EVENT
    name = "event"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        restrictions = (ctx.rules.get("field_restrictions", {}) or {}).get("events", {}) or {}
        max_items = int(restrictions.get("max_items", 5000))
        if ctx.is_dataset:
            items = ctx.dataset_file("events.json")
            if not items:
                items = self._parse_syslog_text(ctx.dataset_text("auth.log"))
            items = apply_filters(items, ctx.params.get("filters", []))
            return apply_limit(items[:max_items], ctx.params)

        items = self._from_syslog_files()
        if not items:
            items = await self._from_journalctl(ctx.time_left())
        if not items and platform.system() == "Windows":
            raise UnsupportedArtifact(
                "Windows EventLog collection requires .evtx sources. Point the investigation at a dataset containing .evtx exports, or install requirements-extra (python-evtx).",
                details={"collector": "events", "platform": platform.system()},
            )
        items = apply_filters(items, ctx.params.get("filters", []))
        return apply_limit(items[:max_items], ctx.params)

    def _from_syslog_files(self) -> list[dict]:
        items: list[dict] = []
        year = datetime.now(UTC).year
        for path in _SYSLOG_CANDIDATES:
            p = Path(path)
            if not p.exists():
                continue
            try:
                text = p.read_text(errors="replace")
            except OSError:
                continue
            items.extend(self._parse_syslog_text(text, year, source=str(p)))
            if items:
                break
        return items

    def _parse_syslog_text(self, text: str, year: int | None = None, source: str = "syslog") -> list[dict]:
        if not text:
            return []
        year = year or datetime.now(UTC).year
        items = []
        for i, line in enumerate(text.splitlines()):
            m = _SYSLOG_RE.match(line)
            if not m:
                continue
            try:
                ts = datetime.strptime(f"{year} {m.group('month')} {m.group('day')} {m.group('time')}", "%Y %b %d %H:%M:%S").replace(tzinfo=UTC)
            except ValueError:
                continue
            etype, desc = _classify(m.group("process"), m.group("msg"))
            items.append(
                {
                    "event_id": i,
                    "event_type": etype,
                    "timestamp": ts.isoformat(),
                    "source": source,
                    "description": desc[:500],
                    "user": _user_from_msg(m.group("msg")),
                    "pid": int(m.group("pid")) if m.group("pid") else None,
                }
            )
        return items

    async def _from_journalctl(self, time_left: float) -> list[dict]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "journalctl", "-n", "1000", "--output=json", "-q",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.DEVNULL,
            )
            out, _ = await asyncio.wait_for(proc.communicate(), timeout=max(2.0, min(time_left, 15.0)))
        except (TimeoutError, OSError):
            return []
        items = []
        for line in out.decode("utf-8", "replace").splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts_us = rec.get("__REALTIME_TIMESTAMP")
            if not ts_us:
                continue
            msg = rec.get("MESSAGE", "")
            if isinstance(msg, list):
                msg = "".join(chr(c) for c in msg)
            etype, desc = _classify(rec.get("SYSLOG_IDENTIFIER", rec.get("_COMM", "")), str(msg))
            items.append(
                {
                    "event_id": rec.get("_BOOT_ID"),
                    "event_type": etype,
                    "timestamp": datetime.fromtimestamp(int(ts_us) / 1e6, tz=UTC).isoformat(),
                    "source": "journalctl",
                    "description": str(msg)[:500],
                    "user": rec.get("_UID"),
                    "pid": int(rec["_PID"]) if str(rec.get("_PID", "")).isdigit() else None,
                }
            )
        return items


def parse_evtx(path: Path) -> list[dict]:
    """Windows .evtx parsing via python-evtx when installed (requirements-extra)."""
    try:
        from Evtx import Evtx  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise UnsupportedArtifact("python-evtx is not installed; install requirements-extra.txt to parse .evtx files.") from e
    items = []
    with Evtx(str(path)) as log:
        for record in log.records():
            try:
                data = json.loads(record.xml())
            except Exception:  # noqa: BLE001
                continue
            system = data.get("Event", {}).get("System", {})
            items.append(
                {
                    "event_id": system.get("EventID"),
                    "event_type": f"evtx:{system.get('Channel')}",
                    "timestamp": record.timestamp().isoformat(),
                    "source": path.name,
                    "description": json.dumps(data.get("Event", {}).get("EventData", {}))[:500],
                    "user": None,
                    "pid": None,
                }
            )
    return items
