/**
 * Monitoring Dashboard Types
 * Aggregates bot health, risk, and alert data
 */

export interface BotSymbolStatus {
  last_price: number;
  active_buys: number;
  active_sells: number;
  trades_executed: number;
  daily_pnl: number;
  daily_trades: number;
  halted: boolean;
}

export interface BotStatus {
  running: boolean;
  enabled: boolean;
  symbols: Record<string, BotSymbolStatus>;
  risk: RiskStatus;
  journal_stats: Record<string, any>;
}

export interface RiskEvent {
  timestamp: number;
  event_type: string;
  symbol?: string;
  message: string;
  severity: string;
}

export interface RiskStatus {
  halted: boolean;
  halt_reason: string;
  daily_pnl: number;
  daily_trades: number;
  daily_wins: number;
  daily_losses: number;
  consecutive_losses: number;
  max_consecutive_losses: number;
  current_drawdown_pct: number;
  max_drawdown_pct: number;
  peak_equity: number;
  total_trades: number;
  win_rate_pct: number;
  last_order_time: number;
  config: {
    max_daily_loss_thb: number;
    max_drawdown_pct: number;
    max_order_size_thb: number;
    risk_per_trade_pct: number;
    max_consecutive_losses: number;
    max_open_orders: number;
  };
  recent_events: RiskEvent[];
}

export interface HealthStatus {
  status: 'healthy' | 'degraded' | 'down';
  redis_connected: boolean;
}

export interface MarketAlert {
  id: string;
  symbol: string;
  market: string;
  source: string;
  type: string;
  severity: string;
  title: string;
  description: string;
  price?: number;
  confidence?: number;
  timestamp?: string;
}

export interface MonitoringData {
  health: HealthStatus;
  bot: BotStatus;
  alerts: MarketAlert[];
  timestamp: number;
}
