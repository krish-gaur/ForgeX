"""Unit tests: evidence graph construction + traversal."""
from __future__ import annotations

from app.db.models import EvidenceItem, Investigation
from app.graph import engine as graph_engine
from app.graph.builder import build_graph_for_evidence


def _ev(id_, etype, data, inv="ginv"):
    import hashlib
    import json as _json
    h = hashlib.sha256(_json.dumps(data, sort_keys=True, default=str).encode()).hexdigest()
    return EvidenceItem(id=id_, investigation_id=inv, evidence_type=etype, data=data, data_hash=h, target_host="h", collected_by="u")


async def test_build_nodes_and_edges(db):
    inv = Investigation(id="ginv", name="g", target_host="h", created_by="u1")
    db.add(inv)
    await db.commit()
    proc = _ev("p1", "PROCESS", {"pid": 42, "name": "bash", "user": "alice", "parent_pid": 1, "parent_name": "systemd", "cmdline": "bash"})
    net = _ev("n1", "NETWORK_CONNECTION", {"src_ip": "10.0.0.1", "src_port": 1, "dst_ip": "1.2.3.4", "dst_port": 4444, "protocol": "TCP", "pid": 42, "process_name": "bash"})
    evt = _ev("e1", "SYSTEM_EVENT", {"event_id": 7, "event_type": "login_failure", "user": "alice", "description": "fail", "timestamp": "2026-09-26T10:00:00+00:00"})
    for e in (proc, net, evt):
        db.add(e)
    await db.commit()
    for e in (proc, net, evt):
        await build_graph_for_evidence(db, e)
    await db.commit()

    g = await graph_engine.get_graph(db, "ginv")
    types = {n["type"] for n in g["nodes"]}
    assert {"process", "user", "network", "event"} <= types
    rels = {e["label"] for e in g["edges"]}
    assert {"LAUNCHED", "SPAWNED", "MADE_CONNECTION", "TRIGGERED_EVENT"} <= rels

    chains = await graph_engine.incident_chains(db, "ginv", start_node="user:alice", depth=3)
    flat = {n for c in chains for n in c}
    assert "process:42:bash" in flat


async def test_graph_idempotent(db):
    inv = Investigation(id="inv2", name="g2", target_host="h", created_by="u1")
    db.add(inv)
    await db.commit()
    proc = _ev("p2", "PROCESS", {"pid": 7, "name": "sh", "user": "bob", "parent_pid": 0, "parent_name": None, "cmdline": "sh"}, inv="inv2")
    db.add(proc)
    await db.commit()
    await build_graph_for_evidence(db, proc)
    await build_graph_for_evidence(db, proc)
    await db.commit()
    g = await graph_engine.get_graph(db, "inv2")
    ids = [n["id"] for n in g["nodes"]]
    assert len(ids) == len(set(ids))
