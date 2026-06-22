/**
 * Backtest Types
 */

export interface BacktestConfig {
  symbol: string;
  days: number;
  interval: string;
  grid_spacing_pct: number;
  grid_levels: number;
  order_size: number;
  max_position: number;
  max_open_orders: number;
  initial_capital_thb: number;
  // ATR-based dynamic spacing
  volatility_mode?: 'fixed' | 'atr';
  atr_period?: number;
  atr_multiplier?: number;
  min_spacing_pct?: number;
  max_spacing_pct?: number;
}

export interface BacktestTrade {
  timestamp: number;
  side: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  pnl: number;
  fee: number;
}

export interface BacktestResult {
  symbol: string;
  start_time: number;
  end_time: number;
  duration_days: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  total_fees: number;
  net_pnl: number;
  max_drawdown: number;
  max_drawdown_pct: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
  avg_grid_spacing_pct: number;
  trades_per_day: number;
  config: Record<string, unknown>;
  trades: BacktestTrade[];
  // ATR-specific metrics
  volatility_mode?: string;
  atr_spacing_avg?: number;
  atr_spacing_min?: number;
  atr_spacing_max?: number;
}

// ── Parameter Sweep Types ──────────────────────────────────────────────────────

export interface SweepResultItem {
  grid_spacing_pct: number;
  grid_levels: number;
  net_pnl: number;
  win_rate: number;
  trades_per_day: number;
  max_drawdown_pct: number;
  profit_factor: number;
  total_trades: number;
  atr_spacing_avg: number;
}

export interface ParameterSweepResult {
  symbol: string;
  days: number;
  interval: string;
  volatility_mode: string;
  total_combinations: number;
  best_config: Record<string, unknown>;
  worst_config: Record<string, unknown>;
  results: SweepResultItem[];
}

// ── Performance Metrics Types ──────────────────────────────────────────────────

export interface SymbolPerformance {
  orders_placed: number;
  orders_filled: number;
  fill_rate: number; // percentage
  last_fill_timestamp: number;
  last_fill_age_sec: number | null;
  last_atr_spacing_pct: number;
  atr_spacing_avg: number;
  atr_spacing_min: number;
  atr_spacing_max: number;
  atr_spacing_stddev: number;
  atr_spacing_samples: number;
  atr_config: {
    atr_period: number;
    atr_multiplier: number;
    min_spacing_pct: number;
    max_spacing_pct: number;
  };
  profit_velocity_thb_per_day: number;
  cumulative_pnl: number;
  performance_tracking_days: number;
  compound_recommendation: string;
  current_compound_multiplier: number;
  // Risk-adjusted return metrics
  sharpe_ratio: number;
  sortino_ratio: number;
  trade_return_samples: number;
  auto_tuned_compound_threshold: number;
  // Regime detection & capital allocation
  regime: string;
  atr_percentile: number;
  allocation_weight: number;
  allocation_score: number;
  current_grid_levels: number;
}

export interface PerformanceData {
  symbols: Record<string, SymbolPerformance>;
  summary: {
    avg_fill_rate: number;
    best_fill_symbol: string | null;
    worst_fill_symbol: string | null;
    total_profit_velocity: number;
    avg_sharpe_ratio: number;
    avg_sortino_ratio: number;
  };
}

export const DEFAULT_BACKTEST_CONFIG: BacktestConfig = {
  symbol: 'BTCTHB',
  days: 30,
  interval: '1h',
  grid_spacing_pct: 1.5,
  grid_levels: 2,
  order_size: 0.00005,
  max_position: 0.001,
  max_open_orders: 10,
  initial_capital_thb: 10000,
  volatility_mode: 'fixed',
  atr_period: 14,
  atr_multiplier: 1.5,
  min_spacing_pct: 0.5,
  max_spacing_pct: 5.0,
};
