"""FQL parser: text → typed AST using the Lark grammar (parse only, never executes)."""
from __future__ import annotations

from pathlib import Path

from lark import Lark, Token, Transformer
from lark.exceptions import UnexpectedInput, VisitError

from app.core.errors import FqlParseError
from app.fql.ast_types import Condition, FqlProgram, InvestigateStmt, TimelineStmt

_GRAMMAR = (Path(__file__).parent / "grammar.lark").read_text()

_parser = Lark(_GRAMMAR, parser="earley", ambiguity="resolve", propagate_positions=True)

_COLLECTORS = {"processes", "files", "network", "users", "events"}


class _Ast(Transformer):
    def start(self, items):
        return FqlProgram(statements=list(items))

    def statement(self, items):
        return items[0]

    def investigate_stmt(self, items):
        collector = None
        conditions: list[Condition] = []
        limit = None
        for it in items:
            if isinstance(it, str) and not isinstance(it, Token) and it in _COLLECTORS:
                collector = it
            elif isinstance(it, list):
                conditions = it
            elif isinstance(it, int):
                limit = it
        return InvestigateStmt(collector=collector, conditions=conditions, limit=limit)

    def timeline_stmt(self, items):
        dts = [it for it in items if isinstance(it, str) and not isinstance(it, Token)]
        return TimelineStmt(start=dts[0], end=dts[1])

    def where_clause(self, items):
        conds: list[Condition] = []
        pending_op: str | None = None
        for it in items:
            if isinstance(it, str) and not isinstance(it, Token) and it in ("AND", "OR"):
                pending_op = it
            elif isinstance(it, Condition):
                it.bool_op = None if not conds else (pending_op or "AND")
                conds.append(it)
                pending_op = None
        return conds

    def condition(self, items):
        field, op, value = items[0], items[1], items[2]
        return Condition(field=field, op=op, value=value)

    def bool_op(self, items):
        return str(items[0]).upper()

    def limit_clause(self, items):
        return next(it for it in items if isinstance(it, int))

    def collector(self, items):
        return str(items[0]).lower()

    def value(self, items):
        return items[0]

    def value_list(self, items):
        return list(items)

    def STRING(self, token: Token):
        return str(token)[1:-1]

    def NUMBER(self, token: Token):
        text = str(token)
        return float(text) if "." in text else int(text)

    def INT(self, token: Token):
        return int(token)

    def DATETIME(self, token: Token):
        return str(token).strip('"')

    def FIELD(self, token: Token):
        return str(token)

    def OP(self, token: Token):
        return " ".join(str(token).upper().split())


def _build(program_tree) -> FqlProgram:
    prog: FqlProgram = _Ast().transform(program_tree)
    return prog


def parse_fql(text: str) -> FqlProgram:
    """Parse FQL source into an AST. Raises FqlParseError with line/col on failure."""
    if not text or not text.strip():
        raise FqlParseError("Empty FQL query.", details={"line": 1, "col": 1, "token": None})
    if len(text) > 20_000:
        raise FqlParseError("FQL query exceeds maximum length of 20000 characters.", details={"line": 1, "col": 1})
    try:
        tree = _parser.parse(text)
    except UnexpectedInput as e:
        line = max(1, int(getattr(e, "line", 1) or 1))
        col = max(1, int(getattr(e, "column", 1) or 1))
        lines = text.splitlines()
        snippet = lines[line - 1][max(col - 1, 0) : col + 7] if 1 <= line <= len(lines) else ""
        raise FqlParseError(
            f"Unexpected token at line {line}, col {col}.",
            details={"line": line, "col": col, "token": snippet, "expected": sorted(str(x) for x in list(getattr(e, "accepts", None) or [])[:8])},
        ) from e
    try:
        prog = _build(tree)
    except VisitError as e:  # pragma: no cover - defensive
        raise FqlParseError(f"Internal parse failure: {e}") from e
    for stmt in prog.statements:
        if isinstance(stmt, InvestigateStmt) and stmt.collector not in _COLLECTORS:
            raise FqlParseError(f"Unknown collector '{stmt.collector}'.", details={"line": 1, "col": 1})
    if not prog.statements:
        raise FqlParseError("No statements found in FQL query.")
    return prog


def validate_fql(text: str) -> dict:
    prog = parse_fql(text)
    return {"valid": True, "ast": prog.to_dict(), "estimated_collectors": prog.collectors}
