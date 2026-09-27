"use client";

// Correlation graph: USERâ†’PROCESSâ†’FILEâ†’NETWORKâ†’EVENT evidence relationships,
// rendered with @xyflow/react. Nodes are built only from real evidence payloads.
import {
  Background,
  Controls,
  MiniMap,
  ReactFlow,
  Handle,
  Position,
  type Edge,
  type Node,
  type NodeProps,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { useCallback, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { useData } from "@/lib/useData";
import { Empty, KV, Panel, Spinner } from "@/components/ui";
import { useCase } from "../layout";
import type { GraphData } from "@/lib/types";

const TYPE_STYLE: Record<string, { border: string; bg: string; text: string; glyph: string }> = {
  user: { border: "#b28dff", bg: "rgba(178,141,255,0.10)", text: "#b28dff", glyph: "ðŸ‘¤" },
  process: { border: "#3dff9e", bg: "rgba(61,255,158,0.08)", text: "#3dff9e", glyph: "âš™" },
  file: { border: "#35d6ff", bg: "rgba(53,214,255,0.08)", text: "#35d6ff", glyph: "ðŸ—Ž" },
  network: { border: "#ffb547", bg: "rgba(255,181,71,0.08)", text: "#ffb547", glyph: "â‡„" },
  event: { border: "#ff8ad1", bg: "rgba(255,138,209,0.08)", text: "#ff8ad1", glyph: "âš¡" },
};

type ForgeNodeData = { label: string; nodeType: string; [k: string]: unknown };

function ForgeNode({ data, selected }: NodeProps<Node<ForgeNodeData>>) {
  const st = TYPE_STYLE[data.nodeType] ?? TYPE_STYLE.event;
  return (
    <div
      className="px-2.5 py-1.5 font-mono text-[10.5px] leading-tight"
      style={{
        border: `1px solid ${st.border}`,
        background: selected ? st.bg.replace(/0\.08|0\.10/, "0.22") : st.bg,
        color: st.text,
        boxShadow: selected ? `0 0 10px ${st.border}55` : "none",
        maxWidth: 230,
      }}
    >
      <Handle type="target" position={Position.Top} style={{ background: st.border, width: 5, height: 5 }} />
      <span className="mr-1">{st.glyph}</span>
      <b>{data.label}</b>
      <span className="mt-0.5 block truncate text-[8.5px] uppercase tracking-wider opacity-60">{data.nodeType}</span>
      <Handle type="source" position={Position.Bottom} style={{ background: st.border, width: 5, height: 5 }} />
    </div>
  );
}

const nodeTypes = { forge: ForgeNode };

/** Deterministic layered layout: users â†’ processes â†’ files/network/events. */
function layout(data: GraphData): { nodes: Node<ForgeNodeData>[]; edges: Edge[] } {
  const layerOf: Record<string, number> = { user: 0, process: 1, file: 2, network: 2, event: 3 };
  const buckets = new Map<number, GraphData["nodes"]>();
  for (const n of data.nodes) {
    const l = layerOf[n.type] ?? 2;
    buckets.set(l, [...(buckets.get(l) ?? []), n]);
  }
  const nodes: Node<ForgeNodeData>[] = [];
  const sortedLayers = [...buckets.keys()].sort((a, b) => a - b);
  sortedLayers.forEach((layer, li) => {
    const row = buckets.get(layer)!;
    const gap = Math.min(260, 2400 / Math.max(1, row.length));
    row.forEach((n, i) => {
      nodes.push({
        id: n.id,
        type: "forge",
        position: { x: 40 + i * gap, y: 60 + li * 150 },
        data: { ...n.data, label: String(n.data.label ?? n.id), nodeType: n.type } as ForgeNodeData,
      });
    });
  });
  const edges: Edge[] = data.edges.map((e) => ({
    id: e.id ?? `${e.source}-${e.target}-${e.label}`,
    source: e.source,
    target: e.target,
    label: e.label,
    type: "default",
    animated: e.label === "MADE_CONNECTION",
    style: { stroke: "#27405a", strokeWidth: 1.2 },
    labelStyle: { fill: "#7c8ea3", fontSize: 8.5, fontFamily: "ui-monospace, monospace" },
    labelBgStyle: { fill: "#0a0f16", fillOpacity: 0.85 },
    labelBgPadding: [3, 2],
  }));
  return { nodes, edges };
}

export default function GraphPage() {
  const { inv } = useCase();
  const [selected, setSelected] = useState<Node<ForgeNodeData> | null>(null);

  const g = useData<GraphData>(() => get<GraphData>(`/api/v1/investigations/${inv!.id}/graph`), [inv?.id]);

  const { nodes, edges } = useMemo(() => (g.data ? layout(g.data) : { nodes: [], edges: [] }), [g.data]);
  const onNodeClick = useCallback((_: unknown, node: Node<ForgeNodeData>) => setSelected(node), []);

  if (!inv) return <div className="p-6"><Spinner /></div>;

  return (
    <div className="grid gap-4 lg:grid-cols-4">
      <Panel
        title={`correlation graph â€” ${nodes.length} node(s), ${edges.length} relation(s)`}
        className="lg:col-span-3"
        variant="cyan"
      >
        {g.loading && <div className="p-6"><Spinner label="traversing evidence graph" /></div>}
        {g.error && <div className="p-3 text-[12px] text-alarm">âš  {g.error}</div>}
        {!g.loading && nodes.length === 0 && (
          <Empty
            text="graph is empty"
            hint="Nodes are built from collected evidence (users, processes, files, connections, events). Collect evidence via FQL or the Script Lab first."
          />
        )}
        {nodes.length > 0 && (
          <div className="h-[62vh] bg-void" style={{ background: "#05080d" }}>
            <ReactFlow
              nodes={nodes}
              edges={edges}
              nodeTypes={nodeTypes}
              onNodeClick={onNodeClick}
              fitView
              fitViewOptions={{ padding: 0.2 }}
              minZoom={0.15}
              proOptions={{ hideAttribution: true }}
              colorMode="dark"
            >
              <Background color="#16212e" gap={26} size={1} />
              <Controls className="!border !border-edge !bg-panel [&>button]:!border-edge [&>button]:!bg-panel2 [&>button]:!text-muted [&>button:hover]:!bg-edge" showInteractive={false} />
              <MiniMap
                className="!bg-panel"
                maskColor="rgba(5,8,13,0.75)"
                nodeColor={(n) => TYPE_STYLE[(n.data as ForgeNodeData).nodeType]?.border ?? "#27405a"}
                nodeStrokeWidth={2}
                pannable
                zoomable
              />
            </ReactFlow>
          </div>
        )}
      </Panel>

      <div className="space-y-3">
        <Panel title="node inspector" variant="dim">
          <div className="p-3">
            {!selected && <Empty text="click a node" hint="Inspect the entity and the evidence fields it was built from." />}
            {selected && (
              <>
                <p className="mb-2 flex items-center gap-2">
                  <span
                    className="badge"
                    style={{ borderColor: TYPE_STYLE[selected.data.nodeType]?.border, color: TYPE_STYLE[selected.data.nodeType]?.text }}
                  >
                    {selected.data.nodeType}
                  </span>
                  <b className="truncate text-[12px] text-ink">{selected.data.label}</b>
                </p>
                {Object.entries(selected.data)
                  .filter(([k, v]) => !["label", "nodeType"].includes(k) && v !== null && v !== undefined)
                  .map(([k, v]) => (
                    <KV key={k} k={k.replace(/_/g, " ")} v={typeof v === "object" ? JSON.stringify(v) : String(v)} mono />
                  ))}
                <p className="mt-2 break-all text-[10px] text-faint">node id: {selected.id}</p>
              </>
            )}
          </div>
        </Panel>

        <Panel title="legend" variant="dim">
          <div className="space-y-1.5 p-3">
            {Object.entries(TYPE_STYLE).map(([k, st]) => (
              <p key={k} className="flex items-center gap-2 text-[11px]" style={{ color: st.text }}>
                <span className="led" style={{ background: st.border }} />
                {k.toUpperCase()}
                <span className="ml-auto text-faint">
                  {nodes.filter((n) => n.data.nodeType === k).length}
                </span>
              </p>
            ))}
            <p className="border-t border-grid pt-2 text-[10px] leading-relaxed text-faint">
              Edges are forensic relations emitted by collectors: LAUNCHED, SPAWNED, ACCESSED_FILE, MADE_CONNECTION,
              TRIGGERED_EVENT, RESOLVED_FROMâ€¦
            </p>
          </div>
        </Panel>
      </div>
    </div>
  );
}
