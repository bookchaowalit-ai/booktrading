/**
 * Trade Journal Service
 * API client for trade journal entries and stats
 */
import type { JournalResponse, JournalStats, DailyReport } from '@/types/trade-journal';

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8001';

export const tradeJournalService = {
  /**
   * Get journal entries (in-memory + DB)
   */
  async getEntries(limit: number = 50, status?: string): Promise<JournalResponse> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (status) params.set('status', status);

    const res = await fetch(`${STRATEGY_URL}/api/journal/entries?${params}`);
    if (!res.ok) throw new Error('Journal entries fetch failed');
    return res.json();
  },

  /**
   * Get journal stats (DB-backed)
   */
  async getStats(): Promise<JournalStats> {
    const res = await fetch(`${STRATEGY_URL}/api/journal/stats`);
    if (!res.ok) throw new Error('Journal stats fetch failed');
    return res.json();
  },

  /**
   * Get daily report for a symbol
   */
  async getDailyReport(symbol: string): Promise<DailyReport> {
    const res = await fetch(`${STRATEGY_URL}/api/report/daily?symbol=${symbol}`);
    if (!res.ok) throw new Error('Daily report fetch failed');
    return res.json();
  },

  /**
   * Get daily reports for all real symbols
   */
  async getAllDailyReports(symbols: string[]): Promise<DailyReport[]> {
    return Promise.all(symbols.map((sym) => this.getDailyReport(sym)));
  },
};
