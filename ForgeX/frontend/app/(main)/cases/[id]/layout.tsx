"use client";

// Investigation workspace chrome: investigation header (status, target, actions)
// and section navigation. Case data is fetched once here and shared with every
// section through CaseContext.
import Link from "next/link";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  ArrowLeft,
  Boxes,
  BrainCircuit,
  FileClock,
  FileText,
  ListChecks,
  Microscope,
  Network,
  RotateCcw,
  TerminalSquare,
} from "lucide-react";
import { get, patch } from "@/lib/api";
import { errMsg } from "@/lib/useData";
import { setBreadcrumb } from "@/lib/breadcrumb";
import {
  Alert,
  Btn,
  MetaItem,
  ProvenanceBadge,
  SkeletonRows,
  StatusPill,
  TabNav,
  useToast,
} from "@/components/ui";
import { roleAtLeast, useAuth } from "@/lib/auth";
import type { Investigation } from "@/lib/types";
import { fmtTime } from "@/lib/format";

interface CaseCtx {
  inv: Investigation | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}
const CaseContext = createContext<CaseCtx>({ inv: null, loading: true, error: null, reload: () => {} });
export const useCase = () => useContext(CaseContext);

const TABS = [
  { seg: "", label: "Overview", icon: Microscope },
  { seg: "evidence", label: "Evidence", icon: Boxes },
  { seg: "lab", label: "Script lab", icon: TerminalSquare },
  { seg: "executions", label: "Execution", icon: FileClock },
  { seg: "findings", label: "Findings", icon: ListChecks },
  { seg: "timeline", label: "Timeline", icon: FileText },
  { seg: "graph", label: "Correlation", icon: Network },
  { seg: "ai", label: "Analysis", icon: BrainCircuit },
  { seg: "reports", label: "Reports", icon: FileText },
];

export default function CaseLayout({ children, params }: { children: ReactNode; params: Promise<{ id: string }> }) {
  const [id, setId] = useState<string | null>(null);
  useEffect(() => {
    void params.then((p) => setId(p.id));
  }, [params]);

  const pathname = usePathname();
  const toast = useToast();
  const { user } = useAuth();
  const [inv, setInv] = useState<Investigation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);

  useEffect(() => {
    if (!id) return;
    let alive = true;
    setLoading(true);
    get<Investigation>(`/api/v1/investigations/${id}`)
      .then((d) => {
        if (!alive) return;
        setInv(d);
        setError(null);
      })
      .catch((e) => alive && setError(errMsg(e)))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
  }, [id, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);

  const activeSeg = useMemo(() => {
    if (!id) return "";
    return TABS.filter((t) => t.seg).find((t) => pathname.startsWith(`/cases/${id}/${t.seg}`))?.seg ?? "";
  }, [id, pathname]);

  const tabs = useMemo(
    () =>
      TABS.map((t) => ({
        href: t.seg && id ? `/cases/${id}/${t.seg}` : id ? `/cases/${id}` : "#",
        label: t.label,
        icon: t.icon,
      })),
    [id],
  );

  useEffect(() => {
    if (!id) return;
    setBreadcrumb([
      { label: "Investigations", href: "/cases" },
      ...(inv ? [{ label: inv.name }] : [{ label: id.slice(0, 8) }]),
      ...(activeSeg ? [{ label: TABS.find((t) => t.seg === activeSeg)?.label ?? activeSeg }] : []),
    ]);
    return () => setBreadcrumb([]);
  }, [id, inv, activeSeg]);

  async function setStatus(status: string) {
    if (!inv) return;
    try {
      const updated = await patch<Investigation>(`/api/v1/investigations/${inv.id}/status`, { status });
      setInv(updated);
      toast("ok", `Investigation status → ${status.replace(/_/g, " ").toLowerCase()}.`);
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  if (!id) return <SkeletonRows rows={5} cols={4} />;

  if (error) {
    return (
      <div className="mx-auto max-w-2xl space-y-3">
        <Link
          href="/cases"
          className="inline-flex items-center gap-1.5 text-[12px] text-muted transition-colors duration-[120ms] hover:text-ink"
        >
          <ArrowLeft size={13} /> Case registry
        </Link>
        <Alert tone="danger" title="Investigation unavailable">
          <span className="font-mono text-[11.5px]">{error}</span>
          <p className="mt-1.5 text-[11.5px] opacity-90">
            The investigation does not exist or falls outside your access scope. Operators only read investigations they
            are cleared for.
          </p>
        </Alert>
      </div>
    );
  }

  const canManage = roleAtLeast(user, "LEAD_INVESTIGATOR");
  const closed = inv?.status === "CLOSED";

  return (
    <CaseContext.Provider value={{ inv, loading, error, reload }}>
      <div className="-mx-4 -mt-5 sm:-mx-6 sm:-mt-6">
        {/* ---------- investigation header ---------- */}
        <div className="border-b border-edge bg-abyss px-4 pb-0 pt-4 sm:px-6">
          <Link
            href="/cases"
            className="inline-flex items-center gap-1.5 text-[11.5px] text-muted transition-colors duration-[120ms] hover:text-ink"
          >
            <ArrowLeft size={13} /> Case registry
          </Link>

          {loading && !inv ? (
            <div className="py-4">
              <SkeletonRows rows={2} cols={4} />
            </div>
          ) : inv ? (
            <div className="flex flex-col gap-3 py-3 lg:flex-row lg:items-start lg:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <h1 className="text-[20px] font-semibold leading-tight tracking-[-0.015em] text-ink">{inv.name}</h1>
                  <StatusPill status={inv.status} />
                  <ProvenanceBadge provenance={inv.provenance} />
                </div>
                <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">
                  <MetaItem label="Target" value={inv.target_host} mono />
                  <MetaItem label="OS" value={inv.target_os ?? "—"} />
                  <MetaItem
                    label="Source"
                    value={inv.source_mode === "DATASET" ? `dataset: ${inv.source_path ?? "—"}` : "live local"}
                  />
                  <MetaItem label="Opened" value={fmtTime(inv.created_at)} mono />
                  <MetaItem label="Last activity" value={fmtTime(inv.last_activity ?? null)} mono />
                  <MetaItem label="Evidence" value={inv.evidence_count ?? 0} />
                </div>
              </div>

              {canManage && (
                <div className="flex shrink-0 items-center gap-2">
                  {!closed && inv.status === "OPEN" && (
                    <Btn size="sm" variant="cyan" onClick={() => void setStatus("IN_PROGRESS")}>
                      Mark in progress
                    </Btn>
                  )}
                  {closed ? (
                    <Btn size="sm" icon={<RotateCcw size={13} />} onClick={() => void setStatus("IN_PROGRESS")}>
                      Reopen
                    </Btn>
                  ) : (
                    <Btn size="sm" variant="danger" onClick={() => void setStatus("CLOSED")}>
                      Close investigation
                    </Btn>
                  )}
                </div>
              )}
            </div>
          ) : null}

          <TabNav
            tabs={tabs}
            isActive={(href) => (activeSeg ? href.endsWith(`/${activeSeg}`) : href === `/cases/${id}`)}
          />
        </div>

        {/* ---------- section body ---------- */}
        <div className="px-4 py-5 sm:px-6">{children}</div>
      </div>
    </CaseContext.Provider>
  );
}
