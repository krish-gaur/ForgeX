"use client";

// Settings: operator profile, RBAC matrix, demo controls, user management
// (ADMIN) and the collection-policy engine console (ADMIN authors, LEAD reads).
import dynamic from "next/dynamic";
import { useState } from "react";
import { KeyRound, ShieldCheck, UserPlus, Zap } from "lucide-react";
import { get, post, patch } from "@/lib/api";
import { errMsg, useData } from "@/lib/useData";
import { Btn, Empty, Field, Modal, Panel, Spinner, StatusPill, useToast } from "@/components/ui";
import { roleAtLeast, useAuth } from "@/lib/auth";
import { fmtTime } from "@/lib/format";

const Monaco = dynamic(() => import("@/components/Monaco"), { ssr: false });

interface AdminUser {
  id: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  created_at: string | null;
}
interface PolicyRow {
  id: string;
  name: string;
  description?: string | null;
  rules: Record<string, unknown>;
  is_default: boolean;
  is_active: boolean;
}

const RBAC_MATRIX: Array<{ cap: string; admin: string; lead: string; inv: string; aud: string }> = [
  { cap: "Open / close cases", admin: "âœ“", lead: "âœ“", inv: "open own", aud: "â€”" },
  { cap: "Run FQL collection", admin: "âœ“", lead: "âœ“", inv: "policy-gated", aud: "â€”" },
  { cap: "Network collector", admin: "âœ“", lead: "âœ“", inv: "denied by policy", aud: "â€”" },
  { cap: "Script Lab executions", admin: "âœ“", lead: "âœ“", inv: "âœ“ own cases", aud: "â€”" },
  { cap: "Findings verify/dismiss", admin: "âœ“", lead: "âœ“", inv: "âœ“", aud: "â€”" },
  { cap: "AI correlation / Q&A", admin: "âœ“", lead: "âœ“", inv: "âœ“", aud: "read results", },
  { cap: "Generate / download reports", admin: "âœ“", lead: "âœ“", inv: "âœ“", aud: "â€”" },
  { cap: "Read audit trail", admin: "âœ“", lead: "â€”", inv: "â€”", aud: "âœ“" },
  { cap: "User management", admin: "âœ“", lead: "â€”", inv: "â€”", aud: "â€”" },
  { cap: "Author collection policies", admin: "âœ“", lead: "read", inv: "read (preview)", aud: "â€”" },
  { cap: "Seed demo data", admin: "âœ“", lead: "âœ“", inv: "â€”", aud: "â€”" },
];

const STARTER_POLICY_YAML = `name: hardened-investigation-policy
description: Stricter variant â€” network collection requires lead role and active case.
allowed_collectors:
  - processes
  - files
  - users
  - events
  - timeline
restricted_collectors:
  network:
    required_role: LEAD_INVESTIGATOR
    requires_case_status: ACTIVE
    max_capture_duration_sec: 300
    log_mandatory: true
field_restrictions:
  files:
    excluded_paths: ["/proc", "/sys", "/dev"]
    max_depth: 6
    max_file_bytes: 10485760
  events:
    max_items: 2000
rate_limits:
  max_executions_per_hour_per_investigator: 10
  max_concurrent_jobs: 2
`;

function UsersPanel() {
  const toast = useToast();
  const users = useData<{ data: AdminUser[] }>(() => get("/api/v1/admin/users"), []);
  const [modal, setModal] = useState(false);
  const [form, setForm] = useState({ username: "", email: "", password: "", role: "INVESTIGATOR" });
  const [busy, setBusy] = useState(false);
  const [pwFor, setPwFor] = useState<AdminUser | null>(null);
  const [newPw, setNewPw] = useState("");

  async function createUser() {
    setBusy(true);
    try {
      await post("/api/v1/admin/users", form);
      toast("ok", `User ${form.username} created with role ${form.role}.`);
      setModal(false);
      setForm({ username: "", email: "", password: "", role: "INVESTIGATOR" });
      users.reload();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setBusy(false);
    }
  }

  async function toggle(u: AdminUser) {
    try {
      await patch(`/api/v1/admin/users/${u.id}`, { is_active: !u.is_active });
      toast("ok", `${u.username} ${u.is_active ? "deactivated" : "reactivated"}.`);
      users.reload();
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  async function changeRole(u: AdminUser, role: string) {
    try {
      await patch(`/api/v1/admin/users/${u.id}`, { role });
      toast("ok", `${u.username} role â†’ ${role}.`);
      users.reload();
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  async function resetPw() {
    if (!pwFor || newPw.length < 8) return;
    try {
      await patch(`/api/v1/admin/users/${pwFor.id}`, { password: newPw });
      toast("ok", `Passphrase for ${pwFor.username} reset (audit-logged).`);
      setPwFor(null);
      setNewPw("");
    } catch (e) {
      toast("err", errMsg(e));
    }
  }

  return (
    <Panel
      title={`operator accounts â€” ${users.data?.data.length ?? "â€¦"}`}
      right={<Btn size="sm" variant="primary" onClick={() => setModal(true)}><UserPlus size={11} /> new user</Btn>}
    >
      {users.loading && <div className="p-4"><Spinner /></div>}
      {users.error && <div className="p-3 text-[12px] text-alarm">âš  {users.error}</div>}
      <table className="tbl">
        <thead>
          <tr><th>username</th><th>email</th><th>role</th><th>state</th><th>created</th><th className="text-right">actions</th></tr>
        </thead>
        <tbody>
          {(users.data?.data ?? []).map((u) => (
            <tr key={u.id}>
              <td className="font-bold text-ink">{u.username}</td>
              <td className="text-muted">{u.email}</td>
              <td>
                <select className="select !w-44 !py-0.5 text-[10.5px]" value={u.role} onChange={(e) => void changeRole(u, e.target.value)}>
                  {["ADMIN", "LEAD_INVESTIGATOR", "INVESTIGATOR", "AUDITOR"].map((r) => <option key={r} value={r}>{r}</option>)}
                </select>
              </td>
              <td>{u.is_active ? <StatusPill status="OPEN" /> : <span className="badge border-alarm/50 text-alarm">DISABLED</span>}</td>
              <td className="text-faint">{fmtTime(u.created_at)}</td>
              <td className="space-x-1.5 text-right">
                <Btn size="sm" variant="ghost" onClick={() => { setPwFor(u); setNewPw(""); }}><KeyRound size={10} /> passwd</Btn>
                <Btn size="sm" variant={u.is_active ? "danger" : "primary"} onClick={() => void toggle(u)}>
                  {u.is_active ? "disable" : "enable"}
                </Btn>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <Modal open={modal} onClose={() => setModal(false)} title="create operator account">
        <div className="space-y-3">
          <Field label="username"><input className="input" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} /></Field>
          <Field label="email"><input className="input" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></Field>
          <Field label="initial passphrase" hint="min 8 characters"><input className="input" type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></Field>
          <Field label="role">
            <select className="select" value={form.role} onChange={(e) => setForm({ ...form, role: e.target.value })}>
              {["ADMIN", "LEAD_INVESTIGATOR", "INVESTIGATOR", "AUDITOR"].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </Field>
          <div className="flex justify-end gap-2">
            <Btn onClick={() => setModal(false)}>cancel</Btn>
            <Btn variant="primary" busy={busy} disabled={!form.username || !form.email || form.password.length < 8} onClick={() => void createUser()}>create</Btn>
          </div>
        </div>
      </Modal>

      {pwFor && (
        <Modal open onClose={() => setPwFor(null)} title={`reset passphrase â€” ${pwFor.username}`}>
          <div className="space-y-3">
            <Field label="new passphrase" hint="min 8 characters"><input className="input" type="password" value={newPw} onChange={(e) => setNewPw(e.target.value)} autoFocus /></Field>
            <div className="flex justify-end gap-2">
              <Btn onClick={() => setPwFor(null)}>cancel</Btn>
              <Btn variant="primary" disabled={newPw.length < 8} onClick={() => void resetPw()}>reset</Btn>
            </div>
          </div>
        </Modal>
      )}
    </Panel>
  );
}

function PoliciesPanel({ canAuthor }: { canAuthor: boolean }) {
  const toast = useToast();
  const policies = useData<{ data: PolicyRow[] }>(() => get("/api/v1/admin/policies"), []);
  const [openId, setOpenId] = useState<string | null>(null);
  const [yaml, setYaml] = useState(STARTER_POLICY_YAML);
  const [name, setName] = useState("");
  const [validating, setValidating] = useState(false);
  const [validation, setValidation] = useState<{ valid: boolean; error?: string } | null>(null);
  const [creating, setCreating] = useState(false);

  async function validate() {
    setValidating(true);
    setValidation(null);
    try {
      const r = await post<{ valid: boolean; error?: string }>("/api/v1/admin/policies/validate", {
        name: name.trim() || "draft", yaml,
      });
      setValidation(r);
    } catch (e) {
      setValidation({ valid: false, error: errMsg(e) });
    } finally {
      setValidating(false);
    }
  }

  async function create() {
    if (!name.trim()) return;
    setCreating(true);
    try {
      await post("/api/v1/admin/policies", { name: name.trim(), description: null, yaml, is_default: false });
      toast("ok", `Policy â€œ${name.trim()}â€ created â€” selectable per execution via policy_id.`);
      policies.reload();
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Panel title={`collection policies â€” ${policies.data?.data.length ?? "â€¦"}`}>
        {policies.loading && <div className="p-4"><Spinner /></div>}
        {policies.error && <div className="p-3 text-[12px] text-alarm">âš  {policies.error}</div>}
        {(policies.data?.data.length ?? 0) === 0 && !policies.loading && <Empty text="no policies" />}
        <div className="divide-y divide-grid">
          {(policies.data?.data ?? []).map((p) => (
            <div key={p.id}>
              <button className="flex w-full items-center gap-2 px-3 py-2.5 text-left hover:bg-panel2/60" onClick={() => setOpenId(openId === p.id ? null : p.id)}>
                <ShieldCheck size={14} className={p.is_default ? "text-phosphorDim" : "text-accent"} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[12px] font-bold text-ink">{p.name}</span>
                  {p.description && <span className="block truncate text-[10.5px] text-faint">{p.description}</span>}
                </span>
                {p.is_default && <span className="badge border-phosphorDim/60 text-phosphorDim">DEFAULT</span>}
                {p.is_active ? <StatusPill status="OPEN" /> : <span className="badge border-edge2 text-faint">INACTIVE</span>}
              </button>
              {openId === p.id && (
                <pre className="max-h-64 overflow-auto border-t border-grid bg-void/70 p-3 text-[10.5px] leading-relaxed text-phosphorDim/85">
                  {JSON.stringify(p.rules, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </Panel>

      {canAuthor ? (
        <Panel title="author policy (yaml)" variant="cyan">
          <div className="space-y-3 p-3">
            <Field label="policy name">
              <input className="input" value={name} onChange={(e) => setName(e.target.value)} placeholder="hardened-investigation-policy" />
            </Field>
            <Monaco value={yaml} onChange={setYaml} language="yaml" height={330} />
            <div className="flex flex-wrap items-center gap-2">
              <Btn variant="cyan" busy={validating} onClick={() => void validate()}>validate yaml</Btn>
              <Btn variant="primary" busy={creating} disabled={!name.trim()} onClick={() => void create()}>create policy</Btn>
              {validation && (
                <span className={`text-[11.5px] ${validation.valid ? "text-phosphorDim" : "text-alarm"}`}>
                  {validation.valid ? "âœ“ schema valid â€” rules parsed" : `âœ— ${validation.error}`}
                </span>
              )}
            </div>
            <p className="text-[10px] leading-relaxed text-faint">
              Policies gate collectors per role and case status, restrict fields (paths, capture duration, item caps) and
              rate-limit executions. The engine evaluates them BEFORE any collector touches a target â€” denials are
              audit-logged with reasons.
            </p>
          </div>
        </Panel>
      ) : (
        <Panel title="author policy" variant="dim">
          <div className="p-4">
            <Empty text="read-only" hint="Only ADMIN accounts can author collection policies. Your role can review the active ruleset on the left." />
          </div>
        </Panel>
      )}
    </div>
  );
}

export default function SettingsPage() {
  const { user, refresh } = useAuth();
  const toast = useToast();
  const [seeding, setSeeding] = useState(false);

  if (!user) return <div className="p-6"><Spinner /></div>;

  async function seedDemo() {
    setSeeding(true);
    try {
      const r = await post<{ case: string; investigation_id: string }>("/api/v1/demo/seed");
      toast("ok", `Demo case re-seeded: ${r.case} (synthetic).`);
    } catch (e) {
      toast("err", errMsg(e));
    } finally {
      setSeeding(false);
    }
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4">
      <h1 className="hud-title">// system settings</h1>

      <div className="grid gap-4 lg:grid-cols-3">
        <Panel title="operator profile">
          <div className="space-y-2 p-4 text-[12px]">
            <p><span className="text-faint">username:</span> <b className="text-ink">{user.username}</b></p>
            <p><span className="text-faint">email:</span> <span className="text-muted">{user.email}</span></p>
            <p><span className="text-faint">role:</span> <span className="badge border-violetx/60 text-muted">{user.role}</span></p>
            <p><span className="text-faint">account created:</span> <span className="text-muted">{fmtTime(user.created_at ?? null)}</span></p>
            <p className="border-t border-grid pt-2 text-[10.5px] leading-relaxed text-faint">
              Sessions use short-lived JWT access tokens plus an httpOnly refresh cookie (<code>forgex_refresh</code>).
              Logins are rate-limited per IP; every sensitive action is written to the audit trail with your identity.
            </p>
            <Btn variant="ghost" size="sm" onClick={() => void refresh()}>â†» refresh profile</Btn>
          </div>
        </Panel>

        <Panel title="demo controls" className="lg:col-span-2" variant="dim">
          <div className="space-y-2 p-4">
            {roleAtLeast(user, "LEAD_INVESTIGATOR") ? (
              <>
                <p className="text-[11.5px] leading-relaxed text-muted">
                  Re-seed the deterministic <b className="text-amber">DEMO-Corp-Breach-2026</b> scenario: a synthetic
                  corporate intrusion corpus (processes, auth logs, network captures incl. a real .pcap, registry,
                  browser, memory, users). All records are labeled <b className="text-amber">SYNTHETIC</b> end-to-end â€”
                  evidence rows, timeline, graph, findings, reports.
                </p>
                <Btn variant="primary" busy={seeding} onClick={() => void seedDemo()}>
                  <Zap size={13} /> re-seed demo case
                </Btn>
              </>
            ) : (
              <Empty text="restricted" hint="Demo seeding requires LEAD_INVESTIGATOR or ADMIN." />
            )}
          </div>
        </Panel>
      </div>

      <Panel title="rbac matrix">
        <div className="overflow-x-auto">
          <table className="tbl min-w-[640px]">
            <thead>
              <tr>
                <th>capability</th>
                <th className="text-center">admin</th>
                <th className="text-center">lead</th>
                <th className="text-center">investigator</th>
                <th className="text-center">auditor</th>
              </tr>
            </thead>
            <tbody>
              {RBAC_MATRIX.map((r) => (
                <tr key={r.cap}>
                  <td className="text-ink">{r.cap}</td>
                  {[r.admin, r.lead, r.inv, r.aud].map((v, i) => (
                    <td key={i} className={`text-center ${v === "âœ“" ? "text-phosphorDim" : v === "â€”" ? "text-faint" : "text-amber"}`}>{v}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      {user.role === "ADMIN" && (
        <div className="space-y-4">
          <UsersPanel />
          <PoliciesPanel canAuthor />
        </div>
      )}
      {user.role === "LEAD_INVESTIGATOR" && <PoliciesPanel canAuthor={false} />}
      {(user.role === "INVESTIGATOR" || user.role === "AUDITOR") && (
        <Panel title="operator accounts" variant="dim">
          <div className="p-4">
            <Empty text="restricted" hint="User management and policy authoring require the ADMIN role. Ask an administrator for account changes." />
          </div>
        </Panel>
      )}
    </div>
  );
}
