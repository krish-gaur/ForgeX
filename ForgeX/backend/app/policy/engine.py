"""Policy evaluation — runs BEFORE any collector; cannot be bypassed."""
from __future__ import annotations

from app.core.errors import RateLimited
from app.core.ratelimit import limiter
from app.db.models import ROLE_RANK, Investigation, Role, User
from app.policy.models import PolicyDecision

COLLECTOR_FOR_TYPE = {
    "PROCESS": "processes",
    "FILE": "files",
    "NETWORK": "network",
    "USER": "users",
    "EVENT": "events",
    "TIMELINE": "timeline",
}


def evaluate(
    user: User,
    investigation: Investigation,
    collector_names: list[str],
    rules: dict,
    check_rate_limit: bool = True,
) -> PolicyDecision:
    decision = PolicyDecision(status="ALLOWED")
    allowed = set(rules.get("allowed_collectors", []))
    restricted: dict = rules.get("restricted_collectors", {}) or {}
    rate = rules.get("rate_limits", {}) or {}

    for name in collector_names:
        entry: dict = {"collector": name, "status": "ALLOWED", "reasons": []}
        if name in restricted:
            spec = restricted[name]
            req_role = spec.get("required_role")
            if req_role and ROLE_RANK[Role(user.role)] < ROLE_RANK[Role(req_role)]:
                entry["status"] = "DENIED"
                entry["reasons"].append(f"Collector '{name}' requires role {req_role}; you have {user.role}.")
                entry["required_approval_from"] = req_role
            req_status = spec.get("requires_case_status")
            if req_status and investigation.status != req_status:
                entry["status"] = "DENIED"
                entry["reasons"].append(f"Collector '{name}' requires case status {req_status}; case is {investigation.status}.")
        elif name not in allowed:
            entry["status"] = "DENIED"
            entry["reasons"].append(f"Collector '{name}' is not permitted by the active policy.")
        decision.per_collector[name] = entry
        if entry["status"] == "DENIED":
            decision.status = "DENIED"
            decision.reasons.extend(entry["reasons"])

    if check_rate_limit and decision.status == "ALLOWED":
        limit = int(rate.get("max_executions_per_hour_per_investigator", 20))
        try:
            limiter.check("fql_exec", user.id, limit, 3600)
        except RateLimited as e:
            decision.status = "DENIED"
            decision.reasons.append(str(e.message))
            decision.per_collector["_rate_limit"] = {"status": "DENIED", "reasons": [e.message]}
    return decision


def field_restrictions_for(collector_name: str, rules: dict) -> dict:
    return (rules.get("field_restrictions", {}) or {}).get(collector_name, {}) or {}
