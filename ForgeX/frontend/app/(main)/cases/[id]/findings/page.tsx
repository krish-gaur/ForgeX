"use client";

// Findings review workflow: OPEN →’ VERIFIED / DISMISSED, grouped by severity,
// every finding cites the real evidence ids it was derived from.
import { useMemo, useState } from "react";
import Link from "next/link";
import { CheckCircle2, ListChecks, ShieldX, XCircle } from "lucide-react";
import { get, patch } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Panel, SeverityBadge, Spinner, StatusPill, useToast } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import { useCase } from "../layout";
import type { Finding } from "@/lib/types";
import { SEVERITY_ORDER, fmtTime, shortHash } from "@/lib/format";

export default function FindingsPage() {
  const { inv, reload } = useCase();
  const { user } = useAuth();
  const toast = useToast();
  const [sev, setSev] = useState("");
  const [status, setStatus] = useState("");
  const [busyId, setBusyId] = useState<string | null>(null);

  const list = useData<{ data: Finding[] }>(
    () => get(`/api/v1/investigations/${inv!.id}/findings${sev ? `?severity=${sev}` : ""}${status ? `${sev ? "&" : "?"}status=${status}` : ""}`),
    [inv?.id, sev, status],
  );

  const grouped = useMemo(() => {
    const g = new Map<string, Finding[]>();
    for (const s of SEVERITY_ORDER) g.set(s, []);
    for (const f of list.data?.data ?? []) {
      const arr = g.get(f.severity);
      if (arr) arr.push(f);
      else g.set(f.severity, [f]);
    }
    return [...g.entries()].filter(([, v]) => v.length > 0);
  }, [list.data]);

  const canEdit = user && user.role !== "AUDITOR";

  async function setFindingStatus(f: Finding, next: string) {
    setBusyId(f.id);
    try {
      await patch(`/api/v1/findings/${f.id}`, { status: next });
      toast("ok", `Finding ${next.toLowerCase()} (audit-logged).`);
      list.reload();
      reload();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setBusyId(null);
    }
  }

  if (!inv) return <div className="p-6"><Spinner /></div>;

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="hud-title">// findings review</h2>
        <span className="text-[11px] text-faint">{list.data?.data.length ?? 0} finding(s) — evidence-cited, never fabricated</span>
        <div className="flex-1" />
        <select className="select w-40" value={sev} onChange={(e) => setSev(e.target.value)}>
          <option value="">ALL SEVERITIES</option>
          {SEVERITY_ORDER.map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        <select className="select w-40" value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">ALL STATUSES</option>
          <option value="OPEN">OPEN</option>
          <option value="VERIFIED">VERIFIED</option>
          <option value="DISMISSED">DISMISSED</option>
        </select>
      </div>

      {list.loading && <Panel className="p-4"><Spinner label="loading findings" /></Panel>}
      {list.error && <p className="border border-alarm/50 bg-alarm/10 px-3 py-2 text-[12px] text-alarm">⚠ {list.error}</p>}
      {!list.loading && (list.data?.data.length ?? 0) === 0 && (
        <Panel>
          <Empty
            text="no findings"
            hint="Findings appear after forensic function runs (Script Lab) or when AI indicators are promoted to findings."
          />
        </Panel>
      )}

      {grouped.map(([severity, findings]) => (
        <Panel key={severity} title={<span className="flex items-center gap-2"><SeverityBadge severity={severity} /> {findings.length} finding(s)</span>}>
          <div className="divide-y divide-grid">
            {findings.map((f) => (
              <div key={f.id} className="p-3">
                <div className="flex flex-wrap items-center gap-2">
                  <ListChecks size={14} className={f.status === "VERIFIED" ? "text-phosphorDim" : f.status === "DISMISSED" ? "text-faint" : "text-amber"} />
                  <b className="text-[12.5px] text-ink">{f.title}</b>
                  <StatusPill status={f.status} />
                  <span className="badge border-violetx/50 text-muted">{f.source}</span>
                  {f.mitre_techniques?.length ? (
                    <span className="badge border-edge2 text-muted">{f.mitre_techniques.join(" · ")}</span>
                  ) : null}
                  <span className="ml-auto text-[10.5px] text-faint">{fmtTime(f.created_at)}</span>
                </div>
                {f.description && <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">{f.description}</p>}
                {f.evidence_ids?.length > 0 && (
                  <p className="mt-1.5 text-[10.5px] text-faint">
                    cites evidence:{" "}
                    {f.evidence_ids.map((id) => (
                      <Link key={id} href={`/cases/${inv.id}/evidence`} className="mr-1.5 font-mono text-muted hover:text-phosphorDim hover:underline" title={id}>
                        {shortHash(id, 4)}
                      </Link>
                    ))}
                  </p>
                )}
                {canEdit && f.status !== "VERIFIED" && f.status !== "DISMISSED" && (
                  <div className="mt-2 flex gap-2">
                    <Btn size="sm" variant="primary" busy={busyId === f.id} onClick={() => void setFindingStatus(f, "VERIFIED")}>
                      <CheckCircle2 size={11} /> verify
                    </Btn>
                    <Btn size="sm" variant="danger" busy={busyId === f.id} onClick={() => void setFindingStatus(f, "DISMISSED")}>
                      <XCircle size={11} /> dismiss
                    </Btn>
                  </div>
                )}
                {canEdit && (f.status === "VERIFIED" || f.status === "DISMISSED") && (
                  <div className="mt-2">
                    <Btn size="sm" variant="ghost" busy={busyId === f.id} onClick={() => void setFindingStatus(f, "OPEN")}>
                      <ShieldX size={11} /> reopen
                    </Btn>
                  </div>
                )}
              </div>
            ))}
          </div>
        </Panel>
      ))}
    </div>
  );
}
