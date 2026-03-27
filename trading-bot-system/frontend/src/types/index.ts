/**
 * Type definitions for the trading bot.
 */

// Asset Categories
export type AssetCategory = 'crypto' | 'stock' | 'forex' | 'commodity' | 'index';

export interface AssetCategoryInfo {
  id: AssetCategory;
  name: string;
  icon: string;
  color: string;
  description: string;
}

// Asset categories configuration
export const ASSET_CATEGORIES: AssetCategoryInfo[] = [
  {
    id: 'crypto',
    name: 'Cryptocurrency',
    icon: 'bitcoin',
    color: '#F7931A',
    description: 'Digital currencies like Bitcoin, Ethereum',
  },
  {
    id: 'stock',
    name: 'Stocks',
    icon: 'building',
    color: '#10B981',
    description: 'Company shares and equities',
  },
  {
    id: 'forex',
    name: 'Forex',
    icon: 'currency',
    color: '#3B82F6',
    description: 'Foreign exchange currency pairs',
  },
  {
    id: 'commodity',
    name: 'Commodities',
    icon: 'box',
    color: '#8B5CF6',
    description: 'Gold, Silver, Oil, and other commodities',
  },
  {
    id: 'index',
    name: 'Indices',
    icon: 'chart',
    color: '#EC4899',
    description: 'Market indices like S&P 500, NASDAQ',
  },
];

// Helper to get category from symbol
export function getAssetCategory(symbol: string): AssetCategory {
  const sym = symbol.toUpperCase();
  
  // Crypto pairs
  if (sym.endsWith('USDT') || sym.endsWith('USDC') || sym.endsWith('BTC') || sym.endsWith('ETH')) {
    return 'crypto';
  }
  
  // Forex pairs
  if (sym.match(/^(EUR|USD|GBP|JPY|AUD|CAD|CHF|NZD)(EUR|USD|GBP|JPY|AUD|CAD|CHF|NZD)$/)) {
    return 'forex';
  }
  
  // Commodities
  if (sym.match(/^(XAU|XAG|XPT|XPD|USOIL|UKOIL|NATGAS)/)) {
    return 'commodity';
  }
  
  // Indices
  if (sym.match(/^(SPX|NDX|DJI|IXIC|FTSE|DAX|N225|HSI)/)) {
    return 'index';
  }
  
  // Stocks (default for other symbols)
  if (sym.match(/^[A-Z]{1,5}$/) || sym.match(/^[A-Z]+\d+[C|P]\d+/)) {
    return 'stock';
  }
  
  // Default to crypto for unknown symbols
  return 'crypto';
}

// Helper to get category info
export function getCategoryInfo(category: AssetCategory): AssetCategoryInfo {
  return ASSET_CATEGORIES.find(c => c.id === category) || ASSET_CATEGORIES[0];
}

export interface MarketData {
  symbol: string;
  price: number;
  volume: number;
  timestamp: string;
  category?: AssetCategory;
  change24h?: number;
  high24h?: number;
  low24h?: number;
}

export interface Order {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  type: 'MARKET' | 'LIMIT';
  quantity: number;
  price?: number;
  status: 'PENDING' | 'FILLED' | 'CANCELLED' | 'REJECTED';
  category?: AssetCategory;
  createdAt: string;
  updatedAt: string;
}

export interface Portfolio {
  symbol: string;
  balance: number;
  locked: number;
  avgBuyPrice: number;
  category?: AssetCategory;
  currentValue?: number;
  profitLoss?: number;
  profitLossPercent?: number;
  updatedAt: string;
}

export interface TradeHistory {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price: number;
  total: number;
  fee: number;
  category?: AssetCategory;
  executedAt: string;
}

export interface BotStatus {
  isActive: boolean;
  startedAt?: string;
  stoppedAt?: string;
  totalTrades: number;
  totalProfit: number;
  profitByCategory?: Record<AssetCategory, number>;
}

export interface TechnicalIndicators {
  symbol: string;
  rsi: number | null;
  ema: number | null;
  sma: number | null;
  macd: number | null;
  macd_signal: number | null;
}

export interface WebSocketMessage {
  type: 'market_data' | 'bot_status' | 'order_update' | 'pong';
  data: MarketData | BotStatus | Order;
}

export interface OrderRequest {
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  price?: number;
  category?: AssetCategory;
}

export interface OrderResponse {
  order_id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  quantity: number;
  status: string;
  createdAt: string;
}

// Category filter state
export interface CategoryFilter {
  categories: AssetCategory[];
  searchQuery: string;
  sortBy: 'value' | 'name' | 'profit' | 'change';
  sortOrder: 'asc' | 'desc';
}
