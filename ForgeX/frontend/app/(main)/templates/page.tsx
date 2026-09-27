"use client";

// Global Template Library: the 10 ready-made forensic function templates with
// full source preview, copy-to-clipboard, and deep links into a case's Script Lab.
import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Copy, TerminalSquare } from "lucide-react";
import { get } from "@/lib/api";
import { useData } from "@/lib/useData";
import { Btn, Empty, Modal, Panel, Spinner, useToast } from "@/components/ui";
import type { Investigation, Paginated, Template } from "@/lib/types";

const Monaco = dynamic(() => import("@/components/Monaco"), { ssr: false });

const TEMPLATE_DOCS: Record<string, { sdk: string[]; output: string }> = {
  "windows-event-analysis": { sdk: ["forgex.events()", "forgex.finding()", "forgex.log()"], output: "Findings for auth anomalies, privilege use, log clearing" },
  "registry-analysis": { sdk: ["forgex.registry()", "forgex.finding()"], output: "Persistence / Run-key findings with evidence citations" },
  "file-metadata-analysis": { sdk: ["forgex.files()", "forgex.metadata()", "forgex.hash.verify()"], output: "Suspicious-path & timestamp-anomaly findings" },
  "network-artifact-analysis": { sdk: ["forgex.network()", "forgex.finding()"], output: "C2, exfil and lateral-movement connection findings" },
  "process-analysis": { sdk: ["forgex.processes()", "forgex.finding()"], output: "Encoded commands, LOLBins, suspicious parentâ†’child chains" },
  "memory-analysis": { sdk: ["forgex.memory()", "forgex.finding()"], output: "Injection / suspicious in-memory artifact findings" },
  "browser-artifact-analysis": { sdk: ["forgex.browser()", "forgex.finding()"], output: "Malicious download & C2-visit findings" },
  "timeline-generation": { sdk: ["forgex.timeline()", "forgex.artifact()"], output: "Unified cross-artifact timeline artifacts" },
  "hash-verification": { sdk: ["forgex.hash.verify()", "forgex.chain_of_custody()"], output: "Integrity pass/fail findings per artifact" },
  "custom-function": { sdk: ["full forgex SDK surface"], output: "Your hypothesis, your logic â€” sandbox-enforced" },
};

export default function TemplatesPage() {
  const toast = useToast();
  const templates = useData<{ templates: Template[] }>(() => get("/api/v1/templates"), []);
  const cases = useData<Paginated<Investigation>>(() => get<Paginated<Investigation>>("/api/v1/investigations?per_page=50"), []);
  const [preview, setPreview] = useState<Template | null>(null);

  const grouped = useMemo(() => {
    const g = new Map<string, Template[]>();
    for (const t of templates.data?.templates ?? []) {
      g.set(t.category, [...(g.get(t.category) ?? []), t]);
    }
    return [...g.entries()];
  }, [templates.data]);

  async function copy(t: Template) {
    try {
      await navigator.clipboard.writeText(t.code);
      toast("ok", `${t.title} source copied â€” paste it into a case's Script Lab (or create from template there).`);
    } catch {
      toast("err", "Clipboard unavailable in this browser context.");
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4">
      <div>
        <h1 className="hud-title">// template library â€” forensic functions</h1>
        <p className="mt-1 max-w-3xl text-[11.5px] leading-relaxed text-faint">
          Ten production-shaped templates for the <code className="text-phosphorDim">forgex</code> SDK. Each ships with
          imports, entry-point structure, parameters, expected output, examples, error handling and forensic context â€”
          the Script Lab instantiates them into editable, sandboxed scripts. Nothing here is a stub: every API shown is
          backed by the real collector/evidence/hash subsystem.
        </p>
      </div>

      {templates.loading && <Panel className="p-6"><Spinner label="loading template vault" /></Panel>}
      {templates.error && <p className="border border-alarm/50 bg-alarm/10 px-3 py-2 text-[12px] text-alarm">âš  {templates.error}</p>}

      {grouped.map(([cat, ts]) => (
        <div key={cat}>
          <p className="mb-2 text-[10px] font-bold uppercase tracking-[0.25em] text-faint">{cat}</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {ts.map((t) => {
              const docs = TEMPLATE_DOCS[t.id];
              return (
                <Panel key={t.id} className="flex flex-col p-4 transition-colors hover:border-phosphorDim">
                  <div className="flex items-start gap-2.5">
                    <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center border border-edge2 bg-panel2 text-accent">
                      <TerminalSquare size={15} />
                    </span>
                    <div className="min-w-0">
                      <p className="truncate text-[12.5px] font-bold uppercase tracking-wider text-ink">{t.title}</p>
                      <p className="font-mono text-[10px] text-muted">{t.id} Â· PYFUNC</p>
                    </div>
                  </div>
                  <p className="mt-2 flex-1 text-[11px] leading-relaxed text-muted">{t.description}</p>
                  {docs && (
                    <div className="mt-2 border-t border-grid pt-2 text-[10px] text-faint">
                      <p><b className="text-muted">sdk:</b> {docs.sdk.join(" Â· ")}</p>
                      <p className="mt-0.5"><b className="text-muted">produces:</b> {docs.output}</p>
                    </div>
                  )}
                  <div className="mt-3 flex gap-2">
                    <Btn size="sm" variant="cyan" onClick={() => setPreview(t)}>view source</Btn>
                    <Btn size="sm" variant="ghost" onClick={() => void copy(t)}><Copy size={11} /> copy</Btn>
                    {cases.data?.data[0] && (
                      <a href={`/cases/${cases.data.data[0].id}/lab`} className="btn-ghost btn-sm ml-auto">
                        open in lab â–¸
                      </a>
                    )}
                  </div>
                </Panel>
              );
            })}
          </div>
        </div>
      ))}

      {!templates.loading && (templates.data?.templates.length ?? 0) === 0 && (
        <Panel><Empty text="template vault empty" hint="backend/templates/functions/*.py not found â€” check TEMPLATE_DIR setting." /></Panel>
      )}

      {preview && (
        <Modal open onClose={() => setPreview(null)} title={`${preview.title} â€” full source`} wide>
          <div className="mb-2 flex items-center gap-2">
            <span className="badge border-cyanx/50 text-accent">{preview.category}</span>
            <span className="text-[11px] text-faint">{preview.description}</span>
            <div className="flex-1" />
            <Btn size="sm" variant="ghost" onClick={() => void copy(preview)}><Copy size={11} /> copy</Btn>
          </div>
          <Monaco value={preview.code} language="python" height={520} readOnly />
        </Modal>
      )}
    </div>
  );
}
