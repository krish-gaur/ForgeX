"""Process collector: live via psutil, or dataset replay."""
from __future__ import annotations

import hashlib
import os
from datetime import UTC, datetime

import psutil

from app.collectors.base import BaseCollector, CollectContext, apply_filters, apply_limit
from app.db.models import CollectorType


def _hash_exe(path: str | None) -> str | None:
    if not path or not os.path.isfile(path):
        return None
    try:
        if os.path.getsize(path) > 52_428_800:
            return None
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


class ProcessCollector(BaseCollector):
    type = CollectorType.PROCESS
    name = "process"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        if ctx.is_dataset:
            items = ctx.dataset_file("processes.json")
        else:
            items = []
            for proc in psutil.process_iter(["pid", "name", "cmdline", "username", "ppid", "create_time", "exe"]):
                try:
                    info = proc.info
                    with proc.oneshot():
                        mem = proc.memory_info().rss / (1024 * 1024)
                        cpu = proc.cpu_percent(interval=None)
                    items.append(
                        {
                            "pid": info["pid"],
                            "name": info["name"] or "",
                            "cmdline": " ".join(info.get("cmdline") or []),
                            "user": info.get("username") or "unknown",
                            "parent_pid": info.get("ppid") or 0,
                            "parent_name": "",
                            "hash_sha256": _hash_exe(info.get("exe")),
                            "started_at": datetime.fromtimestamp(info["create_time"], tz=UTC).isoformat() if info.get("create_time") else None,
                            "memory_mb": round(mem, 2),
                            "cpu_percent": cpu,
                        }
                    )
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            by_pid = {i["pid"]: i["name"] for i in items}
            for i in items:
                i["parent_name"] = by_pid.get(i["parent_pid"], "")
        items = apply_filters(items, ctx.params.get("filters", []))
        return apply_limit(items, ctx.params)
