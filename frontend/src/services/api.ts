/**
 * API Service - Production Ready
 * Robust API client with retry logic, error handling, and type safety
 */

// ── Types ──────────────────────────────────────────────────────────────────────

export interface ApiError extends Error {
  status: number;
  statusText: string;
  endpoint: string;
  retryAfter?: number;
}

export interface FetchOptions extends RequestInit {
  timeout?: number;
  retries?: number;
  retryDelay?: number;
}

// ── Configuration ──────────────────────────────────────────────────────────────

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
const STRATEGY_API_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';
const DEFAULT_TIMEOUT = 15000; // 15 seconds
const DEFAULT_RETRIES = 2;
const DEFAULT_RETRY_DELAY = 1000; // 1 second

// ── Auth Helpers ───────────────────────────────────────────────────────────────

function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('auth_token');
}

function authHeaders(extra?: Record<string, string>): Record<string, string> {
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

// ── Core Fetch with Retry & Timeout ───────────────────────────────────────────

async function fetchWithTimeout(url: string, options: FetchOptions = {}): Promise<Response> {
  const { timeout = DEFAULT_TIMEOUT, signal: existingSignal, ...fetchOptions } = options;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  // If there's an existing signal, abort our controller if that one aborts
  if (existingSignal) {
    existingSignal.addEventListener('abort', () => controller.abort(), { once: true });
  }

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal,
    });
    return response;
  } finally {
    clearTimeout(timeoutId);
  }
}

function createApiError(response: Response, endpoint: string): ApiError {
  const error = new Error(`API request failed: ${response.status} ${response.statusText}`) as ApiError;
  error.status = response.status;
  error.statusText = response.statusText;
  error.endpoint = endpoint;

  // Check for Retry-After header
  const retryAfter = response.headers.get('Retry-After');
  if (retryAfter) {
    error.retryAfter = parseInt(retryAfter, 10);
  }

  return error;
}

async function apiFetch(
  url: string,
  options: FetchOptions = {}
): Promise<Response> {
  const { retries = DEFAULT_RETRIES, retryDelay = DEFAULT_RETRY_DELAY, ...fetchOptions } = options;

  let lastError: ApiError | Error | null = null;

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const response = await fetchWithTimeout(url, fetchOptions);

      // 401 = unauthorized, clear session and redirect
      if (response.status === 401 && typeof window !== 'undefined') {
        const isOptionalEndpoint = url.includes('/api/indicators') ||
                                   url.includes('/api/health') ||
                                   url.includes('/api/status');

        if (!isOptionalEndpoint) {
          localStorage.removeItem('auth_token');
          localStorage.removeItem('user');
          const locale = window.location.pathname.split('/')[1] || 'th';
          window.location.href = `/${locale}`;
        }
      }

      // 429 = rate limited, wait and retry
      if (response.status === 429 && attempt < retries) {
        const retryAfter = response.headers.get('Retry-After');
        const delay = retryAfter ? parseInt(retryAfter, 10) * 1000 : retryDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      // 5xx = server error, retry with exponential backoff
      if (response.status >= 500 && attempt < retries) {
        const delay = retryDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
        continue;
      }

      return response;
    } catch (err) {
      lastError = err instanceof Error ? err : new Error(String(err));

      // Don't retry on abort or client errors
      if (lastError.name === 'AbortError') {
        throw new Error('Request timeout') as ApiError;
      }

      if (attempt < retries) {
        const delay = retryDelay * Math.pow(2, attempt);
        await new Promise(resolve => setTimeout(resolve, delay));
      }
    }
  }

  throw lastError || new Error('Request failed after retries');
}

// ── API Client ─────────────────────────────────────────────────────────────────

export const api = {
  // ── Bot Control ────────────────────────────────────────────────────────────

  async startBot(): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/bot/start`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to start bot' }));
      throw new Error(error.error || 'Failed to start bot');
    }
  },

  async stopBot(): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/bot/stop`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to stop bot' }));
      throw new Error(error.error || 'Failed to stop bot');
    }
  },

  async getBotStatus() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/bot/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  // ── Portfolio ──────────────────────────────────────────────────────────────

  async getPortfolio() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/portfolio`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      const data = await response.json();
      const raw: any[] = data.balances || data || [];
      return raw.map((item) => ({
        symbol: item.symbol ?? '',
        balance: item.balance ?? 0,
        locked: item.locked ?? 0,
        avgBuyPrice: item.avgBuyPrice ?? item.avg_buy_price ?? 0,
        updatedAt: item.updatedAt ?? item.updated_at ?? new Date().toISOString(),
      }));
    } catch {
      return [];
    }
  },

  // ── Orders ─────────────────────────────────────────────────────────────────

  async getOrders() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/orders`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async cancelOrder(orderId: string): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/orders/${orderId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to cancel order' }));
      throw new Error(error.error || 'Failed to cancel order');
    }
  },

  // ── Trade History ──────────────────────────────────────────────────────────

  async getTradeHistory(limit = 50) {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trades?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getPerformance() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/performance`, {
        headers: authHeaders(),
      });
      if (!response.ok) return { winRate: 0 };
      return response.json();
    } catch {
      return { winRate: 0 };
    }
  },

  // ── Technical Indicators ───────────────────────────────────────────────────

  async getIndicators() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/indicators`);
      if (!response.ok) return {};
      return response.json();
    } catch {
      return {};
    }
  },

  // ── Exchange & Balances ────────────────────────────────────────────────────

  async getExchangeBalances(): Promise<Array<{ currency: string; free: number; locked: number; total: number }>> {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/exchange/balances`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      const data = await response.json();
      return (data.balances || []) as Array<{ currency: string; free: number; locked: number; total: number }>;
    } catch {
      return [];
    }
  },

  async getAllBalances() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/exchange/all-balances`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        return { exchanges: {}, totalTHB: 0, totalUSDT: 0, exchangeCount: 0, cached: false, timestamp: '' };
      }
      return response.json();
    } catch {
      return { exchanges: {}, totalTHB: 0, totalUSDT: 0, exchangeCount: 0, cached: false, timestamp: '' };
    }
  },

  async refreshAllBalances() {
    const response = await apiFetch(`${API_BASE_URL}/api/exchange/balances`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to refresh balances' }));
      throw new Error(error.error || 'Failed to refresh balances');
    }
    return response.json();
  },

  // ── Settings ───────────────────────────────────────────────────────────────

  async exportConfig() {
    const response = await apiFetch(`${API_BASE_URL}/api/settings/export`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to export configuration' }));
      throw new Error(error.error || 'Failed to export configuration');
    }
    return response.json();
  },

  async importConfig(config: any): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/settings/import`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to import configuration' }));
      throw new Error(error.error || 'Failed to import configuration');
    }
  },

  // ── Notifications ──────────────────────────────────────────────────────────

  async getNotifications() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/notifications`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async markNotificationRead(id: string): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/notifications/${id}/read`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error('Failed to mark notification as read');
    }
  },

  async markAllNotificationsRead(): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/notifications/read-all`, {
      method: 'POST',
      headers: authHeaders(),
    });
    // Don't throw on error - this is a best-effort operation
  },

  async deleteNotification(id: string): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/notifications/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    // Don't throw on error - this is a best-effort operation
  },

  async clearAllNotifications(): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/notifications/clear-all`, {
      method: 'POST',
      headers: authHeaders(),
    });
    // Don't throw on error - this is a best-effort operation
  },

  // ── Strategy ───────────────────────────────────────────────────────────────

  async getStrategyConfig() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/strategy/config`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  // ── Stop Loss / Take Profit ────────────────────────────────────────────────

  async getSLTP(symbol: string) {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trading/slt/${symbol}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async setSLTP(config: { symbol: string; [key: string]: any }): Promise<void> {
    const { symbol, ...restConfig } = config;
    const response = await apiFetch(`${API_BASE_URL}/api/trading/slt/${symbol}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(restConfig),
    });
    if (!response.ok) {
      throw new Error('Failed to set SL/TP');
    }
  },

  // ── Journal ────────────────────────────────────────────────────────────────

  async getJournalEntries(): Promise<any[]> {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/journal`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async createJournalEntry(entry: any): Promise<any> {
    const response = await apiFetch(`${API_BASE_URL}/api/journal`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(entry),
    });
    if (!response.ok) throw new Error('Failed to create journal entry');
    return response.json();
  },

  async deleteJournalEntry(id: string): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/journal/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    // Don't throw on error - this is a best-effort operation
  },

  async updateJournalEntry(id: string, entry: any): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/journal/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(entry),
    });
    // Don't throw on error - this is a best-effort operation
  },

  // ── Real Grid Trading ───────────────────────────────────────────────────────

  async getRealGridStatus() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async killRealGrid(): Promise<void> {
    const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/kill`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to kill grid bot' }));
      throw new Error(error.error || 'Failed to kill grid bot');
    }
  },

  async enableRealGrid(): Promise<void> {
    const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/enable`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to enable grid bot' }));
      throw new Error(error.error || 'Failed to enable grid bot');
    }
  },

  async getRealGridConfig(symbol: string) {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/config/${symbol}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async updateRealGridConfig(symbol: string, config: Record<string, unknown>): Promise<void> {
    const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/config/${symbol}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json', ...authHeaders() },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to update config' }));
      throw new Error(error.error || 'Failed to update config');
    }
  },

  async getRealGridHealth() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/health`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async restartRealGrid(): Promise<void> {
    const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/restart`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to restart bot' }));
      throw new Error(error.error || 'Failed to restart bot');
    }
  },

  async getRealGridPerformance() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/real-grid/performance`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async getDailyReport(symbol: string = 'BTCTHB') {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/report/daily?symbol=${symbol}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  // ── Polymarket Paper Trading ──────────────────────────────────────────────────

  async getPolyPaperStatus() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async getPolyPaperPositions(activeOnly: boolean = false) {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/positions?active_only=${activeOnly}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getPolyPaperTrades(limit: number = 50) {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/trades?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getPolyPaperPerformance() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/performance`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async getPolyPaperNotifications(limit: number = 20) {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/notifications?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getPolyPaperSignals(limit: number = 30) {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/poly-paper/signals?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getTradeStatus() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trade/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async getTradeBalances(): Promise<Array<{ asset: string; free: number; locked: number; total: number }>> {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trade/balances`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      const data = await response.json();
      return data.balances || [];
    } catch {
      return [];
    }
  },

  async getTradeTicker(symbol: string) {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trade/ticker?symbol=${symbol}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async getTradeOpenOrders(symbol: string = 'BTCTHB') {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trade/open-orders?symbol=${symbol}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return { symbol, orders: [] };
      return response.json();
    } catch {
      return { symbol, orders: [] };
    }
  },

  async getRealTradeHistory(limit: number = 50) {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/trade/history?limit=${limit}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async cancelTradeOrder(symbol: string, orderId: number): Promise<void> {
    const response = await apiFetch(`${API_BASE_URL}/api/trade/cancel-order`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ symbol, orderId }),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to cancel order' }));
      throw new Error(error.error || 'Failed to cancel order');
    }
  },

  // ── Risk Manager ────────────────────────────────────────────────────────────

  async getRiskStatus() {
    try {
      const response = await apiFetch(`${STRATEGY_API_URL}/api/risk/status`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },

  async resetRisk(): Promise<void> {
    const response = await apiFetch(`${STRATEGY_API_URL}/api/risk/reset`, {
      method: 'POST',
      headers: authHeaders(),
    });
    if (!response.ok) {
      const error = await response.json().catch(() => ({ error: 'Failed to reset risk' }));
      throw new Error(error.error || 'Failed to reset risk');
    }
  },

  // ── Trade Journal ─────────────────────────────────────────────────────────

  async getTradeJournalEntries(limit: number = 50, status?: string) {
    try {
      const params = new URLSearchParams({ limit: String(limit) });
      if (status) params.set('status', status);
      const response = await apiFetch(`${API_BASE_URL}/api/journal/list?${params}`, {
        headers: authHeaders(),
      });
      if (!response.ok) return [];
      return response.json();
    } catch {
      return [];
    }
  },

  async getJournalStats() {
    try {
      const response = await apiFetch(`${API_BASE_URL}/api/journal/stats`, {
        headers: authHeaders(),
      });
      if (!response.ok) return null;
      return response.json();
    } catch {
      return null;
    }
  },
};

export default api;
