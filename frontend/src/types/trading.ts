/**
 * Strict TypeScript Types for Trading Bot
 * Comprehensive type definitions for type safety
 */

// ── Bot Types ──────────────────────────────────────────────────────────────────

export type BotMode = 'GRID' | 'SIGNAL' | 'AUTO';
export type BotStatus = 'running' | 'stopped' | 'error';

export interface BotConfig {
  symbol: string;
  lowerPrice: number;
  upperPrice: number;
  gridLevels: number;
  investmentAmount: number;
  botMode: BotMode;
}

export interface BotStatusData {
  isActive: boolean;
  startedAt?: string;
  stoppedAt?: string;
  totalTrades: number;
  totalProfit: number;
  botMode?: BotMode;
}

// ── Order Types ────────────────────────────────────────────────────────────────

export type OrderSide = 'BUY' | 'SELL';
export type OrderType = 'MARKET' | 'LIMIT' | 'STOP_LOSS' | 'TAKE_PROFIT';
export type OrderStatus = 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';

export interface Order {
  id: string;
  symbol: string;
  side: OrderSide;
  type: OrderType;
  quantity: number;
  price?: number;
  status: OrderStatus;
  createdAt: string;
  updatedAt: string;
}

export interface OrderRequest {
  symbol: string;
  side: OrderSide;
  quantity: number;
  price?: number;
}

export interface OrderResponse {
  order_id: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  status: OrderStatus;
  createdAt: string;
}

// ── Portfolio Types ────────────────────────────────────────────────────────────

export interface PortfolioItem {
  symbol: string;
  balance: number;
  locked: number;
  avgBuyPrice: number;
  currentValue?: number;
  profitLoss?: number;
  profitLossPercent?: number;
  updatedAt: string;
}

// ── Trade Types ────────────────────────────────────────────────────────────────

export interface Trade {
  id: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  total: number;
  fee: number;
  pnl?: number;
  executedAt: string;
}

export interface TradeNotification {
  id: string;
  symbol: string;
  side: OrderSide;
  quantity: number;
  price: number;
  total: number;
  type: 'GRID_BUY' | 'GRID_SELL' | 'SIGNAL_BUY' | 'SIGNAL_SELL';
  timestamp: string;
  message: string;
}

// ── Market Data Types ─────────────────────────────────────────────────────────

export interface MarketData {
  symbol: string;
  price: number;
  volume: number;
  timestamp: string;
  change24h?: number;
  high24h?: number;
  low24h?: number;
}

export interface TechnicalIndicators {
  symbol: string;
  rsi: number | null;
  ema: number | null;
  sma: number | null;
  macd: number | null;
  macd_signal: number | null;
}

// ── WebSocket Types ───────────────────────────────────────────────────────────

export type WebSocketMessageType =
  | 'market_data'
  | 'bot_status'
  | 'order_update'
  | 'trade_notification'
  | 'bot_activity'
  | 'pong';

export interface WebSocketMessage {
  type: WebSocketMessageType;
  data: MarketData | BotStatusData | Order | TradeNotification | BotActivity;
}

export interface BotActivity {
  timestamp: string;
  activity: 'SCANNING' | 'ANALYZING' | 'WAITING' | 'PLACING_ORDER' | 'STARTED' | 'STOPPED' | 'ERROR';
  symbol?: string;
  message: string;
  level: 'info' | 'success' | 'warning' | 'error';
}

// ── Exchange Types ────────────────────────────────────────────────────────────

export type ExchangeProvider = 'binance' | 'binance_th' | 'bitkub';

export interface ExchangeBalance {
  currency: string;
  free: number;
  locked: number;
  total: number;
}

export interface AllBalancesResponse {
  exchanges: Record<string, {
    connected: boolean;
    balances: ExchangeBalance[];
    totalTHB: number;
    totalUSDT: number;
    balanceCount: number;
  }>;
  totalTHB: number;
  totalUSDT: number;
  exchangeCount: number;
  cached: boolean;
  timestamp: string;
}

// ── API Error Types ───────────────────────────────────────────────────────────

export interface ApiError {
  status: number;
  statusText: string;
  endpoint: string;
  message: string;
  retryAfter?: number;
}

// ── Performance Types ─────────────────────────────────────────────────────────

export interface PerformanceData {
  date: string;
  value: number;
  profit: number;
  profitPercent: number;
}

export interface PerformanceStats {
  totalTrades: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  sharpeRatio: number;
  maxDrawdown: number;
  totalProfit: number;
}

// ── Utility Types ─────────────────────────────────────────────────────────────

export type Nullable<T> = T | null;
export type Optional<T> = T | undefined;
export type AsyncResult<T> = Promise<T | null>;
export type Result<T, E = Error> = { ok: true; value: T } | { ok: false; error: E };
