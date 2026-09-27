# --- forgex-template
# id: custom-function
# title: Custom Function
# category: Custom
# description: Empty starter with SDK reference comments - write your own forensic logic.
# ---
# ForgeX Forensic Function
# Purpose: <describe your analysis>
#
# SDK cheat-sheet (all APIs operate on REAL case evidence):
#   evidence.processes(name=None, user=None)      -> list[Process]
#   evidence.files(path_contains=None)            -> list[File]
#   evidence.network(dst_port=None, protocol=None)-> list[NetworkConnection]
#   evidence.users()                              -> list[UserAccount]
#   evidence.events(source=None, category=None)   -> list[SystemEvent]
#   evidence.registry(key_contains=None)          -> list[RegistryValue]
#   evidence.browser(kind=None) / evidence.memory()
#   evidence.timeline()                           -> chronological entries
#   evidence.get(id) / evidence.all() / evidence.types()
#   item.is_suspicious(), item.as_dict(), item.data_hash
#   forgex.finding(severity, title, description, evidence=item_or_list, mitre=["T1059.001"])
#   forgex.log(...), forgex.hash.verify(item), forgex.custody(), forgex.verify_chain()
#   forgex.neighbors(item)  -> graph edges touching the item
#
# Allowed imports: forgex, json, re, datetime, collections, math, statistics,
#                  hashlib, itertools, functools, typing, enum, string, operator

import forgex


def analyze(evidence):
    """Your forensic logic here. Return a list of findings."""
    results = []

    # Example: flag every suspicious process
    for proc in evidence.processes():
        if proc.is_suspicious():
            results.append(
                forgex.finding(
                    severity="HIGH",
                    title=f"Suspicious process {proc.name} (PID {proc.pid})",
                    description=f"Command line: {proc.cmdline}",
                    evidence=proc,
                )
            )

    return results
