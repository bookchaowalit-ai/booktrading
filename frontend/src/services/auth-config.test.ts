import { afterEach, describe, expect, it, vi } from 'vitest';

import { CLOSED_AUTH_CONFIG, REGISTRATION_ERRORS_TH, getAuthConfig, register } from './auth';

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { 'Content-Type': 'application/json' } });
}

describe('getAuthConfig', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it('reads the public registration flags', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(200, { registrationOpen: true, inviteRequired: true }));
    await expect(getAuthConfig()).resolves.toEqual({ registrationOpen: true, inviteRequired: true });
    expect((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][0]).toBe('/api/auth/config');
  });

  it('fails closed on errors, old backends and odd payloads', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(404, {}));
    await expect(getAuthConfig()).resolves.toEqual(CLOSED_AUTH_CONFIG);
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(200, { registrationOpen: 'yes' }));
    await expect(getAuthConfig()).resolves.toEqual(CLOSED_AUTH_CONFIG);
    global.fetch = vi.fn().mockRejectedValue(new Error('offline'));
    await expect(getAuthConfig()).resolves.toEqual(CLOSED_AUTH_CONFIG);
  });
});

describe('register 403', () => {
  const realFetch = global.fetch;
  afterEach(() => {
    global.fetch = realFetch;
  });

  it('explains closed registration in Thai', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(403, { error: 'Registration is disabled', code: 'registration_closed' }));
    const res = await register('a@example.test', 'Secret123', 'A');
    expect(res).toEqual({ success: false, error: REGISTRATION_ERRORS_TH.registration_closed });
  });

  it('explains a wrong invite code in Thai and sends the code', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(403, { code: 'invite_invalid' }));
    const res = await register('a@example.test', 'Secret123', 'A', 'fixture-invite');
    expect(res.error).toBe(REGISTRATION_ERRORS_TH.invite_invalid);
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body.inviteCode).toBe('fixture-invite');
  });

  it('omits inviteCode when none is given', async () => {
    global.fetch = vi.fn().mockResolvedValue(jsonResponse(201, { token: 't', user: { id: '1', email: 'a', name: 'A', role: 'trader' } }));
    await register('a@example.test', 'Secret123', 'A');
    const body = JSON.parse((global.fetch as ReturnType<typeof vi.fn>).mock.calls[0][1].body);
    expect(body).not.toHaveProperty('inviteCode');
  });
});
