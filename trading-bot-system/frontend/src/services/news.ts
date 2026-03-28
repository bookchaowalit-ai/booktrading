/**
 * News and Sentiment Analysis Service
 * Connects to backend API for real data with mock fallback
 */
import {
  NewsArticle,
  SentimentAnalysis,
  TradingSignal,
  MarketSentiment,
  NewsFilters,
  NewsResponse,
  SentimentResponse,
  TradingSignalsResponse,
  PositionDirection,
  SentimentScore,
  SentimentLabel,
  SignalStrength,
} from '@/types/news';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8080/api';

export const newsService = {
  /**
   * Get latest news articles from backend API
   */
  async getNews(filters?: NewsFilters): Promise<NewsResponse> {
    try {
      const params = new URLSearchParams();
      if (filters?.symbols?.length) params.append('symbol', filters.symbols[0]);
      if (filters?.sentiment?.length) params.append('sentiment', filters.sentiment[0]);
      if (filters?.categories?.length) params.append('category', filters.categories[0]);

      const response = await fetch(`${API_BASE_URL}/news?${params.toString()}`);
      if (!response.ok) throw new Error('Failed to fetch news');
      return await response.json();
    } catch (error) {
      console.error('News API error:', error);
      return { articles: [], total: 0, page: 1, pageSize: 20 };
    }
  },

  /**
   * Get sentiment analysis for a symbol from backend API
   */
  async getSentiment(symbol: string): Promise<SentimentResponse> {
    try {
      const response = await fetch(`${API_BASE_URL}/sentiment/${symbol}`);
      if (!response.ok) throw new Error('Failed to fetch sentiment');
      const data = await response.json();
      return data;
    } catch (error) {
      console.error('Sentiment API error:', error);
      return {
        sentiment: {
          symbol,
          overallSentiment: 0,
          sentimentLabel: 'neutral' as SentimentLabel,
          confidence: 0,
          recommendation: 'NEUTRAL',
          signalStrength: 'weak' as SignalStrength,
          updatedAt: new Date().toISOString(),
          analysis: {
            technical: 0,
            fundamental: 0,
            social: 0,
            news: 0,
          },
          factors: [],
        },
        history: [],
      };
    }
  },

  /**
   * Get trading signals from backend API
   */
  async getTradingSignals(symbol?: string): Promise<TradingSignalsResponse> {
    try {
      const params = symbol ? `?symbol=${symbol}` : '';
      const response = await fetch(`${API_BASE_URL}/signals${params}`);
      if (!response.ok) throw new Error('Failed to fetch signals');
      return await response.json();
    } catch (error) {
      console.error('Signals API error:', error);
      return { signals: [], total: 0 };
    }
  },

  /**
   * Get market-wide sentiment from backend API
   */
  async getMarketSentiment(): Promise<MarketSentiment> {
    try {
      const response = await fetch(`${API_BASE_URL}/market/sentiment`);
      if (!response.ok) throw new Error('Failed to fetch market sentiment');
      return await response.json();
    } catch (error) {
      console.error('Market sentiment API error:', error);
      return {
        overall: 0,
        label: 'neutral' as SentimentLabel,
        crypto: 0,
        stocks: 0,
        forex: 0,
        commodities: 0,
        fearGreedIndex: 50,
        trendingSymbols: [],
        topStories: [],
        updatedAt: new Date().toISOString(),
      };
    }
  },

  /**
   * Calculate position recommendation based on sentiment
   */
  calculateRecommendation(sentiment: SentimentScore): {
    direction: PositionDirection;
    leverage: number;
    confidence: number;
  } {
    let direction: PositionDirection = 'NEUTRAL';
    let leverage = 1;
    let confidence = 0.5;

    const absSentiment = Math.abs(sentiment);

    if (absSentiment < 0.3) {
      direction = 'NEUTRAL';
      leverage = 1;
      confidence = 0.5;
    } else if (absSentiment < 0.5) {
      direction = sentiment > 0 ? 'LONG' : 'SHORT';
      leverage = 2;
      confidence = 0.6;
    } else if (absSentiment < 0.7) {
      direction = sentiment > 0 ? 'LONG' : 'SHORT';
      leverage = 3;
      confidence = 0.75;
    } else {
      direction = sentiment > 0 ? 'LONG' : 'SHORT';
      leverage = 5;
      confidence = 0.85;
    }

    return { direction, leverage, confidence };
  },
};

// Helper functions
export function getSentimentLabel(score: SentimentScore): SentimentLabel {
  if (score >= 0.7) return 'very_bullish';
  if (score >= 0.3) return 'bullish';
  if (score >= -0.3) return 'neutral';
  if (score >= -0.7) return 'bearish';
  return 'very_bearish';
}

export function getSentimentColor(score: SentimentScore): string {
  if (score >= 0.7) return '#10B981';
  if (score >= 0.3) return '#34D399';
  if (score >= -0.3) return '#9CA3AF';
  if (score >= -0.7) return '#F87171';
  return '#EF4444';
}

export function getSentimentGradient(score: SentimentScore): string {
  if (score >= 0.7) return 'from-emerald-500 to-green-600';
  if (score >= 0.3) return 'from-green-400 to-emerald-500';
  if (score >= -0.3) return 'from-gray-400 to-gray-500';
  if (score >= -0.7) return 'from-orange-400 to-red-500';
  return 'from-red-500 to-rose-600';
}
