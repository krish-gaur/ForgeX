import type { Metadata } from "next";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "FORGE·X — Forensic Intelligence Workbench",
  description:
    "ForgeX (SIH26148, NTRO): a controlled forensic scripting workbench — intent-level FQL queries and sandboxed forensic functions that collect, hash, correlate and explain evidence without tripping endpoint defenses.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
