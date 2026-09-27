"""Policy dataclasses + the shipped default policy (architecture §08 YAML format)."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_POLICY_NAME = "default-investigation-policy"

DEFAULT_POLICY_RULES: dict[str, Any] = {
    "allowed_collectors": ["processes", "files", "users", "events", "timeline"],
    "restricted_collectors": {
        "network": {
            "required_role": "LEAD_INVESTIGATOR",
            "requires_case_status": "ACTIVE",
            "max_capture_duration_sec": 300,
            "log_mandatory": True,
        },
    },
    "field_restrictions": {
        "files": {
            "excluded_paths": ["/proc", "/sys", "/dev", "C:\\Windows\\System32"],
            "max_depth": 8,
            "max_file_bytes": 52_428_800,
        },
        "events": {"max_items": 5000},
    },
    "rate_limits": {
        "max_executions_per_hour_per_investigator": 20,
        "max_concurrent_jobs": 3,
    },
}

DEFAULT_POLICY_YAML = """
name: default-investigation-policy
description: Shipped ForgeX default policy. Network collection requires lead approval.
allowed_collectors:
  - processes
  - files
  - users
  - events
  - timeline
restricted_collectors:
  network:
    required_role: LEAD_INVESTIGATOR
    requires_case_status: ACTIVE
    max_capture_duration_sec: 300
    log_mandatory: true
field_restrictions:
  files:
    excluded_paths:
      - /proc
      - /sys
      - /dev
      - C:\\Windows\\System32
    max_depth: 8
    max_file_bytes: 52428800
  events:
    max_items: 5000
rate_limits:
  max_executions_per_hour_per_investigator: 20
  max_concurrent_jobs: 3
"""


@dataclass
class PolicyDecision:
    status: str  # ALLOWED | DENIED
    reasons: list[str] = field(default_factory=list)
    per_collector: dict[str, dict] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"status": self.status, "reasons": self.reasons, "collectors": self.per_collector}
