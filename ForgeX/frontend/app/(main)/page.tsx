"use client";

// Overview — the operator's starting point. Answers four questions in order:
// what is happening, what needs attention, what was investigated recently,
// and is the system healthy. All figures come from the real stats + registry APIs.
import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Activity,
  AlertOctagon,
  ArrowRight,
  Boxes,
  FolderKanban,
  PlayCircle,
  TerminalSquare,
  Zap,
} from "lucide-react";
import { get, post } from "@/lib/api";
import { useData, errMsg } from "@/lib/useData";
import {
  Alert,
  Btn,
  Empty,
  ErrorStrip,
  Meter,
  PageHeader,
  Panel,
  Pill,
  ProvenanceBadge,
  SkeletonRows,
  SkeletonTable,
  StatTile,
  StatusPill,
  Timeline,
  TimelineItem,
  useToast,
} from "@/components/ui";
import { roleAtLeast, useAuth } from "@/lib/auth";
import type { DashboardStats, Investigation, Paginated } from "@/lib/types";
import { SEVERITY_ORDER, fmtTimeShort } from "@/lib/format";

const SEV_COLOR: Record<string, string> = {
  CRITICAL: "bg-alarm",
  HIGH: "bg-[#F97316]",
  MEDIUM: "bg-amber",
  LOW: "bg-cyanx",
  INFO: "bg-faint",
};
const SEV_TEXT: Record<string, string> = {
  CRITICAL: "text-alarm",
  HIGH: "text-[#C2410C]",
  MEDIUM: "text-amber",
  LOW: "text-cyanx",
  INFO: "text-muted",
};

function SeveritySplit({ dist, total }: { dist: Record<string, number>; total: number }) {
  const present = SEVERITY_ORDER.filter((s) => (dist[s] ?? 0) > 0);
  if (total === 0) {
    return <Empty compact text="No findings recorded" hint="Findings appear once a forensic function produces them." />;
  }
  return (
    <div className="space-y-2.5">
      <div className="flex h-2 w-full overflow-hidden rounded-full bg-panel2">
        {present.map((s) => (
          <span
            key={s}
            className={SEV_COLOR[s]}
            style={{ width: `${((dist[s] ?? 0) / total) * 100}%` }}
            title={`${s}: ${dist[s]}`}
          />
        ))}
      </div>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1 sm:grid-cols-3">
        {SEVERITY_ORDER.map((s) => (
          <li key={s} className="flex items-center gap-1.5 text-[11.5px]">
            <span className={clsxLed(SEV_COLOR[s])} />
            <span className="font-medium text-muted">{s}</span>
            <span className="ml-auto tabular-nums text-ink">{dist[s] ?? 0}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function clsxLed(bg: string): string {
  return `inline-block h-1.5 w-1.5 shrink-0 rounded-full ${bg}`;
}

function ExecutionHistory({ rows }: { rows: Array<{ date: string; count: number }> }) {
  if (rows.length === 0) {
    return <Empty compact text="No executions recorded" hint="Execution volume will appear here as investigations run." />;
  }
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <div className="flex h-20 items-end gap-1">
      {rows.map((r) => (
        <div key={r.date} className="group relative flex-1" title={`${r.date}: ${r.count} executions`}>
          <div
            className="w-full rounded-sm bg-accent/25 transition-colors duration-[120ms] group-hover:bg-accent/60"
            style={{ height: `${Math.max(3, (r.count / max) * 74)}px` }}
          />
        </div>
      ))}
    </div>
  );
}

/** Items that genuinely need an operator decision, derived from real state. */
function buildAttention(
  cases: Investigation[],
  stats: DashboardStats | null,
): Array<{ id: string; severity: "CRITICAL" | "HIGH" | "MEDIUM"; title: string; detail: string; href: string }> {
  const out: Array<{ id: string; severity: "CRITICAL" | "HIGH" | "MEDIUM"; title: string; detail: string; href: string }> = [];

  if (stats && stats.high_severity_findings > 0) {
    out.push({
      id: "sev-findings",
      severity: "CRITICAL",
      title: `${stats.high_severity_findings} high or critical finding${stats.high_severity_findings === 1 ? "" : "s"} unreviewed`,
      detail: "Findings must be verified or dismissed before an investigation can be closed.",
      href: "/cases",
    });
  }

  for (const c of cases) {
    if (c.open_jobs) {
      out.push({
        id: `jobs-${c.id}`,
        severity: "MEDIUM",
        title: `${c.name}: ${c.open_jobs} collection job${c.open_jobs === 1 ? "" : "s"} in flight`,
        detail: `Target ${c.target_host} · evidence collection has not settled.`,
        href: `/cases/${c.id}`,
      });
    }
    if (c.status === "OPEN" && (c.evidence_count ?? 0) === 0) {
      out.push({
        id: `empty-${c.id}`,
        severity: "HIGH",
        title: `${c.name}: opened with no evidence`,
        detail: "Run an FQL intent or a forensic function to begin collection.",
        href: `/cases/${c.id}`,
      });
    }
  }

  const rank = { CRITICAL: 0, HIGH: 1, MEDIUM: 2 } as const;
  return out.sort((a, b) => rank[a.severity] - rank[b.severity]).slice(0, 6);
}

export default function DashboardPage() {
  const toast = useToast();
  const router = useRouter();
  const { user } = useAuth();
  const stats = useData<DashboardStats>(() => get<DashboardStats>("/api/v1/stats/overview"), []);
  const cases = useData<Paginated<Investigation>>(() => get<Paginated<Investigation>>("/api/v1/investigations?per_page=8"), []);
  const [seeding, setSeeding] = useState(false);

  async function seedDemo() {
    setSeeding(true);
    try {
      const r = await post<{ investigation_id: string; case: string }>("/api/v1/demo/seed");
      toast("ok", `Demo investigation ${r.case} seeded — all records labelled synthetic.`);
      stats.reload();
      cases.reload();
      router.push(`/cases/${r.investigation_id}`);
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setSeeding(false);
    }
  }

  const s = stats.data;
  const rows = cases.data?.data ?? [];
  const attention = buildAttention(rows, s);
  const findingsTotal = s ? SEVERITY_ORDER.reduce((a, k) => a + (s.severity_distribution?.[k] ?? 0), 0) : 0;

  return (
    <div className="space-y-5">
      <PageHeader
        eyebrow={
          <>
            <span className="hud-title">ForgeX</span>
            <span className="text-[11px] text-faint">Security investigation workspace</span>
          </>
        }
        title={`Good ${greeting()}, ${user?.username ?? "operator"}`}
        description="Live posture across the case registry, evidence vault and execution pipeline. Every figure is computed from stored records."
        actions={
          <>
            <Btn variant="ghost" icon={<TerminalSquare size={13} />} onClick={() => router.push("/templates")}>
              Function templates
            </Btn>
            <Btn variant="primary" icon={<FolderKanban size={13} />} onClick={() => router.push("/cases?new=1")}>
              New investigation
            </Btn>
          </>
        }
      />

      {stats.error && <ErrorStrip err={stats.error} />}

      {/* ---------- system overview ---------- */}
      <section aria-label="System overview">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="hud-title">System overview</h2>
          {s && (
            <span className="text-[11px] text-faint">
              {s.active_cases} active · {s.evidence_items} evidence items · {s.executions} executions
            </span>
          )}
        </div>
        {stats.loading && !s ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="rounded-lg border border-edge bg-panel p-3.5 shadow-panel">
                <div className="h-2.5 w-20 rounded bg-panel2" />
                <div className="mt-2.5 h-6 w-12 rounded bg-panel2" />
              </div>
            ))}
          </div>
        ) : s ? (
          <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
            <StatTile
              label="Active investigations"
              value={s.active_cases}
              icon={FolderKanban}
              hint="open or in progress"
            />
            <StatTile label="Evidence collected" value={s.evidence_items} icon={Boxes} hint="hashed and anchored" />
            <StatTile label="Executions" value={s.executions} icon={PlayCircle} hint="sandboxed function runs" />
            <StatTile label="Findings" value={s.findings} icon={Activity} hint="evidence-cited" />
            <StatTile
              label="Requires review"
              value={s.high_severity_findings}
              icon={AlertOctagon}
              tone={s.high_severity_findings > 0 ? "danger" : "neutral"}
              hint={s.high_severity_findings > 0 ? "high or critical" : "nothing outstanding"}
            />
          </div>
        ) : null}
      </section>

      {/* ---------- distribution + volume ---------- */}
      {s && (
        <div className="grid gap-3 lg:grid-cols-3">
          <Panel title="Finding severity" className="lg:col-span-1" icon={AlertOctagon}>
            <SeveritySplit dist={s.severity_distribution ?? {}} total={findingsTotal} />
          </Panel>
          <Panel title="Evidence by category" className="lg:col-span-1" icon={Boxes}>
            <CategoryBreakdown cats={s.artifact_categories ?? {}} total={s.evidence_items} />
          </Panel>
          <Panel title="Execution volume" className="lg:col-span-1" icon={Activity}>
            <ExecutionHistory rows={s.execution_history ?? []} />
          </Panel>
        </div>
      )}

      {/* ---------- attention required ---------- */}
      <section aria-label="Attention required">
        <div className="mb-2 flex items-center justify-between">
          <h2 className="hud-title">Requires attention</h2>
          {attention.length > 0 && <Pill>{attention.length} item{attention.length === 1 ? "" : "s"}</Pill>}
        </div>
        {cases.loading && !cases.data ? (
          <div className="rounded-lg border border-edge bg-panel p-3 shadow-panel">
            <SkeletonRows rows={3} cols={3} />
          </div>
        ) : attention.length === 0 ? (
          <Alert tone="success" title="Nothing outstanding">
            No unverified high-severity findings, stalled collection jobs, or empty investigations in the current view.
          </Alert>
        ) : (
          <ul className="divide-y divide-grid overflow-hidden rounded-lg border border-edge bg-panel shadow-panel">
            {attention.map((a) => (
              <li key={a.id}>
                <Link
                  href={a.href}
                  className="flex items-start gap-3 px-3 py-2.5 transition-colors duration-[120ms] hover:bg-[#F7F9FC]"
                >
                  <span
                    className={`mt-1 h-2 w-2 shrink-0 rounded-full ${
                      a.severity === "CRITICAL" ? "bg-alarm" : a.severity === "HIGH" ? "bg-[#F97316]" : "bg-amber"
                    }`}
                  />
                  <span className="min-w-0 flex-1">
                    <span className={`block text-[12.5px] font-medium ${SEV_TEXT[a.severity]}`}>{a.title}</span>
                    <span className="block text-[11.5px] leading-relaxed text-muted">{a.detail}</span>
                  </span>
                  <ArrowRight size={14} className="mt-1 shrink-0 text-faint" />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* ---------- recent investigations ---------- */}
      <Panel
        title="Recent investigations"
        icon={FolderKanban}
        right={
          <Link
            href="/cases"
            className="flex items-center gap-1 text-[11px] font-medium text-accent transition-colors duration-[120ms] hover:text-[#1D4ED8]"
          >
            View registry <ArrowRight size={12} />
          </Link>
        }
        bodyClass=""
      >
        {cases.loading && !cases.data ? (
          <SkeletonTable rows={5} cols={6} />
        ) : cases.data?.data.length === 0 ? (
          <Empty
            text="No investigations yet"
            hint="Create an investigation to begin collecting evidence and running analysis."
            action={
              <Btn variant="primary" icon={<FolderKanban size={13} />} onClick={() => router.push("/cases?new=1")}>
                New investigation
              </Btn>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="tbl">
              <thead>
                <tr>
                  <th>Investigation</th>
                  <th>Target</th>
                  <th>Status</th>
                  <th>Provenance</th>
                  <th className="text-right">Evidence</th>
                  <th>Last activity</th>
                </tr>
              </thead>
              <tbody>
                {(cases.data?.data ?? []).map((c) => (
                  <tr
                    key={c.id}
                    className="cursor-pointer"
                    onClick={() => router.push(`/cases/${c.id}`)}
                    tabIndex={0}
                    onKeyDown={(e) => e.key === "Enter" && router.push(`/cases/${c.id}`)}
                  >
                    <td>
                      <span className="flex items-center gap-2">
                        <span className="truncate font-medium text-ink">{c.name}</span>
                        {c.open_jobs ? <Pill className="border-cyanEdge bg-cyanSoft text-cyanx">{c.open_jobs} running</Pill> : null}
                      </span>
                    </td>
                    <td className="font-mono text-[11.5px] text-muted">{c.target_host}</td>
                    <td>
                      <StatusPill status={c.status} />
                    </td>
                    <td>
                      <ProvenanceBadge provenance={c.provenance} />
                    </td>
                    <td className="text-right tabular-nums">{c.evidence_count ?? 0}</td>
                    <td className="whitespace-nowrap font-mono text-[11px] text-faint">
                      {fmtTimeShort(c.last_activity ?? c.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      {/* ---------- recent activity ---------- */}
      <div className="grid gap-3 lg:grid-cols-2">
        <Panel title="Collection activity" icon={Activity}>
          <ActivityFeed cases={rows} />
        </Panel>
        <Panel title="System" icon={Activity} variant="muted">
          <dl className="space-y-2 text-[12px]">
            {[
              ["Executions recorded", s?.executions],
              ["Findings recorded", s?.findings],
              ["Evidence items", s?.evidence_items],
              ["Artifacts by category", Object.keys(s?.artifact_categories ?? {}).length],
            ].map(([k, v]) => (
              <div key={String(k)} className="flex items-center justify-between border-b border-grid pb-2 last:border-b-0">
                <dt className="text-muted">{k}</dt>
                <dd className="font-medium tabular-nums text-ink">{v ?? "—"}</dd>
              </div>
            ))}
          </dl>
          {roleAtLeast(user, "LEAD_INVESTIGATOR") && (
            <div className="mt-3 border-t border-edge pt-3">
              <p className="text-[11.5px] leading-relaxed text-muted">
                Seed the deterministic breach scenario to load a complete investigation: processes, authentication logs,
                network captures, registry, browser and memory artifacts.
              </p>
              <Btn className="mt-2" variant="ghost" busy={seeding} icon={<Zap size={13} />} onClick={() => void seedDemo()}>
                Seed demo investigation
              </Btn>
            </div>
          )}
        </Panel>
      </div>
    </div>
  );
}

function CategoryBreakdown({ cats, total }: { cats: Record<string, number>; total: number }) {
  const entries = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 7);
  if (entries.length === 0) {
    return <Empty compact text="No artifacts collected" hint="Evidence appears here once collection runs." />;
  }
  return (
    <ul className="space-y-2">
      {entries.map(([k, v]) => (
        <li key={k} className="flex items-center gap-2.5">
          <span className="w-[104px] shrink-0 truncate text-[11.5px] text-muted">{k.replace(/_/g, " ").toLowerCase()}</span>
          <span className="flex-1">
            <Meter pct={(v / Math.max(1, total)) * 100} tone="accent" />
          </span>
          <span className="w-8 shrink-0 text-right text-[11.5px] font-medium tabular-nums text-ink">{v}</span>
        </li>
      ))}
    </ul>
  );
}

function ActivityFeed({ cases }: { cases: Investigation[] }) {
  const items = cases
    .flatMap((c) => [
      { key: `${c.id}-a`, at: c.last_activity, label: c.name, detail: `Last activity on ${c.target_host}`, href: `/cases/${c.id}` },
      { key: `${c.id}-b`, at: c.created_at, label: c.name, detail: "Investigation opened", href: `/cases/${c.id}` },
    ])
    .filter((i) => !!i.at)
    .sort((a, b) => (b.at ?? "").localeCompare(a.at ?? ""))
    .slice(0, 7);

  if (items.length === 0) {
    return <Empty compact text="No recorded activity" hint="Collection runs and status changes will appear here." />;
  }

  return (
    <Timeline>
      {items.map((i, idx) => (
        <TimelineItem
          key={i.key}
          last={idx === items.length - 1}
          dot={idx === 0 ? "accent" : "neutral"}
          title={
            <Link href={i.href} className="transition-colors duration-[120ms] hover:text-accent">
              {i.label}
            </Link>
          }
          meta={fmtTimeShort(i.at)}
        >
          {i.detail}
        </TimelineItem>
      ))}
    </Timeline>
  );
}

function greeting(): string {
  const h = new Date().getHours();
  if (h < 12) return "morning";
  if (h < 18) return "afternoon";
  return "evening";
}
