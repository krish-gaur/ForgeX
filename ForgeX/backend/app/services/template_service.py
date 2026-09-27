"""Template library loader (forensic function templates shipped with ForgeX)."""
from __future__ import annotations

import re
from pathlib import Path

from app.config import get_settings

settings = get_settings()
_FM_RE = re.compile(r"^# --- forgex-template\n(.*?)\n# ---\n", re.S)


def list_templates() -> list[dict]:
    out = []
    tdir = Path(settings.template_dir) / "functions"
    for path in sorted(tdir.glob("*.py")):
        raw = path.read_text(encoding="utf-8")
        meta = {"id": path.stem, "title": path.stem, "category": "Custom", "description": ""}
        m = _FM_RE.match(raw)
        if m:
            for line in m.group(1).splitlines():
                key, _, val = line.lstrip("# ").partition(":")
                meta[key.strip()] = val.strip()
        body = raw[m.end():] if m else raw
        out.append({**meta, "code": body, "language": "PYFUNC"})
    return out


def get_template(template_id: str) -> dict | None:
    for t in list_templates():
        if t["id"] == template_id:
            return t
    return None
