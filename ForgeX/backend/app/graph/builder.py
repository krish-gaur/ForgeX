"""Deterministic evidence-graph construction (USER→PROCESS→FILE→NETWORK→EVENT).

Nodes/edges are derived only from fields present in real evidence payloads
(or explicit relation hints emitted by collectors, key `_links`).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import EvidenceItem, GraphEdge, GraphNode

_NODE_TYPES = {"user", "process", "file", "network", "event"}


def _node_id(kind: str, key: str) -> str:
    return f"{kind}:{key}"[:80]


def _nodes_and_edges_for(item: EvidenceItem) -> tuple[list[tuple[str, str, dict]], list[tuple[str, str, str]]]:
    d = item.data or {}
    t = item.evidence_type
    nodes: list[tuple[str, str, dict]] = []
    edges: list[tuple[str, str, str]] = []  # (src, dst, rel)

    def add(kind: str, key: str, label: str, props: dict | None = None) -> str:
        nid = _node_id(kind, key)
        nodes.append((nid, kind, {"label": label, **(props or {})}))
        return nid

    fallback = f"ev-{item.id[:16]}"

    if t == "PROCESS":
        pid = d.get("pid")
        name = d.get("name") or "?"
        key = f"{pid}:{name}" if pid is not None and d.get("name") else fallback
        nid = add("process", key, name, {"pid": pid, "cmdline": d.get("cmdline"), "user": d.get("user")})
        if d.get("user"):
            uid = add("user", str(d["user"]), str(d["user"]))
            edges.append((uid, nid, "LAUNCHED"))
        if d.get("parent_pid") not in (None, 0) and d.get("parent_name"):
            pnid = _node_id("process", f"{d['parent_pid']}:{d['parent_name']}")
            edges.append((pnid, nid, "SPAWNED"))
    elif t == "FILE":
        path = d.get("path") or fallback
        nid = add("file", path, path.rsplit("/", 1)[-1][:60], {"path": path, "size": d.get("size"), "hash_sha256": d.get("hash_sha256")})
        for hint in d.get("_links", []) or []:
            if hint.get("rel") in ("ACCESSED_FILE", "LOADED_BY") and hint.get("process"):
                p = hint["process"]
                pnid = _node_id("process", f"{p.get('pid')}:{p.get('name')}")
                nodes.append((pnid, "process", {"label": p.get("name"), "pid": p.get("pid")}))
                edges.append((pnid, nid, hint["rel"]))
    elif t == "NETWORK_CONNECTION":
        if d.get("src_ip") is None and d.get("dst_ip") is None:
            key = fallback
        else:
            key = f"{d.get('src_ip')}:{d.get('src_port')}->{d.get('dst_ip')}:{d.get('dst_port')}:{d.get('protocol')}"
        nid = add("network", key, f"{d.get('dst_ip')}:{d.get('dst_port')}", {k: d.get(k) for k in ("src_ip", "src_port", "dst_ip", "dst_port", "protocol", "dns_query", "bytes_sent")})
        if d.get("pid") or d.get("process_name"):
            pnid = _node_id("process", f"{d.get('pid')}:{d.get('process_name')}")
            nodes.append((pnid, "process", {"label": d.get("process_name"), "pid": d.get("pid")}))
            edges.append((pnid, nid, "MADE_CONNECTION"))
        if d.get("dns_query"):
            eid = _node_id("event", f"dns:{d['dns_query']}")
            nodes.append((eid, "event", {"label": f"DNS {d['dns_query']}"}))
            edges.append((nid, eid, "RESOLVED_FROM"))
    elif t in ("SYSTEM_EVENT", "LOG_ENTRY"):
        key = str(d.get("event_id") or item.data_hash[:12])
        nid = add("event", key, (d.get("event_type") or "event")[:60], {"description": d.get("description"), "timestamp": d.get("timestamp")})
        if d.get("user"):
            uid = add("user", str(d["user"]), str(d["user"]))
            edges.append((uid, nid, "TRIGGERED_EVENT"))
        if d.get("pid") and d.get("process"):
            pnid = _node_id("process", f"{d['pid']}:{d['process']}")
            nodes.append((pnid, "process", {"label": d.get("process")}))
            edges.append((pnid, nid, "TRIGGERED_EVENT"))
    elif t == "USER_ACCOUNT":
        uname = d.get("username") or fallback
        add("user", str(uname), str(uname), {"uid": d.get("uid"), "groups": d.get("groups"), "last_login": d.get("last_login")})
    elif t == "REGISTRY":
        nid = add("event", f"reg:{d.get('key') or fallback}", f"REG {str(d.get('key'))[:40]}", {"key": d.get("key"), "value": d.get("value")})
        for hint in d.get("_links", []) or []:
            if hint.get("process"):
                p = hint["process"]
                pnid = _node_id("process", f"{p.get('pid')}:{p.get('name')}")
                nodes.append((pnid, "process", {"label": p.get("name")}))
                edges.append((pnid, nid, "TRIGGERED_EVENT"))
    for src, dst, rel in list(edges):
        if src.split(":", 1)[0] not in _NODE_TYPES or dst.split(":", 1)[0] not in _NODE_TYPES:
            edges.remove((src, dst, rel))
    return nodes, edges


async def build_graph_for_evidence(db: AsyncSession, item: EvidenceItem) -> None:
    nodes, edges = _nodes_and_edges_for(item)
    seen_nodes: set[str] = set()
    for nid, kind, props in nodes:
        if nid in seen_nodes:
            continue
        seen_nodes.add(nid)
        existing = await db.execute(select(GraphNode).where(GraphNode.id == nid, GraphNode.investigation_id == item.investigation_id))
        if existing.scalar_one_or_none():
            continue
        db.add(GraphNode(id=nid, investigation_id=item.investigation_id, node_type=kind, label=props.get("label", nid), props=props, evidence_id=item.id if kind_node_matches(item, kind) else None))
    await db.flush()
    for src, dst, rel in edges:
        src_ok = (await db.execute(select(GraphNode.id).where(GraphNode.id == src, GraphNode.investigation_id == item.investigation_id))).scalar_one_or_none()
        dst_ok = (await db.execute(select(GraphNode.id).where(GraphNode.id == dst, GraphNode.investigation_id == item.investigation_id))).scalar_one_or_none()
        if not src_ok:
            src_props = next((p for n, _, p in nodes if n == src), {"label": src})
            db.add(GraphNode(id=src, investigation_id=item.investigation_id, node_type=src.split(":", 1)[0], label=src_props.get("label", src), props=src_props))
        if not dst_ok:
            dst_props = next((p for n, _, p in nodes if n == dst), {"label": dst})
            db.add(GraphNode(id=dst, investigation_id=item.investigation_id, node_type=dst.split(":", 1)[0], label=dst_props.get("label", dst), props=dst_props))
        await db.flush()
        dup = await db.execute(select(GraphEdge.id).where(GraphEdge.src_node == src, GraphEdge.dst_node == dst, GraphEdge.rel_type == rel))
        if dup.scalar_one_or_none():
            continue
        db.add(GraphEdge(investigation_id=item.investigation_id, src_node=src, dst_node=dst, rel_type=rel, confidence=1.0, evidence_id=item.id))
    await db.flush()


def kind_node_matches(item: EvidenceItem, kind: str) -> bool:
    mapping = {"process": "PROCESS", "file": "FILE", "network": "NETWORK_CONNECTION", "user": "USER_ACCOUNT", "event": "SYSTEM_EVENT"}
    return mapping.get(kind) == item.evidence_type
