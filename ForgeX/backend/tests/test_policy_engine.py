"""Unit tests: policy engine role/collector matrix + rate limits (architecture §12 CRITICAL)."""
from __future__ import annotations

import pytest

from app.core.ratelimit import limiter
from app.db.models import Investigation, User
from app.policy import engine as policy_engine
from app.policy.models import DEFAULT_POLICY_RULES


def _user(role):
    return User(id=f"u-{role}", username=role, email=f"{role}@x", password_hash="x", role=role)


def _inv(status="ACTIVE"):
    return Investigation(id="inv-1", name="t", target_host="10.0.0.5", status=status, created_by="u-x")


MATRIX = [
    ("INVESTIGATOR", "processes", "ALLOWED"),
    ("INVESTIGATOR", "files", "ALLOWED"),
    ("INVESTIGATOR", "users", "ALLOWED"),
    ("INVESTIGATOR", "events", "ALLOWED"),
    ("INVESTIGATOR", "timeline", "ALLOWED"),
    ("INVESTIGATOR", "network", "DENIED"),
    ("LEAD_INVESTIGATOR", "network", "ALLOWED"),
    ("ADMIN", "network", "ALLOWED"),
    ("AUDITOR", "processes", "ALLOWED"),  # policy is role-independent for collectors; endpoints gate auditor separately
]


@pytest.mark.parametrize("role,collector,expected", MATRIX)
def test_role_collector_matrix(role, collector, expected):
    d = policy_engine.evaluate(_user(role), _inv(), [collector], DEFAULT_POLICY_RULES, check_rate_limit=False)
    assert d.status == expected


def test_case_status_restriction():
    d = policy_engine.evaluate(_user("LEAD_INVESTIGATOR"), _inv("COMPLETED"), ["network"], DEFAULT_POLICY_RULES, check_rate_limit=False)
    assert d.status == "DENIED"
    assert any("ACTIVE" in r for r in d.reasons)


def test_unknown_collector_denied():
    rules = dict(DEFAULT_POLICY_RULES)
    d = policy_engine.evaluate(_user("ADMIN"), _inv(), ["memory"], rules, check_rate_limit=False)
    assert d.status == "DENIED"


def test_rate_limit_denies_after_limit():
    limiter.reset()
    user = _user("INVESTIGATOR")
    limit = DEFAULT_POLICY_RULES["rate_limits"]["max_executions_per_hour_per_investigator"]
    for _ in range(limit):
        d = policy_engine.evaluate(user, _inv(), ["processes"], DEFAULT_POLICY_RULES, check_rate_limit=True)
        assert d.status == "ALLOWED"
    d = policy_engine.evaluate(user, _inv(), ["processes"], DEFAULT_POLICY_RULES, check_rate_limit=True)
    assert d.status == "DENIED"
    limiter.reset()


def test_field_restrictions_lookup():
    fr = policy_engine.field_restrictions_for("files", DEFAULT_POLICY_RULES)
    assert "/proc" in fr["excluded_paths"]
    assert fr["max_depth"] == 8
