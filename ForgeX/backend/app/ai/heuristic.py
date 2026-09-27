"""Deterministic forensic correlation engine (offline 'What Happened?').

A rule-based expert system over REAL collected evidence. Every indicator and
stage cites evidence_ids that exist in the case; nothing is fabricated. Used
as the primary engine when no LLM key is configured and as the validation
baseline / fallback when the LLM path fails.
"""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from app.db.models import EvidenceItem
from app.services.timeline_service import parse_ts

FAR_FUTURE = datetime.max.replace(tzinfo=UTC)
FAR_PAST = datetime.min.replace(tzinfo=UTC)

_ENC_RE = re.compile(r"(-enc(odedcommand)?\s+[A-Za-z0-9+/=]{16,}|frombase64string|base64\s+-d)", re.I)
_OFFICE = {"winword", "excel", "outlook", "acrord32", "powerpnt"}
_SHELLS = {"powershell", "pwsh", "cmd", "wscript", "cscript", "mshta", "rundll32", "regsvr32", "bash", "sh", "python", "python3"}
_C2_PORTS = {4444, 1337, 31337}
_LATERAL_PORTS = {445, 3389, 5985, 5986, 22}
_EXFIL_BYTES = 1_000_000
_TMP = ("/tmp/", "/var/tmp/", "/dev/shm/", "c:\\temp\\", "c:\\users\\public\\")

STAGE_ORDER = ["Initial Access", "Execution", "Persistence", "Command and Control", "Lateral Movement", "Exfiltration", "Impact"]


def _ts(item: EvidenceItem):
    d = item.data or {}
    for key in ("timestamp", "started_at", "created_at", "modified_at", "captured_at"):
        ts = parse_ts(d.get(key))
        if ts:
            return ts
    ts = item.collected_at
    if ts is not None and ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return ts


def correlate(evidence: list[EvidenceItem]) -> dict:
    indicators: list[dict] = []
    stages: dict[str, dict] = {}
    mitre: dict[str, dict] = {}

    def add_indicator(sev, text, ids):
        indicators.append({"indicator": text, "severity": sev, "evidence_ids": ids})

    def add_stage(name, desc, ids, tech=None, tech_name=None):
        st = stages.setdefault(name, {"stage": name, "description": desc, "evidence_ids": [], "_first": None})
        st["evidence_ids"] = sorted(set(st["evidence_ids"]) | set(ids))
        ts = min((_ts_by_id(ids, evidence) or []), default=None)
        if ts and (st["_first"] is None or ts < st["_first"]):
            st["_first"] = ts
        if tech:
            m = mitre.setdefault(tech, {"technique_id": tech, "name": tech_name or tech, "evidence_ids": []})
            m["evidence_ids"] = sorted(set(m["evidence_ids"]) | set(ids))

    by_type: dict[str, list[EvidenceItem]] = defaultdict(list)
    for e in evidence:
        by_type[e.evidence_type].append(e)

    events = by_type["SYSTEM_EVENT"] + by_type["LOG_ENTRY"]
    processes = by_type["PROCESS"]
    files = by_type["FILE"]
    conns = by_type["NETWORK_CONNECTION"]
    registry = by_type["REGISTRY"]

    # R1/R2 credential attacks
    fails_by_user: dict[str, list[EvidenceItem]] = defaultdict(list)
    for e in events:
        if (e.data or {}).get("event_type") == "login_failure" and e.data.get("user"):
            fails_by_user[e.data["user"]].append(e)
    for user, fails in fails_by_user.items():
        fails = sorted(fails, key=lambda x: _ts(x) or FAR_FUTURE)
        if len(fails) >= 5:
            window_ok = False
            first, last = _ts(fails[0]), _ts(fails[-1])
            if first and last and (last - first) <= timedelta(minutes=30):
                window_ok = True
            ids = [f.id for f in fails]
            add_indicator("HIGH", f"{len(fails)} failed logins for user '{user}'" + ("" if window_ok else " (wide time window)"), ids)
            add_stage("Credential Access" if "Credential Access" in STAGE_ORDER else "Initial Access", f"Repeated authentication failures against account '{user}' consistent with password guessing.", ids, "T1110", "Brute Force")
            successes = [e for e in events if (e.data or {}).get("event_type") == "login_success" and e.data.get("user") == user]
            for ok in successes:
                prior = [f for f in fails if (_ts(f) or FAR_FUTURE) < (_ts(ok) or FAR_PAST)]
                if len(prior) >= 3:
                    add_indicator("CRITICAL", f"Account '{user}' logged in successfully after {len(prior)} failures", [f.id for f in prior] + [ok.id])
                    add_stage("Initial Access", f"Account '{user}' authenticated successfully immediately after a failure storm — probable compromise of valid credentials.", [f.id for f in prior] + [ok.id], "T1078", "Valid Accounts")

    # R3/R4 process indicators
    for p in processes:
        cmd = (p.data or {}).get("cmdline") or ""
        if _ENC_RE.search(cmd):
            add_indicator("HIGH", f"Encoded/obfuscated command in {p.data.get('name')} (PID {p.data.get('pid')})", [p.id])
            add_stage("Execution", f"Obfuscated command line executed by {p.data.get('name')}.", [p.id], "T1059.001", "PowerShell")
        parent = str((p.data or {}).get("parent_name") or "").lower().split(".")[0]
        name = str((p.data or {}).get("name") or "").lower().split(".")[0]
        if parent in _OFFICE and name in _SHELLS:
            add_indicator("CRITICAL", f"Document reader ({parent}) spawned interpreter {name}", [p.id])
            add_stage("Initial Access", f"Process {name} launched by office application {parent} — consistent with malicious document execution.", [p.id], "T1204.002", "User Execution: Malicious File")

    # R5/R6 dropper files
    exec_files = [f for f in files if (f.data or {}).get("is_executable")]
    for f in exec_files:
        path = str((f.data or {}).get("path") or "").lower()
        if any(path.startswith(t) for t in _TMP):
            add_indicator("MEDIUM", f"Executable staged in temporary location: {f.data.get('path')}", [f.id])
            add_stage("Execution", f"Executable written to a temporary directory ({f.data.get('path')}).", [f.id], "T1105", "Ingress Tool Transfer")
    for f in exec_files:
        fname = str((f.data or {}).get("path") or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1].lower()
        for p in processes:
            if str((p.data or {}).get("name") or "").lower() == fname and (_ts(f) or FAR_FUTURE) <= (_ts(p) or FAR_PAST):
                add_indicator("HIGH", f"Dropper executed: {f.data.get('path')} run as PID {p.data.get('pid')}", [f.id, p.id])
                add_stage("Execution", f"File {f.data.get('path')} was written and subsequently executed as process {p.data.get('name')}.", [f.id, p.id], "T1204.001", "User Execution: Malicious Link")
                break

    # R7/R9 network
    for c in conns:
        d = c.data or {}
        if d.get("dst_port") in _C2_PORTS:
            add_indicator("HIGH", f"Connection to C2-associated port {d.get('dst_port')} ({d.get('dst_ip')})", [c.id])
            add_stage("Command and Control", f"Outbound connection to {d.get('dst_ip')}:{d.get('dst_port')} on a port commonly used by remote access tooling.", [c.id], "T1571", "Non-Standard Port")
        if (d.get("bytes_sent") or 0) > _EXFIL_BYTES:
            add_indicator("HIGH", f"Large outbound transfer ({d.get('bytes_sent')} bytes) to {d.get('dst_ip')}:{d.get('dst_port')}", [c.id])
            add_stage("Exfiltration", f"High-volume outbound transfer to {d.get('dst_ip')} consistent with data exfiltration.", [c.id], "T1048", "Exfiltration Over Alternative Protocol")
        if d.get("dns_query") and re.search(r"(ngrok|burpcollaborator|dnscat|paste)", str(d["dns_query"]), re.I):
            add_indicator("MEDIUM", f"Suspicious DNS lookup {d.get('dns_query')}", [c.id])
            add_stage("Command and Control", f"DNS resolution of attacker-infrastructure domain {d.get('dns_query')}.", [c.id], "T1071.004", "Application Layer Protocol: DNS")
        if d.get("dst_port") in _LATERAL_PORTS and d.get("dst_ip") and not str(d["dst_ip"]).startswith(("127.", "10.", "192.168.", "172.")):
            add_indicator("MEDIUM", f"Remote service connection to external host {d.get('dst_ip')}:{d.get('dst_port')}", [c.id])
            add_stage("Lateral Movement", f"Connection to remote administrative service on {d.get('dst_ip')}.", [c.id], "T1021", "Remote Services")

    # R8 persistence
    for e in events:
        if (e.data or {}).get("event_type") == "persistence":
            add_indicator("HIGH", f"Persistence mechanism: {str(e.data.get('description'))[:100]}", [e.id])
            add_stage("Persistence", str(e.data.get("description"))[:200], [e.id], "T1547.001", "Registry Run Keys / Startup Folder")
    for r in registry:
        if "Run" in str((r.data or {}).get("key")):
            add_indicator("HIGH", f"Autorun registry value: {r.data.get('key')}", [r.id])
            add_stage("Persistence", f"Registry autostart entry {r.data.get('key')} = {r.data.get('value')}", [r.id], "T1547.001", "Registry Run Keys / Startup Folder")

    # narrative
    ordered_stages = sorted(stages.values(), key=lambda s: s["_first"] or FAR_FUTURE)
    for s in ordered_stages:
        s.pop("_first", None)
    if ordered_stages:
        narrative = " → ".join(s["stage"] for s in ordered_stages)
        what = (
            f"Correlated {len(evidence)} evidence items into {len(ordered_stages)} attack stages ({narrative}). "
            + " ".join(f"[{s['stage']}] {s['description']}" for s in ordered_stages[:4])
        )
    else:
        what = f"Analyzed {len(evidence)} evidence items; no attack pattern matched the built-in correlation rules. Review raw evidence and timeline for manual analysis."
    gaps = []
    for t, label in (("PROCESS", "process"), ("FILE", "file"), ("NETWORK_CONNECTION", "network"), ("SYSTEM_EVENT", "event"), ("USER_ACCOUNT", "user")):
        if not by_type[t]:
            gaps.append(f"No {label} evidence collected — the picture may be incomplete.")
    if not by_type["MEMORY_ARTIFACT"]:
        gaps.append("No memory artifacts — in-memory activity cannot be confirmed.")
    coverage = min(len(indicators) / 5.0, 1.0)
    confidence = round(0.35 + 0.55 * coverage, 2)
    return {
        "what_happened": what,
        "attack_stages": ordered_stages,
        "suspicious_indicators": indicators,
        "mitre_techniques": list(mitre.values()),
        "confidence": confidence,
        "gaps": gaps,
    }


def _ts_by_id(ids: list[str], evidence: list[EvidenceItem]):
    m = {e.id: e for e in evidence}
    return [ts for ts in (_ts(m[i]) for i in ids if i in m) if ts]
