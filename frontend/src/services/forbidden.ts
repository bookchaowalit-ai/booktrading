/**
 * 403 handling for admin-only backend routes.
 *
 * The Go backend answers 403 {"error": "Admin role required"} when a
 * non-admin session calls an admin-only route (route_access.go). The UI hides
 * most of those controls already; this module makes the remaining cases show
 * a clear Thai message instead of failing silently or with an English error.
 */

export const FORBIDDEN_MESSAGE_TH =
  'บัญชีนี้ไม่มีสิทธิ์ทำรายการนี้ — ต้องเข้าสู่ระบบด้วยบัญชีผู้ดูแลระบบ (แอดมิน)';

/** Window event fired (detail: {url, message}) when a backend call returns 403. */
export const FORBIDDEN_EVENT = 'booktrading:forbidden';

export interface ForbiddenEventDetail {
  url: string;
  message: string;
}

// Auth endpoints show their own messages (closed registration, invite code).
const AUTH_PATHS = ['/api/auth/login', '/api/auth/register', '/api/auth/config'];

function pathOf(url: string): string {
  try {
    return new URL(url, 'http://localhost').pathname;
  } catch {
    return url;
  }
}

/** True for calls to the Go backend (/api/*) or its strategy proxy (/strategy-api/*). */
export function isBackendApiUrl(url: string): boolean {
  const path = pathOf(url);
  return path.startsWith('/api/') || path.startsWith('/strategy-api/');
}

function isAuthUrl(url: string): boolean {
  return AUTH_PATHS.includes(pathOf(url));
}

// Every 403 shows the same message, and a page often polls several admin
// routes at once: one notice per few seconds is enough.
const DEDUP_MS = 3000;
let lastReportAt = -Infinity;

/** Fire FORBIDDEN_EVENT, at most once per DEDUP_MS. */
export function reportForbidden(url: string, now: number = Date.now()): boolean {
  if (typeof window === 'undefined') return false;
  if (now - lastReportAt < DEDUP_MS) return false;
  lastReportAt = now;
  window.dispatchEvent(
    new CustomEvent<ForbiddenEventDetail>(FORBIDDEN_EVENT, {
      detail: { url, message: FORBIDDEN_MESSAGE_TH },
    }),
  );
  return true;
}

/** Test hook: forget the last report so dedup does not leak across tests. */
export function resetForbiddenReports(): void {
  lastReportAt = -Infinity;
}

/**
 * Error text for a failed backend response: the Thai admin-only message for
 * a 403, otherwise the backend's `error` field or `fallback`.
 */
export async function errorMessageFromResponse(response: Response, fallback: string): Promise<string> {
  if (response.status === 403) return FORBIDDEN_MESSAGE_TH;
  let data: unknown = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  const msg = data && typeof data === 'object' && typeof (data as { error?: unknown }).error === 'string'
    ? (data as { error: string }).error
    : '';
  return msg || fallback;
}

const INSTALLED = Symbol.for('booktrading.forbiddenWatcher');

type FetchHost = { fetch: typeof fetch; [INSTALLED]?: typeof fetch };

function requestUrl(input: RequestInfo | URL): string {
  if (typeof input === 'string') return input;
  if (input instanceof URL) return input.toString();
  return input.url;
}

/**
 * Wrap host.fetch so every backend 403 (outside the auth endpoints) fires
 * FORBIDDEN_EVENT. The many service modules call fetch directly, so this is
 * the one place that sees all of them. Idempotent; returns an uninstaller.
 */
export function installForbiddenWatcher(host: FetchHost = window as unknown as FetchHost): () => void {
  if (host[INSTALLED]) return () => {};
  const original = host.fetch;
  host[INSTALLED] = original;
  host.fetch = (async (input: RequestInfo | URL, init?: RequestInit) => {
    const response = await original(input, init);
    try {
      const url = requestUrl(input);
      if (response.status === 403 && isBackendApiUrl(url) && !isAuthUrl(url)) {
        reportForbidden(url);
      }
    } catch {
      // Never let the watcher break a request.
    }
    return response;
  }) as typeof fetch;
  return () => {
    if (host[INSTALLED] === original) {
      host.fetch = original;
      delete host[INSTALLED];
    }
  };
}
