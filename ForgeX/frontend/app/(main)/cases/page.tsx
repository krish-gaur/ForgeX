"use client";

// Case registry — the authoritative list of investigations, with filtering and
// a guided creation flow (dataset or live-local evidence source).
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { ArrowRight, FolderKanban, Plus, ShieldCheck } from "lucide-react";
import { get, post } from "@/lib/api";
import { useData, errMsg } from "@/lib/useData";
import {
  Alert,
  Btn,
  ChoiceCard,
  Empty,
  ErrorStrip,
  Field,
  Modal,
  PageHeader,
  Panel,
  Pill,
  ProvenanceBadge,
  SearchInput,
  SkeletonTable,
  StatusPill,
  useToast,
} from "@/components/ui";
import { useAuth } from "@/lib/auth";
import type { Dataset, Investigation, Paginated } from "@/lib/types";
import { fmtBytes, fmtTimeShort } from "@/lib/format";

function NewCaseModal({ open, onClose, onCreated }: { open: boolean; onClose: () => void; onCreated: (id: string) => void }) {
  const toast = useToast();
  const datasets = useData<{ datasets: Dataset[] }>(() => get("/api/v1/datasets"), [open]);
  const [name, setName] = useState("");
  const [desc, setDesc] = useState("");
  const [host, setHost] = useState("");
  const [os, setOs] = useState("WINDOWS");
  const [mode, setMode] = useState<"DATASET" | "LIVE_LOCAL">("DATASET");
  const [datasetId, setDatasetId] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (open && datasets.data?.datasets.length && !datasetId) setDatasetId(datasets.data.datasets[0].id);
  }, [open, datasets.data, datasetId]);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const inv = await post<Investigation>("/api/v1/investigations", {
        name: name.trim(),
        description: desc.trim() || null,
        target_host: host.trim(),
        target_os: os,
        source_mode: mode,
        source_path: mode === "DATASET" ? datasetId || null : null,
      });
      toast("ok", `Investigation ${inv.name} opened. Evidence collection is policy-gated.`);
      onCreated(inv.id);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  const selected = datasets.data?.datasets.find((d) => d.id === datasetId);

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Open investigation"
      wide
      footer={
        <>
          <Btn onClick={onClose}>Cancel</Btn>
          <Btn
            variant="primary"
            busy={busy}
            disabled={!name.trim() || !host.trim() || (mode === "DATASET" && !datasetId)}
            onClick={() => void submit()}
            icon={<Plus size={13} />}
          >
            Open investigation
          </Btn>
        </>
      }
    >
      <div className="grid gap-5 md:grid-cols-2">
        <div className="space-y-3">
          <Field label="Investigation name" required>
            <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. DC-01 lateral movement" />
          </Field>
          <Field label="Scope notes" hint="Intake reference, hypothesis, reporting line.">
            <textarea
              className="input min-h-[72px]"
              value={desc}
              onChange={(e) => setDesc(e.target.value)}
              placeholder="Initial assessment and scope boundaries…"
            />
          </Field>
          <Field label="Target host" required hint="Hostname or address of the system under examination.">
            <input className="input font-mono" value={host} onChange={(e) => setHost(e.target.value)} placeholder="ws-01.corp.local" />
          </Field>
          <Field label="Target operating system">
            <select className="select" value={os} onChange={(e) => setOs(e.target.value)}>
              <option value="WINDOWS">Windows</option>
              <option value="LINUX">Linux</option>
              <option value="MACOS">macOS</option>
              <option value="MIXED">Mixed estate</option>
            </select>
          </Field>
        </div>

        <div className="space-y-3">
          <Field label="Evidence source">
            <div className="grid gap-2">
              <ChoiceCard
                active={mode === "DATASET"}
                onClick={() => setMode("DATASET")}
                title="Dataset"
                description="A forensic image export or synthetic corpus. Deterministic and safe for demonstrations."
              />
              <ChoiceCard
                active={mode === "LIVE_LOCAL"}
                onClick={() => setMode("LIVE_LOCAL")}
                title="Live (local)"
                description="Collect from the host running ForgeX — real processes, files and network state."
              />
            </div>
          </Field>

          {mode === "DATASET" && (
            <Field label="Dataset">
              {datasets.data && datasets.data.datasets.length === 0 && (
                <Alert tone="warning" className="mb-2">
                  No datasets found in the vault. Switch to live collection, or place a dataset folder under{" "}
                  <code className="font-mono">datasets/</code>.
                </Alert>
              )}
              <select className="select" value={datasetId} onChange={(e) => setDatasetId(e.target.value)}>
                {(datasets.data?.datasets ?? []).map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.id} — {d.files.length} files, {fmtBytes(d.size_bytes)}
                  </option>
                ))}
              </select>
              {selected && (
                <div className="mt-2 rounded-md border border-edge bg-panel2/50 p-2.5">
                  <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">Manifest</p>
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {selected.files.map((f) => (
                      <span key={f} className="rounded border border-edge bg-panel px-1.5 py-px font-mono text-[10.5px] text-muted">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </Field>
          )}

          <div className="rounded-md border border-edge bg-panel2/50 p-3">
            <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">
              <ShieldCheck size={12} className="text-phosphorDim" />
              Chain of custody
            </p>
            <p className="mt-1.5 text-[11.5px] leading-relaxed text-muted">
              Every item is SHA-256 hashed on collection, anchored to the local hash-chain ledger, and attributable to your
              operator account. Dataset-derived evidence is permanently labelled{" "}
              <ProvenanceBadge provenance="SYNTHETIC" /> or <ProvenanceBadge provenance="LIVE" />.
            </p>
          </div>
        </div>
      </div>

      {err && <ErrorStrip err={err} className="mt-4" />}
    </Modal>
  );
}

function CasesInner() {
  const router = useRouter();
  const params = useSearchParams();
  const toast = useToast();
  const { user } = useAuth();
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [modal, setModal] = useState(params.get("new") === "1");
  const list = useData<Paginated<Investigation>>(
    () =>
      get<Paginated<Investigation>>(
        `/api/v1/investigations?per_page=100${status ? `&status=${status}` : ""}${search ? `&search=${encodeURIComponent(search)}` : ""}`,
      ),
    [status, search],
  );

  const canCreate = user && user.role !== "AUDITOR";

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={<span className="hud-title">Case registry</span>}
        title="Investigations"
        description={
          user?.role === "INVESTIGATOR"
            ? "Scoped to investigations you opened."
            : "All investigations visible at your clearance level."
        }
        actions={
          <>
            <div className="flex items-center gap-2">
              <SearchInput value={search} onChange={setSearch} placeholder="Search investigations…" className="w-56" />
              <select className="select w-40" value={status} onChange={(e) => setStatus(e.target.value)} aria-label="Filter by status">
                <option value="">All statuses</option>
                <option value="OPEN">Open</option>
                <option value="IN_PROGRESS">In progress</option>
                <option value="CLOSED">Closed</option>
              </select>
            </div>
            {canCreate && (
              <Btn variant="primary" icon={<Plus size={13} />} onClick={() => setModal(true)}>
                New investigation
              </Btn>
            )}
          </>
        }
      />

      <Panel
        title="All investigations"
        icon={FolderKanban}
        right={list.data ? <Pill>{list.data.pagination.total} total</Pill> : undefined}
        bodyClass=""
      >
        {list.error ? (
          <div className="p-3">
            <ErrorStrip err={list.error} />
          </div>
        ) : list.loading && !list.data ? (
          <SkeletonTable rows={6} cols={6} />
        ) : (list.data?.data.length ?? 0) === 0 ? (
          <Empty
            text={search || status ? "No investigations match these filters" : "No investigations yet"}
            hint={
              search || status
                ? "Clear the search or status filter to see the full registry."
                : canCreate
                  ? "Open an investigation to begin collecting evidence and running analysis."
                  : "No investigations are visible to your role."
            }
            action={
              canCreate && !search && !status ? (
                <Btn variant="primary" icon={<Plus size={13} />} onClick={() => setModal(true)}>
                  New investigation
                </Btn>
              ) : undefined
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Investigation</th>
                  <th>Target</th>
                  <th>Source</th>
                  <th>Provenance</th>
                  <th>Status</th>
                  <th className="text-right">Evidence</th>
                  <th>Opened</th>
                  <th className="w-8" />
                </tr>
              </thead>
              <tbody>
                {(list.data?.data ?? []).map((c) => (
                  <tr
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/cases/${c.id}`)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && router.push(`/cases/${c.id}`)}
                  >
                    <td>
                      <span className="flex items-center gap-2">
                        <span className="min-w-0">
                          <span className="block truncate font-medium text-ink">{c.name}</span>
                          {c.description && (
                            <span className="block max-w-sm truncate text-[11px] text-faint">{c.description}</span>
                          )}
                        </span>
                        {c.open_jobs ? (
                          <Pill className="border-cyanEdge bg-cyanSoft text-cyanx">{c.open_jobs} running</Pill>
                        ) : null}
                      </span>
                    </td>
                    <td className="whitespace-nowrap font-mono text-[11.5px] text-muted">{c.target_host}</td>
                    <td className="whitespace-nowrap text-[11.5px] text-muted">
                      {c.source_mode === "DATASET" ? `dataset: ${c.source_path ?? "—"}` : "live local"}
                    </td>
                    <td>
                      <ProvenanceBadge provenance={c.provenance} />
                    </td>
                    <td>
                      <StatusPill status={c.status} />
                    </td>
                    <td className="text-right tabular-nums">{c.evidence_count ?? 0}</td>
                    <td className="whitespace-nowrap font-mono text-[11px] text-faint">{fmtTimeShort(c.created_at)}</td>
                    <td className="text-right">
                      <ArrowRight size={13} className="inline text-faint" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {canCreate && (
        <NewCaseModal
          open={modal}
          onClose={() => {
            setModal(false);
            if (params.get("new") === "1") router.replace("/cases");
          }}
          onCreated={(id) => {
            setModal(false);
            toast("info", "Investigation opened. Next: run an FQL intent or a forensic function.");
            router.push(`/cases/${id}`);
          }}
        />
      )}
    </div>
  );
}

export default function CasesPage() {
  return (
    <Suspense fallback={<div className="p-6 text-[12px] text-muted">Loading registry…</div>}>
      <CasesInner />
    </Suspense>
  );
}
