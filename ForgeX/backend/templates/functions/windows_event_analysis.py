# --- forgex-template
# id: windows-event-analysis
# title: Windows Event Analysis
# category: Event Analysis
# description: Analyze Windows Event Log artifacts (or syslog/journal equivalents) for authentication attacks, privilege use and persistence events.
# ---
# ForgeX Forensic Function
# Purpose: Analyze Windows Event Log artifacts
#
# Example output (findings):
#   HIGH  "Brute-force pattern: 12 failed logins for user 'svc_backup'"
#
# The `evidence` argument is a forgex.Evidence view over the case snapshot.

from collections import Counter

import forgex


def analyze(evidence):
    """
    Analyze Windows Event Log artifacts.

    Input:
        evidence - forensic evidence source (forgex.Evidence)

    Output:
        Structured forensic findings via forgex.finding(...)
    """
    try:
        events = evidence.events(source="windows")
    except forgex.UnsupportedArtifactError:
        # No Windows channel in this case: fall back to whatever event source exists.
        events = evidence.events()
        forgex.log("No Windows EventLog channel present; analyzing available event sources instead.")

    if not events:
        forgex.log("No event artifacts in this case. Run: INVESTIGATE events")
        return []

    failures = [e for e in events if e.event_type == "login_failure"]
    by_user = Counter(e.user for e in failures if e.user)

    results = []
    for user, count in by_user.items():
        if count >= 5:
            related = [e for e in failures if e.user == user]
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Brute-force pattern: {count} failed logins for user '{user}'",
                    description="Repeated authentication failures are consistent with a password guessing attack (MITRE T1110).",
                    evidence=related,
                    mitre=["T1110"],
                )
            )

    # Failure storm followed by success = likely compromised account
    for user in by_user:
        fails = sorted([e for e in failures if e.user == user], key=lambda e: e.timestamp or "")
        successes = [e for e in events if e.event_type == "login_success" and e.user == user]
        for ok in successes:
            prior = [f for f in fails if (f.timestamp or "") < (ok.timestamp or "")]
            if len(prior) >= 5:
                results.append(
                    forgex.finding(
                        severity="CRITICAL",
                        title=f"Account '{user}' succeeded after {len(prior)} failed logins",
                        description="Successful authentication immediately following a failure storm indicates probable account compromise (MITRE T1078).",
                        evidence=prior + [ok],
                        mitre=["T1078"],
                    )
                )

    for e in events:
        if e.event_type == "persistence":
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Persistence event: {e.description[:80]}",
                    description="Autostart/persistence modification observed (MITRE T1547).",
                    evidence=e,
                    mitre=["T1547.001"],
                )
            )

    forgex.log(f"Analyzed {len(events)} events; produced {len(results)} findings.")
    return results
