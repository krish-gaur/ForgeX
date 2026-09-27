"use client";

// AI analysis: evidence-first correlation ("what happened?") + RAG Q&A.
// The engine is always disclosed (LLM vs deterministic heuristic) and every
// claim cites real evidence ids. Indicators can be promoted to findings.
import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUpRight, BrainCircuit, MessageSquareQuote, Sparkles, Wand2 } from "lucide-react";
import { get, post, ApiError } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Panel, SeverityBadge, Spinner, useToast } from "@/components/ui";
import { useCase } from "../layout";
import type { AiAnalysis, CorrelationResult, Finding } from "@/lib/types";
import { fmtTime } from "@/lib/format";

type QaReply = { answer: string; evidence_refs: string[]; confidence: number; caveat?: string | null; engine?: string; model?: string | null };

function EngineBadge({ engine, model }: { engine?: string | null; model?: string | null }) {
  const isLlm = (engine ?? "").toLowerCase().includes("llm") || (engine ?? "").toLowerCase().includes("anthropic") || (engine ?? "").toLowerCase().includes("openai");
  return (
    <span className={`badge ${isLlm ? "border-violetx/60 text-muted" : "border-cyanx/50 text-accent"}`} title={model ?? undefined}>
      <BrainCircuit size={10} /> {isLlm ? `LLM engine${model ? ` Â· ${model}` : ""}` : `deterministic heuristic${engine ? ` Â· ${engine}` : ""}`}
    </span>
  );
}

function ConfidenceBar({ value }: { value: number }) {
  const pct = Math.round(Math.min(1, Math.max(0, value)) * 100);
  const color = pct >= 70 ? "#3dff9e" : pct >= 40 ? "#ffb547" : "#ff4d5e";
  return (
    <span className="flex items-center gap-2">
      <span className="h-1.5 w-28 border border-grid bg-void">
        <span className="block h-full" style={{ width: `${pct}%`, background: color }} />
      </span>
      <b className="tabular-nums text-[11px]" style={{ color }}>{pct}%</b>
    </span>
  );
}

function CorrelationView({ a, onPromote, promoting }: { a: AiAnalysis; onPromote: (idx: number) => void; promoting: number | null }) {
  const r = a.result as CorrelationResult | null;
  if (!r) return <Empty text="analysis produced no result" />;
  return (
    <div className="space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <EngineBadge engine={a.engine} model={a.model_used} />
        <span className="text-[10.5px] text-faint">{fmtTime(a.created_at ?? null)}</span>
        <span className="text-[10.5px] text-faint">input evidence: {a.input_evidence_ids?.length ?? 0} item(s)</span>
        <span className="ml-auto flex items-center gap-2 text-[10.5px] text-faint">confidence <ConfidenceBar value={a.confidence_score ?? r.confidence ?? 0} /></span>
      </div>

      <div className="border border-phosphorDim/50 bg-phosphor/5 p-3.5">
        <p className="hud-title mb-1.5">what happened</p>
        <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-ink">{r.what_happened}</p>
        {r.caveat && <p className="mt-2 text-[10.5px] text-amber">âš  {r.caveat}</p>}
      </div>

      {r.attack_stages?.length > 0 && (
        <div>
          <p className="label">attack stage reconstruction</p>
          <div className="flex flex-wrap items-stretch gap-1.5">
            {r.attack_stages.map((s, i) => (
              <div key={i} className="flex items-center gap-1.5">
                <div className="min-w-36 border border-edge2 bg-panel2/60 p-2">
                  <p className="text-[10px] font-bold uppercase tracking-widest text-accent">{s.stage}</p>
                  {s.summary && <p className="mt-0.5 max-w-56 text-[10.5px] leading-snug text-muted">{s.summary}</p>}
                  <p className="mt-1 text-[9.5px] text-faint">{s.evidence_ids?.length ?? 0} evidence ref(s)</p>
                </div>
                {i < r.attack_stages.length - 1 && <ArrowUpRight size={13} className="shrink-0 text-faint" />}
              </div>
            ))}
          </div>
        </div>
      )}

      {r.suspicious_indicators?.length > 0 && (
        <div>
          <p className="label">suspicious indicators â€” each cites collected evidence</p>
          <div className="space-y-1.5">
            {r.suspicious_indicators.map((ind, i) => (
              <div key={i} className="flex flex-wrap items-center gap-2 border border-grid bg-void/60 p-2.5">
                <SeverityBadge severity={ind.severity} />
                <span className="min-w-0 flex-1 text-[12px] text-ink">{ind.indicator}</span>
                {ind.technique && <span className="badge border-edge2 text-muted">{ind.technique}</span>}
                <span className="font-mono text-[10px] text-muted">
                  ev: {ind.evidence_ids.map((id) => id.slice(0, 6)).join(", ")}
                </span>
                <Btn size="sm" variant="primary" busy={promoting === i} onClick={() => onPromote(i)}>
                  <Wand2 size={11} /> promote to finding
                </Btn>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2">
        {r.mitre_techniques?.length > 0 && (
          <div>
            <p className="label">MITRE ATT&amp;CK mapping</p>
            <div className="space-y-1">
              {r.mitre_techniques.map((m, i) => (
                <p key={i} className="border border-grid bg-panel2/40 px-2.5 py-1.5 text-[11px]">
                  <b className="text-amber">{m.technique_id}</b>
                  {m.name && <span className="ml-2 text-muted">{m.name}</span>}
                  {m.evidence_ids?.length ? <span className="ml-2 font-mono text-[9.5px] text-muted">({m.evidence_ids.length} ev)</span> : null}
                </p>
              ))}
            </div>
          </div>
        )}
        {r.gaps?.length > 0 && (
          <div>
            <p className="label">investigative gaps (what the evidence does NOT show)</p>
            <ul className="space-y-1">
              {r.gaps.map((g2, i) => (
                <li key={i} className="border border-grid bg-panel2/40 px-2.5 py-1.5 text-[11px] text-muted">Â· {g2}</li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}

export default function AiPage() {
  const { inv } = useCase();
  const toast = useToast();
  const [running, setRunning] = useState(false);
  const [question, setQuestion] = useState("");
  const [qa, setQa] = useState<QaReply[]>([]);
  const [asking, setAsking] = useState(false);
  const [promoting, setPromoting] = useState<number | null>(null);
  const baseline = useRef<Set<string>>(new Set());
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const analyses = useData<{ data: AiAnalysis[] }>(
    () => get(`/api/v1/investigations/${inv!.id}/ai/analyses`),
    [inv?.id],
  );

  useEffect(() => {
    if (analyses.data) for (const a of analyses.data.data) baseline.current.add(a.id);
  }, [analyses.data]);

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current); }, []);

  const correlations = (analyses.data?.data ?? []).filter((a) => a.analysis_type === "CORRELATION");
  const queries = (analyses.data?.data ?? []).filter((a) => a.analysis_type === "QUERY_RESPONSE");

  const runCorrelation = useCallback(async () => {
    if (!inv) return;
    setRunning(true);
    try {
      await post(`/api/v1/investigations/${inv.id}/ai/correlate`);
      toast("info", "Correlation job submitted â€” analyzing real collected evidenceâ€¦");
      const started = Date.now();
      pollRef.current = setInterval(async () => {
        analyses.reload();
        const fresh = (analyses.data?.data ?? []).find((a) => a.analysis_type === "CORRELATION" && !baseline.current.has(a.id));
        if (fresh || Date.now() - started > 90_000) {
          if (pollRef.current) clearInterval(pollRef.current);
          setRunning(false);
          if (fresh) {
            baseline.current.add(fresh.id);
            toast("ok", `Correlation complete (engine: ${fresh.engine ?? "unknown"}).`);
          } else {
            toast("warn", "Correlation is taking longer than expected â€” check the list below.");
          }
        }
      }, 1500);
    } catch (e) {
      setRunning(false);
      toast("err", errMsg(e));
    }
  }, [inv, analyses, toast]);

  async function ask() {
    if (!inv || !question.trim()) return;
    setAsking(true);
    const q = question.trim();
    setQa((prev) => [...prev, { answer: `> ${q}`, evidence_refs: [], confidence: -1 }]);
    setQuestion("");
    try {
      const r = await post<QaReply>(`/api/v1/investigations/${inv.id}/ai/query`, { question: q });
      setQa((prev) => [...prev, r]);
      analyses.reload();
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : errMsg(e);
      setQa((prev) => [...prev, { answer: `AI PROCESSING FAILURE: ${msg}`, evidence_refs: [], confidence: -1 }]);
    } finally {
      setAsking(false);
    }
  }

  async function promote(a: AiAnalysis, idx: number) {
    setPromoting(idx);
    try {
      const f = await post<Finding>(`/api/v1/ai/analyses/${a.id}/promote`, { indicator_index: idx });
      toast("ok", `Indicator promoted to finding â€œ${f.title}â€ â€” traceable to analysis ${a.id.slice(0, 8)}.`);
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setPromoting(null);
    }
  }

  if (!inv) return <div className="p-6"><Spinner /></div>;

  const latest = correlations[0];
  const evidenceTotal = inv.evidence_summary?.total ?? 0;

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Panel
          title="correlation engine â€” â€œwhat happened?â€"
          variant="cyan"
          right={
            <Btn size="sm" variant="primary" busy={running} onClick={() => void runCorrelation()} disabled={evidenceTotal === 0}>
              <Sparkles size={12} /> run correlation
            </Btn>
          }
        >
          {evidenceTotal === 0 && (
            <div className="p-4">
              <Empty text="no evidence to correlate" hint="AI never fabricates evidence â€” collect artifacts first (FQL console or Script Lab), then run correlation." />
            </div>
          )}
          {evidenceTotal > 0 && running && !latest && (
            <div className="p-4"><Spinner label="correlating user â†’ process â†’ file â†’ network â†’ event" /></div>
          )}
          {latest ? (
            <CorrelationView a={latest} onPromote={(i) => void promote(latest, i)} promoting={promoting} />
          ) : (
            evidenceTotal > 0 && !running && (
              <div className="p-4">
                <Empty text="no correlation run yet" hint={`Press â€œrun correlationâ€ to reconstruct the incident from ${evidenceTotal} collected evidence item(s).`} />
              </div>
            )
          )}
        </Panel>

        <Panel title={`analysis history â€” ${analyses.data?.data.length ?? 0}`}>
          {(analyses.data?.data.length ?? 0) === 0 && <Empty text="no analyses yet" />}
          <div className="max-h-56 divide-y divide-grid overflow-y-auto">
            {(analyses.data?.data ?? []).map((a) => (
              <div key={a.id} className="flex flex-wrap items-center gap-2 px-3 py-2 text-[11px]">
                <span className={`badge ${a.analysis_type === "CORRELATION" ? "border-phosphorDim/60 text-phosphorDim" : "border-cyanx/50 text-accent"}`}>
                  {a.analysis_type.replace(/_/g, " ")}
                </span>
                <EngineBadge engine={a.engine} model={a.model_used} />
                {typeof a.confidence_score === "number" && <ConfidenceBar value={a.confidence_score} />}
                <span className="text-faint">{fmtTime(a.created_at ?? null)}</span>
                <span className="ml-auto font-mono text-[10px] text-faint">{a.id.slice(0, 8)}</span>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      <div className="space-y-4">
        <Panel title="evidence q&a â€” retrieval-augmented">
          <div className="space-y-2 p-3">
            <p className="text-[10.5px] leading-relaxed text-faint">
              Questions are answered from the case&apos;s own embedded evidence (local RAG). Answers always list the
              evidence they used; when the evidence cannot answer, the engine says so instead of guessing.
            </p>
            <textarea
              className="input min-h-16"
              placeholder="e.g. Which process made the external connection on port 4444?"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) void ask();
              }}
            />
            <Btn variant="cyan" className="w-full" busy={asking} disabled={!question.trim() || evidenceTotal === 0} onClick={() => void ask()}>
              <MessageSquareQuote size={13} /> ask the evidence
            </Btn>

            <div className="max-h-[46vh] space-y-2 overflow-y-auto pt-1">
              {qa.length === 0 && <Empty text="no questions yet" />}
              {qa.map((m, i) => (
                <div key={i} className={m.confidence < 0 ? "" : "border border-grid bg-void/60 p-2.5"}>
                  {m.answer.startsWith(">") ? (
                    <p className="text-[11.5px] font-bold text-accent">{m.answer}</p>
                  ) : (
                    <>
                      <p className="whitespace-pre-wrap text-[11.5px] leading-relaxed text-ink">{m.answer}</p>
                      {m.evidence_refs.length > 0 && (
                        <p className="mt-1.5 font-mono text-[10px] text-muted">refs: {m.evidence_refs.map((r) => r.slice(0, 8)).join(", ")}</p>
                      )}
                      <div className="mt-1.5 flex items-center gap-2">
                        <ConfidenceBar value={m.confidence} />
                        {m.engine && <span className="text-[9.5px] uppercase tracking-wider text-faint">{m.engine}</span>}
                      </div>
                      {m.caveat && <p className="mt-1 text-[10px] text-amber">âš  {m.caveat}</p>}
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        </Panel>

        <Panel title="recent queries (stored)" variant="dim">
          {queries.length === 0 && <Empty text="none" />}
          <div className="max-h-40 divide-y divide-grid overflow-y-auto">
            {queries.slice(0, 8).map((q) => (
              <p key={q.id} className="truncate px-3 py-1.5 text-[10.5px] text-muted" title={q.result?.answer ?? ""}>
                <b className="text-accent">Q</b> {(q.result as { question?: string } | null)?.question ?? q.id.slice(0, 8)} Â·{" "}
                <span className="text-faint">{fmtTime(q.created_at ?? null)}</span>
              </p>
            ))}
          </div>
        </Panel>
      </div>
    </div>
  );
}
