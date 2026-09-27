"use client";

// Breadcrumb trail published by nested layouts so the app shell can render an
// accurate trail (including the investigation name) without extra requests.
import { useEffect, useState } from "react";

export interface Crumb {
  label: string;
  href?: string;
}

let trail: Crumb[] = [];
const subscribers = new Set<(t: Crumb[]) => void>();

export function setBreadcrumb(next: Crumb[]): void {
  trail = next;
  subscribers.forEach((fn) => fn(trail));
}

export function useBreadcrumbTrail(): Crumb[] {
  const [t, setT] = useState<Crumb[]>(trail);
  useEffect(() => {
    const fn = (next: Crumb[]) => setT(next);
    subscribers.add(fn);
    return () => {
      subscribers.delete(fn);
    };
  }, []);
  return t;
}
