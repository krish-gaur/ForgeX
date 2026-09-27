"use client";

// FQL intent console: validate (syntax + policy preview) →’ execute →’ poll job.
// The entry point of the product flow: INTENT →’ EXECUTION →’ EVIDENCE.
import dynamic from "next/dynamic";
import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Play, ScanSearch, ShieldQuestion, XCircle } from "lucide-react";
import { get, post, ApiError } from "@/lib/api";
import { errMsg } from "@/lib/useData";
import { Btn, StatusPill, useToast } from "@/components/ui";
import { useCaseSocket, type WsMessage } from "@/lib/ws";
import type { JobStatus } from "@/lib/types";

const Monaco = dynamic(() => import("@/components/Monaco"), { ssr: false });

interface PolicyPreview {
  status: "ALLOWED" | "DENIED" | string;
  reasons?: string[];
  rules_evaluated?: number;
  [k: string]: unknown;
}

interface ValidateResult {
  valid: boolean;
  ast?: Record<string, unknown>;
  estimated_collectors?: string[];
  policy_preview?: PolicyPreview;
  error?: { line?: number; col?: number; message?: string };
}

const STARTER = "INVESTIGATE processes WHERE user = 'svc_backup' LIMIT 50";

export default function FqlConsole({ investigationId, onCollected }: { investigationId: string; onCollected?: () => void }) {
  const toast = useToast();
  const [fql, setFql] = useState(STARTER);
  const [validation, setValidation] = useState<ValidateResult | null>(null);
  const [validating, setValidating] = useState(false);
  const [job, setJob] = useState<JobStatus | null>(null);
  const [polling, setPolling] = useState(false);
  const [examples, setExamples] = useState<Array<{ label?: string; fql: string; description?: string }>>([]);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const { connected } = useCaseSocket(investigationId, useCallback((m: WsMessage) => {
    setJob((prev) => {
      if (!prev) return prev;
      if ((m.type === "JOB_STATUS" || m.type === "JOB_COMPLETE" || m.type === "JOB_FAILED") && m.job_id === prev.job_id) {
        const status = (m.status as string) ?? (m.type === "JOB_COMPLETE" ? "COMPLETED" : m.type === "JOB_FAILED" ? "FAILED" : prev.status);
        return { ...prev, status };
      }
      return prev;
    });
  }, []));

  useEffect(() => {
    get<{ queries: Array<{ label?: string; fql: string; description?: string }> }>("/api/v1/demo/fql-examples")
      .then((r) => setExamples(r.queries ?? []))
      .catch(() => setExamples([]));
  }, []);

  const stopPoll = () => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = null;
    setPolling(false);
  };
  useEffect(() => stopPoll, []);

  const pollJob = useCallback(
    (jobId: string) => {
      stopPoll();
      setPolling(true);
      const tick = async () => {
        try {
          const st = await get<JobStatus>(`/api/v1/jobs/${jobId}/status`);
          setJob(st);
          if (["COMPLETED", "FAILED", "PARTIAL", "POLICY_DENIED"].includes(st.status)) {
            stopPoll();
            if (st.status === "COMPLETED" || st.status === "PARTIAL") {
              toast("ok", `Collection ${st.status.toLowerCase()} — ${st.items_collected_so_far ?? 0} evidence item(s) secured.`);
              onCollected?.();
            } else {
              toast("err", `Job ${st.status}: ${st.error ?? "see job status"}`);
            }
          }
        } catch {
          stopPoll();
        }
      };
      void tick();
      pollRef.current = setInterval(tick, 1200);
    },
    [toast, onCollected],
  );

  async function validate() {
    setValidating(true);
    setValidation(null);
    try {
      const r = await post<ValidateResult>(`/api/v1/investigations/${investigationId}/fql/validate`, { fql });
      setValidation(r);
    } catch (e) {
      if (e instanceof ApiError && e.code === "FQL_PARSE_ERROR") {
        const d = (e.details ?? {}) as { line?: number; col?: number; token?: string };
        setValidation({ valid: false, error: { line: d.line, col: d.col, message: `${e.message} (line ${d.line}, col ${d.col}${d.token ? `, near "${d.token}"` : ""})` } });
      } else if (e instanceof ApiError && e.code === "POLICY_DENIED") {
        setValidation({ valid: true, policy_preview: { status: "DENIED", reasons: [e.message] } });
      } else {
        setValidation({ valid: false, error: { message: errMsg(e) } });
      }
    } finally {
      setValidating(false);
    }
  }

  async function execute() {
    setJob(null);
    try {
      const r = await post<{ job_id: string; status_endpoint: string; collectors: string[] }>(
        `/api/v1/investigations/${investigationId}/fql/execute`,
        { fql },
      );
      toast("info", `Job ${r.job_id.slice(0, 8)} queued — collectors: ${r.collectors.join(", ")}`);
      setJob({ job_id: r.job_id, status: "QUEUED" });
      pollJob(r.job_id);
    } catch (e) {
      if (e instanceof ApiError && e.code === "POLICY_DENIED") {
        toast("warn", `Policy engine denied execution: ${e.message}`);
        setValidation({ valid: true, policy_preview: { status: "DENIED", reasons: [e.message] } });
      } else {
        toast("err", errMsg(e));
      }
    }
  }

  const pv = validation?.policy_preview;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.2em] text-faint">
        <span className={connected ? "led bg-phosphor " : "led bg-faint"} />
        {connected ? "live channel connected" : "polling mode"}
        <span className="flex-1" />
        <span>fql · intent language</span>
      </div>

      <Monaco value={fql} onChange={setFql} language="fql" height={130} />

      <div className="flex flex-wrap items-center gap-2">
        <Btn variant="cyan" busy={validating} onClick={() => void validate()}>
          <ScanSearch size={13} /> validate
        </Btn>
        <Btn variant="primary" busy={polling} onClick={() => void execute()} disabled={pv?.status === "DENIED"}>
          <Play size={13} /> execute collection
        </Btn>
        {validation?.error && (
          <span className="flex items-center gap-1.5 text-[11.5px] text-alarm">
            <XCircle size={13} /> {validation.error.message}
          </span>
        )}
        {validation?.valid && !pv && (
          <span className="flex items-center gap-1.5 text-[11.5px] text-phosphorDim">
            <CheckCircle2 size={13} /> syntax ok — collectors: {(validation.estimated_collectors ?? []).join(", ")}
          </span>
        )}
        {pv && (
          <span className="flex items-center gap-1.5 text-[11.5px]">
            {pv.status === "ALLOWED" ? <CheckCircle2 size={13} className="text-phosphorDim" /> : <ShieldQuestion size={13} className="text-alarm" />}
            policy: <StatusPill status={pv.status} />
            {pv.reasons?.length ? <span className="text-faint">— {pv.reasons.join("; ")}</span> : null}
          </span>
        )}
      </div>

      {job && (
        <div className="border border-grid bg-void/60 p-2.5 text-[11.5px]">
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-faint">job {job.job_id.slice(0, 8)}</span>
            <StatusPill status={job.status} />
            {typeof job.items_collected_so_far === "number" && (
              <span className="tabular-nums text-accent">{job.items_collected_so_far} item(s)</span>
            )}
            {job.collectors && Object.keys(job.collectors).length > 0 && (
              <span className="flex flex-wrap gap-1">
                {Object.entries(job.collectors).map(([c, st]) => (
                  <span key={c} className="badge border-edge2 bg-panel2 text-[9.5px] text-muted">
                    {c}: <StatusPill status={st} />
                  </span>
                ))}
              </span>
            )}
            {job.error && <span className="text-alarm">⚠ {job.error}</span>}
          </div>
        </div>
      )}

      {examples.length > 0 && (
        <details className="group border border-grid bg-panel2/30">
          <summary className="cursor-pointer select-none px-3 py-2 text-[10px] font-bold uppercase tracking-[0.2em] text-faint hover:text-muted">
            ▷ example intents ({examples.length})
          </summary>
          <div className="space-y-1 border-t border-grid p-2">
            {examples.map((ex, i) => (
              <button
                key={i}
                className="block w-full border border-transparent px-2 py-1.5 text-left hover:border-phosphorDim hover:bg-phosphor/5"
                onClick={() => {
                  setFql(ex.fql);
                  setValidation(null);
                }}
              >
                <code className="text-[11.5px] text-phosphorDim">{ex.fql}</code>
                {(ex.label || ex.description) && (
                  <span className="block text-[10px] text-faint">{ex.label ?? ex.description}</span>
                )}
              </button>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
