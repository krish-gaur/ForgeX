"use client";

// Operator login — real auth against /api/v1/auth/login (JWT + refresh cookie).
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { Btn, Field } from "@/components/ui";

const DEMO_ACCOUNTS = [
  { role: "ADMIN", username: "admin", password: "ForgeX-Admin-2026!", description: "Users · policies · audit · demo seed" },
  { role: "LEAD INVESTIGATOR", username: "lead", password: "ForgeX-Lead-2026!", description: "Cases · execution · reports" },
  { role: "INVESTIGATOR", username: "investigator", password: "ForgeX-Investigator-2026!", description: "Own cases · policy-restricted" },
  { role: "AUDITOR", username: "auditor", password: "ForgeX-Auditor-2026!", description: "Read-only · audit trail" },
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
        <div className="mb-6 flex flex-col items-center gap-2.5 px-2 text-center">
          <svg width="54" height="54" viewBox="0 0 32 32" aria-hidden>
            <polygon points="16,2 29,9.5 29,22.5 16,30 3,22.5 3,9.5" fill="none" stroke="#3dff9e" strokeWidth="1.4" />
            <polygon points="16,8 23.5,12.2 23.5,19.8 16,24 8.5,19.8 8.5,12.2" fill="rgba(61,255,158,0.12)" stroke="#35d6ff" strokeWidth="0.9" />
            <circle cx="16" cy="16" r="2.2" fill="#3dff9e" />
          </svg>
          <h1 className="text-xl font-black uppercase tracking-[0.4em] text-ink">
            FORGE<span className="text-phosphorDim glow-text">·X</span>
          </h1>
          <p className="text-[10.5px] uppercase tracking-[0.2em] text-faint">
            Forensic Intelligence Workbench
            <span className="mt-1 block tracking-[0.28em]">SIH26148 · NTRO</span>
          </p>
        </div>

        <form onSubmit={submit} className="panel p-5 sm:p-6">
          <p className="hud-title">// operator authentication</p>
          <div className="mt-4 space-y-4">
            <Field label="Username">
              <input className="input h-10" value={username} onChange={(e) => setUsername(e.target.value)} autoComplete="username" autoFocus required />
            </Field>
            <Field label="Passphrase">
              <input className="input h-10" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoComplete="current-password" required />
            </Field>
          </div>
          {(localErr || error) && (
            <p className="mt-4 border border-alarm/50 bg-alarm/10 px-3 py-2 text-[11.5px] text-alarm">⚠ {localErr ?? error}</p>
          )}
          <Btn type="submit" variant="primary" busy={busy} className="mt-4 h-10 w-full">
            {busy ? "Signing in…" : "Sign in"}
          </Btn>
        </form>

        <div className="panel panel-dim mt-5 p-4 sm:p-5">
          <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-amber">
            Demo accounts
          </p>
          <p className="mt-1 text-[10px] text-faint">Seeded on first boot. Select an account to fill the form.</p>
          <ul className="mt-3 space-y-2">
            {DEMO_ACCOUNTS.map((a) => (
              <li key={a.username}>
                <button
                  type="button"
                  className="group w-full rounded-md border border-grid bg-panel2/40 px-3 py-2.5 text-left transition-[border-color,background-color] hover:border-phosphorDim hover:bg-panel2/70 focus-visible:border-accent"
                  onClick={() => {
                    setUsername(a.username);
                    setPassword(a.password);
                  }}
                >
                  <span className="flex items-center justify-between gap-3">
                    <span className="text-[10px] font-bold uppercase tracking-[0.1em] text-muted">{a.role}</span>
                    <span className="text-[10px] text-faint">select</span>
                  </span>
                  <span className="mt-1 block font-mono text-[11.5px] text-phosphorDim group-hover:glow-text">{a.username}</span>
                  <span className="mt-0.5 block break-all font-mono text-[10.5px] text-muted">{a.password}</span>
                  <span className="mt-1.5 block text-[10px] text-faint">{a.description}</span>
                </button>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[10px] leading-relaxed text-faint">
            All demonstration data produced by these accounts is clearly labeled SYNTHETIC.
          </p>
        </div>
      </div>
    </div>
  );
}
