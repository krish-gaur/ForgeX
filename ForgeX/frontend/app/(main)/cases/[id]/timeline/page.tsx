"use client";

// Reconstructed incident timeline: custom SVG lane chart (no chart lib) with
// severity-colored evidence events, type filters, hover detail and a synced
// entry list â€” the "what happened, in what order" screen.
import { useMemo, useState } from "react";
import { get } from "@/lib/api";
import { useData } from "@/lib/useData";
import { Empty, Panel, SeverityBadge, Spinner, TypeBadge } from "@/components/ui";
import { useCase } from "../layout";
import type { TimelineEntry } from "@/lib/types";
import { fmtTime } from "@/lib/format";

const TYPE_COLORS: Record<string, string> = {
  PROCESS: "#3dff9e",
  FILE: "#35d6ff",
  NETWORK_CONNECTION: "#ffb547",
  SYSTEM_EVENT: "#b28dff",
  LOG_ENTRY: "#b28dff",
  USER_ACCOUNT: "#ff8ad1",
  REGISTRY: "#7ce38b",
  MEMORY: "#5eead4",
  BROWSER: "#93c5fd",
  HASH: "#94a3b8",
};
const SEV_COLOR: Record<string, string> = { CRITICAL: "#ff4d5e", HIGH: "#ff8a4d", MEDIUM: "#ffb547", LOW: "#35d6ff", INFO: "#4a5b6e" };

function colorFor(e: TimelineEntry): string {
  if (e.severity && SEV_COLOR[e.severity]) return SEV_COLOR[e.severity];
  return TYPE_COLORS[e.type] ?? "#7c8ea3";
}

function TimelineChart({ entries, onPick, picked }: { entries: TimelineEntry[]; onPick: (i: number) => void; picked: number | null }) {
  const [hover, setHover] = useState<number | null>(null);
  const W = 1100;
  const lanes = useMemo(() => [...new Set(entries.map((e) => e.type))], [entries]);
  const laneH = 34;
  const padL = 150;
  const padR = 20;
  const H = lanes.length * laneH + 46;

  const t0 = entries.length ? new Date(entries[0].timestamp).getTime() : 0;
  const t1 = entries.length ? new Date(entries[entries.length - 1].timestamp).getTime() : 1;
  const span = Math.max(1, t1 - t0);
  const x = (ts: string) => padL + ((new Date(ts).getTime() - t0) / span) * (W - padL - padR);
  const y = (type: string) => 30 + lanes.indexOf(type) * laneH + laneH / 2;

  // time ticks
  const ticks = useMemo(() => {
    const n = Math.min(6, Math.max(2, Math.floor((W - padL - padR) / 160)));
    return Array.from({ length: n + 1 }, (_, i) => new Date(t0 + (span * i) / n).toISOString());
  }, [t0, span]);

  if (entries.length === 0) return <Empty text="no timestamped evidence" />;

  const active = hover ?? picked;

  return (
    <div className="overflow-x-auto">
      <svg viewBox={`0 0 ${W} ${H}`} className="min-w-[760px]" style={{ width: "100%", height: H }}>
        {/* grid + ticks */}
        {ticks.map((t, i) => (
          <g key={i}>
            <line x1={x(t)} x2={x(t)} y1={20} y2={H - 18} stroke="#16212e" strokeWidth={1} />
            <text x={x(t)} y={H - 5} fill="#4a5b6e" fontSize={9} textAnchor="middle" fontFamily="ui-monospace, monospace">
              {t.slice(11, 19)}Z
            </text>
          </g>
        ))}
        {/* lanes */}
        {lanes.map((l, i) => (
          <g key={l}>
            <line x1={padL} x2={W - padR} y1={y(l)} y2={y(l)} stroke="#101923" strokeWidth={laneH - 6} />
            <text x={10} y={y(l) + 3.5} fill={TYPE_COLORS[l] ?? "#7c8ea3"} fontSize={10} fontFamily="ui-monospace, monospace" fontWeight={700}>
              {l.replace(/_/g, " ").slice(0, 20)}
            </text>
            {i === 0 && <line x1={padL} x2={W - padR} y1={20} y2={20} stroke="#1d2b3a" strokeWidth={1} />}
          </g>
        ))}
        {/* events */}
        {entries.map((e, i) => {
          const isActive = active === i;
          return (
            <g key={i} onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onClick={() => onPick(i)} style={{ cursor: "pointer" }}>
              <line x1={x(e.timestamp)} x2={x(e.timestamp)} y1={y(e.type) - 7} y2={y(e.type) + 7} stroke={colorFor(e)} strokeWidth={isActive ? 3 : 1.4} opacity={isActive ? 1 : 0.85} />
              <circle cx={x(e.timestamp)} cy={y(e.type)} r={isActive ? 5 : 3} fill={isActive ? colorFor(e) : "#05080d"} stroke={colorFor(e)} strokeWidth={1.6} />
            </g>
          );
        })}
        {/* hover label */}
        {active !== null && entries[active] && (
          <g pointerEvents="none">
            <rect
              x={Math.min(W - 320, Math.max(padL, x(entries[active].timestamp) - 150))}
              y={4}
              width={310}
              height={26}
              fill="#0d141d"
              stroke="#27405a"
            />
            <text
              x={Math.min(W - 314, Math.max(padL + 6, x(entries[active].timestamp) - 144))}
              y={21}
              fill="#c8d6e5"
              fontSize={10.5}
              fontFamily="ui-monospace, monospace"
            >
              {`${entries[active].timestamp.slice(11, 19)}Z Â· ${entries[active].label.slice(0, 34)}`}
            </text>
          </g>
        )}
      </svg>
    </div>
  );
}

export default function TimelinePage() {
  const { inv } = useCase();
  const [typeFilter, setTypeFilter] = useState<Set<string>>(new Set());
  const [picked, setPicked] = useState<number | null>(null);

  const tl = useData<{ timeline: TimelineEntry[] }>(
    () => get(`/api/v1/investigations/${inv!.id}/timeline`),
    [inv?.id],
  );

  const all = tl.data?.timeline ?? [];
  const types = useMemo(() => [...new Set(all.map((e) => e.type))].sort(), [all]);
  const entries = useMemo(
    () => (typeFilter.size === 0 ? all : all.filter((e) => typeFilter.has(e.type))),
    [all, typeFilter],
  );

  if (!inv) return <div className="p-6"><Spinner /></div>;

  function toggleType(t: string) {
    setTypeFilter((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
    setPicked(null);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="hud-title">// incident timeline</h2>
        <span className="text-[11px] text-faint">
          {all.length} timestamped evidence item(s){typeFilter.size ? ` Â· ${entries.length} shown` : ""} â€” reconstructed from real collected artifacts
        </span>
        <div className="flex-1" />
        {types.map((t) => (
          <button
            key={t}
            onClick={() => toggleType(t)}
            className={`badge transition-opacity ${typeFilter.size === 0 || typeFilter.has(t) ? "" : "opacity-30"}`}
            style={{ borderColor: TYPE_COLORS[t] ?? "#27405a", color: TYPE_COLORS[t] ?? "#7c8ea3" }}
          >
            <span className="led" style={{ background: TYPE_COLORS[t] ?? "#7c8ea3" }} />
            {t.replace(/_/g, " ")}
          </button>
        ))}
      </div>

      <Panel title="lane view â€” time flows left â†’ right">
        {tl.loading && <div className="p-4"><Spinner label="reconstructing timeline" /></div>}
        {tl.error && <div className="p-3 text-[12px] text-alarm">âš  {tl.error}</div>}
        {!tl.loading && all.length === 0 && (
          <Empty text="nothing to reconstruct yet" hint="Collect evidence first â€” timeline entries are derived from artifact timestamps (process starts, log events, connection times)." />
        )}
        {!tl.loading && all.length > 0 && (
          <div className="p-2">
            <TimelineChart entries={entries} onPick={(i) => setPicked(i === picked ? null : i)} picked={picked} />
          </div>
        )}
      </Panel>

      <Panel title="event log">
        <div className="max-h-96 overflow-y-auto">
          {entries.length === 0 && !tl.loading && <Empty text="filtered out" hint="Clear type filters to see all events." />}
          <table className="tbl">
            <thead>
              <tr>
                <th>timestamp</th>
                <th>type</th>
                <th>event</th>
                <th>severity</th>
                <th>evidence</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((e, i) => (
                <tr
                  key={`${e.evidence_id}-${i}`}
                  className={picked === i ? "bg-phosphor/5" : ""}
                  onClick={() => setPicked(i === picked ? null : i)}
                  style={{ cursor: "pointer" }}
                >
                  <td className="whitespace-nowrap font-mono text-[11px] text-accent">{fmtTime(e.timestamp)}</td>
                  <td><TypeBadge type={e.type} /></td>
                  <td className="max-w-md truncate text-ink" title={e.label}>{e.label}</td>
                  <td>{e.severity ? <SeverityBadge severity={e.severity} /> : <span className="text-faint">â€”</span>}</td>
                  <td className="font-mono text-[10.5px] text-muted">{e.evidence_id.slice(0, 8)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
    </div>
  );
}
