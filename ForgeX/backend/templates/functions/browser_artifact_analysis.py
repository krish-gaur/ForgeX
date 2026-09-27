# --- forgex-template
# id: browser-artifact-analysis
# title: Browser Artifact Analysis
# category: Browser Analysis
# description: Review browser history/downloads for phishing origins, malware downloads and exfil endpoints.
# ---
# ForgeX Forensic Function
# Purpose: Analyze browser artifacts (history, downloads)

import forgex

RISK_TLD = (".zip", ".top", ".click", ".loan", ".work")
EXEC_EXT = (".exe", ".dll", ".scr", ".hta", ".js", ".vbs", ".iso", ".img")


def analyze(evidence):
    """Correlate browser activity with intrusion patterns."""
    items = evidence.browser()
    if not items:
        forgex.log("No browser artifacts in this case.")
        return []

    results = []
    for b in items:
        url = str(b.url or "").lower()
        if b.kind == "download" and url.endswith(EXEC_EXT):
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Executable downloaded: {url[:120]}",
                    description="Browser download of an executable payload (MITRE T1105).",
                    evidence=b,
                    mitre=["T1105"],
                )
            )
        if any(url.endswith(t) for t in RISK_TLD):
            results.append(
                forgex.finding(
                    severity="MEDIUM",
                    title=f"High-risk domain visited: {url[:120]}",
                    description="Domain uses a TLD statistically associated with phishing campaigns (MITRE T1566).",
                    evidence=b,
                    mitre=["T1566.001"],
                )
            )
    forgex.log(f"Reviewed {len(items)} browser artifacts; {len(results)} findings.")
    return results
