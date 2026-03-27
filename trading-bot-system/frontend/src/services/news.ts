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
      // Fallback to mock data
      return getMockNews(filters);
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
      // Fallback to mock data
      return getMockSentiment(symbol);
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
      // Fallback to mock data
      return getMockSignals(symbol);
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
      // Fallback to mock data
      return getMockMarketSentiment();
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

// Mock data functions for fallback
function getMockNews(filters?: NewsFilters): NewsResponse {
  const mockNewsArticles: NewsArticle[] = [
    {
      id: '1',
      title: 'Bitcoin Surges Past $50,000 as Institutional Adoption Grows',
      summary: 'Major financial institutions continue to add Bitcoin to their balance sheets.',
      content: 'Bitcoin has broken through the $50,000 resistance level...',
      source: 'CryptoNews',
      author: 'John Smith',
      publishedAt: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
      url: '#',
      imageUrl: 'https://images.unsplash.com/photo-1518546305927-5a555bb7020d?w=400',
      symbols: ['BTCUSDT'],
      categories: ['crypto', 'market'],
      sentiment: 0.75,
      sentimentLabel: 'bullish',
      relevanceScore: 0.95,
    },
    // Add more mock articles as needed
  ];
  
  return {
    articles: mockNewsArticles,
    total: mockNewsArticles.length,
    page: 1,
    pageSize: 20,
  };
}

function getMockSentiment(symbol: string): SentimentResponse {
  const mockSentiment: SentimentAnalysis = {
    symbol,
    overallSentiment: 0.65,
    sentimentLabel: 'bullish',
    confidence: 0.8,
    recommendation: 'LONG',
    signalStrength: 'strong',
    leverageSuggestion: 3,
    analysis: {
      technical: 0.6,
      fundamental: 0.7,
      social: 0.65,
      news: 0.75,
    },
    factors: [
      {
        type: 'news',
        impact: 'positive',
        strength: 0.75,
        description: 'Positive institutional adoption news',
      },
    ],
    updatedAt: new Date().toISOString(),
  };

  const history = Array.from({ length: 24 }, (_, i) => {
    const timestamp = new Date(Date.now() - (23 - i) * 60 * 60 * 1000).toISOString();
    const baseSentiment = mockSentiment.overallSentiment;
    const variation = (Math.random() - 0.5) * 0.3;
    const sentValue = Math.max(-1, Math.min(1, baseSentiment + variation));
    
    return {
      timestamp,
      sentiment: sentValue,
      label: getSentimentLabel(sentValue),
    };
  });

  return {
    sentiment: mockSentiment,
    history,
  };
}

function getMockSignals(symbol?: string): TradingSignalsResponse {
  const mockSignals: TradingSignal[] = [
    {
      id: 'signal-1',
      symbol: symbol || 'BTCUSDT',
      direction: 'LONG',
      entryPrice: 49500,
      targetPrices: [51000, 53000, 55000],
      stopLoss: 47500,
      leverage: 3,
      confidence: 0.82,
      strength: 'strong',
      timeframe: 'swing',
      reasoning: [
        'Breaking above key resistance',
        'Positive institutional news',
        'RSI showing bullish divergence',
      ],
      riskRewardRatio: 2.5,
      createdAt: new Date().toISOString(),
      expiresAt: new Date(Date.now() + 1000 * 60 * 60 * 24 * 3).toISOString(),
      status: 'active',
    },
  ];

  return {
    signals: mockSignals,
    total: mockSignals.length,
  };
}

function getMockMarketSentiment(): MarketSentiment {
  return {
    overall: 0.55,
    label: 'bullish',
    crypto: 0.72,
    stocks: 0.35,
    forex: 0.15,
    commodities: 0.58,
    fearGreedIndex: 68,
    trendingSymbols: ['BTCUSDT', 'ETHUSDT', 'XAUUSD'],
    topStories: [],
    updatedAt: new Date().toISOString(),
  };
}

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
