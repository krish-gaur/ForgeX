# --- forgex-template
# id: hash-verification
# title: Hash Verification
# category: Integrity
# description: Verify SHA-256 integrity of every evidence item and validate the anchor chain (chain of custody).
# ---
# ForgeX Forensic Function
# Purpose: Verify evidence integrity and chain of custody

import forgex


def analyze(evidence):
    """Recompute SHA-256 for each item and verify the tamper-evident anchor chain."""
    items = evidence.all()
    if not items:
        forgex.log("No evidence to verify.")
        return []

    results = []
    bad = [it for it in items if not forgex.hash.verify(it)]
    for it in bad:
        results.append(
            forgex.finding(
                severity="CRITICAL",
                title=f"EVIDENCE TAMPERED: hash mismatch for {it.id}",
                description="Recomputed SHA-256 differs from the hash stored at collection time.",
                evidence=it,
            )
        )

    chain_ok = forgex.verify_chain()
    if not chain_ok:
        results.append(
            forgex.finding(
                severity="CRITICAL",
                title="Anchor chain verification FAILED",
                description="The append-only hash chain binding evidence hashes is broken; treat case integrity as compromised.",
            )
        )
    else:
        forgex.log(f"Anchor chain verified: {len(forgex.custody())} records, integrity OK.")

    forgex.log(f"Verified {len(items)} evidence items; {len(bad)} mismatches.")
    return results
