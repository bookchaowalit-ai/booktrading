/**
 * Sentiment Dashboard Component
 * Comprehensive view of market sentiment, news, and trading signals
 */
'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { newsService, getSentimentGradient } from '@/services/news';
import { SentimentAnalysis, MarketSentiment, TradingSignal, SentimentHistory } from '@/types/news';
import Card from './ui/Card';
import SentimentGauge from './SentimentGauge';
import NewsFeed from './NewsFeed';
import TradingSignals from './TradingSignals';
import {
  SentimentHistoryChart,
  MarketSentimentPieChart,
  SignalStrengthBarChart,
  AssetAllocationDonutChart,
} from '@/components/charts';
import { Activity, Newspaper, Zap, TrendingUp, TrendingDown, BarChart3 } from 'lucide-react';
import { useToast } from './ui/Toast';
import { useAppStore } from '@/store/store';

interface SentimentDashboardProps {
  symbol?: string;
}

export default function SentimentDashboard({ symbol }: SentimentDashboardProps) {
  const { success, error } = useToast();
  const portfolio = useAppStore((state) => state.portfolio);
  const [marketSentiment, setMarketSentiment] = useState<MarketSentiment | null>(null);
  const [symbolSentiment, setSymbolSentiment] = useState<SentimentAnalysis | null>(null);
  const [sentimentHistory, setSentimentHistory] = useState<SentimentHistory[]>([]);
  const [tradingSignals, setTradingSignals] = useState<TradingSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, [symbol]);

  const loadData = async () => {
    setIsLoading(true);
    try {
      // Fetch real market sentiment from backend
      const marketResponse = await fetch('http://localhost:8080/api/market/sentiment');
      const marketData = await marketResponse.json().catch(() => null);

      // Fetch real sentiment for symbol
      let symbolData = null;
      if (symbol) {
        const symbolResponse = await fetch(`http://localhost:8080/api/sentiment/${symbol}`);
        symbolData = await symbolResponse.json().catch(() => null);
      }

      // Fetch real trading signals
      const signalsResponse = await fetch(`http://localhost:8080/api/signals${symbol ? `?symbol=${symbol}` : ''}`);
      const signalsData = await signalsResponse.json().catch(() => ({ signals: [] }));

      setMarketSentiment(marketData);
      setSymbolSentiment(symbolData?.sentiment || null);
      setSentimentHistory(symbolData?.history || []);
      setTradingSignals(signalsData.signals || []);

      if (marketData || symbolData) {
        success('Real-time data loaded');
      }
    } catch (err) {
      console.error('Failed to load sentiment data:', err);
      error('Using cached data - backend unavailable');
    } finally {
      setIsLoading(false);
    }
  };

  const handleTrade = (direction: import('@/types/news').PositionDirection, leverage: number) => {
    if (direction === 'NEUTRAL') return;
    success(`Executing ${direction} position with ${leverage}x leverage`);
  };

  const getCategoryColor = (score: number) => {
    if (score >= 0.5) return 'text-green-600';
    if (score >= -0.5) return 'text-gray-500';
    return 'text-red-600';
  };

  if (isLoading) {
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="p-6 lg:col-span-1">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
            <div className="h-32 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </Card>
        <Card className="p-6 lg:col-span-2">
          <div className="animate-pulse space-y-4">
            <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/3" />
            <div className="h-24 bg-gray-200 dark:bg-gray-700 rounded" />
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Market Overview */}
      {marketSentiment && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
        >
          <Card variant="elevated" gradient className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <BarChart3 className="w-6 h-6 text-purple-600" />
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Market Sentiment Overview
                </h3>
              </div>
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Zap className="w-4 h-4 text-yellow-500" />
                Updated {new Date(marketSentiment.updatedAt).toLocaleTimeString()}
              </div>
            </div>

            {/* Overall Sentiment */}
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4 mb-6">
              <div className="md:col-span-1">
                <div className="text-center p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Overall</div>
                  <div className={`text-2xl font-bold ${getCategoryColor(marketSentiment.overall)}`}>
                    {(marketSentiment.overall * 100).toFixed(0)}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                    {marketSentiment.label.replace('_', ' ')}
                  </div>
                </div>
              </div>

              <div className="md:col-span-4 grid grid-cols-2 md:grid-cols-4 gap-4">
                <div className="text-center p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Crypto</div>
                  <div className={`text-2xl font-bold ${getCategoryColor(marketSentiment.crypto)}`}>
                    {(marketSentiment.crypto * 100).toFixed(0)}
                  </div>
                </div>
                <div className="text-center p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Stocks</div>
                  <div className={`text-2xl font-bold ${getCategoryColor(marketSentiment.stocks)}`}>
                    {(marketSentiment.stocks * 100).toFixed(0)}
                  </div>
                </div>
                <div className="text-center p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Forex</div>
                  <div className={`text-2xl font-bold ${getCategoryColor(marketSentiment.forex)}`}>
                    {(marketSentiment.forex * 100).toFixed(0)}
                  </div>
                </div>
                <div className="text-center p-4 bg-white/50 dark:bg-gray-800/50 rounded-lg">
                  <div className="text-sm text-gray-600 dark:text-gray-400 mb-2">Commodities</div>
                  <div className={`text-2xl font-bold ${getCategoryColor(marketSentiment.commodities)}`}>
                    {(marketSentiment.commodities * 100).toFixed(0)}
                  </div>
                </div>
              </div>
            </div>

            {/* Fear & Greed */}
            {marketSentiment.fearGreedIndex && (
              <div className="flex items-center justify-between p-4 bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-lg">
                <div className="flex items-center gap-3">
                  {marketSentiment.fearGreedIndex >= 50 ? (
                    <TrendingUp className="w-6 h-6 text-green-600" />
                  ) : (
                    <TrendingDown className="w-6 h-6 text-red-600" />
                  )}
                  <div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Fear & Greed Index
                    </div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">
                      Market sentiment indicator
                    </div>
                  </div>
                </div>
                <div className="text-right">
                  <div className={`text-3xl font-bold ${marketSentiment.fearGreedIndex >= 50 ? 'text-green-600' : 'text-red-600'
                    }`}>
                    {marketSentiment.fearGreedIndex}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400 capitalize">
                    {marketSentiment.fearGreedIndex >= 75 ? 'Extreme Greed' :
                      marketSentiment.fearGreedIndex >= 50 ? 'Greed' :
                        marketSentiment.fearGreedIndex >= 25 ? 'Fear' : 'Extreme Fear'}
                  </div>
                </div>
              </div>
            )}
          </Card>
        </motion.div>
      )}

      {/* Main Content Grid - Charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        {/* Sentiment History Chart */}
        {sentimentHistory && sentimentHistory.length > 0 && (
          <div className="lg:col-span-2">
            <SentimentHistoryChart
              data={sentimentHistory}
              symbol={symbol}
              height={250}
            />
          </div>
        )}

        {/* Market Sentiment Pie Chart */}
        {marketSentiment && (
          <MarketSentimentPieChart
            crypto={marketSentiment.crypto}
            stocks={marketSentiment.stocks}
            forex={marketSentiment.forex}
            commodities={marketSentiment.commodities}
            height={250}
          />
        )}

        {/* Signal Strength Bar Chart */}
        {tradingSignals && tradingSignals.length > 0 && (
          <SignalStrengthBarChart
            signals={tradingSignals}
            height={250}
          />
        )}
      </div>

      {/* Asset Allocation (if portfolio data available) */}
      {portfolio && portfolio.length > 0 && (
        <div className="mb-6">
          <AssetAllocationDonutChart
            portfolio={portfolio}
            height={250}
          />
        </div>
      )}

      {/* Main Content Grid - News and Signals */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Sentiment Gauge & Active Signals */}
        <div className="space-y-6">
          {/* Symbol Sentiment Gauge */}
          {symbolSentiment && (
            <SentimentGauge
              sentiment={symbolSentiment}
              onTrade={handleTrade}
            />
          )}

          {/* Active Trading Signals */}
          <div>
            <div className="flex items-center gap-2 mb-4">
              <Zap className="w-5 h-5 text-purple-600" />
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Active Signals
              </h3>
            </div>
            <TradingSignals symbol={symbol} />
          </div>
        </div>

        {/* Right Column - News Feed */}
        <div className="lg:col-span-2">
          <NewsFeed symbol={symbol} limit={8} />
        </div>
      </div>
    </div>
  );
}
