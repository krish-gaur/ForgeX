"use client";

import type { ReactNode } from "react";
import { AuthProvider } from "@/lib/auth";
import { ToastHost } from "@/components/ui";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <AuthProvider>
      <ToastHost>{children}</ToastHost>
    </AuthProvider>
  );
}
