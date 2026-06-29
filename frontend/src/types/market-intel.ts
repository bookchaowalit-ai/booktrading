/**
 * Market Intelligence Types
 * Type definitions for the multi-market scanner
 */

export type MarketType = 'crypto' | 'stock' | 'forex' | 'commodity' | 'prediction' | 'airdrop' | 'degen';
export type OpportunityType = 'momentum' | 'volume_spike' | 'mispricing' | 'liquidity_gap' | 'mean_reversion' | 'breakout' | 'airdrop_free' | 'early_alpha' | 'cross_exchange_arb' | 'trending_degen';
export type Severity = 'critical' | 'high' | 'medium' | 'low';

export interface MarketQuote {
  symbol: string;
  market_type: MarketType;
  source: string;
  price: number;
  change_24h: number | null;
  change_pct_24h: number | null;
  volume_24h: number | null;
  bid: number | null;
  ask: number | null;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface MarketOpportunity {
  opportunity_id: string;
  symbol: string;
  market_type: MarketType;
  source: string;
  opportunity_type: OpportunityType;
  severity: Severity;
  title: string;
  description: string;
  current_price: number;
  target_price: number | null;
  confidence: number;
  timestamp: string;
  metadata: Record<string, any>;
}

export interface ScannerResult {
  scan_id: string;
  timestamp: string;
  markets_scanned: MarketType[];
  total_opportunities: number;
  by_severity: Record<string, number>;
  by_market: Record<string, number>;
  opportunities: MarketOpportunity[];
  summary: Record<string, any>;
}

export interface MarketSource {
  name: string;
  market_type: string;
  enabled: boolean;
}

export interface MarketAlert {
  id: string;
  symbol: string;
  market: string;
  source: string;
  type: string;
  severity: Severity;
  title: string;
  description: string;
  price: number;
  confidence: number;
  timestamp: string;
}

export interface MarketOverview {
  [key: string]: {
    market_type: string;
    instruments: number;
    opportunities: number;
    top_opps: Array<{
      title: string;
      severity: string;
      confidence: number;
    }>;
    sample_quotes: Array<{
      symbol: string;
      price: number;
      change_pct: number | null;
    }>;
  };
}
