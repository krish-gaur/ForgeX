"use client";

// App chrome: left navigation rail, top bar (breadcrumb / command entry / operator),
// and a fixed operator + system-status footer. Collapses to an off-canvas rail
// below the lg breakpoint.
import clsx from "clsx";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  ChevronDown,
  FolderKanban,
  LayoutDashboard,
  LogOut,
  Menu,
  PanelLeftClose,
  ScrollText,
  Settings,
  ShieldCheck,
  TerminalSquare,
  X,
} from "lucide-react";
import { useAuth } from "@/lib/auth";
import { useBreadcrumbTrail, type Crumb } from "@/lib/breadcrumb";
import { Dropdown, MenuItem, StatusDot, Tooltip } from "@/components/ui";
import CommandSearch from "@/components/CommandSearch";

const VERSION = "1.0.0";

interface NavItem {
  href: string;
  label: string;
  icon: typeof LayoutDashboard;
  exact?: boolean;
  roles?: readonly string[];
  hint?: string;
}

interface NavGroup {
  heading: string;
  items: NavItem[];
}

const NAV: NavGroup[] = [
  {
    heading: "Workspace",
    items: [
      { href: "/", label: "Overview", icon: LayoutDashboard, exact: true, hint: "System-wide posture" },
      { href: "/cases", label: "Investigations", icon: FolderKanban, hint: "Case registry" },
      { href: "/templates", label: "Functions", icon: TerminalSquare, hint: "Forensic function templates" },
    ],
  },
  {
    heading: "Governance",
    items: [
      { href: "/audit", label: "Audit log", icon: ScrollText, roles: ["ADMIN", "AUDITOR"], hint: "Append-only operator log" },
      { href: "/settings", label: "Settings", icon: Settings, hint: "Profile, RBAC, policies" },
    ],
  },
];

const ROLE_LABEL: Record<string, string> = {
  ADMIN: "Administrator",
  LEAD_INVESTIGATOR: "Lead investigator",
  INVESTIGATOR: "Investigator",
  AUDITOR: "Auditor",
};

/** Brand mark: a hexagonal aperture, drawn in the accent colour. */
function Mark({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden className="shrink-0">
      <polygon points="16,2.5 28,9.5 28,22.5 16,29.5 4,22.5 4,9.5" fill="none" stroke="#2563EB" strokeWidth="1.8" strokeLinejoin="round" />
      <polygon points="16,9 22.5,12.8 22.5,19.2 16,23 9.5,19.2 9.5,12.8" fill="#EFF4FF" stroke="#2563EB" strokeWidth="1.1" strokeLinejoin="round" />
      <circle cx="16" cy="16" r="2" fill="#2563EB" />
    </svg>
  );
}

function useBackendHealth() {
  const [ok, setOk] = useState<boolean | null>(null);
  useEffect(() => {
    let alive = true;
    const check = async () => {
      try {
        const r = await fetch("/health");
        if (alive) setOk(r.ok);
      } catch {
        if (alive) setOk(false);
      }
    };
    void check();
    const t = setInterval(check, 15000);
    return () => {
      alive = false;
      clearInterval(t);
    };
  }, []);
  return ok;
}

function useClock() {
  const [now, setNow] = useState("");
  useEffect(() => {
    const tick = () => setNow(new Date().toISOString().slice(11, 19) + "Z");
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

/** Path-derived trail used before a nested layout publishes a richer one. */
function crumbsFromPath(pathname: string): Crumb[] {
  const seg = pathname.split("/").filter(Boolean);
  if (seg.length === 0) return [{ label: "Overview" }];
  const known: Record<string, string> = {
    cases: "Investigations",
    templates: "Functions",
    audit: "Audit log",
    settings: "Settings",
    evidence: "Evidence",
    lab: "Script lab",
    executions: "Execution",
    findings: "Findings",
    timeline: "Timeline",
    graph: "Correlation graph",
    ai: "Analysis",
    reports: "Reports",
  };
  if (seg[0] === "cases" && seg[1]) {
    const out: Crumb[] = [{ label: "Investigations", href: "/cases" }, { label: seg[1].slice(0, 8) }];
    if (seg[2] && known[seg[2]]) out.push({ label: known[seg[2]] });
    return out;
  }
  return [{ label: known[seg[0]] ?? seg[0] }];
}

function NavLink({
  item,
  pathname,
  collapsed,
  onNavigate,
}: {
  item: NavItem;
  pathname: string;
  collapsed: boolean;
  onNavigate: () => void;
}) {
  const active = item.exact ? pathname === item.href : pathname.startsWith(item.href);
  const Icon = item.icon;
  const link = (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={clsx(
        "group relative flex h-8 items-center gap-2.5 rounded-md px-2.5 text-[12.5px] transition-[background-color,color] duration-[120ms]",
        active ? "bg-accentSoft font-medium text-accent" : "text-muted hover:bg-panel2 hover:text-ink",
      )}
    >
      {active && <span className="absolute left-0 top-1/2 h-4 w-[2px] -translate-y-1/2 rounded-r bg-accent" />}
      <Icon size={15} className="shrink-0" />
      {!collapsed && <span className="min-w-0 flex-1 truncate">{item.label}</span>}
    </Link>
  );
  return collapsed ? (
    <Tooltip key={item.href} label={item.label}>
      {link}
    </Tooltip>
  ) : (
    <div key={item.href}>{link}</div>
  );
}

function RailContent({
  pathname,
  user,
  backendOk,
  onNavigate,
}: {
  pathname: string;
  user: ReturnType<typeof useAuth>["user"];
  backendOk: boolean | null;
  onNavigate: () => void;
}) {
  const groups = NAV.map((g) => ({
    heading: g.heading,
    items: g.items.filter((n) => !n.roles || (user && n.roles.includes(user.role))),
  })).filter((g) => g.items.length > 0);

  return (
    <>
      <nav className="min-h-0 flex-1 overflow-y-auto px-2.5 py-3">
        {groups.map((g) => (
          <div key={g.heading} className="mb-4 last:mb-0">
            <p className="mb-1 px-2.5 text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">{g.heading}</p>
            <div className="space-y-0.5">
              {g.items.map((item) => (
                <NavLink key={item.href} item={item} pathname={pathname} collapsed={false} onNavigate={onNavigate} />
              ))}
            </div>
          </div>
        ))}
      </nav>

      <div className="shrink-0 border-t border-edge p-2.5">
        <div className="rounded-md border border-edge bg-panel2/60 px-2.5 py-2">
          <div className="flex items-center justify-between">
            <span className="text-[10px] font-semibold uppercase tracking-[0.1em] text-faint">System</span>
            <StatusDot state={backendOk === null ? "idle" : backendOk ? "ok" : "err"} />
          </div>
          <p className="mt-1 text-[11.5px] font-medium text-ink">
            {backendOk === null ? "Checking services" : backendOk ? "All services nominal" : "API unreachable"}
          </p>
          <p className="mt-0.5 truncate font-mono text-[10.5px] text-faint">
            {backendOk ? `api/v1 Â· forgex v${VERSION}` : "no response from /health"}
          </p>
        </div>

        {user && (
          <div className="mt-2 flex items-center gap-2 rounded-md px-2.5 py-1.5">
            <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accentSoft text-[10px] font-semibold uppercase text-accent">
              {user.username.slice(0, 2)}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[12px] font-medium text-ink">{user.username}</span>
              <span className="block truncate text-[10.5px] text-faint">{ROLE_LABEL[user.role] ?? user.role}</span>
            </span>
          </div>
        )}
      </div>
    </>
  );
}

export default function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const { user, logout } = useAuth();
  const backendOk = useBackendHealth();
  const clock = useClock();
  const published = useBreadcrumbTrail();
  const [railOpen, setRailOpen] = useState(false);

  const crumbs = published.length > 0 ? published : crumbsFromPath(pathname);

  useEffect(() => setRailOpen(false), [pathname]);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-void">
      {/* ---------- top bar ---------- */}
      <header className="z-30 flex h-topbar shrink-0 items-center gap-3 border-b border-edge bg-panel px-3 sm:px-4">
        <button
          className="btn btn-ghost btn-icon lg:hidden"
          onClick={() => setRailOpen(true)}
          aria-label="Open navigation"
        >
          <Menu size={16} />
        </button>

        <Link href="/" className="flex shrink-0 items-center gap-2.5">
          <Mark />
          <span className="hidden text-[14.5px] font-semibold tracking-[-0.01em] text-ink sm:block">
            Forge<span className="text-accent">X</span>
          </span>
        </Link>

        <span className="hidden h-5 w-px shrink-0 bg-edge xl:block" />
        <nav className="hidden min-w-0 flex-1 xl:block">
          <BreadcrumbTrail items={crumbs} />
        </nav>

        <div className="ml-auto flex min-w-0 flex-1 items-center justify-end gap-2 xl:flex-none xl:flex-initial">
          <CommandSearch />
        </div>

        <span className="hidden shrink-0 items-center gap-2 border-l border-edge pl-3 md:flex">
          <StatusDot
            state={backendOk === null ? "idle" : backendOk ? "ok" : "err"}
            label={backendOk === null ? "checking" : backendOk ? "nominal" : "offline"}
          />
          <span className="hidden font-mono text-[11px] tabular-nums text-faint lg:block">{clock}</span>
        </span>

        {user && (
          <div className="shrink-0 border-l border-edge pl-2">
            <Dropdown
              trigger={({ toggle }) => (
                <button
                  onClick={toggle}
                  className="flex h-8 items-center gap-2 rounded-md border border-transparent px-1.5 transition-colors duration-[120ms] hover:border-edge hover:bg-panel2"
                >
                  <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accentSoft text-[10px] font-semibold uppercase text-accent">
                    {user.username.slice(0, 2)}
                  </span>
                  <span className="hidden text-[12px] font-medium text-ink md:block">{user.username}</span>
                  <ChevronDown size={13} className="text-faint" />
                </button>
              )}
            >
              {(close) => (
                <>
                  <div className="border-b border-edge px-2 pb-2 pt-1.5">
                    <p className="truncate text-[12px] font-medium text-ink">{user.email}</p>
                    <p className="mt-0.5 flex items-center gap-1.5">
                      <ShieldCheck size={11} className="text-faint" />
                      <span className="text-[11px] text-muted">{ROLE_LABEL[user.role] ?? user.role}</span>
                    </p>
                  </div>
                  <div className="pt-1">
                    <Link
                      href="/settings"
                      onClick={close}
                      className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[12px] text-ink transition-colors duration-[120ms] hover:bg-panel2"
                    >
                      <Settings size={13} className="shrink-0 text-faint" />
                      Account &amp; settings
                    </Link>
                    <MenuItem icon={LogOut} danger onClick={() => { close(); void logout(); }}>
                      Sign out
                    </MenuItem>
                  </div>
                </>
              )}
            </Dropdown>
          </div>
        )}
      </header>

      <div className="flex min-h-0 flex-1">
        {/* ---------- desktop rail ---------- */}
        <aside className="hidden w-sidebar shrink-0 flex-col border-r border-edge bg-panel lg:flex">
          <RailContent pathname={pathname} user={user} backendOk={backendOk} onNavigate={() => {}} />
        </aside>

        {/* ---------- mobile / tablet drawer ---------- */}
        {railOpen && (
          <div className="fixed inset-0 z-50 flex lg:hidden" onClick={() => setRailOpen(false)}>
            <div className="absolute inset-0 bg-[#101828]/40" />
            <aside
              className="relative flex w-[268px] animate-slide-left flex-col border-r border-edge bg-panel shadow-overlay"
              onClick={(e) => e.stopPropagation()}
            >
              <div className="flex h-topbar shrink-0 items-center gap-2 border-b border-edge px-3">
                <Mark size={22} />
                <span className="flex-1 text-[14px] font-semibold text-ink">
                  Forge<span className="text-accent">X</span>
                </span>
                <button className="btn btn-ghost btn-icon" onClick={() => setRailOpen(false)} aria-label="Close navigation">
                  <X size={15} />
                </button>
              </div>
              <RailContent pathname={pathname} user={user} backendOk={backendOk} onNavigate={() => setRailOpen(false)} />
            </aside>
          </div>
        )}

        {/* ---------- content ---------- */}
        <main className="min-w-0 flex-1 overflow-y-auto">
          <div className="mx-auto w-full max-w-shell px-4 py-5 sm:px-6 sm:py-6">{children}</div>
        </main>
      </div>

      {/* ---------- status bar ---------- */}
      <footer className="z-30 flex h-statusbar shrink-0 items-center gap-3 border-t border-edge bg-panel px-3 text-[10.5px] text-faint">
        <span className="flex items-center gap-1.5">
          <PanelLeftClose size={11} className="opacity-70" />
          <span className="font-mono">v{VERSION}</span>
        </span>
        <span className="hidden h-3 w-px bg-edge sm:block" />
        <span className="hidden sm:inline">Forensic investigation workspace</span>
        <span className="flex-1" />
        {user && <span className="hidden truncate font-mono md:inline">operator: {user.email}</span>}
        <span className="flex items-center gap-1.5">
          <StatusDot state={backendOk === null ? "idle" : backendOk ? "ok" : "err"} />
          <span className={clsx(backendOk === false && "text-alarm")}>
            {backendOk === null ? "Checking" : backendOk ? "Connected" : "Disconnected"}
          </span>
        </span>
      </footer>
    </div>
  );
}

function BreadcrumbTrail({ items }: { items: Crumb[] }) {
  return (
    <ol className="flex min-w-0 items-center gap-1.5 text-[12px]">
      {items.map((it, i) => {
        const last = i === items.length - 1;
        return (
          <li key={`${it.label}-${i}`} className={clsx("flex min-w-0 items-center gap-1.5", last && "min-w-0")}>
            {i > 0 && <span className="select-none text-faint">/</span>}
            {it.href && !last ? (
              <Link href={it.href} className="truncate text-muted transition-colors duration-[120ms] hover:text-ink">
                {it.label}
              </Link>
            ) : (
              <span className={clsx("truncate", last ? "font-medium text-ink" : "text-muted")}>{it.label}</span>
            )}
          </li>
        );
      })}
    </ol>
  );
}
