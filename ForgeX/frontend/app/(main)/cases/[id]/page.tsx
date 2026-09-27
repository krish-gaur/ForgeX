"use client";

// Case overview: intent console + evidence posture + integrity ledger.
import dynamic from "next/dynamic";
import Link from "next/link";
import { useState } from "react";
import { BrainCircuit, Boxes, Link2, ListChecks, TerminalSquare } from "lucide-react";
import { get } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, KV, Panel, Spinner, StatusPill, useToast } from "@/components/ui";
import { useCase } from "./layout";
import { fmtTime, shortHash } from "@/lib/format";

const FqlConsole = dynamic(() => import("@/components/FqlConsole"), { ssr: false });

interface ChainVerify {
  valid: boolean;
  records: number;
  broken_at_record_id?: string | null;
  reason?: string | null;
  head_hash?: string | null;
  anchor_backend?: string;
}

function QuickCard({ href, icon: Icon, title, sub }: { href: string; icon: typeof Boxes; title: string; sub: string }) {
  return (
    <Link href={href} className="panel group flex items-center gap-3 p-3.5 transition-colors hover:border-phosphorDim">
      <span className="flex h-9 w-9 items-center justify-center border border-edge2 bg-panel2 text-accent transition-colors group-hover:border-phosphorDim group-hover:text-phosphorDim">
        <Icon size={16} />
      </span>
      <span className="min-w-0">
        <span className="block text-[11px] font-bold uppercase tracking-[0.18em] text-ink">{title}</span>
        <span className="block truncate text-[10.5px] text-faint">{sub}</span>
      </span>
    </Link>
  );
}

export default function CaseOverviewPage() {
  const { inv, loading, reload } = useCase();
  const toast = useToast();
  const [chain, setChain] = useState<ChainVerify | null>(null);
  const [verifying, setVerifying] = useState(false);

  async function verifyChain() {
    if (!inv) return;
    setVerifying(true);
    try {
      setChain(await get<ChainVerify>(`/api/v1/investigations/${inv.id}/anchor-chain/verify`));
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setVerifying(false);
    }
  }

  if (loading && !inv) return <div className="p-6"><Spinner label="loading case workspace" /></div>;
  if (!inv) return <Empty text="case not found" />;

  const byType = inv.evidence_summary?.by_type ?? {};
  const types = Object.entries(byType).sort((a, b) => b[1] - a[1]);

  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Panel title="intent console â€” fql" variant="cyan">
          <div className="p-3">
            <FqlConsole investigationId={inv.id} onCollected={reload} />
          </div>
        </Panel>

        <div className="grid gap-3 sm:grid-cols-2">
          <QuickCard href={`/cases/${inv.id}/lab`} icon={TerminalSquare} title="Script Lab" sub="template-first forensic functions, sandboxed" />
          <QuickCard href={`/cases/${inv.id}/evidence`} icon={Boxes} title="Evidence Vault" sub={`${inv.evidence_summary?.total ?? 0} hashed items`} />
          <QuickCard href={`/cases/${inv.id}/ai`} icon={BrainCircuit} title="AI Analysis" sub="evidence-first correlation & Q&A" />
          <QuickCard href={`/cases/${inv.id}/findings`} icon={ListChecks} title="Findings" sub="verify / dismiss workflow" />
        </div>

        <Panel title="recent collection jobs">
          {(inv.recent_jobs?.length ?? 0) === 0 && <Empty text="no fql jobs yet" hint="Run your first intent above â€” e.g. INVESTIGATE processes." />}
          {(inv.recent_jobs?.length ?? 0) > 0 && (
            <table className="tbl">
              <thead>
                <tr><th>intent</th><th>status</th><th>completed</th></tr>
              </thead>
              <tbody>
                {inv.recent_jobs!.map((j) => (
                  <tr key={j.id}>
                    <td><code className="text-[11.5px] text-phosphorDim">{j.fql}</code></td>
                    <td><StatusPill status={j.status} /></td>
                    <td className="text-faint">{fmtTime(j.completed_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </Panel>
      </div>

      <div className="space-y-4">
        <Panel title="case dossier">
          <div className="p-3">
            <KV k="Case ID" v={<span className="text-[11px]">{inv.id}</span>} mono />
            <KV k="Target" v={inv.target_host} mono />
            <KV k="OS" v={inv.target_os ?? "â€”"} />
            <KV k="Source" v={inv.source_mode === "DATASET" ? `dataset:${inv.source_path ?? "â€”"}` : "live-local"} mono />
            <KV k="Provenance" v={inv.provenance} />
            <KV k="Opened" v={fmtTime(inv.created_at)} mono />
            <KV k="Last activity" v={fmtTime(inv.last_activity ?? null)} mono />
            {inv.description && <p className="mt-2 border-t border-grid pt-2 text-[11.5px] leading-relaxed text-muted">{inv.description}</p>}
          </div>
        </Panel>

        <Panel title="evidence posture">
          <div className="p-3">
            {types.length === 0 && <Empty text="nothing collected yet" />}
            {types.map(([t, n]) => (
              <div key={t} className="mb-1.5">
                <div className="flex justify-between text-[11px]">
                  <span className="text-muted">{t.replace(/_/g, " ").toLowerCase()}</span>
                  <b className="tabular-nums text-ink">{n}</b>
                </div>
                <div className="mt-0.5 h-1.5 border border-grid bg-void">
                  <div className="h-full bg-cyanx/70" style={{ width: `${Math.min(100, (n / Math.max(1, inv.evidence_summary?.total ?? 1)) * 100)}%` }} />
                </div>
              </div>
            ))}
          </div>
        </Panel>

        <Panel title="integrity ledger â€” hash chain" variant="dim">
          <div className="space-y-2 p-3">
            <p className="text-[11px] leading-relaxed text-muted">
              Every evidence item is SHA-256 hashed and anchored to an append-only local hash-chain ledger
              (blockchain-anchored when Sepolia keys are configured). Re-verify the full chain at any time.
            </p>
            <Btn variant="cyan" busy={verifying} onClick={() => void verifyChain()} className="w-full">
              <Link2 size={13} /> verify anchor chain
            </Btn>
            {chain && (
              <div className={`border p-2.5 text-[11.5px] ${chain.valid ? "border-phosphorDim bg-phosphor/5" : "border-alarm bg-alarm/10"}`}>
                <p className={chain.valid ? "font-bold text-phosphorDim" : "font-bold text-alarm"}>
                  {chain.valid ? "âœ“ CHAIN INTACT" : "âœ— CHAIN BROKEN"} â€” {chain.records} record(s)
                </p>
                {chain.anchor_backend && <p className="mt-1 text-faint">backend: {chain.anchor_backend}</p>}
                {chain.head_hash && <p className="mt-1 text-faint">head: {shortHash(chain.head_hash, 16)}</p>}
                {!chain.valid && (
                  <p className="mt-1 text-alarm">
                    broken at {chain.broken_at_record_id ?? "?"} {chain.reason ? `â€” ${chain.reason}` : ""}
                  </p>
                )}
              </div>
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
