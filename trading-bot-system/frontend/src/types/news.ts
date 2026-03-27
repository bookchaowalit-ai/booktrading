/**
 * News and Sentiment Analysis Types
 */

// Sentiment Score: -1 (Very Bearish) to 1 (Very Bullish)
export type SentimentScore = number;

// Sentiment Label
export type SentimentLabel = 'very_bearish' | 'bearish' | 'neutral' | 'bullish' | 'very_bullish';

// Position Direction
export type PositionDirection = 'LONG' | 'SHORT' | 'NEUTRAL';

// Trading Signal Strength
export type SignalStrength = 'weak' | 'moderate' | 'strong' | 'very_strong';

export interface NewsArticle {
  id: string;
  title: string;
  summary: string;
  content: string;
  source: string;
  author?: string;
  publishedAt: string;
  url: string;
  imageUrl?: string;
  symbols: string[]; // Related trading symbols
  categories: string[]; // e.g., ['crypto', 'regulation', 'market']
  sentiment?: SentimentScore;
  sentimentLabel?: SentimentLabel;
  relevanceScore?: number; // 0-1
}

export interface SentimentAnalysis {
  symbol: string;
  overallSentiment: SentimentScore;
  sentimentLabel: SentimentLabel;
  confidence: number; // 0-1
  recommendation: PositionDirection;
  signalStrength: SignalStrength;
  leverageSuggestion?: number; // Suggested leverage (1x, 2x, 3x, 5x, 10x)
  analysis: {
    technical: SentimentScore;
    fundamental: SentimentScore;
    social: SentimentScore;
    news: SentimentScore;
  };
  factors: SentimentFactor[];
  updatedAt: string;
}

export interface SentimentFactor {
  type: 'news' | 'technical' | 'social' | 'fundamental';
  impact: 'positive' | 'negative' | 'neutral';
  strength: number; // 0-1
  description: string;
  source?: string;
}

export interface TradingSignal {
  id: string;
  symbol: string;
  direction: PositionDirection;
  entryPrice?: number;
  targetPrices: number[];
  stopLoss?: number;
  leverage?: number;
  confidence: number;
  strength: SignalStrength;
  timeframe: 'scalp' | 'day' | 'swing' | 'position';
  reasoning: string[];
  riskRewardRatio?: number;
  createdAt: string;
  expiresAt?: string;
  status: 'active' | 'executed' | 'expired' | 'cancelled';
}

export interface MarketSentiment {
  overall: SentimentScore;
  label: SentimentLabel;
  crypto: SentimentScore;
  stocks: SentimentScore;
  forex: SentimentScore;
  commodities: SentimentScore;
  fearGreedIndex?: number; // 0-100
  trendingSymbols: string[];
  topStories: NewsArticle[];
  updatedAt: string;
}

export interface NewsFilters {
  categories: string[];
  symbols: string[];
  sentiment?: SentimentLabel[];
  sources?: string[];
  timeRange?: '1h' | '6h' | '24h' | '7d' | '30d';
  searchQuery?: string;
}

// API Response Types
export interface NewsResponse {
  articles: NewsArticle[];
  total: number;
  page: number;
  pageSize: number;
}

export interface SentimentResponse {
  sentiment: SentimentAnalysis;
  history: SentimentHistory[];
}

export interface SentimentHistory {
  timestamp: string;
  sentiment: SentimentScore;
  label: SentimentLabel;
}

export interface TradingSignalsResponse {
  signals: TradingSignal[];
  total: number;
}
