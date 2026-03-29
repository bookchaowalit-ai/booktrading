/**
 * Analytics Page
 * Comprehensive market analytics with charts and visualizations
 */
'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/store/store';
import { newsService } from '@/services/news';
import { MarketSentiment, TradingSignal, SentimentHistory } from '@/types/news';
import Card from '@/components/ui/Card';
import {
  SentimentHistoryChart,
  MarketSentimentPieChart,
  SignalStrengthBarChart,
  AssetAllocationDonutChart,
} from '@/components/charts';
import { useTranslation } from '@/i18n/translations';
import { BarChart3, TrendingUp, Activity, Zap, DollarSign } from 'lucide-react';
import StatCard from '@/components/StatCard';
import TradingPerformance from '@/components/TradingPerformance';
import OrderTracking from '@/components/OrderTracking';
import TradingJournal from '@/components/TradingJournal';

export default function AnalyticsPage() {
  const { t } = useTranslation();
  const portfolio = useAppStore((state) => state.portfolio);
  const [marketSentiment, setMarketSentiment] = useState<MarketSentiment | null>(null);
  const [sentimentHistory, setSentimentHistory] = useState<SentimentHistory[]>([]);
  const [tradingSignals, setTradingSignals] = useState<TradingSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
    setIsLoading(true);
    try {
      // Fetch real market sentiment from backend
      const marketResponse = await fetch(`${API_BASE_URL}/api/market/sentiment`);
      const marketData = await marketResponse.json().catch(() => null);

      // Fetch real trading signals
      const signalsResponse = await fetch(`${API_BASE_URL}/api/signals`);
      const signalsData = await signalsResponse.json().catch(() => ({ signals: [] }));

      // Fetch real sentiment history
      const sentimentResponse = await fetch(`${API_BASE_URL}/api/sentiment/BTCUSDT`);
      const sentimentData = await sentimentResponse.json().catch(() => null);

      setMarketSentiment(marketData);
      setTradingSignals(signalsData.signals || []);
      setSentimentHistory(sentimentData?.history || []);
    } catch (error) {
      console.error('Failed to load analytics data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading analytics...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compact Header */}
      <div className="flex items-center gap-2">
        <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
          <BarChart3 className="w-5 h-5 text-purple-600" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">
            Market Analytics
          </h1>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            Comprehensive market analysis and visualizations
          </p>
        </div>
      </div>

      {/* Compact Key Metrics */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <Activity className="w-4 h-4 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Market Sentiment</span>
          </div>
          <div className="text-lg font-bold text-purple-600">
            {marketSentiment ? (marketSentiment.overall * 100).toFixed(0) : 0}%
          </div>
        </div>

        <StatCard
          title="Active Signals"
          value={tradingSignals.length}
          icon={<Zap className="w-6 h-6" />}
          color="#10B981"
          delay={0.2}
        />

        <StatCard
          title="Fear & Greed"
          value={marketSentiment?.fearGreedIndex || 0}
          icon={<TrendingUp className="w-6 h-6" />}
          trend={marketSentiment?.fearGreedIndex && marketSentiment.fearGreedIndex >= 50 ? 10 : -10}
          color="#F59E0B"
          delay={0.3}
        />

        <StatCard
          title="Portfolio Value"
          value={`$${portfolio.reduce((sum, item) => sum + (item.balance * item.avgBuyPrice), 0).toLocaleString(undefined, { maximumFractionDigits: 0 })}`}
          icon={<DollarSign className="w-6 h-6" />}
          color="#3B82F6"
          delay={0.4}
        />
      </div>

      {/* Charts Grid - Row 1 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Sentiment History */}
        <SentimentHistoryChart
          data={sentimentHistory}
          symbol="BTCUSDT"
          height={300}
        />

        {/* Market Sentiment by Asset Class */}
        {marketSentiment && (
          <MarketSentimentPieChart
            crypto={marketSentiment.crypto}
            stocks={marketSentiment.stocks}
            forex={marketSentiment.forex}
            commodities={marketSentiment.commodities}
            height={300}
          />
        )}
      </div>

      {/* Charts Grid - Row 2 */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Signal Strength Analysis */}
        {tradingSignals.length > 0 && (
          <SignalStrengthBarChart
            signals={tradingSignals}
            height={300}
          />
        )}

        {/* Asset Allocation */}
        {portfolio && portfolio.length > 0 && (
          <AssetAllocationDonutChart
            portfolio={portfolio}
            height={300}
          />
        )}
      </div>

      {/* Trading Signals Table */}
      {tradingSignals.length > 0 && (
        <Card variant="elevated" className="p-6">
          <div className="flex items-center gap-2 mb-6">
            <Zap className="w-5 h-5 text-purple-600" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Active Trading Signals
            </h3>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Symbol
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Direction
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Entry Price
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Targets
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Stop Loss
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Leverage
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Confidence
                  </th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                    Strength
                  </th>
                </tr>
              </thead>
              <tbody>
                {tradingSignals.map((signal) => (
                  <motion.tr
                    key={signal.id}
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                  >
                    <td className="py-3 px-4">
                      <span className="font-medium text-gray-900 dark:text-white">
                        {signal.symbol}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2.5 py-1 rounded-full text-xs font-bold ${signal.direction === 'LONG'
                          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                          : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          }`}
                      >
                        {signal.direction}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-gray-900 dark:text-white">
                      ${signal.entryPrice?.toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <div className="space-y-1">
                        <div className="text-xs text-green-600">T1: ${signal.targetPrices[0]?.toLocaleString()}</div>
                        <div className="text-xs text-green-600">T2: ${signal.targetPrices[1]?.toLocaleString()}</div>
                        <div className="text-xs text-green-600">T3: ${signal.targetPrices[2]?.toLocaleString()}</div>
                      </div>
                    </td>
                    <td className="py-3 px-4 text-red-600">
                      ${signal.stopLoss?.toLocaleString()}
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {signal.leverage}x
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${signal.confidence * 100}%`,
                              backgroundColor: signal.confidence >= 0.8 ? '#10B981' : signal.confidence >= 0.6 ? '#F59E0B' : '#EF4444',
                            }}
                          />
                        </div>
                        <span className="text-xs text-gray-600 dark:text-gray-400">
                          {(signal.confidence * 100).toFixed(0)}%
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-4">
                      <span
                        className={`px-2 py-1 rounded text-xs font-medium capitalize ${signal.strength === 'very_strong'
                          ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400'
                          : signal.strength === 'strong'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : signal.strength === 'moderate'
                              ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                              : 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400'
                          }`}
                      >
                        {signal.strength.replace('_', ' ')}
                      </span>
                    </td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Trading Performance */}
      <TradingPerformance />

      {/* Order Tracking */}
      <OrderTracking symbol="BTCUSDT" gridLevels={10} />

      {/* Trading Journal */}
      <TradingJournal />
    </div>
  );
}
