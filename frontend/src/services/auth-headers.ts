/**
 * Session auth headers shared by every service that calls a protected route.
 *
 * The bearer token is the signed-in session token the login flow stores in
 * localStorage (`auth_token`); no server secret is ever bundled for the
 * browser. Strategy calls go through the same-origin `/strategy-api` proxy.
 */

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return window.localStorage.getItem('auth_token');
  } catch {
    return null;
  }
}

export function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const token = getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  if (extra) {
    Object.assign(headers, extra);
  }
  return headers;
}

/** Strategy API base: same-origin proxy unless explicitly configured. */
export const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';
