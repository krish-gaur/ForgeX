# --- forgex-template
# id: file-metadata-analysis
# title: File Metadata Analysis
# category: File Analysis
# description: Review file metadata: executables in world-writable dirs, timestamp anomalies, hash coverage.
# ---
# ForgeX Forensic Function
# Purpose: Analyze file metadata artifacts

import forgex

RISK_DIRS = ("/tmp/", "/var/tmp/", "/dev/shm/", "C:\\Temp\\", "C:\\Users\\Public\\")


def analyze(evidence):
    """Flag executables in temporary locations and files missing integrity hashes."""
    files = evidence.files()
    if not files:
        forgex.log("No file evidence in this case. Run: INVESTIGATE files WHERE path = '/var/log'")
        return []

    results = []
    for f in files:
        path = str(f.path or "")
        if f.is_executable and any(path.startswith(d) or path.lower().startswith(d.lower()) for d in RISK_DIRS):
            results.append(
                forgex.finding(
                    severity="MEDIUM",
                    title=f"Executable in temporary location: {path}",
                    description="Executables staged in temp directories are a common dropper pattern (MITRE T1105).",
                    evidence=f,
                    mitre=["T1105"],
                )
            )
        if not f.hash_sha256:
            forgex.log(f"WARNING: no SHA-256 recorded for {path} (file exceeded hash size cap?)")
    forged = [f for f in files if f.created_at and f.modified_at and f.created_at > f.modified_at]
    for f in forged:
        results.append(
            forgex.finding(
                severity="LOW",
                title=f"Timestamp anomaly (timestomping?): {f.path}",
                description="Creation time later than modification time; possible timestamp manipulation (MITRE T1070.006).",
                evidence=f,
                mitre=["T1070.006"],
            )
        )
    forgex.log(f"Reviewed {len(files)} files; {len(results)} findings.")
    return results
