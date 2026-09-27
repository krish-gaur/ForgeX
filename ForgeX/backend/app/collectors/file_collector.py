"""File collector: metadata + SHA-256/MD5 within policy-allowed paths."""
from __future__ import annotations

import hashlib
import os
import stat
import sys
from datetime import UTC, datetime
from pathlib import Path

from app.collectors.base import BaseCollector, CollectContext, apply_filters, apply_limit
from app.core.errors import ValidationError
from app.db.models import CollectorType

_DEFAULT_MAX_ITEMS = 2000


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=UTC).isoformat()


def _hash_file(path: str, max_bytes: int) -> tuple[str, str] | None:
    try:
        if os.path.getsize(path) > max_bytes:
            return None
        sha = hashlib.sha256()
        md5 = hashlib.md5(usedforsecurity=False) if sys.version_info >= (3, 9) else hashlib.md5()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                sha.update(chunk)
                md5.update(chunk)
        return sha.hexdigest(), md5.hexdigest()
    except OSError:
        return None


class FileCollector(BaseCollector):
    type = CollectorType.FILE
    name = "file"

    async def collect(self, ctx: CollectContext) -> list[dict]:
        restrictions = (ctx.rules.get("field_restrictions", {}) or {}).get("files", {}) or {}
        excluded = [Path(p) for p in restrictions.get("excluded_paths", [])]
        max_depth = int(restrictions.get("max_depth", 8))
        max_bytes = int(restrictions.get("max_file_bytes", 52_428_800))

        if ctx.is_dataset:
            items = ctx.dataset_file("files.json")
            items = apply_filters(items, ctx.params.get("filters", []))
            return apply_limit(items, ctx.params)

        roots = self._roots(ctx)
        if not roots:
            raise ValidationError(
                "File collection requires an explicit path filter on live targets (e.g. WHERE path = '/var/log').",
                details={"hint": "Add a condition on the 'path' field, or run against a dataset source."},
            )
        items: list[dict] = []
        for root in roots:
            self._walk(root, root, 0, max_depth, excluded, max_bytes, items)
            if len(items) >= _DEFAULT_MAX_ITEMS:
                break
        items = apply_filters(items, ctx.params.get("filters", []))
        return apply_limit(items[:_DEFAULT_MAX_ITEMS], ctx.params)

    def _roots(self, ctx: CollectContext) -> list[Path]:
        roots = []
        for cond in ctx.params.get("filters", []):
            if cond["field"] == "path" and cond["op"] in ("=", "CONTAINS"):
                candidate = Path(str(cond["value"]))
                if candidate.is_dir():
                    roots.append(candidate.resolve())
        return roots

    def _walk(self, root: Path, current: Path, depth: int, max_depth: int, excluded: list[Path], max_bytes: int, out: list[dict]) -> None:
        if depth > max_depth or len(out) >= _DEFAULT_MAX_ITEMS:
            return
        try:
            for entry in sorted(os.scandir(current), key=lambda e: e.name):
                rp = Path(entry.path).resolve()
                if any(rp == ex or ex in rp.parents or str(rp).startswith(str(ex)) for ex in excluded):
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        self._walk(root, rp, depth + 1, max_depth, excluded, max_bytes, out)
                    elif entry.is_file(follow_symlinks=False):
                        st = entry.stat(follow_symlinks=False)
                        hashes = _hash_file(entry.path, max_bytes)
                        out.append(
                            {
                                "path": str(rp),
                                "size": st.st_size,
                                "hash_sha256": hashes[0] if hashes else None,
                                "hash_md5": hashes[1] if hashes else None,
                                "created_at": _iso(st.st_ctime),
                                "modified_at": _iso(st.st_mtime),
                                "accessed_at": _iso(st.st_atime),
                                "permissions": stat.filemode(st.st_mode),
                                "owner": str(st.st_uid),
                                "is_executable": bool(st.st_mode & stat.S_IXUSR),
                            }
                        )
                except OSError:
                    continue
        except (PermissionError, OSError):
            return
