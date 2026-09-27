"use client";

// Reports: generate real PDF investigative reports (FULL / SUMMARY /
// CHAIN_OF_CUSTODY), poll generation job, download when READY.
import { useEffect, useRef, useState } from "react";
import { Download, FileText, ScrollText } from "lucide-react";
import { download, get, post } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Field, Panel, Spinner, StatusPill, useToast } from "@/components/ui";
import { useCase } from "../layout";
import type { Report } from "@/lib/types";
import { fmtBytes, fmtTime } from "@/lib/format";

const TYPES: Array<{ id: Report["report_type"]; label: string; sub: string }> = [
  { id: "FULL", label: "Full investigative report", sub: "narrative, findings, evidence index, AI correlation, MITRE mapping" },
  { id: "SUMMARY", label: "Executive summary", sub: "one-page situation overview for command briefing" },
  { id: "CHAIN_OF_CUSTODY", label: "Chain of custody", sub: "hash-anchored custody ledger for every evidence item" },
];

export default function ReportsPage() {
  const { inv } = useCase();
  const toast = useToast();
  const [type, setType] = useState<string>("FULL");
  const [title, setTitle] = useState("");
  const [busy, setBusy] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const list = useData<{ data: Report[] }>(() => get(`/api/v1/investigations/${inv!.id}/reports`), [inv?.id]);

  // keep polling while any report is still generating
  useEffect(() => {
    const pending = (list.data?.data ?? []).some((r) => r.status === "GENERATING" || r.status === "PENDING");
    if (pending && !pollRef.current) {
      pollRef.current = setInterval(() => list.reload(), 1500);
    } else if (!pending && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current && !pending) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [list.data]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  async function generate() {
    if (!inv) return;
    setBusy(true);
    try {
      const r = await post<{ report_id: string; status: string }>(`/api/v1/investigations/${inv.id}/reports`, {
        type,
        title: title.trim() || null,
      });
      toast("info", `Report ${r.report_id.slice(0, 8)} queued (${type}) — rendering PDF…`);
      list.reload();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function grab(r: Report) {
    try {
      await download(`/api/v1/investigations/${inv!.id}/reports/${r.id}/download`, `${(r.title || "forgex-report").replace(/[^a-z0-9-_]+/gi, "-").toLowerCase()}.pdf`);
      toast("ok", "Report downloaded (access audit-logged).");
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  if (!inv) return <div className="p-6"><Spinner /></div>;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Panel title="generate report" variant="cyan">
        <div className="space-y-3 p-4">
          <div className="space-y-2">
            {TYPES.map((t) => (
              <button
                key={t.id}
                className={`block w-full border p-3 text-left transition-colors ${type === t.id ? "border-phosphorDim bg-phosphor/5" : "border-grid hover:border-edge2"}`}
                onClick={() => setType(t.id)}
              >
                <span className={`flex items-center gap-2 text-[12px] font-bold uppercase tracking-wider ${type === t.id ? "text-phosphorDim" : "text-ink"}`}>
                  {t.id === "CHAIN_OF_CUSTODY" ? <ScrollText size={13} /> : <FileText size={13} />}
                  {t.label}
                </span>
                <span className="mt-1 block text-[10.5px] leading-relaxed text-faint">{t.sub}</span>
              </button>
            ))}
          </div>
          <Field label="custom title (optional)">
            <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} placeholder={`${inv.name} — ${type.toLowerCase()} report`} />
          </Field>
          <Btn variant="primary" className="w-full" busy={busy} onClick={() => void generate()}>
            ▷ render pdf report
          </Btn>
          <p className="text-[10px] leading-relaxed text-faint">
            Reports are rendered server-side from REAL case data (findings, evidence, anchors, AI analyses). Synthetic
            demo cases are watermarked as such inside the document.
          </p>
        </div>
      </Panel>

      <Panel title={`generated reports — ${list.data?.data.length ?? 0}`} className="lg:col-span-2">
        {list.loading && <div className="p-4"><Spinner label="loading reports" /></div>}
        {list.error && <div className="p-3 text-[12px] text-alarm">⚠ {list.error}</div>}
        {(list.data?.data.length ?? 0) === 0 && !list.loading && (
          <Empty text="no reports yet" hint="Generate a report once findings exist — FULL reports include the complete evidentiary narrative." />
        )}
        <div className="divide-y divide-grid">
          {(list.data?.data ?? []).map((r) => (
            <div key={r.id} className="flex flex-wrap items-center gap-3 px-3 py-3">
              <FileText size={16} className={r.status === "READY" ? "text-phosphorDim" : "text-faint"} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12.5px] font-bold text-ink">{r.title}</span>
                <span className="block text-[10.5px] text-faint">
                  {r.report_type.replace(/_/g, " ")} · requested {fmtTime(r.created_at)}
                  {r.completed_at ? ` · rendered ${fmtTime(r.completed_at)}` : ""}
                  {r.file_size_bytes ? ` · ${fmtBytes(r.file_size_bytes)}` : ""}
                </span>
              </span>
              <StatusPill status={r.status} />
              {r.status === "READY" && (
                <Btn size="sm" variant="primary" onClick={() => void grab(r)}>
                  <Download size={12} /> pdf
                </Btn>
              )}
              {(r.status === "GENERATING" || r.status === "PENDING") && <Spinner />}
            </div>
          ))}
        </div>
      </Panel>
    </div>
  );
}
