# --- forgex-template
# id: process-analysis
# title: Process Analysis
# category: Process Analysis
# description: Hunt encoded commands, suspicious parent-child chains and tooling consistent with intrusion.
# ---
# ForgeX Forensic Function
# Purpose: Analyze process artifacts

import re

import forgex

ENCODED = re.compile(r"(-enc(odedcommand)?\s+[A-Za-z0-9+/=]{16,}|frombase64string|base64\s+-d)", re.I)
LOLBINS = ("powershell", "pwsh", "cmd", "wscript", "cscript", "mshta", "rundll32", "regsvr32", "bash", "sh", "curl", "wget")


def analyze(evidence):
    """Flag encoded-command execution and suspicious process lineage."""
    procs = evidence.processes()
    if not procs:
        forgex.log("No process evidence. Run: INVESTIGATE processes")
        return []

    results = []
    for p in procs:
        cmd = p.cmdline or ""
        if ENCODED.search(cmd):
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Encoded command executed by {p.name} (PID {p.pid})",
                    description="Obfuscated command line consistent with script-based execution (MITRE T1059.001).",
                    evidence=p,
                    mitre=["T1059.001"],
                )
            )
        parent = (p.parent_name or "").lower().split(".")[0]
        name = (p.name or "").lower().split(".")[0]
        if parent in ("winword", "excel", "outlook", "acrord32") and name in LOLBINS:
            results.append(
                forgex.finding(
                    severity="CRITICAL",
                    title=f"Office application spawned {p.name}",
                    description="Document-driven process spawn is a classic initial-access pattern (MITRE T1204.002).",
                    evidence=p,
                    mitre=["T1204.002"],
                )
            )
    forgex.log(f"Reviewed {len(procs)} processes; {len(results)} findings.")
    return results
