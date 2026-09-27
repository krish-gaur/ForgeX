"use client";

// Authenticated area: boot screen → auth gate → Shell chrome.
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import Shell from "@/components/Shell";
import { useAuth } from "@/lib/auth";

function Boot() {
  return (
    <div className="flex h-screen flex-col items-center justify-center gap-3 bg-void">
      <svg width="30" height="30" viewBox="0 0 32 32" aria-hidden className="animate-pulse-dot">
        <polygon points="16,2.5 28,9.5 28,22.5 16,29.5 4,22.5 4,9.5" fill="none" stroke="#2563EB" strokeWidth="1.8" strokeLinejoin="round" />
        <polygon points="16,9 22.5,12.8 22.5,19.2 16,23 9.5,19.2 9.5,12.8" fill="#EFF4FF" stroke="#2563EB" strokeWidth="1.1" strokeLinejoin="round" />
      </svg>
      <p className="text-[11px] font-medium uppercase tracking-[0.18em] text-muted">Restoring session</p>
    </div>
  );
}

export default function MainLayout({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!loading && !user) router.replace("/login");
  }, [loading, user, router]);

  if (loading) return <Boot />;
  if (!user) return <Boot />;
  return <Shell>{children}</Shell>;
}
