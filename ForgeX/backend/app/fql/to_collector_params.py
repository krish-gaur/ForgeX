"""AST → collector parameters (typed dicts only; never shell strings)."""
from __future__ import annotations

from app.db.models import CollectorType
from app.fql.ast_types import FqlProgram, InvestigateStmt, TimelineStmt

_COLLECTOR_MAP = {
    "processes": CollectorType.PROCESS,
    "files": CollectorType.FILE,
    "network": CollectorType.NETWORK,
    "users": CollectorType.USER,
    "events": CollectorType.EVENT,
}


def ast_to_collector_params(prog: FqlProgram) -> list[tuple[CollectorType, dict]]:
    out: list[tuple[CollectorType, dict]] = []
    for stmt in prog.statements:
        if isinstance(stmt, InvestigateStmt):
            ctype = _COLLECTOR_MAP[stmt.collector]
            params = {
                "filters": [c.to_dict() for c in stmt.conditions],
                "limit": stmt.limit,
            }
            if not any(t == ctype for t, _ in out):
                out.append((ctype, params))
            else:
                # merge additional statements against same collector
                for existing_type, existing_params in out:
                    if existing_type == ctype:
                        existing_params.setdefault("extra_filters", []).append(params["filters"])
                        if stmt.limit:
                            existing_params["limit"] = min(existing_params.get("limit") or stmt.limit, stmt.limit)
        elif isinstance(stmt, TimelineStmt):
            out.append((CollectorType.TIMELINE, {"from": stmt.start, "to": stmt.end}))
    return out
