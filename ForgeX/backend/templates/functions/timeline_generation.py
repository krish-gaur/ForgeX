# --- forgex-template
# id: timeline-generation
# title: Timeline Generation
# category: Timeline
# description: Build a chronological incident narrative from all evidence and highlight the suspicious window.
# ---
# ForgeX Forensic Function
# Purpose: Generate an investigation timeline narrative

import forgex


def analyze(evidence):
    """Summarize the chronological order of suspicious activity."""
    timeline = evidence.timeline()
    if not timeline:
        forgex.log("Timeline is empty - collect evidence first.")
        return []

    suspicious = [e for e in timeline if e.get("severity") in ("HIGH", "CRITICAL", "MEDIUM")]
    if not suspicious:
        forgex.log(f"Timeline has {len(timeline)} entries but no suspicious severities.")
        return []

    first, last = suspicious[0], suspicious[-1]
    results = [
        forgex.finding(
            severity="MEDIUM",
            title=f"Suspicious activity window: {first['timestamp']} → {last['timestamp']}",
            description=(
                f"{len(suspicious)} suspicious entries between first ('{first['label'][:80]}') "
                f"and last ('{last['label'][:80]}'). Review the Timeline tab for full ordering."
            ),
            evidence=[e["evidence_id"] for e in suspicious if e.get("evidence_id")],
        )
    ]
    for entry in suspicious:
        forgex.log(f"{entry['timestamp']}  [{entry['severity']}] {entry['label']}")
    return results
