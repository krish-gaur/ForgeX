"use client";

// Execution history: sandbox runs with console output, real resource usage,
// findings produced, and stop control for running executions.
import { useState } from "react";
import { ChevronRight, Square, Terminal } from "lucide-react";
import { get, post } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Panel, SeverityBadge, Spinner, StatusPill, useToast } from "@/components/ui";
import { useCase } from "../layout";
import type { Execution, ExecutionDetail, Script } from "@/lib/types";
import { fmtTime } from "@/lib/format";

export default function ExecutionsPage() {
  const { inv } = useCase();
  const toast = useToast();
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<ExecutionDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const list = useData<{ data: Execution[] }>(() => get(`/api/v1/investigations/${inv!.id}/executions`), [inv?.id]);
  const scripts = useData<{ data: Script[] }>(() => get(`/api/v1/investigations/${inv!.id}/scripts`), [inv?.id]);

  const scriptName = (id?: string | null) => scripts.data?.data.find((s) => s.id === id)?.name ?? "ad-hoc function";

  async function open(id: string) {
    setOpenId(id);
    setLoadingDetail(true);
    try {
      setDetail(await get<ExecutionDetail>(`/api/v1/executions/${id}`));
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setLoadingDetail(false);
    }
  }

  if (!inv) return <div className="p-6"><Spinner /></div>;

  const rows = list.data?.data ?? [];
  const running = rows.filter((r) => r.status === "RUNNING" || r.status === "PENDING");

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel
        title={`execution history — ${rows.length}`}
        right={running.length ? <span className="badge animate-pulse-dot border-cyanx/60 text-accent">{running.length} active</span> : undefined}
      >
        {list.loading && <div className="p-4"><Spinner label="loading executions" /></div>}
        {list.error && <div className="p-3 text-[12px] text-alarm">⚠ {list.error}</div>}
        {rows.length === 0 && !list.loading && (
          <Empty text="no executions yet" hint="Run a forensic function from the Script Lab — every run lands here with its sandbox console and resource usage." />
        )}
        <div className="max-h-[68vh] overflow-y-auto">
          {rows.map((e) => (
            <button
              key={e.id}
              className={`flex w-full items-center gap-3 border-b border-grid px-3 py-2.5 text-left transition-colors hover:bg-panel2/60 ${openId === e.id ? "bg-phosphor/5" : ""}`}
              onClick={() => void open(e.id)}
            >
              <Terminal size={14} className={e.status === "COMPLETED" ? "shrink-0 text-phosphorDim" : e.status === "RUNNING" ? "shrink-0 animate-pulse-dot text-accent" : "shrink-0 text-alarm"} />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[12px] font-bold text-ink">{scriptName(e.script_id)}</span>
                <span className="block text-[10.5px] text-faint">
                  {e.id.slice(0, 8)} · {fmtTime(e.started_at ?? null)} · {e.findings_count ?? 0} finding(s)
                </span>
              </span>
              <StatusPill status={e.status} />
              <ChevronRight size={13} className="shrink-0 text-faint" />
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="execution detail" variant="dim">
        {loadingDetail && <div className="p-4"><Spinner label="fetching execution record" /></div>}
        {!loadingDetail && !detail && <Empty text="select an execution" />}
        {!loadingDetail && detail && (
          <div className="max-h-[68vh] space-y-3 overflow-y-auto p-3">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill status={detail.status} />
              <span className="text-[11px] text-faint">{detail.id}</span>
              {detail.status === "RUNNING" && (
                <Btn
                  size="sm"
                  variant="danger"
                  onClick={async () => {
                    try {
                      await post(`/api/v1/executions/${detail.id}/stop`);
                      toast("info", "Stop signal sent — sandbox child will be terminated.");
                      setTimeout(() => void open(detail.id), 1500);
                    } catch (e) {
                      toast("err", errMsg(e));
                    }
                  }}
                >
                  <Square size={11} /> stop
                </Btn>
              )}
            </div>

            {detail.error_message && (
              <div className="border border-alarm/60 bg-alarm/10 p-2.5 text-[11.5px] text-alarm"><b>ERROR</b>: {detail.error_message}</div>
            )}

            {detail.resource_usage && (
              <div className="grid grid-cols-3 gap-2">
                {([
                  ["user cpu", `${Number(detail.resource_usage.user_cpu_sec ?? 0).toFixed(3)} s`],
                  ["sys cpu", `${Number(detail.resource_usage.system_cpu_sec ?? 0).toFixed(3)} s`],
                  ["peak rss", `${Number(detail.resource_usage.max_rss_mb ?? 0).toFixed(1)} MB`],
                ] as const).map(([k, v]) => (
                  <div key={k} className="border border-grid bg-void/60 p-2 text-center">
                    <p className="text-[9px] font-bold uppercase tracking-[0.2em] text-faint">{k}</p>
                    <p className="mt-0.5 text-[13px] font-bold tabular-nums text-accent">{v}</p>
                  </div>
                ))}
              </div>
            )}

            {(detail.findings?.length ?? 0) > 0 && (
              <div>
                <p className="label">findings ({detail.findings!.length})</p>
                <div className="space-y-1.5">
                  {detail.findings!.map((f) => (
                    <div key={f.id} className="border border-grid bg-void/60 p-2.5">
                      <div className="flex flex-wrap items-center gap-2">
                        <SeverityBadge severity={f.severity} />
                        <b className="text-[12px] text-ink">{f.title}</b>
                      </div>
                      {f.description && <p className="mt-1 text-[11px] leading-relaxed text-muted">{f.description}</p>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div>
              <p className="label">sandbox console ({detail.console_log?.length ?? 0} lines)</p>
              <pre className="max-h-64 overflow-auto border border-grid bg-void p-2.5 text-[11px] leading-relaxed text-phosphorDim/90">
                {(detail.console_log ?? []).join("\n") || "(no output)"}
              </pre>
            </div>
          </div>
        )}
      </Panel>
    </div>
  );
}
