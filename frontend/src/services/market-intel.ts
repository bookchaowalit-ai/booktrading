/**
 * Market Intelligence Service
 * API client for the multi-market scanner
 */
import type {
  ScannerResult,
  MarketQuote,
  MarketSource,
  MarketAlert,
  MarketOverview,
} from '@/types/market-intel';

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8001';

export const marketIntelService = {
  /**
   * Run a cross-market opportunity scan
   */
  async scan(minConfidence: number = 0.3, markets?: string[]): Promise<ScannerResult> {
    const params = new URLSearchParams({ min_confidence: minConfidence.toString() });
    if (markets?.length) params.set('markets', markets.join(','));

    const res = await fetch(`${STRATEGY_URL}/api/market-intel/scan?${params}`);
    if (!res.ok) throw new Error('Scan failed');
    return res.json();
  },

  /**
   * Fetch live quotes from market sources
   */
  async getQuotes(markets?: string[]): Promise<{ quotes: MarketQuote[]; total: number }> {
    const params = new URLSearchParams();
    if (markets?.length) params.set('markets', markets.join(','));

    const res = await fetch(`${STRATEGY_URL}/api/market-intel/quotes?${params}`);
    if (!res.ok) throw new Error('Quotes fetch failed');
    return res.json();
  },

  /**
   * Get market overview across all sources
   */
  async getOverview(): Promise<MarketOverview> {
    const res = await fetch(`${STRATEGY_URL}/api/market-intel/overview`);
    if (!res.ok) throw new Error('Overview fetch failed');
    return res.json();
  },

  /**
   * List available market data sources
   */
  async getSources(): Promise<{ sources: MarketSource[]; total: number }> {
    const res = await fetch(`${STRATEGY_URL}/api/market-intel/sources`);
    if (!res.ok) throw new Error('Sources fetch failed');
    return res.json();
  },

  /**
   * Get high-severity alerts from background scanning
   */
  async getAlerts(limit: number = 50, severity?: string): Promise<{ alerts: MarketAlert[]; total: number }> {
    const params = new URLSearchParams({ limit: limit.toString() });
    if (severity) params.set('severity', severity);

    const res = await fetch(`${STRATEGY_URL}/api/market-intel/alerts?${params}`);
    if (!res.ok) throw new Error('Alerts fetch failed');
    return res.json();
  },

  /**
   * Get the most recent background scan result
   */
  async getLastScan(): Promise<ScannerResult | { status: string; message: string }> {
    const res = await fetch(`${STRATEGY_URL}/api/market-intel/last-scan`);
    if (!res.ok) throw new Error('Last scan fetch failed');
    return res.json();
  },
};
