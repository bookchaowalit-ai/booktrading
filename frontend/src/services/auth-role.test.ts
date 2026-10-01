import { afterEach, describe, expect, it, vi } from 'vitest';

import { isAdmin } from './auth';

describe('isAdmin', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('accepts only the admin role', () => {
    expect(isAdmin({ role: 'admin' })).toBe(true);
    expect(isAdmin({ role: 'trader' })).toBe(false);
    expect(isAdmin({ role: '' })).toBe(false);
    expect(isAdmin(null)).toBe(false);
  });

  it('reads the stored user by default and fails closed on bad data', () => {
    const spy = vi.spyOn(Storage.prototype, 'getItem');
    spy.mockReturnValue(JSON.stringify({ id: '1', email: 'a@example.test', name: 'A', role: 'admin' }));
    expect(isAdmin()).toBe(true);
    spy.mockReturnValue(JSON.stringify({ id: '2', email: 'b@example.test', name: 'B', role: 'trader' }));
    expect(isAdmin()).toBe(false);
    spy.mockReturnValue('{not json');
    expect(isAdmin()).toBe(false);
    spy.mockReturnValue(null);
    expect(isAdmin()).toBe(false);
  });
});
