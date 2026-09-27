// ForgeX API client — same-origin calls proxied to FastAPI by next.config rewrites.
// Handles the JWT access token, transparent refresh via the httpOnly cookie,
// and the standard error envelope {error:{code,message,details,request_id}}.

export class ApiError extends Error {
  code: string;
  status: number;
  details: unknown;
  requestId: string | null;
  constructor(status: number, code: string, message: string, details: unknown = null, requestId: string | null = null) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
    this.requestId = requestId;
  }
}

const TOKEN_KEY = "forgex_access_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return sessionStorage.getItem(TOKEN_KEY);
}
export function setToken(t: string | null) {
  if (typeof window === "undefined") return;
  if (t) sessionStorage.setItem(TOKEN_KEY, t);
  else sessionStorage.removeItem(TOKEN_KEY);
}

async function refreshOnce(): Promise<boolean> {
  try {
    const r = await fetch("/api/v1/auth/refresh", { method: "POST", credentials: "same-origin" });
    if (!r.ok) return false;
    const j = await r.json();
    if (j?.access_token) {
      setToken(j.access_token);
      return true;
    }
    return false;
  } catch {
    return false;
  }
}

async function raw(method: string, url: string, body?: unknown, retry = true): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";
  const r = await fetch(url, {
    method,
    headers,
    credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (r.status === 401 && retry && (await refreshOnce())) {
    return raw(method, url, body, false);
  }
  return r;
}

async function parseError(r: Response): Promise<ApiError> {
  let code = "HTTP_ERROR";
  let message = `Request failed (${r.status})`;
  let details: unknown = null;
  let requestId: string | null = null;
  try {
    const j = await r.json();
    if (j?.error) {
      code = j.error.code ?? code;
      message = j.error.message ?? message;
      details = j.error.details ?? null;
      requestId = j.error.request_id ?? null;
    }
  } catch {
    /* non-JSON error body */
  }
  return new ApiError(r.status, code, message, details, requestId);
}

export async function api<T = unknown>(method: string, url: string, body?: unknown): Promise<T> {
  const r = await raw(method, url, body);
  if (!r.ok) throw await parseError(r);
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

export const get = <T = unknown>(url: string) => api<T>("GET", url);
export const post = <T = unknown>(url: string, body?: unknown) => api<T>("POST", url, body ?? {});
export const put = <T = unknown>(url: string, body?: unknown) => api<T>("PUT", url, body ?? {});
export const patch = <T = unknown>(url: string, body?: unknown) => api<T>("PATCH", url, body ?? {});

/** Authenticated file download (PDF/CSV) via blob. */
export async function download(url: string, filename: string): Promise<void> {
  const r = await raw("GET", url);
  if (!r.ok) throw await parseError(r);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 4000);
}

export function qs(params: Record<string, string | number | boolean | undefined | null>): string {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined && v !== null && v !== "") u.set(k, String(v));
  }
  const s = u.toString();
  return s ? `?${s}` : "";
}
