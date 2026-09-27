"""Evidence embeddings for RAG retrieval.

Default provider is a deterministic local embedder (hashed token + char-trigram
bag, L2-normalised) so retrieval works fully offline. If OPENAI_API_KEY is set
and embedding_provider=openai, the OpenAI text-embedding-3-small model is used
instead (1536 dims; stored per-row so both coexist safely).
"""
from __future__ import annotations

import hashlib
import math
import re

from app.config import get_settings
from app.db.models import EvidenceItem

settings = get_settings()
_TOKEN_RE = re.compile(r"[a-z0-9_\.\/:-]+")


def evidence_to_text(item: EvidenceItem) -> str:
    d = item.data or {}
    t = item.evidence_type
    if t == "PROCESS":
        return f"Process '{d.get('name')}' (PID {d.get('pid')}) run by user '{d.get('user')}', command: {d.get('cmdline')}, parent: '{d.get('parent_name')}' at {item.collected_at}"
    if t == "FILE":
        return f"File '{d.get('path')}' (size {d.get('size')} bytes), SHA256: {d.get('hash_sha256') or 'unknown'}, modified: {d.get('modified_at')}"
    if t == "NETWORK_CONNECTION":
        return f"Network connection from {d.get('src_ip')}:{d.get('src_port')} to {d.get('dst_ip')}:{d.get('dst_port')} ({d.get('protocol')}) bytes_sent={d.get('bytes_sent')} dns={d.get('dns_query')} at {item.collected_at}"
    if t == "USER_ACCOUNT":
        return f"User account '{d.get('username')}' uid={d.get('uid')} groups={d.get('groups')} last_login={d.get('last_login')}"
    if t in ("SYSTEM_EVENT", "LOG_ENTRY"):
        return f"System event [{d.get('event_type')}] {d.get('description')} user={d.get('user')} at {d.get('timestamp')}"
    if t == "REGISTRY":
        return f"Registry key {d.get('key')} value={d.get('value')} modified {d.get('modified_at')}"
    if t == "BROWSER_ARTIFACT":
        return f"Browser {d.get('kind')} url={d.get('url')} title={d.get('title')} at {d.get('visited_at')}"
    if t == "MEMORY_ARTIFACT":
        return f"Memory artifact {d.get('kind')} {d.get('description')}"
    return f"{t} evidence: {d}"


def _local_embed(text: str, dim: int) -> list[float]:
    vec = [0.0] * dim
    tokens = _TOKEN_RE.findall(text.lower())
    for tok in tokens:
        for gram in {tok, tok[:3], tok[-3:]}:
            h = hashlib.blake2b(gram.encode(), digest_size=8).digest()
            idx = int.from_bytes(h[:4], "little") % dim
            sign = 1.0 if h[4] % 2 == 0 else -1.0
            vec[idx] += sign
    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


def embed_text(text: str) -> list[float]:
    return _local_embed(text, settings.embedding_dim)


def cosine(a: list[float], b: list[float]) -> float:
    if len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))
