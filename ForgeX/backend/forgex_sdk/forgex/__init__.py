"""ForgeX Forensic SDK — the programming surface for ForgeX forensic functions.

Functions run inside the ForgeX sandbox and operate on a read-only snapshot of
the case evidence. Every API here works against real collected evidence; nothing
is hardcoded or simulated.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

__version__ = "1.0.0"


class ForgeXError(Exception):
    """Base error for all ForgeX SDK failures."""


class EvidenceUnavailableError(ForgeXError):
    """Requested evidence source is not present in this case."""


class UnsupportedArtifactError(ForgeXError):
    """Artifact type not supported on this target/platform."""


# --------------------------------------------------------------------------- items
class _Item:
    _type = "GENERIC"

    def __init__(self, raw: dict, runtime: _Runtime):
        self._raw = raw
        self._rt = runtime
        self.data = raw.get("data", {})
        self.id = raw.get("id")
        self.collected_at = raw.get("collected_at")
        self.data_hash = raw.get("data_hash")
        self.provenance = raw.get("provenance")

    def __getattr__(self, name):
        if name.startswith("_") or name in ("data", "id", "collected_at", "data_hash", "provenance"):
            raise AttributeError(name)
        # Sparse forensic data is normal: missing fields read as None instead of crashing analyses.
        return self.data.get(name)

    def as_dict(self) -> dict:
        return dict(self.data)

    def is_suspicious(self) -> bool:
        return _suspicious(self._type, self.data)

    def severity(self) -> str:
        return "HIGH" if self.is_suspicious() else "INFO"

    def __repr__(self) -> str:
        return f"<{self._type} {self.data.get('name') or self.data.get('path') or self.id}>"


class Process(_Item):
    _type = "PROCESS"


class File(_Item):
    _type = "FILE"


class NetworkConnection(_Item):
    _type = "NETWORK_CONNECTION"


class UserAccount(_Item):
    _type = "USER_ACCOUNT"


class SystemEvent(_Item):
    _type = "SYSTEM_EVENT"


class RegistryValue(_Item):
    _type = "REGISTRY"


class BrowserArtifact(_Item):
    _type = "BROWSER_ARTIFACT"


class MemoryArtifact(_Item):
    _type = "MEMORY_ARTIFACT"


_ITEM_CLASSES = {
    "PROCESS": Process,
    "FILE": File,
    "NETWORK_CONNECTION": NetworkConnection,
    "USER_ACCOUNT": UserAccount,
    "SYSTEM_EVENT": SystemEvent,
    "LOG_ENTRY": SystemEvent,
    "REGISTRY": RegistryValue,
    "BROWSER_ARTIFACT": BrowserArtifact,
    "MEMORY_ARTIFACT": MemoryArtifact,
}

_ENC_RE = ("-enc", "encodedcommand", "base64", "frombase64string")
_EXFIL_RE = ("curl ", "wget ", "nc ", "netcat", "scp ", "ftp ")


def _suspicious(etype: str, d: dict) -> bool:
    if etype == "PROCESS":
        cmd = (d.get("cmdline") or "").lower()
        return any(tok in cmd for tok in _ENC_RE) or (any(t in cmd for t in _EXFIL_RE) and "." in cmd)
    if etype == "SYSTEM_EVENT":
        return d.get("event_type") in ("persistence", "privilege_use") or d.get("event_type") == "login_failure"
    if etype == "NETWORK_CONNECTION":
        return (d.get("bytes_sent") or 0) > 1_000_000 or d.get("dst_port") in (4444, 1337, 31337)
    if etype == "FILE":
        p = d.get("path") or ""
        return bool(d.get("is_executable")) and p.startswith(("/tmp", "/var/tmp", "/dev/shm", "C:\\Temp"))
    if etype == "REGISTRY":
        return "Run" in str(d.get("key"))
    return False


# --------------------------------------------------------------------------- evidence view
class Evidence:
    """Read-only view over the case evidence snapshot."""

    def __init__(self, runtime: _Runtime):
        self._rt = runtime

    def _items(self, etype: str) -> list[_Item]:
        cls = _ITEM_CLASSES.get(etype, _Item)
        return [cls(raw, self._rt) for raw in self._rt.snapshot.get("evidence", []) if raw.get("evidence_type") == etype]

    def all(self) -> list[_Item]:
        return [ _ITEM_CLASSES.get(raw.get("evidence_type"), _Item)(raw, self._rt) for raw in self._rt.snapshot.get("evidence", []) ]

    def get(self, evidence_id: str):
        for raw in self._rt.snapshot.get("evidence", []):
            if raw.get("id") == evidence_id:
                return _ITEM_CLASSES.get(raw.get("evidence_type"), _Item)(raw, self._rt)
        raise EvidenceUnavailableError(f"No evidence item with id {evidence_id} in this case.")

    def processes(self, name: str | None = None, user: str | None = None) -> list[Process]:
        out = self._items("PROCESS")
        if name:
            out = [p for p in out if name.lower() in (p.data.get("name") or "").lower()]
        if user:
            out = [p for p in out if (p.data.get("user") or "").lower() == user.lower()]
        return out

    def files(self, path_contains: str | None = None, executable_only: bool = False) -> list[File]:
        out = self._items("FILE")
        if path_contains:
            out = [f for f in out if path_contains.lower() in (f.data.get("path") or "").lower()]
        if executable_only:
            out = [f for f in out if f.data.get("is_executable")]
        return out

    def network(self, dst_port: int | None = None, protocol: str | None = None) -> list[NetworkConnection]:
        out = self._items("NETWORK_CONNECTION")
        if dst_port is not None:
            out = [n for n in out if n.data.get("dst_port") == dst_port]
        if protocol:
            out = [n for n in out if (n.data.get("protocol") or "").upper() == protocol.upper()]
        return out

    def users(self) -> list[UserAccount]:
        return self._items("USER_ACCOUNT")

    def events(self, source: str | None = None, category: str | None = None) -> list[SystemEvent]:
        out = self._items("SYSTEM_EVENT")
        if source:
            src = source.lower()
            matched = [e for e in out if src in str(e.data.get("source", "")).lower()]
            if not matched and src in ("windows", "eventlog"):
                raise UnsupportedArtifactError("No Windows EventLog artifacts in this case. Collect from a Windows target or dataset containing .evtx exports.")
            out = matched
        if category:
            cat = category.lower()
            out = [e for e in out if cat in str(e.data.get("event_type", "")).lower() or cat in str(e.data.get("description", "")).lower()]
        return out

    def registry(self, key_contains: str | None = None) -> list[RegistryValue]:
        out = self._items("REGISTRY")
        if not out and key_contains is None:
            raise EvidenceUnavailableError("No registry artifacts collected in this case.")
        if key_contains:
            out = [r for r in out if key_contains.lower() in str(r.data.get("key", "")).lower()]
        return out

    def browser(self, kind: str | None = None) -> list[BrowserArtifact]:
        out = self._items("BROWSER_ARTIFACT")
        if kind:
            out = [b for b in out if (b.data.get("kind") or "").lower() == kind.lower()]
        return out

    def memory(self) -> list[MemoryArtifact]:
        return self._items("MEMORY_ARTIFACT")

    def timeline(self) -> list[dict]:
        return sorted(self._rt.snapshot.get("timeline", []), key=lambda e: e.get("timestamp") or "")

    def types(self) -> dict:
        counts: dict = {}
        for raw in self._rt.snapshot.get("evidence", []):
            counts[raw.get("evidence_type")] = counts.get(raw.get("evidence_type"), 0) + 1
        return counts


# --------------------------------------------------------------------------- runtime
class _Runtime:
    def __init__(self, snapshot: dict):
        self.snapshot = snapshot
        self.findings: list[dict] = []
        self.console: list[str] = []

    # -- public SDK surface
    def load_evidence(self, case: str | None = None) -> Evidence:
        if case and case not in (self.snapshot.get("investigation", {}).get("name"), self.snapshot.get("investigation", {}).get("id")):
            raise EvidenceUnavailableError(f"Case '{case}' is not the case bound to this execution.")
        return Evidence(self)

    def finding(self, severity: str, title: str, description: str = "", evidence=None, mitre: list | None = None) -> dict:
        sev = str(severity).upper()
        if sev not in ("INFO", "LOW", "MEDIUM", "HIGH", "CRITICAL"):
            raise ForgeXError(f"Invalid severity '{severity}'. Use INFO, LOW, MEDIUM, HIGH or CRITICAL.")
        ids = []
        if evidence is not None:
            items = evidence if isinstance(evidence, (list, tuple)) else [evidence]
            for it in items:
                ids.append(it.id if isinstance(it, _Item) else str(it))
        rec = {"severity": sev, "title": title, "description": description, "evidence_ids": ids, "mitre_techniques": mitre or []}
        self.findings.append(rec)
        return rec

    def log(self, *args) -> None:
        self.console.append(" ".join(str(a) for a in args))

    def neighbors(self, item) -> list[dict]:
        nid = item if isinstance(item, str) else _node_key(item)
        return [e for e in self.snapshot.get("graph", {}).get("edges", []) if e.get("source") == nid or e.get("target") == nid]

    def custody(self) -> list[dict]:
        return self.snapshot.get("custody", [])

    def verify_chain(self) -> bool:
        chain = self.custody()
        prev = "0" * 64
        for rec in chain:
            expect = hashlib.sha256(f"{prev}|{rec['evidence_id']}|{rec['data_hash']}|{rec['created_at']}".encode()).hexdigest()
            if expect != rec["record_hash"]:
                return False
            prev = rec["record_hash"]
        return True

    @property
    def meta(self) -> dict:
        return self.snapshot.get("investigation", {})


def _node_key(item: _Item) -> str:
    d = item.data
    t = item._type
    if t == "PROCESS":
        return f"process:{d.get('pid')}:{d.get('name')}"[:80]
    if t == "FILE":
        return f"file:{d.get('path')}"[:80]
    if t == "NETWORK_CONNECTION":
        return f"network:{d.get('src_ip')}:{d.get('src_port')}->{d.get('dst_ip')}:{d.get('dst_port')}:{d.get('protocol')}"[:80]
    if t in ("SYSTEM_EVENT", "LOG_ENTRY"):
        return f"event:{d.get('event_id') or (item.data_hash or '')[:12]}"[:80]
    if t == "USER_ACCOUNT":
        return f"user:{d.get('username')}"[:80]
    return str(item.id)


class _Hash:
    @staticmethod
    def sha256_text(text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    @staticmethod
    def sha256_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def canonical(item: _Item) -> str:
        return hashlib.sha256(json.dumps(item.data, sort_keys=True, default=str).encode("utf-8")).hexdigest()

    @staticmethod
    def verify(item: _Item) -> bool:
        """Recompute the item's SHA-256 and compare with the hash stored at collection time."""
        return _Hash.canonical(item) == item.data_hash


class _Timeline:
    def __init__(self, rt: _Runtime):
        self._rt = rt

    def of(self, items) -> list[dict]:
        ids = {it.id for it in items}
        return [e for e in self._rt.snapshot.get("timeline", []) if e.get("evidence_id") in ids]

    def between(self, start_iso: str, end_iso: str) -> list[dict]:
        s = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
        e = datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
        out = []
        for entry in self._rt.snapshot.get("timeline", []):
            ts = entry.get("timestamp")
            if not ts:
                continue
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if s <= dt <= e:
                out.append(entry)
        return sorted(out, key=lambda x: x["timestamp"])


_rt: _Runtime | None = None


def _bind(snapshot: dict) -> _Runtime:
    global _rt
    _rt = _Runtime(snapshot)
    return _rt


def _current() -> _Runtime:
    if _rt is None:
        raise ForgeXError("ForgeX runtime is not bound. Functions must run inside the ForgeX execution engine.")
    return _rt


# Module-level API (import forgex; forgex.load_evidence() ...)
def load_evidence(case: str | None = None) -> Evidence:
    return _current().load_evidence(case)


def finding(severity: str, title: str, description: str = "", evidence=None, mitre: list | None = None) -> dict:
    return _current().finding(severity, title, description, evidence, mitre)


def log(*args) -> None:
    _current().log(*args)


def neighbors(item) -> list[dict]:
    return _current().neighbors(item)


def custody() -> list[dict]:
    return _current().custody()


def verify_chain() -> bool:
    return _current().verify_chain()


meta = property(lambda self: _current().meta)  # type: ignore[assignment]


def get_meta() -> dict:
    return _current().meta


hash = _Hash()
timeline = _Timeline(_current()) if _rt else None


def _late_timeline() -> _Timeline:
    return _Timeline(_current())


class _ModuleProxy:
    """Provides forgex.timeline bound at call time."""

    def __getattr__(self, name):
        return getattr(_late_timeline(), name)


timeline = _ModuleProxy()  # type: ignore[assignment]


class _MetaProxy:
    def __getattr__(self, name):
        return _current().meta[name]

    def __repr__(self):
        return repr(_current().meta)


meta = _MetaProxy()  # type: ignore[assignment]

__all__ = [
    "ForgeXError",
    "EvidenceUnavailableError",
    "UnsupportedArtifactError",
    "Evidence",
    "Process",
    "File",
    "NetworkConnection",
    "UserAccount",
    "SystemEvent",
    "RegistryValue",
    "BrowserArtifact",
    "MemoryArtifact",
    "load_evidence",
    "finding",
    "log",
    "neighbors",
    "custody",
    "verify_chain",
    "hash",
    "timeline",
    "meta",
    "get_meta",
]
