"use client";

// ForgeX design system — light forensic workstation primitives.
// Every screen composes from this file; do not restyle primitives per page.
import clsx from "clsx";
import Link from "next/link";
import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Copy,
  Check,
  Info,
  X,
  XCircle,
} from "lucide-react";

/* ================================================================== Panel */

export function Panel({
  title,
  right,
  children,
  className,
  bodyClass,
  variant,
  dense,
  icon: Icon,
}: {
  title?: ReactNode;
  right?: ReactNode;
  children: ReactNode;
  className?: string;
  bodyClass?: string;
  variant?: "accent" | "muted" | "cyan" | "dim";
  dense?: boolean;
  icon?: typeof Info;
}) {
  return (
    <section
      className={clsx(
        "panel",
        (variant === "accent" || variant === "cyan") && "border-accentEdge",
        (variant === "muted" || variant === "dim") && "bg-panel2/50",
        className,
      )}
    >
      {title !== undefined && (
        <header className="panel-title">
          {Icon && <Icon size={13} className="shrink-0 text-faint" />}
          <span className="min-w-0 flex-1 truncate">{title}</span>
          {right}
        </header>
      )}
      <div className={clsx(dense ? "" : "p-3", bodyClass)}>{children}</div>
    </section>
  );
}

/* ================================================================== Page header */

export function PageHeader({
  eyebrow,
  title,
  description,
  actions,
  meta,
}: {
  eyebrow?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-3 border-b border-edge pb-4 md:flex-row md:items-start md:justify-between">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 flex flex-wrap items-center gap-2">{eyebrow}</div>}
        <h1 className="page-title">{title}</h1>
        {description && <p className="page-sub max-w-3xl">{description}</p>}
        {meta && <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Small uppercase label above a value, used in headers and stat tiles. */
export function MetaItem({ label, value, mono }: { label: string; value: ReactNode; mono?: boolean }) {
  return (
    <span className="flex items-baseline gap-1.5">
      <span className="text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">{label}</span>
      <span className={clsx("text-[12px] text-ink", mono && "font-mono")}>{value}</span>
    </span>
  );
}

/* ================================================================== Semantic colour maps */

type Tone = { fg: string; bg: string; bd: string };

const SEVERITY_TONE: Record<string, Tone> = {
  CRITICAL: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  HIGH: { fg: "text-[#C2410C]", bg: "bg-[#FFF4ED]", bd: "border-[#FDDCC7]" },
  MEDIUM: { fg: "text-amber", bg: "bg-amberSoft", bd: "border-amberEdge" },
  LOW: { fg: "text-cyanx", bg: "bg-cyanSoft", bd: "border-cyanEdge" },
  INFO: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
};

const STATUS_TONE: Record<string, Tone> = {
  /* terminal-success */
  COMPLETED: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  READY: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  VERIFIED: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  ALLOWED: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  VALID: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  INTACT: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  SUCCESS: { fg: "text-muted", bg: "bg-phosphorSoft", bd: "border-phosphorEdge" },
  /* in-flight */
  OPEN: { fg: "text-accent", bg: "bg-accentSoft", bd: "border-accentEdge" },
  IN_PROGRESS: { fg: "text-accent", bg: "bg-accentSoft", bd: "border-accentEdge" },
  RUNNING: { fg: "text-cyanx", bg: "bg-cyanSoft", bd: "border-cyanEdge" },
  NEW: { fg: "text-accent", bg: "bg-accentSoft", bd: "border-accentEdge" },
  /* neutral / terminal-quiet */
  PENDING: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  QUEUED: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  GENERATING: { fg: "text-cyanx", bg: "bg-cyanSoft", bd: "border-cyanEdge" },
  CLOSED: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  REJECTED: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  DISMISSED: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  FALSE_POSITIVE: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  INACTIVE: { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" },
  /* warning */
  PARTIAL: { fg: "text-amber", bg: "bg-amberSoft", bd: "border-amberEdge" },
  DEGRADED: { fg: "text-amber", bg: "bg-amberSoft", bd: "border-amberEdge" },
  /* failure */
  FAILED: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  ERROR: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  TIMEOUT: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  SANDBOX_VIOLATION: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  DENIED: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  POLICY_DENIED: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  TAMPERED: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
  BROKEN: { fg: "text-alarm", bg: "bg-alarmSoft", bd: "border-alarmEdge" },
};

export function tone(map: Record<string, Tone>, key: string): Tone {
  return map[key.toUpperCase()] ?? map.INFO ?? { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" };
}

/* ================================================================== Badges */

export function SeverityBadge({ severity, className }: { severity: string; className?: string }) {
  const s = (severity || "INFO").toUpperCase();
  const t = SEVERITY_TONE[s] ?? SEVERITY_TONE.INFO;
  return <span className={clsx("badge", t.fg, t.bg, t.bd, className)}>{s}</span>;
}

export function StatusPill({ status, className }: { status: string; className?: string }) {
  const s = (status || "").toUpperCase();
  const t = STATUS_TONE[s] ?? { fg: "text-muted", bg: "bg-panel2", bd: "border-edge" };
  const live = s === "RUNNING" || s === "IN_PROGRESS" || s === "PENDING" || s === "QUEUED";
  return (
    <span className={clsx("badge", t.fg, t.bg, t.bd, className)}>
      <span className={clsx("led", live && "led-live", t.fg.replace("text-", "bg-"))} />
      {s.replace(/_/g, " ")}
    </span>
  );
}

export function ProvenanceBadge({ provenance }: { provenance: string }) {
  if ((provenance || "").toUpperCase() === "SYNTHETIC") {
    return (
      <span className="badge synthetic-stripe border-amberEdge text-amber" title="Clearly-labelled synthetic demonstration data">
        synthetic
      </span>
    );
  }
  return <span className="badge border-phosphorEdge bg-phosphorSoft text-muted">live</span>;
}

export function TypeBadge({ type }: { type: string }) {
  return <span className="badge border-edge2 bg-panel2 text-muted">{type.replace(/_/g, " ")}</span>;
}

/** Neutral pill for counts and metadata. */
export function Pill({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={clsx("badge-neutral", className)}>{children}</span>;
}

/** Small count bubble used beside section titles. */
export function Count({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex h-[18px] min-w-[18px] items-center justify-center rounded-full bg-panel2 px-1.5 text-[10px] font-semibold tabular-nums text-muted">
      {children}
    </span>
  );
}

/* ================================================================== Status indicator */

export function StatusDot({ state, label }: { state: "ok" | "warn" | "err" | "idle" | "live"; label?: string }) {
  const map = {
    ok: "bg-phosphor",
    live: "bg-cyanx led-live",
    warn: "bg-amber",
    err: "bg-alarm",
    idle: "bg-faint",
  } as const;
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={clsx("led", map[state])} />
      {label && <span className="text-[11px] text-muted">{label}</span>}
    </span>
  );
}

/* ================================================================== Buttons */

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "cyan" | "ghost" | "danger" | "success";
  size?: "sm" | "md";
  busy?: boolean;
  icon?: ReactNode;
};

export function Btn({ variant = "ghost", size = "md", busy, className, children, disabled, icon, ...rest }: BtnProps) {
  const v = {
    primary: "btn-primary",
    cyan: "btn-cyan",
    ghost: "btn-ghost",
    danger: "btn-danger",
    success: "btn-success",
  }[variant];
  return (
    <button className={clsx(v, size === "sm" && "btn-sm", className)} disabled={disabled || busy} {...rest}>
      {busy ? <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-[1.5px] border-current border-r-transparent" /> : icon}
      {children}
    </button>
  );
}

export function IconBtn({
  label,
  className,
  children,
  ...rest
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button className={clsx("btn btn-ghost btn-icon", className)} title={label} aria-label={label} {...rest}>
      {children}
    </button>
  );
}

/* ================================================================== Tabs */

export function Tabs({
  tabs,
  active,
  onChange,
  className,
}: {
  tabs: Array<{ key: string; label: string; icon?: typeof Info; count?: ReactNode }>;
  active: string;
  onChange: (key: string) => void;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-end gap-0 overflow-x-auto border-b border-edge", className)} role="tablist">
      {tabs.map((t) => {
        const on = t.key === active;
        const Icon = t.icon;
        return (
          <button
            key={t.key}
            role="tab"
            aria-selected={on}
            onClick={() => onChange(t.key)}
            className={clsx(
              "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[12px] font-medium transition-colors duration-[120ms]",
              on
                ? "-mb-px border-accent text-accent"
                : "-mb-px border-transparent text-muted hover:border-edge2 hover:text-ink",
            )}
          >
            {Icon && <Icon size={13} className="shrink-0" />}
            {t.label}
            {t.count !== undefined && <span className="tabular-nums text-[10.5px] text-faint">{t.count}</span>}
          </button>
        );
      })}
    </div>
  );
}

/* ================================================================== Inputs */

export function Field({
  label,
  children,
  hint,
  required,
  className,
}: {
  label: string;
  children: ReactNode;
  hint?: ReactNode;
  required?: boolean;
  className?: string;
}) {
  return (
    <label className={clsx("block", className)}>
      <span className="label">
        {label}
        {required && <span className="ml-0.5 text-alarm">*</span>}
      </span>
      {children}
      {hint && <span className="mt-1 block text-[11px] leading-relaxed text-faint">{hint}</span>}
    </label>
  );
}

export function SearchInput({
  value,
  onChange,
  placeholder = "Search",
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  className?: string;
}) {
  return (
    <div className={clsx("relative", className)}>
      <svg
        width="14"
        height="14"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        aria-hidden
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-faint"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        className="input pl-8"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        type="search"
      />
    </div>
  );
}

/** Selectable option rows (radio / checkbox semantics) for form choices. */
export function ChoiceCard({
  active,
  title,
  description,
  onClick,
}: {
  active: boolean;
  title: string;
  description?: ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={clsx(
        "rounded-md border px-3 py-2 text-left transition-[border-color,background-color,box-shadow] duration-[120ms]",
        active
          ? "border-accent bg-accentSoft shadow-[inset_2px_0_0_0_theme(colors.accent)]"
          : "border-edge bg-panel hover:border-edge2 hover:bg-panel2/60",
      )}
    >
      <span className={clsx("block text-[12px] font-semibold", active ? "text-accent" : "text-ink")}>{title}</span>
      {description && <span className="mt-0.5 block text-[11px] leading-relaxed text-muted">{description}</span>}
    </button>
  );
}

/* ================================================================== Overlays */

export function Modal({
  open,
  onClose,
  title,
  children,
  wide,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  wide?: boolean;
  footer?: ReactNode;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-[#101828]/40 p-4 backdrop-blur-[1px] sm:p-6"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className={clsx("panel animate-pop-in my-8 w-full shadow-overlay", wide ? "max-w-4xl" : "max-w-lg")}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="panel-title">
          <span className="min-w-0 flex-1 truncate">{title}</span>
          <IconBtn label="Close" onClick={onClose}>
            <X size={14} />
          </IconBtn>
        </header>
        <div className="max-h-[calc(100vh-12rem)] overflow-y-auto p-4">{children}</div>
        {footer && <div className="flex items-center justify-end gap-2 border-t border-edge bg-panel2/50 px-4 py-3">{footer}</div>}
      </div>
    </div>
  );
}

export function Drawer({
  open,
  onClose,
  title,
  subtitle,
  actions,
  children,
  width = "max-w-xl",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  children: ReactNode;
  width?: string;
}) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-40 flex justify-end bg-[#101828]/30" onClick={onClose} role="dialog" aria-modal="true">
      <aside
        className={clsx("flex h-full w-full animate-slide-left flex-col border-l border-edge bg-panel shadow-overlay", width)}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="flex min-h-[52px] shrink-0 items-center gap-3 border-b border-edge bg-panel px-4 py-2.5">
          <div className="min-w-0 flex-1">
            <div className="truncate text-[13px] font-semibold text-ink">{title}</div>
            {subtitle && <div className="truncate text-[11px] text-muted">{subtitle}</div>}
          </div>
          {actions}
          <IconBtn label="Close" onClick={onClose}>
            <X size={15} />
          </IconBtn>
        </header>
        <div className="min-h-0 flex-1 overflow-y-auto">{children}</div>
      </aside>
    </div>
  );
}

/* ================================================================== Dropdown */

export function Dropdown({
  trigger,
  children,
  align = "right",
  className,
}: {
  trigger: (props: { open: boolean; toggle: () => void }) => ReactNode;
  children: (close: () => void) => ReactNode;
  align?: "left" | "right";
  className?: string;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={clsx("relative", className)} ref={ref}>
      {trigger({ open, toggle: () => setOpen((o) => !o) })}
      {open && (
        <div
          className={clsx(
            "absolute top-[calc(100%+4px)] z-40 min-w-[180px] animate-slide-down rounded-lg border border-edge bg-panel p-1 shadow-overlay",
            align === "right" ? "right-0" : "left-0",
          )}
        >
          {children(() => setOpen(false))}
        </div>
      )}
    </div>
  );
}

export function MenuItem({
  children,
  onClick,
  danger,
  icon: Icon,
}: {
  children: ReactNode;
  onClick?: () => void;
  danger?: boolean;
  icon?: typeof Info;
}) {
  return (
    <button
      onClick={onClick}
      className={clsx(
        "flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-[12px] transition-colors duration-[120ms]",
        danger ? "text-alarm hover:bg-alarmSoft" : "text-ink hover:bg-panel2",
      )}
    >
      {Icon && <Icon size={13} className="shrink-0 text-faint" />}
      {children}
    </button>
  );
}

/* ================================================================== Tooltip */

export function Tooltip({ label, children }: { label: string; children: ReactNode }) {
  return (
    <span className="group/tt relative inline-flex">
      {children}
      <span
        role="tooltip"
        className="pointer-events-none absolute bottom-[calc(100%+6px)] left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded border border-edge bg-ink px-1.5 py-1 text-[10.5px] text-white opacity-0 shadow-raised transition-opacity duration-[120ms] group-hover/tt:opacity-100"
      >
        {label}
      </span>
    </span>
  );
}

/* ================================================================== Tab navigation (route-based) */

export function TabNav({
  tabs,
  isActive,
  className,
}: {
  tabs: Array<{ href: string; label: string; icon?: typeof Info; count?: ReactNode }>;
  isActive: (href: string) => boolean;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-end gap-0 overflow-x-auto border-b border-edge", className)} role="tablist">
      {tabs.map((t) => {
        const on = isActive(t.href);
        const Icon = t.icon;
        return (
          <Link
            key={t.href}
            href={t.href}
            role="tab"
            aria-selected={on}
            className={clsx(
              "relative flex shrink-0 items-center gap-1.5 whitespace-nowrap border-b-2 px-3 py-2 text-[12px] font-medium transition-colors duration-[120ms]",
              on
                ? "-mb-px border-accent text-accent"
                : "-mb-px border-transparent text-muted hover:border-edge2 hover:text-ink",
            )}
          >
            {Icon && <Icon size={13} className="shrink-0" />}
            {t.label}
            {t.count !== undefined && <span className="tabular-nums text-[10.5px] text-faint">{t.count}</span>}
          </Link>
        );
      })}
    </div>
  );
}

/* ================================================================== Breadcrumb */

export function Breadcrumb({ items }: { items: Array<{ label: ReactNode; href?: string }> }) {
  return (
    <nav aria-label="Breadcrumb" className="flex min-w-0 items-center gap-1 text-[12px]">
      {items.map((it, i) => {
        const last = i === items.length - 1;
        return (
          <span key={i} className={clsx("flex min-w-0 items-center gap-1", last && "min-w-0")}>
            {i > 0 && <span className="select-none text-faint">/</span>}
            {it.href && !last ? (
              <a href={it.href} className="truncate text-muted transition-colors duration-[120ms] hover:text-ink">
                {it.label}
              </a>
            ) : (
              <span className={clsx("truncate", last ? "font-medium text-ink" : "text-muted")}>{it.label}</span>
            )}
          </span>
        );
      })}
    </nav>
  );
}

/* ================================================================== Stat tiles */

export function StatTile({
  label,
  value,
  hint,
  tone: t = "neutral",
  icon: Icon,
  active,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "neutral" | "accent" | "success" | "warning" | "danger" | "info";
  icon?: typeof Info;
  active?: boolean;
}) {
  const tones: Record<string, string> = {
    neutral: "text-ink",
    accent: "text-accent",
    success: "text-phosphorDim",
    warning: "text-amber",
    danger: "text-alarm",
    info: "text-cyanx",
  };
  return (
    <div
      className={clsx(
        "rounded-lg border bg-panel px-3.5 py-3 transition-[border-color,box-shadow] duration-[120ms]",
        active ? "border-accent shadow-focus" : "border-edge shadow-panel",
      )}
    >
      <div className="flex items-center gap-1.5">
        {Icon && <Icon size={12.5} className="shrink-0 text-faint" />}
        <span className="truncate text-[10px] font-semibold uppercase tracking-[0.08em] text-muted">{label}</span>
      </div>
      <p className={clsx("mt-1 text-[26px] font-semibold leading-none tracking-[-0.02em] tabular-nums", tones[t])}>{value}</p>
      {hint && <p className="mt-1.5 text-[11px] leading-snug text-faint">{hint}</p>}
    </div>
  );
}

/** Horizontal proportion bar used for distributions. */
export function Meter({ pct, tone = "accent" }: { pct: number; tone?: "accent" | "success" | "warning" | "danger" | "info" | "neutral" }) {
  const bg = {
    accent: "bg-accent",
    success: "bg-phosphor",
    warning: "bg-amber",
    danger: "bg-alarm",
    info: "bg-cyanx",
    neutral: "bg-faint",
  }[tone];
  return (
    <span className="block h-1.5 w-full overflow-hidden rounded-full bg-panel2">
      <span className={clsx("block h-full rounded-full", bg)} style={{ width: `${Math.max(0, Math.min(100, pct))}%` }} />
    </span>
  );
}

/* ================================================================== Key/value */

export function KV({ k, v, mono }: { k: string; v: ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-grid py-1.5 last:border-b-0">
      <span className="shrink-0 text-[10.5px] font-medium uppercase tracking-[0.06em] text-faint">{k}</span>
      <span className={clsx("min-w-0 break-all text-right text-[12px] text-ink", mono && "font-mono text-[11.5px]")}>{v}</span>
    </div>
  );
}

/** Read-only technical value: hash, id, tx, path. */
export function TechValue({ value, label, className }: { value: ReactNode; label?: string; className?: string }) {
  return (
    <span className={clsx("block", className)}>
      {label && <span className="mb-0.5 block text-[10px] font-semibold uppercase tracking-[0.08em] text-faint">{label}</span>}
      <span className="block break-all rounded border border-edge bg-code px-2 py-1 font-mono text-[11.5px] text-codeInk">
        {value}
      </span>
    </span>
  );
}

/* ================================================================== Code viewer */

export function CodeBlock({
  code,
  title,
  language,
  copyable = true,
  className,
  maxHeight,
  tone,
}: {
  code: string;
  title?: ReactNode;
  language?: string;
  copyable?: boolean;
  className?: string;
  maxHeight?: number | string;
  tone?: "neutral" | "danger" | "success";
}) {
  const [copied, setCopied] = useState(false);
  const toneCls =
    tone === "danger"
      ? "border-alarmEdge bg-alarmSoft text-alarm"
      : tone === "success"
        ? "border-phosphorEdge bg-phosphorSoft text-muted"
        : "";

  async function copy() {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className={clsx("overflow-hidden rounded-md border border-codeEdge bg-code", className)}>
      {(title || copyable) && (
        <div className="flex items-center gap-2 border-b border-codeEdge bg-panel2/70 px-2.5 py-1.5">
          <span className="min-w-0 flex-1 truncate text-[10.5px] font-semibold uppercase tracking-[0.07em] text-muted">
            {title ?? (language ?? "output")}
          </span>
          {copyable && (
            <button
              onClick={() => void copy()}
              className="flex items-center gap-1 rounded px-1 py-0.5 text-[10.5px] text-muted transition-colors duration-[120ms] hover:bg-panel hover:text-ink"
            >
              {copied ? <Check size={11} className="text-phosphor" /> : <Copy size={11} />}
              {copied ? "copied" : "copy"}
            </button>
          )}
        </div>
      )}
      <pre
        className={clsx("mono overflow-auto p-2.5 leading-relaxed text-codeInk", toneCls)}
        style={{ maxHeight: maxHeight ?? 320 }}
      >
        {code}
      </pre>
    </div>
  );
}

/* ================================================================== Timeline */

export function Timeline({ children, className }: { children: ReactNode; className?: string }) {
  return <ol className={clsx("relative", className)}>{children}</ol>;
}

export function TimelineItem({
  title,
  meta,
  children,
  dot = "neutral",
  last,
}: {
  title: ReactNode;
  meta?: ReactNode;
  children?: ReactNode;
  dot?: "neutral" | "accent" | "success" | "warning" | "danger" | "info";
  last?: boolean;
}) {
  const bg = {
    neutral: "bg-faint",
    accent: "bg-accent",
    success: "bg-phosphor",
    warning: "bg-amber",
    danger: "bg-alarm",
    info: "bg-cyanx",
  }[dot];
  return (
    <li className="relative flex gap-3 pb-3 last:pb-0">
      <div className="relative flex w-3 shrink-0 justify-center">
        <span className={clsx("mt-1.5 h-[7px] w-[7px] shrink-0 rounded-full ring-4 ring-panel", bg)} />
        {!last && <span className="absolute top-4 h-full w-px bg-edge" />}
      </div>
      <div className="min-w-0 flex-1 pb-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
          <span className="text-[12.5px] font-medium text-ink">{title}</span>
          {meta && <span className="font-mono text-[10.5px] text-faint">{meta}</span>}
        </div>
        {children && <div className="mt-1 text-[11.5px] leading-relaxed text-muted">{children}</div>}
      </div>
    </li>
  );
}

/* ================================================================== States */

export function Empty({
  text,
  hint,
  action,
  icon: Icon,
  compact,
}: {
  text: ReactNode;
  hint?: ReactNode;
  action?: ReactNode;
  icon?: typeof Info;
  compact?: boolean;
}) {
  return (
    <div className={clsx("flex flex-col items-center justify-center px-6 text-center", compact ? "py-6" : "py-12")}>
      {Icon && <Icon size={18} className="mb-2 text-faint" />}
      <p className="text-[13px] font-medium text-ink">{text}</p>
      {hint && <p className="mt-1 max-w-md text-[12px] leading-relaxed text-muted">{hint}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

export function Alert({
  tone = "neutral",
  title,
  children,
  className,
}: {
  tone?: "neutral" | "info" | "success" | "warning" | "danger";
  title?: ReactNode;
  children?: ReactNode;
  className?: string;
}) {
  const map = {
    neutral: "border-edge bg-panel2 text-ink",
    info: "border-cyanEdge bg-cyanSoft text-[#075985]",
    success: "border-phosphorEdge bg-phosphorSoft text-muted",
    warning: "border-amberEdge bg-amberSoft text-[#92400E]",
    danger: "border-alarmEdge bg-alarmSoft text-alarm",
  }[tone];
  const Icon = tone === "danger" ? XCircle : tone === "warning" ? AlertTriangle : tone === "success" ? CheckCircle2 : Info;
  return (
    <div className={clsx("flex items-start gap-2 rounded-md border px-3 py-2 text-[12px] leading-relaxed", map, className)}>
      <Icon size={14} className="mt-px shrink-0" />
      <div className="min-w-0 flex-1">
        {title && <p className="font-semibold">{title}</p>}
        {children}
      </div>
    </div>
  );
}

export function ErrorNote({ err, className }: { err: unknown; className?: string }) {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    <Alert tone="danger" className={className}>
      {msg}
    </Alert>
  );
}

/** Non-blocking error strip used above content areas. */
export function ErrorStrip({ err, className }: { err: unknown; className?: string }) {
  const msg = err instanceof Error ? err.message : String(err);
  return (
    <div
      className={clsx(
        "flex items-start gap-2 rounded-md border border-alarmEdge bg-alarmSoft px-3 py-2 text-[12px] text-alarm",
        className,
      )}
    >
      <AlertTriangle size={14} className="mt-px shrink-0" />
      <span className="min-w-0 flex-1">{msg}</span>
    </div>
  );
}

/* ================================================================== Loading */

export function Skeleton({ className }: { className?: string }) {
  return <div className={clsx("skeleton h-4", className)} />;
}

export function SkeletonRows({ rows = 5, cols = 4 }: { rows?: number; cols?: number }) {
  return (
    <div className="divide-y divide-grid">
      {Array.from({ length: rows }).map((_, r) => (
        <div key={r} className="flex items-center gap-4 px-3 py-2.5">
          {Array.from({ length: cols }).map((__, c) => (
            <Skeleton key={c} className={clsx("h-3", c === 0 ? "w-40" : "flex-1")} />
          ))}
        </div>
      ))}
    </div>
  );
}

export function SkeletonTable({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <div>
      <div className="flex items-center gap-4 border-b border-edge bg-panel2/70 px-3 py-2">
        {Array.from({ length: cols }).map((_, c) => (
          <Skeleton key={c} className={clsx("h-2.5", c === 0 ? "w-32" : "flex-1")} />
        ))}
      </div>
      <SkeletonRows rows={rows} cols={cols} />
    </div>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-[12px] text-muted">
      <span className="h-3 w-3 shrink-0 animate-spin rounded-full border-[1.5px] border-edge2 border-t-accent" />
      {label}
    </span>
  );
}

/** Panel-shaped loading placeholder that does not flash an empty state. */
export function LoadingPanel({ label, rows = 4 }: { label?: string; rows?: number }) {
  return (
    <Panel title={label ?? "Loading"}>
      <SkeletonRows rows={rows} cols={3} />
    </Panel>
  );
}

/* ================================================================== Toasts */

type ToastKind = "ok" | "err" | "warn" | "info";
interface Toast {
  id: number;
  kind: ToastKind;
  msg: string;
}

const ToastCtx = createContext<(kind: ToastKind, msg: string) => void>(() => {});
export const useToast = () => useContext(ToastCtx);

const TOAST_STYLE: Record<ToastKind, { cls: string; Icon: typeof Info }> = {
  ok: { cls: "border-phosphorEdge bg-phosphorSoft text-muted", Icon: CheckCircle2 },
  err: { cls: "border-alarmEdge bg-alarmSoft text-alarm", Icon: XCircle },
  warn: { cls: "border-amberEdge bg-amberSoft text-[#92400E]", Icon: AlertTriangle },
  info: { cls: "border-accentEdge bg-accentSoft text-accent", Icon: Info },
};

export function ToastHost({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((kind: ToastKind, msg: string) => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t.slice(-4), { id, kind, msg }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), 5200);
  }, []);
  const dismiss = (id: number) => setToasts((t) => t.filter((x) => x.id !== id));

  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex w-[min(24rem,calc(100vw-2rem))] flex-col gap-2">
        {toasts.map((t) => {
          const s = TOAST_STYLE[t.kind];
          return (
            <div
              key={t.id}
              role="status"
              className={clsx(
                "pointer-events-auto flex animate-slide-down items-start gap-2 rounded-md border px-3 py-2 text-[12px] leading-relaxed shadow-overlay",
                s.cls,
              )}
            >
              <s.Icon size={14} className="mt-px shrink-0" />
              <span className="min-w-0 flex-1 break-words">{t.msg}</span>
              <button onClick={() => dismiss(t.id)} className="shrink-0 opacity-60 transition-opacity hover:opacity-100" aria-label="Dismiss">
                <X size={12} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastCtx.Provider>
  );
}

/* ================================================================== Misc */

export { ChevronDown };
