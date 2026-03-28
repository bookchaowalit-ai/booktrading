/**
 * API service for communicating with the backend.
 */
import {
  BotStatus,
  Order,
  OrderRequest,
  OrderResponse,
  Portfolio,
  TechnicalIndicators,
  TradeHistory,
} from '@/types';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080';
const STRATEGY_API_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8000';

/** Returns headers including Authorization if a token is stored */
function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return { ...base, ...extra };
}

export const api = {
  // Bot Control
  async startBot(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/start`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          symbol: 'BTC_THB',
          quantity: 0.001,
          gridLevels: 10,
          lowerPrice: 1500000,
          upperPrice: 2500000,
          investment: 10000,
        }),
      });
      if (!response.ok) {
        throw new Error('Failed to start bot');
      }
    } catch (error) {
      // Backend not available - suppress error for demo
      throw error;
    }
  },

  async stopBot(): Promise<void> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/stop`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error('Failed to stop bot');
      }
    } catch (error) {
      // Backend not available - suppress error for demo
      throw error;
    }
  },

  async getBotStatus(): Promise<BotStatus> {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/status`, { headers: authHeaders() });
      if (!response.ok) throw new Error('Failed to get bot status');
      const raw = await response.json();
      // Normalize: Go backend sends snake_case (is_active, total_trades, total_profit)
      return {
        isActive: raw.isActive ?? raw.is_active ?? false,
        totalTrades: raw.totalTrades ?? raw.total_trades ?? 0,
        totalProfit: raw.totalProfit ?? raw.total_profit ?? 0,
        startedAt: raw.startedAt ?? raw.started_at ?? undefined,
        stoppedAt: raw.stoppedAt ?? raw.stopped_at ?? undefined,
      };
    } catch {
      return { isActive: false, totalTrades: 0, totalProfit: 0 };
    }
  },

  // Orders
  async createOrder(order: OrderRequest): Promise<OrderResponse> {
    const response = await fetch(`${API_BASE_URL}/api/orders`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(order),
    });
    if (!response.ok) {
      throw new Error('Failed to create order');
    }
    return response.json();
  },

  async getOrders(): Promise<Order[]> {
    const response = await fetch(`${API_BASE_URL}/api/orders`, { headers: authHeaders() });
    if (!response.ok) {
      throw new Error('Failed to get orders');
    }
    return response.json();
  },

  async cancelOrder(orderId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error('Failed to cancel order');
    }
  },

  // Portfolio
  async getPortfolio(): Promise<Portfolio[]> {
    const response = await fetch(`${API_BASE_URL}/api/portfolio`, { headers: authHeaders() });
    if (!response.ok) return [];
    const data = await response.json();
    const raw: any[] = data.balances || data || [];
    // Normalize snake_case from Go backend → camelCase
    return raw.map((item) => ({
      symbol: item.symbol ?? '',
      balance: item.balance ?? 0,
      locked: item.locked ?? 0,
      avgBuyPrice: item.avgBuyPrice ?? item.avg_buy_price ?? 0,
      updatedAt: item.updatedAt ?? item.updated_at ?? new Date().toISOString(),
    }));
  },

  // Trade History
  async getTradeHistory(limit: number = 50): Promise<TradeHistory[]> {
    const response = await fetch(`${API_BASE_URL}/api/trades?limit=${limit}`, { headers: authHeaders() });
    if (!response.ok) {
      throw new Error('Failed to get trade history');
    }
    return response.json();
  },

  // Technical Indicators (from Strategy Service)
  async getIndicators(): Promise<Record<string, TechnicalIndicators>> {
    const response = await fetch(`${STRATEGY_API_URL}/api/indicators`);
    if (!response.ok) {
      throw new Error('Failed to get indicators');
    }
    return response.json();
  },

  async getStrategyConfig(): Promise<{
    rsi_period: number;
    ema_period: number;
    rsi_oversold: number;
    rsi_overbought: number;
    min_signal_strength: number;
  }> {
    const response = await fetch(`${STRATEGY_API_URL}/api/strategy/config`);
    if (!response.ok) {
      throw new Error('Failed to get strategy config');
    }
    return response.json();
  },

  // Health Check
  async healthCheck(): Promise<{ status: string }> {
    const response = await fetch(`${API_BASE_URL}/api/health`);
    if (!response.ok) {
      throw new Error('Backend health check failed');
    }
    return response.json();
  },

  // Performance Metrics
  async getPerformance(): Promise<{
    totalTrades: number;
    winningTrades: number;
    losingTrades: number;
    winRate: number;
    totalPnL: number;
    totalPnLPercent: number;
    avgWin: number;
    avgLoss: number;
    profitFactor: number;
    bestTrade: number;
    worstTrade: number;
    avgTradeDuration: string;
    sharpeRatio: number;
    maxDrawdown: number;
    maxDrawdownPercent: number;
  }> {
    const response = await fetch(`${API_BASE_URL}/api/performance`, { headers: authHeaders() });
    if (!response.ok) throw new Error('Failed to get performance');
    return response.json();
  },

  // Notifications
  async getNotifications(): Promise<Array<{
    id: string;
    type: string;
    title: string;
    message: string;
    timestamp: string;
    read: boolean;
    priority: string;
  }>> {
    const response = await fetch(`${API_BASE_URL}/api/notifications`, { headers: authHeaders() });
    if (!response.ok) return [];
    return response.json();
  },

  async markNotificationRead(id: string): Promise<void> {
    await fetch(`${API_BASE_URL}/api/notifications/${id}/read`, { method: 'PUT', headers: authHeaders() });
  },

  async markAllNotificationsRead(): Promise<void> {
    await fetch(`${API_BASE_URL}/api/notifications/read-all`, { method: 'PUT', headers: authHeaders() });
  },

  async deleteNotification(id: string): Promise<void> {
    await fetch(`${API_BASE_URL}/api/notifications/${id}`, { method: 'DELETE', headers: authHeaders() });
  },

  async clearAllNotifications(): Promise<void> {
    await fetch(`${API_BASE_URL}/api/notifications`, { method: 'DELETE', headers: authHeaders() });
  },

  // Journal
  async getJournalEntries(): Promise<Array<{
    id: string;
    date: string;
    symbol: string;
    side: string;
    entryPrice: number;
    exitPrice?: number;
    quantity: number;
    pnl: number;
    pnlPercent: number;
    notes?: string;
    rating?: number;
    strategy?: string;
    emotions?: string;
    lessons?: string;
    createdAt: string;
    updatedAt: string;
  }>> {
    const response = await fetch(`${API_BASE_URL}/api/journal`, { headers: authHeaders() });
    if (!response.ok) return [];
    return response.json();
  },

  async createJournalEntry(entry: {
    date?: string;
    symbol: string;
    side: string;
    entryPrice: number;
    exitPrice?: number;
    quantity: number;
    pnl: number;
    pnlPercent: number;
    notes?: string;
    rating?: number;
    strategy?: string;
    emotions?: string;
    lessons?: string;
  }): Promise<{ id: string }> {
    const response = await fetch(`${API_BASE_URL}/api/journal`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(entry),
    });
    if (!response.ok) throw new Error('Failed to create journal entry');
    return response.json();
  },

  async updateJournalEntry(id: string, entry: object): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/journal/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(entry),
    });
    if (!response.ok) throw new Error('Failed to update journal entry');
  },

  async deleteJournalEntry(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/journal/${id}`, { method: 'DELETE', headers: authHeaders() });
    if (!response.ok) throw new Error('Failed to delete journal entry');
  },

  // Auth
  async login(email: string, password: string): Promise<{ token: string; user: { id: string; email: string; name: string; role: string } }> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    if (!response.ok) {
      const err = await response.json().catch(() => ({ error: 'Login failed' }));
      throw new Error(err.error || 'Login failed');
    }
    return response.json();
  },

  async getMe(token: string): Promise<{ id: string; email: string; name: string; role: string }> {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!response.ok) throw new Error('Unauthorized');
    return response.json();
  },

  async logout(token: string): Promise<void> {
    await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  },

  // Stop-Loss / Take-Profit
  async getSLTP(symbol: string): Promise<{
    symbol: string;
    stopLossPercent: number;
    takeProfitPercent: number;
    stopLossPrice: number;
    takeProfitPrice: number;
    trailingStop: boolean;
    trailingStopPercent: number;
    enabled: boolean;
  }> {
    const response = await fetch(`${API_BASE_URL}/api/sltp/${symbol}`, { headers: authHeaders() });
    if (!response.ok) throw new Error('Failed to get SL/TP config');
    return response.json();
  },

  async setSLTP(config: {
    symbol: string;
    stopLossPercent?: number;
    takeProfitPercent?: number;
    stopLossPrice?: number;
    takeProfitPrice?: number;
    trailingStop?: boolean;
    trailingStopPercent?: number;
    enabled: boolean;
  }): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/sltp`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(config),
    });
    if (!response.ok) throw new Error('Failed to save SL/TP config');
  },

  async deleteSLTP(symbol: string): Promise<void> {
    await fetch(`${API_BASE_URL}/api/sltp/${symbol}`, { method: 'DELETE', headers: authHeaders() });
  },
};
