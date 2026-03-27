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

export const api = {
  // Bot Control
  async startBot(): Promise<void> {
    // Get API keys from localStorage
    const storedKeys = localStorage.getItem('exchange_api_keys');
    let apiKey = '';
    let apiSecret = '';
    let testnet = false;
    
    if (storedKeys) {
      const keys = JSON.parse(storedKeys);
      const bitkubKey = keys.find((k: any) => k.exchange === 'bitkub');
      if (bitkubKey) {
        apiKey = bitkubKey.apiKey;
        apiSecret = bitkubKey.apiSecret;
        testnet = bitkubKey.testnet;
      }
    }

    // First configure API if keys exist
    if (apiKey && apiSecret) {
      await fetch(`${API_BASE_URL}/api/trading/configure`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ apiKey, apiSecret, testnet }),
      });
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
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
        headers: { 'Content-Type': 'application/json' },
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
      const response = await fetch(`${API_BASE_URL}/api/bot/status`);
      if (!response.ok) {
        throw new Error('Failed to get bot status');
      }
      return response.json();
    } catch (error) {
      // Return mock data when backend unavailable
      console.debug('Backend unavailable - returning mock status');
      return { isActive: false, totalTrades: 0, totalProfit: 0 };
    }
  },

  // Orders
  async createOrder(order: OrderRequest): Promise<OrderResponse> {
    const response = await fetch(`${API_BASE_URL}/api/orders`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(order),
    });
    if (!response.ok) {
      throw new Error('Failed to create order');
    }
    return response.json();
  },

  async getOrders(): Promise<Order[]> {
    const response = await fetch(`${API_BASE_URL}/api/orders`);
    if (!response.ok) {
      throw new Error('Failed to get orders');
    }
    return response.json();
  },

  async cancelOrder(orderId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/orders/${orderId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to cancel order');
    }
  },

  // Portfolio
  async getPortfolio(): Promise<any[]> {
    const response = await fetch(`${API_BASE_URL}/api/portfolio`);
    if (!response.ok) {
      return []; // Return empty array if backend unavailable
    }
    const data = await response.json();
    return data.balances || [];
  },

  // Trade History
  async getTradeHistory(limit: number = 50): Promise<TradeHistory[]> {
    const response = await fetch(`${API_BASE_URL}/api/trades?limit=${limit}`);
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
};
