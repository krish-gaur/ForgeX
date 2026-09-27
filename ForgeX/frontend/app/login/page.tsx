"use client";

// Operator login â€” real auth against /api/v1/auth/login (JWT + refresh cookie).
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Btn, Field } from "@/components/ui";

const DEMO_ACCOUNTS = [
  { u: "admin", p: "ForgeX-Admin-2026!", r: "ADMIN â€” users, policies, audit, demo seed" },
  { u: "lead", p: "ForgeX-Lead-2026!", r: "LEAD INVESTIGATOR â€” cases, execution, reports" },
  { u: "investigator", p: "ForgeX-Investigator-2026!", r: "INVESTIGATOR â€” own cases, policy-restricted" },
  { u: "auditor", p: "ForgeX-Auditor-2026!", r: "AUDITOR â€” read-only + audit trail" },
];

export default function LoginPage() {
  const { user, loading, login, error } = useAuth();
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [localErr, setLocalErr] = useState<string | null>(null);

  useEffect(() => {
    if (!loading && user) router.replace("/");
  }, [loading, user, router]);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setLocalErr(null);
    try {
      await login(username.trim(), password);
      router.replace("/");
    } catch (err) {
      setLocalErr(err instanceof Error ? err.message : "Login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="relative flex min-h-screen items-center justify-center bg-void p-6">
      <div className="pointer-events-none absolute inset-0 opacity-60">
        <div className="absolute left-1/2 top-0 h-64 w-[42rem] -translate-x-1/2 bg-phosphor/5 blur-3xl" />
      </div>
      <div className="relative w-full max-w-md">
        <div className="mb-6 flex flex-col items-center gap-3">
          <svg width="54" height="54" viewBox="0 0 32 32" aria-hidden>
            <polygon points="16,2 29,9.5 29,22.5 16,30 3,22.5 3,9.5" fill="none" stroke="#3dff9e" strokeWidth="1.4" />
            <polygon points="16,8 23.5,12.2 23.5,19.8 16,24 8.5,19.8 8.5,12.2" fill="rgba(61,255,158,0.12)" stroke="#35d6ff" strokeWidth="0.9" />
            <circle cx="16" cy="16" r="2.2" fill="#3dff9e" />
          </svg>
          <h1 className="text-xl font-black uppercase tracking-[0.4em] text-ink">
            FORGE<span className="text-phosphorDim glow-text">Â·X</span>
          </h1>
          <p className="text-center text-[10.5px] uppercase tracking-[0.28em] text-faint">
            Forensic Intelligence Workbench Â· SIH26148 Â· NTRO
          </p>
        </div>

        <form onSubmit={submit} className="panel space-y-4 p-5">
          <p className="hud-title">// operator authentication</p>
          <Field label="Username">
            <input className="input" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
          </Field>
          <Field label="Passphrase">
            <input className="input" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
          </Field>
          {(localErr || error) && (
            <p className="border border-alarm/50 bg-alarm/10 px-3 py-2 text-[11.5px] text-alarm">âš  {localErr ?? error}</p>
          )}
          <Btn type="submit" variant="primary" busy={busy} className="w-full">
            {busy ? "authenticatingâ€¦" : "â–¸ authenticate"}
          </Btn>
        </form>

        <div className="panel panel-dim mt-4 p-4">
          <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-amber">
            demo credentials â€” seeded on first boot
          </p>
          <ul className="mt-2 space-y-1.5">
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.u}>
                <button
                  type="button"
                  className="group w-full border border-grid bg-panel2/40 px-2.5 py-1.5 text-left transition-colors hover:border-phosphorDim"
                  onClick={() => {
                    setUsername(a.u);
                    setPassword(a.p);
                  }}
                >
                  <span className="text-[11.5px] text-phosphorDim group-hover:glow-text">
                    {a.u} <span className="text-faint">/</span> {a.p}
                  </span>
                  <span className="block text-[10px] text-faint">{a.r}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-2 text-[10px] leading-relaxed text-faint">
            Click an account to fill the form. All demonstration data produced by these accounts is clearly labeled SYNTHETIC.
          </p>
        </div>
      </div>
    </div>
  );
}
