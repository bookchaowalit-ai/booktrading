/**
 * Trade Journal Types
 */

export interface JournalEntry {
  id?: number;
  symbol: string;
  side: 'BUY' | 'SELL';
  strategy: string;
  entry_reason: string;
  entry_price: number;
  quantity: number;
  expected_risk_thb: number;
  expected_reward_thb: number;
  stop_loss_price?: number;
  take_profit_price?: number;
  exit_price: number;
  exit_reason: string;
  actual_pnl: number;
  fee: number;
  drawdown_impact_pct: number;
  exchange_order_id: string;
  status: 'OPEN' | 'CLOSED' | 'CANCELLED';
  created_at: number | string;
  closed_at?: number | string | null;
  notes?: string;
}

export interface JournalStats {
  total_entries: number;
  open_entries?: number;
  closed_entries: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  total_fees: number;
  avg_win: number;
  avg_loss: number;
  profit_factor: number;
}

export interface JournalResponse {
  in_memory: JournalEntry[];
  db_entries: JournalEntry[];
  in_memory_stats: JournalStats;
  db_stats: JournalStats;
}

export interface DailyReport {
  symbol: string;
  bot_enabled: boolean;
  bot_running: boolean;
  symbol_state: {
    last_price: number;
    active_buys: number;
    active_sells: number;
    daily_pnl: number;
    daily_trades: number;
    halted: boolean;
  } | Record<string, never>;
  open_orders: Array<{
    order_id: string;
    symbol: string;
    side: string;
    price: number;
    quantity: number;
    status: string;
    created_at: string;
  }>;
  filled_trades: Array<{
    order_id: string;
    symbol: string;
    side: string;
    price: number;
    quantity: number;
    fee: number;
    created_at: string;
  }>;
  risk: {
    halted: boolean;
    halt_reason: string;
    daily_pnl: number;
    daily_trades: number;
    daily_wins: number;
    daily_losses: number;
    consecutive_losses: number;
    current_drawdown_pct: number;
  };
  journal_stats: JournalStats;
  risk_events: Array<{
    event_type: string;
    message: string;
    timestamp: string;
  }>;
}
