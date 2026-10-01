/**
 * The strategy routes behind @auth_required (airdrop-tracker writes,
 * backtest run/sweep, signal evaluation, real-grid kill/enable) must receive
 * the session bearer token, same as api.ts protected calls.
 */
import {
  afterEach,
  beforeEach,
  describe,
  expect,
  it,
  vi,
  type Mock,
  type MockInstance,
} from 'vitest';

import { airdropTrackerService } from './airdrop-tracker';
import { authHeaders, getAuthToken } from './auth-headers';
import { backtestService } from './backtest';
import { marketIntelService } from './market-intel';
import { monitoringService } from './monitoring';
import { signalTrackerService } from './signal-tracker';
import { tradeJournalService } from './trade-journal';

const okJson = () => ({ ok: true, json: async () => ({}), text: async () => '' });

describe('strategy services send the session bearer token', () => {
  let storage: MockInstance;

  beforeEach(() => {
    global.fetch = vi.fn().mockResolvedValue(okJson()) as unknown as typeof fetch;
    storage = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation((key: string) => (key === 'auth_token' ? 'fixture-session' : null));
  });

  afterEach(() => {
    storage.mockRestore();
  });

  const protectedCalls: Array<[string, () => Promise<unknown>, string, string]> = [
    [
      'airdrop add',
      () => airdropTrackerService.addTask({ name: 'x' }),
      'POST',
      '/api/airdrop-tracker/tasks',
    ],
    [
      'airdrop update',
      () => airdropTrackerService.updateTask('t1', { notes: 'n' }),
      'PATCH',
      '/api/airdrop-tracker/tasks/t1',
    ],
    [
      'airdrop subtask',
      () => airdropTrackerService.toggleSubtask('t1', 0, true),
      'PATCH',
      '/api/airdrop-tracker/tasks/t1/subtasks/0',
    ],
    [
      'airdrop delete',
      () => airdropTrackerService.deleteTask('t1'),
      'DELETE',
      '/api/airdrop-tracker/tasks/t1',
    ],
    [
      'backtest run',
      () => backtestService.runBacktest({ symbol: 'BTCTHB' } as never),
      'POST',
      '/api/backtest/run',
    ],
    [
      'backtest sweep',
      () => backtestService.runParameterSweep({ symbol: 'BTCTHB' }),
      'POST',
      '/api/backtest/sweep',
    ],
    [
      'signal evaluate',
      () => signalTrackerService.evaluate(),
      'POST',
      '/api/signal-tracker/evaluate',
    ],
    [
      'market-intel scan',
      () => marketIntelService.scan(0.3),
      'POST',
      '/api/market-intel/scan?min_confidence=0.3',
    ],
    ['kill switch', () => monitoringService.killBot(), 'POST', '/api/real-grid/kill'],
    ['enable bot', () => monitoringService.enableBot(), 'POST', '/api/real-grid/enable'],
  ];

  it.each(protectedCalls)('%s', async (_name, call, method, path) => {
    await call();
    expect(fetch).toHaveBeenCalledTimes(1);
    const [url, options] = (fetch as Mock).mock.calls[0];
    expect(url).toBe(`/strategy-api${path}`);
    expect(options.method).toBe(method);
    expect(options.headers.Authorization).toBe('Bearer fixture-session');
  });

  it('keeps the JSON body contract on writes', async () => {
    await airdropTrackerService.toggleSubtask('t1', 2, true);
    const [, options] = (fetch as Mock).mock.calls[0];
    expect(options.headers['Content-Type']).toBe('application/json');
    expect(JSON.parse(options.body)).toEqual({ completed: true });
  });

  it('reads also go through the same-origin strategy proxy', async () => {
    await airdropTrackerService.getTasks();
    await signalTrackerService.getStats();
    const urls = (fetch as Mock).mock.calls.map(([url]) => url);
    // Previously these two defaulted to http://localhost:8001 in the browser.
    expect(urls).toEqual([
      '/strategy-api/api/airdrop-tracker/tasks',
      '/strategy-api/api/signal-tracker/stats',
    ]);
  });

  it('journal and market-intel reads use the proxy with the session token', async () => {
    // The backend /strategy-api proxy requires a session on every route
    // except the health probe; these used to call localhost:8001 bare.
    await tradeJournalService.getStats();
    await marketIntelService.getOverview();
    const calls = (fetch as Mock).mock.calls;
    expect(calls.map(([url]) => url)).toEqual([
      '/strategy-api/api/journal/stats',
      '/strategy-api/api/market-intel/overview',
    ]);
    for (const [, options] of calls) {
      expect(options.headers.Authorization).toBe('Bearer fixture-session');
    }
  });
});

describe('authHeaders', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('omits Authorization when signed out', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockReturnValue(null);
    expect(authHeaders()).toEqual({ 'Content-Type': 'application/json' });
  });

  it('treats blocked storage as signed out', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('SecurityError');
    });
    expect(getAuthToken()).toBeNull();
    expect(authHeaders().Authorization).toBeUndefined();
  });
});
