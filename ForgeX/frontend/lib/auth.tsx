"use client";

// Auth context: login/logout, current user, role gates.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { get, post, setToken, getToken, ApiError } from "@/lib/api";
import type { Me, Role } from "@/lib/types";

interface AuthState {
  user: Me | null;
  loading: boolean;
  error: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (...roles: Role[]) => boolean;
  refresh: () => Promise<void>;
}

const AuthContext = createContext<AuthState | null>(null);

const ROLE_RANK: Record<Role, number> = { INVESTIGATOR: 1, AUDITOR: 1, LEAD_INVESTIGATOR: 2, ADMIN: 3 };

export function roleAtLeast(user: Me | null, min: Role): boolean {
  if (!user) return false;
  return ROLE_RANK[user.role] >= ROLE_RANK[min];
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const loadMe = useCallback(async () => {
    if (!getToken()) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const me = await get<Me>("/api/v1/auth/me");
      setUser(me);
    } catch {
      setToken(null);
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMe();
  }, [loadMe]);

  const login = useCallback(async (username: string, password: string) => {
    setError(null);
    try {
      const r = await post<{ access_token: string; user: Me }>("/api/v1/auth/login", { username, password });
      setToken(r.access_token);
      setUser(r.user ?? (await get<Me>("/api/v1/auth/me")));
    } catch (e) {
      const msg = e instanceof ApiError ? e.message : "Login failed — is the backend running?";
      setError(msg);
      throw e;
    }
  }, []);

  const logout = useCallback(async () => {
    try {
      await post("/api/v1/auth/logout");
    } catch {
      /* best-effort */
    }
    setToken(null);
    setUser(null);
  }, []);

  const value = useMemo<AuthState>(
    () => ({
      user,
      loading,
      error,
      login,
      logout,
      hasRole: (...roles: Role[]) => (user ? roles.includes(user.role) : false),
      refresh: loadMe,
    }),
    [user, loading, error, login, logout, loadMe],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth outside AuthProvider");
  return ctx;
}
