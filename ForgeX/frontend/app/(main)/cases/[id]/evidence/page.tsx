"use client";

// Evidence vault: filterable table, detail drawer with live integrity
// re-verification, and authenticated CSV/JSON exports.
import { useMemo, useState } from "react";
import { Boxes, Download, FileJson, ShieldCheck, X } from "lucide-react";
import { download, get, qs } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Panel, ProvenanceBadge, Spinner, TypeBadge, useToast } from "@/components/ui";
import { useCase } from "../layout";
import type { EvidenceItem, Paginated } from "@/lib/types";
import { fmtTime, shortHash } from "@/lib/format";

const TYPES = ["PROCESS", "FILE", "NETWORK_CONNECTION", "SYSTEM_EVENT", "LOG_ENTRY", "USER_ACCOUNT", "REGISTRY", "MEMORY", "BROWSER", "HASH"];

function JsonView({ data }: { data: unknown }) {
  return (
    <pre className="max-h-80 overflow-auto border border-grid bg-void p-2.5 text-[11px] leading-relaxed text-muted">
      {JSON.stringify(data, null, 2)}
    </pre>
  );
}

function DetailDrawer({ id, onClose }: { id: string; onClose: () => void }) {
  const { inv } = useCase();
  const toast = useToast();
  const [verifying, setVerifying] = useState(false);
  const detail = useData<EvidenceItem>(
    () => get<EvidenceItem>(`/api/v1/investigations/${inv!.id}/evidence/${id}`),
    [inv?.id, id],
  );

  async function verify() {
    if (!inv) return;
    setVerifying(true);
    try {
      const d = await get<EvidenceItem>(`/api/v1/investigations/${inv.id}/evidence/${id}?verify=true`);
      const ok = d.integrity?.matches_stored;
      toast(ok ? "ok" : "err", ok ? "Integrity verified â€” recomputed SHA-256 matches the stored hash." : "INTEGRITY MISMATCH â€” evidence was altered after collection!");
      detail.reload();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setVerifying(false);
    }
  }

  const e = detail.data;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-void/70 backdrop-blur-[2px]" onClick={onClose}>
      <aside className="panel h-full w-full max-w-xl overflow-y-auto border-l-2 border-l-cyanx/60" onClick={(ev) => ev.stopPropagation()}>
        <header className="panel-title sticky top-0 z-10 bg-panel">
          <span className="led bg-cyanx " />
          <span className="flex-1 truncate">evidence {shortHash(id, 8)}</span>
          <button className="text-faint hover:text-alarm" onClick={onClose} aria-label="Close">
            <X size={14} />
          </button>
        </header>
        <div className="space-y-3 p-4">
          {detail.loading && <Spinner label="retrieving evidence record" />}
          {detail.error && <p className="text-[12px] text-alarm">âš  {detail.error}</p>}
          {e && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <TypeBadge type={e.evidence_type} />
                <ProvenanceBadge provenance={e.provenance} />
                <span className="badge border-edge2 text-faint">{fmtTime(e.collected_at)}</span>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <Btn variant="cyan" busy={verifying} onClick={() => void verify()}>
                  <ShieldCheck size={13} /> re-verify sha-256
                </Btn>
                <div className={`flex items-center justify-center border px-2 text-[11px] font-bold uppercase tracking-wider ${
                  e.integrity ? (e.integrity.matches_stored ? "border-phosphorDim bg-phosphor/10 text-phosphorDim" : "border-alarm bg-alarm/10 text-alarm") : "border-edge text-faint"
                }`}>
                  {e.integrity ? (e.integrity.matches_stored ? "âœ“ hash intact" : "âœ— tampered") : "not yet verified"}
                </div>
              </div>

              <div className="border border-grid bg-void/60 p-2.5">
                <p className="text-[9.5px] font-bold uppercase tracking-[0.2em] text-faint">stored sha-256</p>
                <p className="mt-0.5 break-all font-mono text-[11px] text-phosphorDim">{e.data_hash}</p>
                {e.integrity?.recomputed_hash && (
                  <>
                    <p className="mt-1.5 text-[9.5px] font-bold uppercase tracking-[0.2em] text-faint">recomputed</p>
                    <p className="mt-0.5 break-all font-mono text-[11px] text-accent">{e.integrity.recomputed_hash}</p>
                  </>
                )}
              </div>

              <div>
                <p className="label">payload</p>
                <JsonView data={e.data} />
              </div>

              <div className="grid grid-cols-2 gap-x-4 text-[11px]">
                <p><span className="text-faint">anchor status:</span> <span className="text-muted">{e.blockchain_status}</span></p>
                {e.blockchain_tx && <p className="truncate"><span className="text-faint">tx:</span> <span className="text-muted">{shortHash(e.blockchain_tx, 12)}</span></p>}
                {e.raw_file_path && <p className="col-span-2 truncate"><span className="text-faint">raw file:</span> <span className="text-muted">{e.raw_file_path}</span></p>}
              </div>
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function EvidencePage() {
  const { inv } = useCase();
  const toast = useToast();
  const [type, setType] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [selected, setSelected] = useState<string | null>(null);
  const perPage = 25;

  const list = useData<Paginated<EvidenceItem>>(
    () =>
      get<Paginated<EvidenceItem>>(
        `/api/v1/investigations/${inv!.id}/evidence${qs({ type, search, page, per_page: perPage })}`,
      ),
    [inv?.id, type, search, page],
  );

  const availableTypes = useMemo(() => {
    const fromSummary = Object.keys(inv?.evidence_summary?.by_type ?? {});
    const merged = new Set([...(fromSummary.length ? fromSummary : TYPES)]);
    return [...merged].sort();
  }, [inv]);

  if (!inv) return <div className="p-6"><Spinner /></div>;

  const totalPages = Math.max(1, Math.ceil((list.data?.pagination.total ?? 0) / perPage));

  async function exportAs(format: "csv" | "json") {
    try {
      await download(`/api/v1/investigations/${inv!.id}/evidence/export?format=${format}`, `${inv!.name}-evidence.${format}`);
      toast("ok", `Evidence exported as ${format.toUpperCase()} (audit-logged).`);
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="hud-title">// evidence vault</h2>
        <span className="text-[11px] text-faint">{list.data ? `${list.data.pagination.total} item(s) â€” hashed, anchored, exportable` : ""}</span>
        <div className="flex-1" />
        <select className="select w-52" value={type} onChange={(e) => { setType(e.target.value); setPage(1); }}>
          <option value="">ALL ARTIFACT TYPES</option>
          {availableTypes.map((t) => (
            <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
          ))}
        </select>
        <input
          className="input w-64"
          placeholder="search payloadsâ€¦"
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
        />
        <Btn variant="ghost" onClick={() => void exportAs("csv")}><Download size={13} /> csv</Btn>
        <Btn variant="ghost" onClick={() => void exportAs("json")}><FileJson size={13} /> json</Btn>
      </div>

      <Panel title="collected artifacts">
        {list.loading && <div className="p-4"><Spinner label="querying evidence vault" /></div>}
        {list.error && <div className="p-3 text-[12px] text-alarm">âš  {list.error}</div>}
        {list.data?.data.length === 0 && (
          <Empty
            text="no evidence matches"
            hint="Collect evidence from the Overview intent console (FQL) or run a forensic function in the Script Lab."
          />
        )}
        {list.data && list.data.data.length > 0 && (
          <>
            <div className="max-h-[62vh] overflow-auto">
              <table className="tbl">
                <thead>
                  <tr>
                    <th>type</th>
                    <th>summary</th>
                    <th>provenance</th>
                    <th>sha-256</th>
                    <th>anchored</th>
                    <th>collected</th>
                  </tr>
                </thead>
                <tbody>
                  {list.data.data.map((e) => {
                    const d = e.data ?? {};
                    const summary =
                      (d.name as string) || (d.path as string) || (d.dst_ip as string) || (d.username as string) ||
                      (d.description as string) || (d.event_type as string) || (d.query as string) || "â€”";
                    return (
                      <tr key={e.id} className="cursor-pointer" onClick={() => setSelected(e.id)}>
                        <td><TypeBadge type={e.evidence_type} /></td>
                        <td className="max-w-72 truncate text-ink" title={JSON.stringify(d)}>{String(summary)}</td>
                        <td><ProvenanceBadge provenance={e.provenance} /></td>
                        <td className="font-mono text-[10.5px] text-muted">{shortHash(e.data_hash, 8)}</td>
                        <td><span className="badge border-edge2 text-faint">{e.blockchain_status}</span></td>
                        <td className="text-faint">{fmtTime(e.collected_at)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div className="flex items-center justify-between border-t border-edge px-3 py-2 text-[11px] text-faint">
              <span>page {page} / {totalPages}</span>
              <span className="flex items-center gap-2">
                <Boxes size={12} className="text-muted" />
                <Btn size="sm" variant="ghost" disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>â—‚ prev</Btn>
                <Btn size="sm" variant="ghost" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>next â–¸</Btn>
              </span>
            </div>
          </>
        )}
      </Panel>

      {selected && <DetailDrawer id={selected} onClose={() => setSelected(null)} />}
    </div>
  );
}
