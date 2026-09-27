"""Graph queries: React Flow export, incident-chain traversal, summaries."""
from __future__ import annotations

from collections import defaultdict, deque

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import GraphEdge, GraphNode

NODE_LIMIT = 200


async def get_graph(db: AsyncSession, investigation_id: str) -> dict:
    nodes = (await db.execute(select(GraphNode).where(GraphNode.investigation_id == investigation_id).limit(NODE_LIMIT))).scalars().all()
    node_ids = {n.id for n in nodes}
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id))).scalars().all()
    edges = [e for e in edges if e.src_node in node_ids and e.dst_node in node_ids]
    return {
        "nodes": [
            {"id": n.id, "type": n.node_type, "data": {"label": n.label, **{k: v for k, v in (n.props or {}).items() if k != "label"}}}
            for n in nodes
        ],
        "edges": [{"id": e.id, "source": e.src_node, "target": e.dst_node, "label": e.rel_type, "type": "default"} for e in edges],
    }


async def incident_chains(db: AsyncSession, investigation_id: str, start_node: str | None = None, depth: int = 3) -> list[list[str]]:
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id))).scalars().all()
    adj: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for e in edges:
        adj[e.src_node].append((e.dst_node, e.rel_type))
    starts = [start_node] if start_node else [n for n in adj if n.startswith(("user:", "process:"))]
    chains: list[list[str]] = []
    for start in starts[:50]:
        queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
        while queue:
            node, path = queue.popleft()
            if len(path) > 1:
                chains.append(path)
            if len(path) >= depth + 1:
                continue
            for nxt, _rel in adj.get(node, []):
                if nxt not in path:
                    queue.append((nxt, path + [nxt]))
    chains.sort(key=len, reverse=True)
    return chains[:100]


async def graph_summary(db: AsyncSession, investigation_id: str) -> dict:
    nodes = (await db.execute(select(GraphNode).where(GraphNode.investigation_id == investigation_id))).scalars().all()
    edges = (await db.execute(select(GraphEdge).where(GraphEdge.investigation_id == investigation_id))).scalars().all()
    by_type: dict[str, int] = defaultdict(int)
    for n in nodes:
        by_type[n.node_type] += 1
    rel_count: dict[str, int] = defaultdict(int)
    for e in edges:
        rel_count[e.rel_type] += 1
    return {"nodes": len(nodes), "edges": len(edges), "nodes_by_type": dict(by_type), "relationships": dict(rel_count)}
