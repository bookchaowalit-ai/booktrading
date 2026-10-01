import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { api } from './api';
import {
  FORBIDDEN_EVENT,
  FORBIDDEN_MESSAGE_TH,
  errorMessageFromResponse,
  installForbiddenWatcher,
  isBackendApiUrl,
  resetForbiddenReports,
} from './forbidden';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  });
}

describe('errorMessageFromResponse', () => {
  it('maps 403 to the Thai admin-only message', async () => {
    const msg = await errorMessageFromResponse(jsonResponse(403, { error: 'Admin role required' }), 'Failed');
    expect(msg).toBe(FORBIDDEN_MESSAGE_TH);
    expect(msg).toMatch(/แอดมิน/);
  });

  it('keeps the backend error or the fallback for other statuses', async () => {
    expect(await errorMessageFromResponse(jsonResponse(400, { error: 'bad symbol' }), 'Failed')).toBe('bad symbol');
    expect(await errorMessageFromResponse(new Response('not json', { status: 500 }), 'Failed')).toBe('Failed');
  });
});

describe('isBackendApiUrl', () => {
  it('matches backend and strategy-proxy paths only', () => {
    expect(isBackendApiUrl('/api/bot/start')).toBe(true);
    expect(isBackendApiUrl('http://localhost:8080/api/orders')).toBe(true);
    expect(isBackendApiUrl('/strategy-api/api/real-grid/kill')).toBe(true);
    expect(isBackendApiUrl('https://api.coingecko.com/v3/simple')).toBe(false);
    expect(isBackendApiUrl('/en/dashboard')).toBe(false);
  });
});

describe('installForbiddenWatcher', () => {
  let host: { fetch: typeof fetch };
  let uninstall: () => void;
  const events: string[] = [];
  const onForbidden = (e: Event) => events.push((e as CustomEvent).detail.message);

  beforeEach(() => {
    resetForbiddenReports();
    events.length = 0;
    window.addEventListener(FORBIDDEN_EVENT, onForbidden);
  });

  afterEach(() => {
    uninstall?.();
    window.removeEventListener(FORBIDDEN_EVENT, onForbidden);
  });

  it('reports a 403 from an admin-only backend route and still returns the response', async () => {
    host = { fetch: vi.fn().mockResolvedValue(jsonResponse(403, { error: 'Admin role required' })) };
    uninstall = installForbiddenWatcher(host);
    const res = await host.fetch('/api/bot/start', { method: 'POST' });
    expect(res.status).toBe(403);
    expect(events).toEqual([FORBIDDEN_MESSAGE_TH]);
  });

  it('ignores successes, 401s, auth endpoints and third-party URLs', async () => {
    const inner = vi.fn();
    host = { fetch: inner as unknown as typeof fetch };
    uninstall = installForbiddenWatcher(host);
    inner.mockResolvedValueOnce(jsonResponse(200, {}));
    await host.fetch('/api/balance');
    inner.mockResolvedValueOnce(jsonResponse(401, {}));
    await host.fetch('/api/balance');
    inner.mockResolvedValueOnce(jsonResponse(403, { code: 'registration_closed' }));
    await host.fetch('/api/auth/register', { method: 'POST' });
    inner.mockResolvedValueOnce(jsonResponse(403, {}));
    await host.fetch('https://example.test/other');
    expect(events).toEqual([]);
  });

  it('deduplicates polling and installs only once', async () => {
    host = { fetch: vi.fn().mockImplementation(async () => jsonResponse(403, {})) };
    uninstall = installForbiddenWatcher(host);
    const second = installForbiddenWatcher(host);
    await host.fetch(new Request('http://localhost/api/settings/export', { method: 'POST' }));
    await host.fetch('/api/settings/export');
    expect(events).toHaveLength(1);
    second();
  });

  it('restores the original fetch on uninstall', () => {
    const original = vi.fn() as unknown as typeof fetch;
    host = { fetch: original };
    uninstall = installForbiddenWatcher(host);
    expect(host.fetch).not.toBe(original);
    uninstall();
    expect(host.fetch).toBe(original);
  });
});

describe('api client 403 handling', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it('throws the Thai message instead of the raw backend text', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(403, { error: 'Admin role required' }));
    await expect(api.startBot()).rejects.toThrow(FORBIDDEN_MESSAGE_TH);
  });

  it('keeps the backend message for other failures', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(400, { error: 'grid levels must be > 0' }));
    await expect(api.startBot()).rejects.toThrow('grid levels must be > 0');
  });
});
