"use client";

// Audit trail: immutable, append-only record of every operator action.
// ADMIN/AUDITOR only (server-enforced; client shows a real permission state).
import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, Download, ShieldAlert } from "lucide-react";
import { download, get, qs } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Panel, Spinner, useToast } from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { AuditRow, Paginated } from "@/lib/types";
import { fmtTime } from "@/lib/format";

const RESULT_STYLE: Record<string, string> = {
  SUCCESS: "text-phosphorDim",
  DENIED: "text-alarm",
  FAILURE: "text-alarm",
};

const KNOWN_ACTIONS = [
  "LOGIN", "LOGOUT", "INVESTIGATION_CREATED", "INVESTIGATION_STATUS_CHANGED",
  "FQL_EXECUTED", "FQL_POLICY_DENIED", "SCRIPT_CREATED", "SCRIPT_UPDATED", "SCRIPT_EXECUTED",
  "EVIDENCE_INGESTED", "EVIDENCE_EXPORTED", "FINDING_STATUS_CHANGED",
  "AI_CORRELATION_REQUESTED", "AI_QUERY", "AI_INDICATOR_PROMOTED",
  "REPORT_REQUESTED", "REPORT_DOWNLOADED", "DEMO_SEEDED", "USER_CREATED", "USER_UPDATED", "POLICY_CREATED",
];

export default function AuditPage() {
  const { user } = useAuth();
  const toast = useToast();
  const [action, setAction] = useState("");
  const [actor, setActor] = useState("");
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<string | null>(null);
  const perPage = 50;

  const list = useData<Paginated<AuditRow>>(
    () => get<Paginated<AuditRow>>(`/api/v1/admin/audit${qs({ action, actor, page, per_page: perPage })}`),
    [action, actor, page],
  );

  if (!user || (user.role !== "ADMIN" && user.role !== "AUDITOR")) {
    return (
      <div className="mx-auto max-w-2xl p-6">
        <Panel className="border-l-2 border-l-alarm p-6">
          <div className="flex items-start gap-3">
            <ShieldAlert size={20} className="mt-0.5 shrink-0 text-alarm" />
            <div>
              <p className="hud-title text-alarm">// permission denied</p>
              <p className="mt-2 text-[12.5px] leading-relaxed text-muted">
                The audit trail is restricted to <b className="text-ink">ADMIN</b> and <b className="text-ink">AUDITOR</b> roles.
                Your current role (<b className="text-accent">{user?.role ?? "anonymous"}</b>) cannot read it â€” this attempt itself would be
                audit-logged server-side. RBAC matrix is documented in Settings.
              </p>
            </div>
          </div>
        </Panel>
      </div>
    );
  }

  const totalPages = Math.max(1, Math.ceil((list.data?.pagination.total ?? 0) / perPage));

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <div>
          <h1 className="hud-title">// audit trail</h1>
          <p className="mt-1 text-[11.5px] text-faint">
            append-only operator log â€” {list.data ? `${list.data.pagination.total} record(s)` : "â€¦"} â€” every login, query, execution, export and status change
          </p>
        </div>
        <div className="flex-1" />
        <select className="select w-64" value={action} onChange={(e) => { setAction(e.target.value); setPage(1); }}>
          <option value="">ALL ACTIONS</option>
          {KNOWN_ACTIONS.map((a) => <option key={a} value={a}>{a}</option>)}
        </select>
        <input className="input w-52" placeholder="actor email containsâ€¦" value={actor} onChange={(e) => { setActor(e.target.value); setPage(1); }} />
        <Btn
          variant="ghost"
          onClick={async () => {
            try {
              await download(`/api/v1/admin/audit/export${qs({ action, actor })}`, "forgex-audit.csv");
              toast("ok", "Audit trail exported (CSV).");
            } catch (e) {
              toast("err", errMsg(e));
            }
          }}
        >
          <Download size={13} /> export csv
        </Btn>
      </div>

      <Panel title="records">
        {list.loading && <div className="p-4"><Spinner label="reading audit ledger" /></div>}
        {list.error && <div className="p-3 text-[12px] text-alarm">âš  {list.error}</div>}
        {(list.data?.data.length ?? 0) === 0 && !list.loading && <Empty text="no audit records match" />}
        {list.data && list.data.data.length > 0 && (
          <>
            <table className="tbl">
              <thead>
                <tr>
                  <th className="w-8" />
                  <th>timestamp</th>
                  <th>actor</th>
                  <th>action</th>
                  <th>resource</th>
                  <th>result</th>
                  <th>ip</th>
                </tr>
              </thead>
              <tbody>
                {list.data.data.map((a) => (
                  <Fragment key={a.id}>
                    <tr className="cursor-pointer" onClick={() => setExpanded(expanded === a.id ? null : a.id)}>
                      <td className="text-faint">{expanded === a.id ? <ChevronDown size={12} /> : <ChevronRight size={12} />}</td>
                      <td className="whitespace-nowrap font-mono text-[11px] text-accent">{fmtTime(a.created_at)}</td>
                      <td>
                        <span className="text-ink">{a.actor_email ?? "system"}</span>
                        {a.actor_role && <span className="ml-1.5 badge border-edge2 text-[9px] text-faint">{a.actor_role}</span>}
                      </td>
                      <td className="font-bold tracking-wide text-ink">{a.action}</td>
                      <td className="max-w-56 truncate font-mono text-[10.5px] text-muted">
                        {a.resource_type ?? "â€”"}{a.resource_id ? `:${a.resource_id.slice(0, 12)}` : ""}
                      </td>
                      <td className={RESULT_STYLE[a.result] ?? "text-muted"}>{a.result}</td>
                      <td className="font-mono text-[10.5px] text-faint">{a.ip_address ?? "â€”"}</td>
                    </tr>
                    {expanded === a.id && (
                      <tr>
                        <td />
                        <td colSpan={6} className="bg-void/60">
                          <pre className="overflow-auto py-1 text-[10.5px] leading-relaxed text-phosphorDim/80">
                            {JSON.stringify(a.metadata ?? {}, null, 2)}
                          </pre>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            <div className="flex items-center justify-between border-t border-edge px-3 py-2 text-[11px] text-faint">
              <span>page {page} / {totalPages}</span>
              <span className="flex gap-2">
                <Btn size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>â—‚ prev</Btn>
                <Btn size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>next â–¸</Btn>
              </span>
            </div>
          </>
        )}
      </Panel>
    </div>
  );
}
