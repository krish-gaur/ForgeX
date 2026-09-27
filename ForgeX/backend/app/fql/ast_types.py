"""Typed AST nodes for FQL."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Condition:
    field: str
    op: str
    value: Any
    bool_op: str | None = None  # operator joining this condition to the previous one

    def to_dict(self) -> dict:
        return {"field": self.field, "op": self.op, "value": self.value, "bool_op": self.bool_op}


@dataclass
class InvestigateStmt:
    collector: str  # processes | files | network | users | events
    conditions: list[Condition] = field(default_factory=list)
    limit: int | None = None

    def to_dict(self) -> dict:
        return {
            "type": "INVESTIGATE",
            "collector": self.collector,
            "where": [c.to_dict() for c in self.conditions],
            "limit": self.limit,
        }


@dataclass
class TimelineStmt:
    start: str
    end: str

    def to_dict(self) -> dict:
        return {"type": "TIMELINE", "from": self.start, "to": self.end}


@dataclass
class FqlProgram:
    statements: list[InvestigateStmt | TimelineStmt] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"statements": [s.to_dict() for s in self.statements]}

    @property
    def collectors(self) -> list[str]:
        seen: list[str] = []
        for s in self.statements:
            if isinstance(s, InvestigateStmt) and s.collector not in seen:
                seen.append(s.collector)
        return seen
