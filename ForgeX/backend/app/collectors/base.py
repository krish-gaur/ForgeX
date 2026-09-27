"""Collector framework: context, filtering, dataset access."""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path

from app.config import get_settings
from app.core.errors import EvidenceUnavailable
from app.db.models import CollectorType, Investigation, Provenance

settings = get_settings()


@dataclass
class CollectContext:
    investigation: Investigation
    params: dict = field(default_factory=dict)
    rules: dict = field(default_factory=dict)
    provenance: Provenance = Provenance.LIVE
    deadline: float = field(default_factory=lambda: time.monotonic() + 30.0)

    @property
    def is_dataset(self) -> bool:
        return self.investigation.source_mode == "DATASET"

    def dataset_dir(self) -> Path:
        src = self.investigation.source_path or ""
        p = Path(src)
        if not p.is_absolute():
            p = Path(settings.dataset_dir) / src
        if not p.exists():
            raise EvidenceUnavailable(
                f"Evidence source '{src}' is not available on this server.",
                details={"source_path": src, "hint": "Check investigation.source_path or re-run scripts/seed_demo.py"},
            )
        return p

    def dataset_file(self, name: str) -> list | dict:
        path = self.dataset_dir() / name
        if not path.exists():
            return []
        try:
            return json.loads(path.read_text())
        except (json.JSONDecodeError, UnicodeDecodeError):
            return []

    def dataset_text(self, name: str) -> str:
        path = self.dataset_dir() / name
        if not path.exists():
            return ""
        return path.read_text(errors="replace")

    def time_left(self) -> float:
        return max(0.0, self.deadline - time.monotonic())


class BaseCollector:
    type: CollectorType = CollectorType.PROCESS
    name: str = "base"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        raise NotImplementedError


def _match(item: dict, cond: dict) -> bool:
    field_name = cond["field"]
    value = item
    for part in field_name.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break
    op = cond["op"]
    target = cond["value"]
    if value is None:
        return op in ("!=", "NOT CONTAINS", "NOT IN")
    if isinstance(value, str) and isinstance(target, str):
        lhs, rhs = value.lower(), target.lower()
    else:
        lhs, rhs = value, target
    try:
        if op == "=":
            return lhs == rhs
        if op == "!=":
            return lhs != rhs
        if op == "CONTAINS":
            return rhs in lhs if isinstance(lhs, (str, list)) else False
        if op == "NOT CONTAINS":
            return rhs not in lhs if isinstance(lhs, (str, list)) else True
        if op == "IN":
            return lhs in (target if isinstance(target, list) else [target])
        if op == "NOT IN":
            return lhs not in (target if isinstance(target, list) else [target])
        if op == ">":
            return float(lhs) > float(rhs)
        if op == ">=":
            return float(lhs) >= float(rhs)
        if op == "<":
            return float(lhs) < float(rhs)
        if op == "<=":
            return float(lhs) <= float(rhs)
    except (TypeError, ValueError):
        return False
    return False


def apply_filters(items: list[dict], filters: list[dict]) -> list[dict]:
    """Left-to-right boolean evaluation of FQL WHERE conditions against item dicts."""
    if not filters:
        return items
    out = []
    for item in items:
        result = _match(item, filters[0])
        for cond in filters[1:]:
            m = _match(item, cond)
            result = (result and m) if cond.get("bool_op", "AND") == "AND" else (result or m)
        if result:
            out.append(item)
    return out


def apply_limit(items: list[dict], params: dict) -> list[dict]:
    limit = params.get("limit")
    return items[: int(limit)] if limit else items
