"use client";

// Command entry: searches investigations through the existing case registry
// endpoint and exposes the primary navigation targets. No new API surface.
import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Boxes, CornerDownLeft, FolderKanban, ListChecks, Network, ScrollText, Settings, TerminalSquare } from "lucide-react";
import { get, qs } from "@/lib/api";
import type { Investigation, Paginated } from "@/lib/types";
import { StatusPill } from "@/components/ui";

const DESTINATIONS = [
  { label: "Overview", href: "/", icon: Boxes },
  { label: "Investigations", href: "/cases", icon: FolderKanban },
  { label: "Findings review", href: "/cases", icon: ListChecks },
  { label: "Function templates", href: "/templates", icon: TerminalSquare },
  { label: "Audit log", href: "/audit", icon: ScrollText },
  { label: "Settings", href: "/settings", icon: Settings },
];

interface Row {
  key: string;
  label: string;
  hint?: string;
  href: string;
  icon: typeof Boxes;
  status?: string;
}

export default function CommandSearch({ onNavigate }: { onNavigate?: () => void }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [rows, setRows] = useState<Row[]>([]);
  const [cursor, setCursor] = useState(0);
  const [searching, setSearching] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const listRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (open) {
      setQ("");
      setCursor(0);
      const t = setTimeout(() => inputRef.current?.focus(), 10);
      return () => clearTimeout(t);
    }
  }, [open]);

  useEffect(() => {
    const term = q.trim();
    if (term.length < 2) {
      setRows([]);
      setSearching(false);
      return;
    }
    let alive = true;
    setSearching(true);
    const t = setTimeout(() => {
      get<Paginated<Investigation>>(`/api/v1/investigations${qs({ search: term, per_page: 8 })}`)
        .then((r) => {
          if (!alive) return;
          setRows(
            (r.data ?? []).map((c) => ({
              key: c.id,
              label: c.name,
              hint: c.target_host,
              href: `/cases/${c.id}`,
              icon: Network,
              status: c.status,
            })),
          );
          setCursor(0);
        })
        .catch(() => alive && setRows([]))
        .finally(() => alive && setSearching(false));
    }, 180);
    return () => {
      alive = false;
      clearTimeout(t);
    };
  }, [q]);

  const term = q.trim();
  const navRows: Row[] = DESTINATIONS.map((d) => ({ key: `nav:${d.href}`, label: d.label, href: d.href, icon: d.icon }));
  const items: Row[] = term
    ? [
        ...rows,
        ...navRows.filter((d) => d.label.toLowerCase().includes(term.toLowerCase())),
      ]
    : navRows;

  function go(href: string) {
    setOpen(false);
    onNavigate?.();
    router.push(href);
  }

  function onListKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setCursor((c) => Math.min(items.length - 1, c + 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setCursor((c) => Math.max(0, c - 1));
    } else if (e.key === "Enter") {
      e.preventDefault();
      const row = items[cursor];
      if (row) go(row.href);
    } else if (e.key === "Escape") {
      setOpen(false);
    }
  }

  useEffect(() => {
    listRef.current?.querySelector('[data-active="true"]')?.scrollIntoView({ block: "nearest" });
  }, [cursor, items.length]);

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="group flex h-8 w-full max-w-md items-center gap-2 rounded-md border border-edge bg-panel2/60 px-2.5 text-left transition-[border-color,background-color] duration-[120ms] hover:border-edge2 hover:bg-panel"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden className="shrink-0 text-faint">
          <circle cx="11" cy="11" r="7" />
          <path d="m20 20-3.5-3.5" />
        </svg>
        <span className="flex-1 truncate text-[12px] text-faint">Search investigations…</span>
        <span className="hidden shrink-0 items-center gap-0.5 sm:flex">
          <span className="kbd">Ctrl</span>
          <span className="kbd">K</span>
        </span>
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-[60] flex items-start justify-center bg-[#101828]/30 p-4 pt-[12vh]" onClick={() => setOpen(false)}>
      <div
        className="panel w-full max-w-xl animate-pop-in overflow-hidden shadow-overlay"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Command search"
      >
        <div className="flex items-center gap-2 border-b border-edge px-3">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden className="shrink-0 text-faint">
            <circle cx="11" cy="11" r="7" />
            <path d="m20 20-3.5-3.5" />
          </svg>
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            onKeyDown={onListKey}
            placeholder="Search investigations by name, target or id…"
            className="h-11 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-faint"
          />
          <span className="kbd shrink-0">esc</span>
        </div>

        <div ref={listRef} className="max-h-[22rem] overflow-y-auto p-1">
          {searching && <p className="px-2 py-3 text-[12px] text-muted">Searching registry…</p>}
          {!searching && items.length === 0 && (
            <p className="px-2 py-3 text-[12px] text-muted">
              {term ? `No investigations match “${term}”.` : "Start typing to search the case registry."}
            </p>
          )}
          {items.map((row, i) => {
            const Icon = row.icon;
            return (
              <button
                key={row.key}
                data-active={i === cursor}
                onMouseEnter={() => setCursor(i)}
                onClick={() => go(row.href)}
                className={`flex w-full items-center gap-2.5 rounded-md px-2 py-2 text-left transition-colors duration-[120ms] ${
                  i === cursor ? "bg-accentSoft" : "hover:bg-panel2"
                }`}
              >
                <Icon size={14} className={clsxIcon(i === cursor)} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12.5px] font-medium text-ink">{row.label}</span>
                  {row.hint && <span className="block truncate font-mono text-[10.5px] text-faint">{row.hint}</span>}
                </span>
                {row.status && <StatusPill status={row.status} />}
                {i === cursor && <CornerDownLeft size={12} className="shrink-0 text-faint" />}
              </button>
            );
          })}
        </div>

        <div className="flex items-center gap-3 border-t border-edge bg-panel2/50 px-3 py-1.5 text-[10.5px] text-faint">
          <span className="flex items-center gap-1">
            <span className="kbd">↑</span>
            <span className="kbd">↓</span> navigate
          </span>
          <span className="flex items-center gap-1">
            <span className="kbd">↵</span> open
          </span>
          <span className="flex-1 truncate text-right">Results are scoped to your access</span>
        </div>
      </div>
    </div>
  );
}

function clsxIcon(active: boolean): string {
  return active ? "shrink-0 text-accent" : "shrink-0 text-faint";
}
