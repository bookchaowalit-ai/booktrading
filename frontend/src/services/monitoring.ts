/**
 * Monitoring API Service
 * Aggregates data from multiple backend endpoints
 */
import type { HealthStatus, BotStatus, MarketAlert } from '@/types/monitoring';

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

export const monitoringService = {
  /**
   * Get system health (redis, services)
   */
  async getHealth(): Promise<HealthStatus> {
    const res = await fetch(`${STRATEGY_URL}/api/health`);
    if (!res.ok) return { status: 'down', redis_connected: false };
    return res.json();
  },

  /**
   * Get real grid bot status (includes risk + journal stats)
   */
  async getBotStatus(): Promise<BotStatus> {
    const res = await fetch(`${STRATEGY_URL}/api/real-grid/status`);
    if (!res.ok) throw new Error('Bot status fetch failed');
    return res.json();
  },

  /**
   * Get market alerts (high severity)
   */
  async getAlerts(limit: number = 20): Promise<MarketAlert[]> {
    const res = await fetch(`${STRATEGY_URL}/api/market-intel/alerts?limit=${limit}`);
    if (!res.ok) return [];
    const data = await res.json();
    return data.alerts || [];
  },

  /**
   * Kill switch - halt all trading
   */
  async killBot(): Promise<void> {
    const res = await fetch(`${STRATEGY_URL}/api/real-grid/kill`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error('Kill switch failed');
  },

  /**
   * Re-enable bot after kill
   */
  async enableBot(): Promise<void> {
    const res = await fetch(`${STRATEGY_URL}/api/real-grid/enable`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    });
    if (!res.ok) throw new Error('Enable failed');
  },

  /**
   * Get fill notifications from real grid bot
   */
  async getNotifications(limit: number = 20): Promise<any[]> {
    try {
      const res = await fetch(`${STRATEGY_URL}/api/real-grid/notifications?limit=${limit}`);
      if (!res.ok) return [];
      return res.json();
    } catch {
      return [];
    }
  },

  /**
   * Aggregate all monitoring data
   */
  async getAll(): Promise<{ health: HealthStatus; bot: BotStatus; alerts: MarketAlert[] }> {
    const [health, bot, alerts] = await Promise.all([
      this.getHealth(),
      this.getBotStatus(),
      this.getAlerts(20),
    ]);
    return { health, bot, alerts };
  },
};
