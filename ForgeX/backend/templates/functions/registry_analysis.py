# --- forgex-template
# id: registry-analysis
# title: Registry Analysis
# category: Registry Analysis
# description: Inspect registry artifacts for autorun/persistence keys and suspicious value writes.
# ---
# ForgeX Forensic Function
# Purpose: Analyze registry artifacts for persistence and misconfiguration

import forgex

PERSISTENCE_KEYS = ("Run", "RunOnce", "Winlogon", "Services", "Scheduled Tasks")


def analyze(evidence):
    """Inspect registry artifacts; flag autostart extensibility points (ASEPs)."""
    try:
        values = evidence.registry()
    except forgex.EvidenceUnavailableError as exc:
        forgex.log(f"Registry artifacts unavailable: {exc}")
        forgex.log("Collect from a Windows target or a dataset containing registry exports.")
        return []

    results = []
    for val in values:
        key = str(val.key or "")
        if any(seg in key for seg in PERSISTENCE_KEYS):
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Autorun entry: {key}",
                    description=f"Value '{val.value}' configured under an autostart extensibility point (MITRE T1547.001).",
                    evidence=val,
                    mitre=["T1547.001"],
                )
            )
        elif val.is_suspicious():
            results.append(
                forgex.finding(
                    severity="MEDIUM",
                    title=f"Suspicious registry value under {key}",
                    description="Registry value matches ForgeX suspicion heuristics.",
                    evidence=val,
                )
            )
    forgex.log(f"Reviewed {len(values)} registry values; {len(results)} findings.")
    return results
