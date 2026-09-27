"""Unit tests: FQL parser (architecture §12 CRITICAL)."""
from __future__ import annotations

import pytest

from app.core.errors import FqlParseError
from app.fql.parser import parse_fql
from app.fql.to_collector_params import ast_to_collector_params


@pytest.mark.parametrize(
    "src,collectors",
    [
        ("INVESTIGATE processes", ["processes"]),
        ("INVESTIGATE files WHERE path CONTAINS '/var/log'", ["files"]),
        ("INVESTIGATE network WHERE dst_port IN (443, 80) LIMIT 10", ["network"]),
        ("INVESTIGATE users WHERE username != 'root'", ["users"]),
        ("INVESTIGATE events WHERE type = 'login_failure' AND count > 5", ["events"]),
        ('TIMELINE FROM "2026-09-26T00:00" TO "2026-09-26T23:59"', []),
        ("INVESTIGATE processes WHERE name CONTAINS 'x'\nINVESTIGATE events", ["processes", "events"]),
    ],
)
def test_valid_statements(src, collectors):
    prog = parse_fql(src)
    assert prog.collectors == collectors


def test_where_operators_and_bool_ops():
    prog = parse_fql("INVESTIGATE processes WHERE name CONTAINS 'pow' AND user = 'SYSTEM' OR pid > 100")
    conds = prog.statements[0].conditions
    assert [c.op for c in conds] == ["CONTAINS", "=", ">"]
    assert [c.bool_op for c in conds] == [None, "AND", "OR"]


def test_not_contains_and_not_in():
    prog = parse_fql("INVESTIGATE files WHERE path NOT CONTAINS '/proc' AND name NOT IN ('a', 'b')")
    assert [c.op for c in prog.statements[0].conditions] == ["NOT CONTAINS", "NOT IN"]


def test_parse_error_line_col():
    with pytest.raises(FqlParseError) as ei:
        parse_fql("INVESTIGATE processes WHERE name = 'ok'\nINVESTIGATE bananas")
    assert ei.value.details["line"] == 2
    assert ei.value.code == "FQL_PARSE_ERROR"


def test_parse_error_unexpected_eof():
    with pytest.raises(FqlParseError):
        parse_fql("INVESTIGATE")


def test_empty_query_rejected():
    with pytest.raises(FqlParseError):
        parse_fql("   ")


def test_oversized_query_rejected():
    with pytest.raises(FqlParseError):
        parse_fql("INVESTIGATE processes WHERE name = '" + "a" * 25000 + "'")


@pytest.mark.parametrize(
    "malicious",
    [
        "INVESTIGATE processes; os.system('id')",
        "INVESTIGATE processes WHERE name = $(rm -rf /)",
        "INVESTIGATE processes WHERE name = `id`",
        "INVESTIGATE processes WHERE name = 'x' || SHUTDOWN",
        "INVESTIGATE processes UNION SELECT * FROM users",
    ],
)
def test_injection_attempts_rejected(malicious):
    with pytest.raises(FqlParseError):
        parse_fql(malicious)


def test_collector_params_typed():
    prog = parse_fql("INVESTIGATE network WHERE dst_port = 4444 LIMIT 5")
    params = ast_to_collector_params(prog)
    ctype, p = params[0]
    assert ctype.value == "NETWORK"
    assert p["filters"][0]["value"] == 4444
    assert isinstance(p["filters"][0]["value"], int)
    assert p["limit"] == 5
