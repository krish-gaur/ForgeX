"use client";

// Minimal data hook: fetch on mount/deps, manual reload, error capture.
import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";

interface DataState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
  reload: () => void;
}

export function useData<T>(fetcher: () => Promise<T>, deps: unknown[] = []): DataState<T> {
  const [data, setData] = useState<T | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [nonce, setNonce] = useState(0);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    let alive = true;
    setLoading(true);
    fetcher()
      .then((d) => {
        if (alive && mounted.current) {
          setData(d);
          setError(null);
        }
      })
      .catch((e) => {
        if (alive && mounted.current) setError(e instanceof ApiError ? `${e.code}: ${e.message}` : e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (alive && mounted.current) setLoading(false);
      });
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, loading, error, reload };
}

export function errMsg(e: unknown): string {
  if (e instanceof ApiError) return `${e.code}: ${e.message}`;
  return e instanceof Error ? e.message : String(e);
}
