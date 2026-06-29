/**
 * Signal Performance Tracker Service
 * API client for tracking signal performance over time
 */

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8001';

export interface SignalEvaluation {
  price_at_eval: number;
  pct_change: number;
  evaluated_at: string;
  correct: boolean;
}

export interface LoggedSignal {
  signal_id: string;
  symbol: string;
  market_type: string;
  source: string;
  signal_type: string;
  severity: string;
  title: string;
  price_at_signal: number;
  confidence: number;
  timestamp: string;
  eval_24h: SignalEvaluation | null;
  eval_7d: SignalEvaluation | null;
  metadata: Record<string, any>;
}

export interface SignalPerformanceStats {
  total_signals: number;
  evaluated_24h: number;
  evaluated_7d: number;
  by_source: Record<string, {
    total: number;
    correct_24h: number;
    incorrect_24h: number;
  }>;
  by_market_type: Record<string, {
    total: number;
    correct_24h: number;
    incorrect_24h: number;
  }>;
  accuracy_24h: {
    correct: number;
    incorrect: number;
    rate: number;
  };
  accuracy_7d: {
    correct: number;
    incorrect: number;
    rate: number;
  };
}

export const signalTrackerService = {
  /**
   * Get logged signals with optional filters
   */
  async getSignals(params?: {
    limit?: number;
    source?: string;
    market_type?: string;
    evaluated_only?: boolean;
  }): Promise<{ signals: LoggedSignal[]; total: number }> {
    const searchParams = new URLSearchParams();
    if (params?.limit) searchParams.set('limit', params.limit.toString());
    if (params?.source) searchParams.set('source', params.source);
    if (params?.market_type) searchParams.set('market_type', params.market_type);
    if (params?.evaluated_only) searchParams.set('evaluated_only', 'true');

    const res = await fetch(`${STRATEGY_URL}/api/signal-tracker/signals?${searchParams}`);
    if (!res.ok) throw new Error('Failed to fetch signals');
    return res.json();
  },

  /**
   * Get performance statistics
   */
  async getStats(): Promise<SignalPerformanceStats> {
    const res = await fetch(`${STRATEGY_URL}/api/signal-tracker/stats`);
    if (!res.ok) throw new Error('Failed to fetch signal stats');
    return res.json();
  },

  /**
   * Manually trigger signal evaluation
   */
  async evaluate(): Promise<{ evaluated: number; total_signals: number }> {
    const res = await fetch(`${STRATEGY_URL}/api/signal-tracker/evaluate`, {
      method: 'POST',
    });
    if (!res.ok) throw new Error('Failed to evaluate signals');
    return res.json();
  },
};
