/**
 * API client for new features: paper trading, risk management, alerts, backtesting
 */

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

// ── Paper Trading ─────────────────────────────────────────────────────────────

export interface PaperOrderRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  limit_price: number;
}

export interface PaperPosition {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  updated_at: string;
}

export interface PaperPortfolio {
  initial_balance: number;
  current_balance: number;
  total_value: number;
  positions: PaperPosition[];
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  max_drawdown: number;
  updated_at: string;
}

export interface PaperOrder {
  id: string;
  symbol: string;
  side: string;
  quantity: number;
  price: number;
  limit_price: number;
  status: string;
  fee: number;
  created_at: string;
  filled_at: string | null;
}

export const paperApi = {
  async placeOrder(order: PaperOrderRequest): Promise<PaperOrder> {
    const res = await fetch(`${API_BASE_URL}/api/paper/order`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(order),
    });
    if (!res.ok) throw new Error('Failed to place paper order');
    return res.json();
  },

  async getPortfolio(): Promise<PaperPortfolio> {
    const res = await fetch(`${API_BASE_URL}/api/paper/portfolio`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get paper portfolio');
    return res.json();
  },

  async getHistory(): Promise<PaperOrder[]> {
    const res = await fetch(`${API_BASE_URL}/api/paper/history`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get paper trade history');
    return res.json();
  },

  async reset(): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/paper/reset`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to reset paper trading');
  },
};

// ── Risk Management ───────────────────────────────────────────────────────────

export interface RiskConfig {
  stop_loss_percent: number;
  take_profit_percent: number;
  max_position_size_percent: number;
  max_daily_loss_percent: number;
  max_drawdown_percent: number;
  max_concurrent_positions: number;
  trade_cooldown_sec: number;
  trailing_stop: boolean;
  trailing_stop_percent: number;
}

export interface RiskMetrics {
  current_drawdown: number;
  max_drawdown: number;
  peak_value: number;
  current_value: number;
  daily_pnl: number;
  daily_pnl_percent: number;
  sharpe_ratio: number;
  win_rate: number;
  profit_factor: number;
  avg_win: number;
  avg_loss: number;
  trades_today: number;
  total_trades: number;
  stop_loss_hits: number;
  take_profit_hits: number;
  last_trade_at: string;
  blocked_reasons?: string[];
}

export interface RiskCheckRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  portfolio_value: number;
}

export interface RiskCheckResponse {
  approved: boolean;
  reasons?: string[];
}

export const riskApi = {
  async getConfig(): Promise<RiskConfig> {
    const res = await fetch(`${API_BASE_URL}/api/risk/config`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get risk config');
    return res.json();
  },

  async updateConfig(config: RiskConfig): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/risk/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error('Failed to update risk config');
  },

  async getMetrics(): Promise<RiskMetrics> {
    const res = await fetch(`${API_BASE_URL}/api/risk/metrics`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get risk metrics');
    return res.json();
  },

  async checkTrade(req: RiskCheckRequest): Promise<RiskCheckResponse> {
    const res = await fetch(`${API_BASE_URL}/api/risk/check`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(req),
    });
    if (!res.ok) throw new Error('Failed to check trade approval');
    return res.json();
  },
};

// ── Alerts ────────────────────────────────────────────────────────────────────

export interface AlertConfig {
  discord_webhook_url: string;
  telegram_bot_token: string;
  telegram_chat_id: string;
  custom_webhook_url: string;
  notify_on_trade: boolean;
  notify_on_bot_start: boolean;
  notify_on_error: boolean;
  notify_on_risk: boolean;
  notify_on_price: boolean;
}

export const alertApi = {
  async getConfig(): Promise<AlertConfig> {
    const res = await fetch(`${API_BASE_URL}/api/alerts/config`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get alert config');
    return res.json();
  },

  async updateConfig(config: AlertConfig): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/alerts/config`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(config),
    });
    if (!res.ok) throw new Error('Failed to update alert config');
  },

  async testAlert(): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/alerts/test`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to send test alert');
  },
};

// ── Backtesting ───────────────────────────────────────────────────────────────

export interface BacktestRequest {
  symbol: string;
  start_date: string;
  end_date: string;
  initial_capital: number;
  commission: number;
  slippage: number;
  strategy: string;
  rsi_period: number;
  rsi_oversold: number;
  rsi_overbought: number;
  ema_fast_period: number;
  ema_slow_period: number;
}

export interface TradeResult {
  symbol: string;
  side: string;
  entry_price: number;
  exit_price: number;
  quantity: number;
  pnl: number;
  pnl_percent: number;
  entry_time: string;
  exit_time: string;
  duration: string;
}

export interface EquityPoint {
  time: string;
  value: number;
}

export interface BacktestResult {
  initial_capital: number;
  final_capital: number;
  total_return: number;
  total_return_percent: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  win_rate: number;
  profit_factor: number;
  max_drawdown: number;
  max_drawdown_percent: number;
  sharpe_ratio: number;
  sortino_ratio: number;
  avg_win: number;
  avg_loss: number;
  best_trade: number;
  worst_trade: number;
  avg_trade_duration: string;
  trades: TradeResult[];
  equity_curve: EquityPoint[];
}

export const backtestApi = {
  async run(config: BacktestRequest): Promise<BacktestResult> {
    const res = await fetch(`${API_BASE_URL}/api/backtest/run`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(config),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Backtest failed' }));
      throw new Error(err.error || 'Backtest failed');
    }
    return res.json();
  },
};

// ── Helper ────────────────────────────────────────────────────────────────────

function getAuthToken(): string {
  if (typeof window === 'undefined') return '';
  return localStorage.getItem('auth_token') || '';
}

// ── Copy Trading ──────────────────────────────────────────────────────────────

export interface LeaderboardEntry {
  strategy_id: string;
  name: string;
  description?: string;
  strategy_type: string;
  total_copiers: number;
  win_rate: number;
  total_return: number;
  profit_factor: number;
  max_drawdown: number;
  sharpe_ratio: number;
}

export interface StrategyProfile {
  id: string;
  owner_id: string;
  name: string;
  description?: string;
  strategy_type: string;
  is_public: boolean;
  parameters: Record<string, any>;
  performance?: Record<string, any>;
  total_copiers: number;
  created_at: string;
  updated_at: string;
}

export interface CopyRelationship {
  id: string;
  copier_id: string;
  strategy_id: string;
  allocation_percent: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  strategy_name?: string;
  strategy_type?: string;
}

export interface CopyTrade {
  id: string;
  copy_relationship_id: string;
  original_trade_id?: string;
  symbol: string;
  side: string;
  quantity: number;
  entry_price: number;
  exit_price?: number;
  pnl?: number;
  status: string;
  opened_at: string;
  closed_at?: string;
}

export const copyTradingApi = {
  async getLeaderboard(limit = 20): Promise<LeaderboardEntry[]> {
    const res = await fetch(`${API_BASE_URL}/api/copy/leaderboard?limit=${limit}`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get leaderboard');
    const data = await res.json();
    return data;
  },

  async getMyStrategies(): Promise<StrategyProfile[]> {
    const res = await fetch(`${API_BASE_URL}/api/copy/strategies/my`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get my strategies');
    return res.json();
  },

  async createStrategy(req: {
    name: string;
    description?: string;
    strategy_type: string;
    is_public: boolean;
    parameters?: Record<string, any>;
  }): Promise<StrategyProfile> {
    const res = await fetch(`${API_BASE_URL}/api/copy/strategies`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify(req),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to create strategy' }));
      throw new Error(err.error || 'Failed to create strategy');
    }
    return res.json();
  },

  async startCopying(strategyId: string, allocationPct: number): Promise<CopyRelationship> {
    const res = await fetch(`${API_BASE_URL}/api/copy/copy`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify({ strategy_id: strategyId, allocation_percent: allocationPct }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to start copying' }));
      throw new Error(err.error || 'Failed to start copying');
    }
    return res.json();
  },

  async stopCopying(relationshipId: string): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/copy/copy/${relationshipId}`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to stop copying');
  },

  async getMyCopied(): Promise<CopyRelationship[]> {
    const res = await fetch(`${API_BASE_URL}/api/copy/copied`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get copied strategies');
    return res.json();
  },
};

// ── Portfolio Rebalancing ─────────────────────────────────────────────────────

export interface RebalanceTarget {
  symbol: string;
  target_percent: number;
}

export interface PortfolioAllocation {
  symbol: string;
  current_value: number;
  current_percent: number;
  target_percent: number;
  deviation: number;
  action_needed: string;
}

export interface RequiredTrade {
  symbol: string;
  action: string;
  quantity: number;
  value: number;
  current_percent: number;
  target_percent: number;
}

export interface RebalancePlan {
  total_value: number;
  current_alloc: PortfolioAllocation[];
  required_trades: RequiredTrade[];
  estimated_fees: number;
  threshold_breached: boolean;
}

export interface RebalanceHistoryEntry {
  id: string;
  user_id: string;
  triggered_by: string;
  allocations_before: Record<string, number>;
  allocations_after: Record<string, number>;
  trades_executed: number;
  total_fees: number;
  status: string;
  executed_at: string;
}

export const rebalanceApi = {
  async getTargets(): Promise<RebalanceTarget[]> {
    const res = await fetch(`${API_BASE_URL}/api/rebalance/targets`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get rebalance targets');
    return res.json();
  },

  async setTargets(targets: RebalanceTarget[]): Promise<void> {
    const res = await fetch(`${API_BASE_URL}/api/rebalance/targets`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${getAuthToken()}` },
      body: JSON.stringify({ targets }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to set targets' }));
      throw new Error(err.error || 'Failed to set targets');
    }
  },

  async analyze(): Promise<RebalancePlan> {
    const res = await fetch(`${API_BASE_URL}/api/rebalance/analyze`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to analyze portfolio' }));
      throw new Error(err.error || 'Failed to analyze portfolio');
    }
    return res.json();
  },

  async execute(triggeredBy = 'manual'): Promise<RebalanceHistoryEntry> {
    const res = await fetch(`${API_BASE_URL}/api/rebalance/execute?triggered_by=${triggeredBy}`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ error: 'Failed to execute rebalance' }));
      throw new Error(err.error || 'Failed to execute rebalance');
    }
    return res.json();
  },

  async getHistory(limit = 20): Promise<RebalanceHistoryEntry[]> {
    const res = await fetch(`${API_BASE_URL}/api/rebalance/history?limit=${limit}`, {
      headers: { Authorization: `Bearer ${getAuthToken()}` },
    });
    if (!res.ok) throw new Error('Failed to get rebalance history');
    return res.json();
  },
};
