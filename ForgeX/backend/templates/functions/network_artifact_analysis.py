# --- forgex-template
# id: network-artifact-analysis
# title: Network Artifact Analysis
# category: Network Analysis
# description: Analyze connections/PCAP-derived artifacts for C2 ports, large outbound transfers and DNS anomalies.
# ---
# ForgeX Forensic Function
# Purpose: Analyze network artifacts (live sockets, PCAP, Zeek logs)

import forgex

C2_PORTS = (4444, 1337, 31337, 8443, 53)
EXFIL_BYTES = 1_000_000


def analyze(evidence):
    """Detect suspicious outbound connections and large transfers."""
    conns = evidence.network()
    if not conns:
        forgex.log("No network evidence. Run: INVESTIGATE network (requires LEAD_INVESTIGATOR approval).")
        return []

    results = []
    for c in conns:
        if c.dst_port in C2_PORTS and c.dst_port != 53:
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Connection to uncommon port {c.dst_port} ({c.dst_ip})",
                    description="Destination port is associated with remote access tooling (MITRE T1090/T1571).",
                    evidence=c,
                    mitre=["T1571"],
                )
            )
        if (c.bytes_sent or 0) > EXFIL_BYTES:
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Large outbound transfer: {c.bytes_sent} bytes to {c.dst_ip}:{c.dst_port}",
                    description="Volume is consistent with data exfiltration (MITRE T1048).",
                    evidence=c,
                    mitre=["T1048"],
                )
            )
        if c.dns_query and any(tok in str(c.dns_query) for tok in ("paste", "ngrok", "burpcollaborator", "dnscat")):
            results.append(
                forgex.finding(
                    severity="MEDIUM",
                    title=f"Suspicious DNS lookup: {c.dns_query}",
                    description="Lookup matches known attacker-infrastructure naming (MITRE T1071.004).",
                    evidence=c,
                    mitre=["T1071.004"],
                )
            )
    forgex.log(f"Reviewed {len(conns)} connections; {len(results)} findings.")
    return results
