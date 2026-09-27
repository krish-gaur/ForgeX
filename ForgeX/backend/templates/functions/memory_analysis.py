# --- forgex-template
# id: memory-analysis
# title: Memory Analysis
# category: Memory Analysis
# description: Review memory-image artifacts (strings/volatility exports) for injected code and credentials material.
# ---
# ForgeX Forensic Function
# Purpose: Analyze memory artifacts

import forgex

RISK_MARKERS = ("inject", "mimikatz", "lsass", "hook", "shellcode", "unbacked")


def analyze(evidence):
    """Inspect memory artifacts for injection and credential-access indicators."""
    artifacts = evidence.memory()
    if not artifacts:
        forgex.log("No memory artifacts in this case.")
        forgex.log("Add a memory image export (volatility/json) to the dataset to enable this analysis.")
        return []

    results = []
    for a in artifacts:
        desc = str(a.description or "").lower()
        hits = [m for m in RISK_MARKERS if m in desc]
        if hits:
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Memory indicator: {', '.join(hits)}",
                    description=f"Memory artifact '{a.kind}' matches injection/credential-access markers (MITRE T1055/T1003).",
                    evidence=a,
                    mitre=["T1055", "T1003.001"],
                )
            )
    forgex.log(f"Reviewed {len(artifacts)} memory artifacts; {len(results)} findings.")
    return results
