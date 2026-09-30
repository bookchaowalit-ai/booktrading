/**
 * Backtest Service
 * API client for grid trading backtester
 */
import type { BacktestConfig, BacktestResult, ParameterSweepResult } from '@/types/backtest';
import { authHeaders, STRATEGY_URL } from './auth-headers';


export const backtestService = {
  /**
   * Run a backtest with given configuration
   */
  async runBacktest(config: BacktestConfig): Promise<BacktestResult> {
    const res = await fetch(`${STRATEGY_URL}/api/backtest/run`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Backtest failed: ${err}`);
    }
    return res.json();
  },

  /**
   * Run parameter sweep across multiple spacing/levels combinations
   */
  async runParameterSweep(params: {
    symbol: string;
    days?: number;
    interval?: string;
    volatility_mode?: string;
    spacing_range?: number[];
    levels_range?: number[];
    atr_period?: number;
    atr_multiplier?: number;
    order_size?: number;
    initial_capital_thb?: number;
  }): Promise<ParameterSweepResult> {
    const res = await fetch(`${STRATEGY_URL}/api/backtest/sweep`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(params),
    });
    if (!res.ok) {
      const err = await res.text();
      throw new Error(`Parameter sweep failed: ${err}`);
    }
    return res.json();
  },
};
