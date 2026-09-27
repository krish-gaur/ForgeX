"use client";

// Script Lab â€” TEMPLATE-FIRST: the editor is never empty. Users start from one
// of the 10 forensic function templates, review the code, then validate/run it
// in the sandboxed pipeline (validation â†’ policy â†’ sandbox â†’ findings â†’ audit).
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useState } from "react";
import { BookOpenCheck, FileCode2, History, Play, Save, ScanSearch, Square, TerminalSquare, Wand2 } from "lucide-react";
import { get, post, put, ApiError } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Modal, Panel, SeverityBadge, Spinner, StatusPill, useToast } from "@/components/ui";
import { useCase } from "../layout";
import { useCaseSocket, type WsMessage } from "@/lib/ws";
import type { ExecutionDetail, Script, Template } from "@/lib/types";
import { fmtDuration, fmtTime } from "@/lib/format";

const Monaco = dynamic(() => import("@/components/Monaco"), { ssr: false });

interface ValidateOk {
  valid: true;
  entry: string;
  imports: string[];
  functions: string[];
}
interface ValidateBad {
  valid: false;
  problems: string[];
  line?: number | null;
}
type ValidationResult = ValidateOk | ValidateBad;

function TemplatePreview({ tpl, onClose, onCreate }: { tpl: Template; onClose: () => void; onCreate: (name: string) => void }) {
  const [name, setName] = useState(tpl.title.toLowerCase().replace(/\s+/g, "-"));
  return (
    <Modal open onClose={onClose} title={`template â€” ${tpl.title}`} wide>
      <div className="grid gap-4 lg:grid-cols-5">
        <div className="space-y-3 lg:col-span-2">
          <p className="badge border-cyanx/50 text-accent">{tpl.category}</p>
          <p className="text-[12px] leading-relaxed text-muted">{tpl.description}</p>
          <div className="border border-grid bg-void/60 p-3 text-[11px] leading-relaxed text-faint">
            <p className="font-bold uppercase tracking-widest text-muted">forensic context</p>
            <p className="mt-1">
              Templates ship with imports, function structure, parameters, expected output, examples and error
              handling pre-wired against the <code className="text-phosphorDim">forgex</code> SDK. Review the code,
              adapt it to your hypothesis, then run it â€” execution is sandboxed, policy-checked and fully audited.
            </p>
          </div>
          <div>
            <span className="label">script name</span>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} />
          </div>
          <Btn variant="primary" className="w-full" disabled={!name.trim()} onClick={() => onCreate(name.trim())}>
            <Wand2 size={13} /> create script from template
          </Btn>
        </div>
        <div className="lg:col-span-3">
          <p className="label">template source (read-only preview)</p>
          <Monaco value={tpl.code} language="python" height={430} readOnly />
        </div>
      </div>
    </Modal>
  );
}

interface VersionRow {
  version: number;
  note?: string | null;
  created_at?: string | null;
  code: string;
}

function VersionsModal({ scriptId, onClose }: { scriptId: string; onClose: () => void }) {
  const versions = useData<{ data: VersionRow[] }>(
    () => get(`/api/v1/scripts/${scriptId}/versions`),
    [scriptId],
  );
  const [view, setView] = useState<string | null>(null);
  const rows = versions.data?.data ?? [];
  return (
    <Modal open onClose={onClose} title="version history" wide>
      {versions.loading && <Spinner />}
      <div className="grid gap-3 md:grid-cols-2">
        <div className="space-y-1.5">
          {rows.map((v) => (
            <button
              key={v.version}
              className={`block w-full border px-3 py-2 text-left text-[11.5px] ${view === v.code ? "border-phosphorDim bg-phosphor/5" : "border-grid hover:border-edge2"}`}
              onClick={() => setView(v.code)}
            >
              <b className="text-phosphorDim">v{v.version}</b>
              <span className="ml-2 text-faint">{fmtTime(v.created_at ?? null)}</span>
              {v.note && <span className="block text-[10.5px] text-muted">{v.note}</span>}
            </button>
          ))}
          {rows.length === 0 && <Empty text="no versions stored" />}
        </div>
        <div>{view !== null ? <Monaco value={view} language="python" height={360} readOnly /> : <Empty text="select a version" />}</div>
      </div>
    </Modal>
  );
}

export default function ScriptLabPage() {
  const { inv, reload: reloadCase } = useCase();
  const toast = useToast();

  const templates = useData<{ templates: Template[] }>(() => get("/api/v1/templates"), []);
  const scripts = useData<{ data: Script[] }>(
    () => get(`/api/v1/investigations/${inv!.id}/scripts`),
    [inv?.id],
  );

  const [activeId, setActiveId] = useState<string | null>(null);
  const [active, setActive] = useState<(Script & { code: string }) | null>(null);
  const [code, setCode] = useState("");
  const [dirty, setDirty] = useState(false);
  const [note, setNote] = useState("");
  const [preview, setPreview] = useState<Template | null>(null);
  const [versionsFor, setVersionsFor] = useState<string | null>(null);
  const [validation, setValidation] = useState<ValidationResult | null>(null);
  const [busy, setBusy] = useState<"" | "validate" | "save" | "run" | "adhoc">("");
  const [exec, setExec] = useState<ExecutionDetail | null>(null);
  const [execLoading, setExecLoading] = useState(false);

  const { connected } = useCaseSocket(inv?.id, useCallback((m: WsMessage) => {
    if (m.type === "SCRIPT_COMPLETE" && typeof m.execution_id === "string") {
      toast("info", `Execution ${String(m.execution_id).slice(0, 8)} â†’ ${String(m.status)} (${String(m.findings ?? 0)} finding(s))`);
      void loadExec(String(m.execution_id));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []));

  async function loadExec(id: string) {
    setExecLoading(true);
    try {
      setExec(await get<ExecutionDetail>(`/api/v1/executions/${id}`));
      reloadCase();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setExecLoading(false);
    }
  }

  async function openScript(id: string) {
    try {
      const s = await get<Script & { code: string }>(`/api/v1/scripts/${id}`);
      setActiveId(s.id);
      setActive(s);
      setCode(s.code);
      setDirty(false);
      setValidation(null);
      setExec(null);
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  useEffect(() => {
    // template-first: if the case already has scripts, open the most recent one
    if (!activeId && scripts.data?.data?.length) void openScript(scripts.data.data[0].id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scripts.data]);

  async function createFromTemplate(tpl: Template, name: string) {
    try {
      const s = await post<Script>(`/api/v1/investigations/${inv!.id}/scripts`, { name, template_id: tpl.id });
      toast("ok", `Script â€œ${s.name}â€ created from template ${tpl.id} â€” review the code, then run it.`);
      setPreview(null);
      scripts.reload();
      await openScript(s.id);
    } catch (e) {
      if (e instanceof ApiError && e.code === "CONFLICT") toast("warn", e.message);
      else toast("err", errMsg(e));
    }
  }

  async function validate() {
    setBusy("validate");
    setValidation(null);
    try {
      const r = await post<ValidateOk>("/api/v1/scripts/validate", { code });
      setValidation({ ...r, valid: true });
    } catch (e) {
      if (e instanceof ApiError && (e.code === "SCRIPT_VALIDATION" || e.code === "VALIDATION_ERROR" || e.status === 422)) {
        const d = (e.details ?? {}) as { problems?: string[]; line?: number };
        setValidation({ valid: false, problems: d.problems ?? [e.message], line: d.line ?? null });
      } else {
        setValidation({ valid: false, problems: [errMsg(e)] });
      }
    } finally {
      setBusy("");
    }
  }

  async function save(): Promise<boolean> {
    if (!active) return false;
    setBusy("save");
    try {
      const s = await put<Script>(`/api/v1/scripts/${active.id}`, { code, note: note.trim() || null });
      setActive({ ...active, ...s, code });
      setDirty(false);
      setNote("");
      scripts.reload();
      toast("ok", `Saved â€” now at version ${s.version}.`);
      return true;
    } catch (e) {
      toast("err", errMsg(e));
      return false;
    } finally {
      setBusy("");
    }
  }

  async function run(adhoc: boolean) {
    setBusy(adhoc ? "adhoc" : "run");
    setExec(null);
    try {
      let r: { execution_id: string; status: string; findings: number; error: string | null };
      if (adhoc) {
        r = await post(`/api/v1/investigations/${inv!.id}/run-adhoc`, { investigation_id: inv!.id, code });
      } else {
        if (dirty && !(await save())) return;
        r = await post(`/api/v1/scripts/${active!.id}/run`, { investigation_id: inv!.id });
      }
      toast(r.status === "COMPLETED" ? "ok" : "warn", `Execution ${r.status}${r.findings ? ` â€” ${r.findings} finding(s)` : ""}`);
      await loadExec(r.execution_id);
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setBusy("");
    }
  }

  const tplList = templates.data?.templates ?? [];
  const grouped = useMemo(() => {
    const g = new Map<string, Template[]>();
    for (const t of tplList) {
      const arr = g.get(t.category) ?? [];
      arr.push(t);
      g.set(t.category, arr);
    }
    return [...g.entries()];
  }, [tplList]);

  if (!inv) return <div className="p-6"><Spinner /></div>;

  return (
    <div className="grid gap-4 xl:grid-cols-4">
      {/* left rail: scripts + templates */}
      <div className="space-y-3 xl:col-span-1">
        <Panel title="case scripts" right={<span className="badge border-edge2 text-faint">{scripts.data?.data.length ?? 0}</span>}>
          <div className="max-h-64 space-y-1 overflow-y-auto p-2">
            {(scripts.data?.data ?? []).map((s) => (
              <button
                key={s.id}
                className={`flex w-full items-center gap-2 border px-2.5 py-1.5 text-left text-[11.5px] transition-colors ${activeId === s.id ? "border-phosphorDim bg-phosphor/10 text-phosphorDim" : "border-transparent text-muted hover:border-edge2 hover:text-ink"}`}
                onClick={() => void openScript(s.id)}
              >
                <FileCode2 size={13} className="shrink-0" />
                <span className="min-w-0 flex-1 truncate">{s.name}</span>
                <span className="badge border-edge2 text-[9px] text-faint">v{s.version}</span>
              </button>
            ))}
            {scripts.loading && <div className="p-2"><Spinner /></div>}
            {!scripts.loading && (scripts.data?.data.length ?? 0) === 0 && (
              <Empty text="no scripts yet" hint="Pick a template below â€” you never start from an empty editor." />
            )}
          </div>
        </Panel>

        <Panel title="template library" variant="cyan" right={<span className="badge border-edge2 text-faint">{tplList.length}</span>}>
          <div className="max-h-[46vh] space-y-3 overflow-y-auto p-2.5">
            {templates.loading && <Spinner label="loading templates" />}
            {grouped.map(([cat, ts]) => (
              <div key={cat}>
                <p className="mb-1 text-[9.5px] font-bold uppercase tracking-[0.22em] text-faint">{cat}</p>
                <div className="space-y-1">
                  {ts.map((t) => (
                    <button
                      key={t.id}
                      className="group flex w-full items-start gap-2 border border-grid bg-panel2/40 px-2.5 py-2 text-left transition-colors hover:border-phosphorDim hover:bg-phosphor/5"
                      onClick={() => setPreview(t)}
                    >
                      <TerminalSquare size={13} className="mt-0.5 shrink-0 text-accent group-hover:text-phosphorDim" />
                      <span className="min-w-0">
                        <span className="block truncate text-[11.5px] font-bold text-ink">{t.title}</span>
                        <span className="block truncate text-[10px] text-faint">{t.description}</span>
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </Panel>
      </div>

      {/* editor + results */}
      <div className="space-y-3 xl:col-span-3">
        {active ? (
          <Panel
            title={
              <span className="flex items-center gap-2">
                forensic function â€” <b className="text-ink">{active.name}</b>
                <span className="badge border-edge2 text-faint">v{active.version}</span>
                {dirty && <span className="badge border-amber/60 text-amber">unsaved edits</span>}
                {active.template_id && <span className="badge border-violetx/50 text-muted">from {active.template_id}</span>}
              </span>
            }
            right={
              <span className="flex items-center gap-2">
                <span className={`led ${connected ? "bg-phosphor" : "bg-faint"}`} title={connected ? "live channel" : "polling"} />
                <button className="text-[10px] uppercase tracking-widest text-faint hover:text-accent" onClick={() => setVersionsFor(active.id)}>
                  <History size={12} className="mr-1 inline" />versions
                </button>
              </span>
            }
          >
            <div className="p-3">
              <Monaco
                value={code}
                onChange={(v) => {
                  setCode(v);
                  setDirty(v !== active.code);
                }}
                language="python"
                height={440}
                line={validation && !validation.valid ? validation.line ?? null : null}
              />

              <div className="mt-2.5 flex flex-wrap items-center gap-2">
                <Btn variant="cyan" busy={busy === "validate"} onClick={() => void validate()}>
                  <ScanSearch size={13} /> validate
                </Btn>
                <Btn variant="ghost" busy={busy === "save"} disabled={!dirty} onClick={() => void save()}>
                  <Save size={13} /> save {dirty ? "â€¢" : ""}
                </Btn>
                <Btn variant="primary" busy={busy === "run"} onClick={() => void run(false)}>
                  <Play size={13} /> save &amp; run
                </Btn>
                <Btn variant="ghost" busy={busy === "adhoc"} onClick={() => void run(true)} title="Run current editor content without saving a version">
                  <Play size={13} /> run unsaved
                </Btn>
                <input
                  className="input ml-auto w-64"
                  placeholder="version note (optional)"
                  value={note}
                  onChange={(e) => setNote(e.target.value)}
                />
              </div>

              {validation && (
                <div className={`mt-2.5 border p-2.5 text-[11.5px] ${validation.valid ? "border-phosphorDim bg-phosphor/5" : "border-alarm bg-alarm/10"}`}>
                  {validation.valid ? (
                    <p className="text-phosphorDim">
                      âœ“ valid â€” entry <b>{validation.entry}</b>() Â· imports [{validation.imports.join(", ") || "none"}] Â· functions [{validation.functions.join(", ")}]
                    </p>
                  ) : (
                    <>
                      <p className="font-bold text-alarm">âœ— validation failed{validation.line ? ` (line ${validation.line})` : ""}</p>
                      <ul className="mt-1 list-inside list-disc space-y-0.5 text-alarm/90">
                        {validation.problems.map((p, i) => (
                          <li key={i}>{p}</li>
                        ))}
                      </ul>
                    </>
                  )}
                </div>
              )}
            </div>
          </Panel>
        ) : (
          <Panel title="forensic function editor">
            <Empty
              text="template-first workspace"
              hint="Select a template from the library to generate a fully-formed forensic function â€” imports, SDK bindings, error handling and forensic context included. You never start from an empty editor."
            />
            <div className="grid gap-2 p-4 sm:grid-cols-2 lg:grid-cols-3">
              {tplList.slice(0, 6).map((t) => (
                <button key={t.id} className="panel group p-3 text-left transition-colors hover:border-phosphorDim" onClick={() => setPreview(t)}>
                  <BookOpenCheck size={15} className="text-accent group-hover:text-phosphorDim" />
                  <p className="mt-1.5 text-[11.5px] font-bold uppercase tracking-wider text-ink">{t.title}</p>
                  <p className="mt-0.5 line-clamp-2 text-[10.5px] text-faint">{t.description}</p>
                </button>
              ))}
            </div>
          </Panel>
        )}

        {/* execution results */}
        <Panel title="execution results" variant="dim">
          {execLoading && <div className="p-4"><Spinner label="sandbox executing â€” validation â†’ policy â†’ rlimit â†’ findings" /></div>}
          {!execLoading && !exec && <Empty text="no execution yet" hint="Run the function above. Results include findings, sandbox console output and real resource usage." />}
          {!execLoading && exec && (
            <div className="space-y-3 p-3">
              <div className="flex flex-wrap items-center gap-2 text-[11.5px]">
                <StatusPill status={exec.status} />
                <span className="text-faint">exec {exec.id.slice(0, 8)}</span>
                <span className="text-faint">{fmtTime(exec.started_at ?? null)}</span>
                {exec.resource_usage?.user_cpu_sec !== undefined && (
                  <span className="badge border-edge2 text-muted">
                    cpu {Number(exec.resource_usage.user_cpu_sec).toFixed(3)}s Â· rss {Number(exec.resource_usage.max_rss_mb ?? 0).toFixed(1)}MB
                  </span>
                )}
                {exec.status === "RUNNING" && (
                  <Btn size="sm" variant="danger" onClick={async () => {
                    try {
                      await post(`/api/v1/executions/${exec.id}/stop`);
                      toast("info", "Stop signal sent to sandbox.");
                      setTimeout(() => void loadExec(exec.id), 1500);
                    } catch (e) {
                      toast("err", errMsg(e));
                    }
                  }}>
                    <Square size={11} /> stop
                  </Btn>
                )}
              </div>

              {exec.error_message && (
                <div className="border border-alarm/60 bg-alarm/10 p-2.5 text-[11.5px] text-alarm">
                  <b>ERROR</b>: {exec.error_message}
                </div>
              )}

              {(exec.findings?.length ?? 0) > 0 && (
                <div>
                  <p className="label">findings ({exec.findings!.length}) â€” each cites real evidence ids</p>
                  <div className="space-y-1.5">
                    {exec.findings!.map((f) => (
                      <div key={f.id} className="border border-grid bg-void/60 p-2.5">
                        <div className="flex flex-wrap items-center gap-2">
                          <SeverityBadge severity={f.severity} />
                          <b className="text-[12px] text-ink">{f.title}</b>
                          <span className="badge border-edge2 text-faint">{f.source}</span>
                        </div>
                        {f.description && <p className="mt-1 text-[11.5px] leading-relaxed text-muted">{f.description}</p>}
                        {f.evidence_ids?.length > 0 && (
                          <p className="mt-1 text-[10.5px] text-faint">
                            evidence: {f.evidence_ids.map((id) => id.slice(0, 8)).join(", ")}
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {(exec.console_log?.length ?? 0) > 0 && (
                <div>
                  <p className="label">sandbox console</p>
                  <pre className="max-h-44 overflow-auto border border-grid bg-void p-2.5 text-[11px] leading-relaxed text-phosphorDim/90">
                    {exec.console_log!.join("\n")}
                  </pre>
                </div>
              )}
            </div>
          )}
        </Panel>
      </div>

      {preview && (
        <TemplatePreview tpl={preview} onClose={() => setPreview(null)} onCreate={(name) => void createFromTemplate(preview, name)} />
      )}
      {versionsFor && <VersionsModal scriptId={versionsFor} onClose={() => setVersionsFor(null)} />}
    </div>
  );
}
