/**
 * Trading Performance Analytics
 * Comprehensive trading statistics and metrics
 */
'use client';

import { useState, useEffect } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Activity,
  Award,
  Target,
  BarChart3,
} from 'lucide-react';

interface Trade {
  id: string;
  symbol: string;
  side: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice?: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  timestamp: Date;
  status: 'OPEN' | 'CLOSED';
}

interface PerformanceMetrics {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  winRate: number;
  totalPnL: number;
  totalPnLPercent: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  bestTrade: number;
  worstTrade: number;
  avgTradeDuration: string;
  sharpeRatio: number;
  maxDrawdown: number;
  maxDrawdownPercent: number;
}

export default function TradingPerformance() {
  // Mock data (replace with real data from backend)
  const [metrics, setMetrics] = useState<PerformanceMetrics>({
    totalTrades: 47,
    winningTrades: 31,
    losingTrades: 16,
    winRate: 65.96,
    totalPnL: 1247.53,
    totalPnLPercent: 12.48,
    avgWin: 87.32,
    avgLoss: -42.15,
    profitFactor: 2.07,
    bestTrade: 342.50,
    worstTrade: -125.30,
    avgTradeDuration: '4h 23m',
    sharpeRatio: 1.85,
    maxDrawdown: -234.50,
    maxDrawdownPercent: -2.34,
  });

  const getPnLColor = (value: number) => {
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const getBadgeVariant = (value: number) => {
    return value >= 0 ? 'success' : 'error';
  };

  const getMetricColor = (value: number, good: number, bad: number) => {
    if (value >= good) return 'text-green-600';
    if (value <= bad) return 'text-red-600';
    return 'text-amber-600';
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-purple-600" />
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            Trading Performance
          </h3>
        </div>
        <Badge variant="info" size="sm">
          Last 30 Days
        </Badge>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {/* Win Rate */}
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-4 h-4 text-blue-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Win Rate</span>
          </div>
          <div
            className={`text-xl font-bold ${getMetricColor(
              metrics.winRate,
              60,
              40
            )}`}
          >
            {metrics.winRate.toFixed(2)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {metrics.winningTrades}W / {metrics.losingTrades}L
          </div>
        </Card>

        {/* Profit Factor */}
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-2">
            <Award className="w-4 h-4 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Profit Factor
            </span>
          </div>
          <div
            className={`text-xl font-bold ${getMetricColor(
              metrics.profitFactor,
              2,
              1
            )}`}
          >
            {metrics.profitFactor.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {metrics.profitFactor >= 2
              ? '✅ Excellent'
              : metrics.profitFactor >= 1.5
              ? '⚠️ Good'
              : '❌ Poor'}
          </div>
        </Card>

        {/* Sharpe Ratio */}
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-green-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Sharpe Ratio
            </span>
          </div>
          <div
            className={`text-xl font-bold ${getMetricColor(
              metrics.sharpeRatio,
              1.5,
              0.5
            )}`}
          >
            {metrics.sharpeRatio.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {metrics.sharpeRatio >= 2
              ? '✅ Excellent'
              : metrics.sharpeRatio >= 1
              ? '⚠️ Good'
              : '❌ Poor'}
          </div>
        </Card>

        {/* Max Drawdown */}
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-2">
            <TrendingDown className="w-4 h-4 text-red-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Max Drawdown
            </span>
          </div>
          <div className="text-xl font-bold text-red-600">
            {metrics.maxDrawdownPercent.toFixed(2)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            ${metrics.maxDrawdown.toFixed(2)}
          </div>
        </Card>
      </div>

      {/* P&L Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
        {/* Total P&L */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Total P&L
            </span>
          </div>
          <div
            className={`text-2xl font-bold ${getPnLColor(metrics.totalPnL)}`}
          >
            {metrics.totalPnL >= 0 ? '+' : ''}${metrics.totalPnL.toFixed(2)}
          </div>
          <Badge
            variant={getBadgeVariant(metrics.totalPnLPercent)}
            size="sm"
            className="mt-2"
          >
            {metrics.totalPnLPercent.toFixed(2)}%
          </Badge>
        </Card>

        {/* Average Win/Loss */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Percent className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Avg Win / Loss
            </span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Avg Win:
              </span>
              <span className="text-sm font-bold text-green-600">
                +${metrics.avgWin.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Avg Loss:
              </span>
              <span className="text-sm font-bold text-red-600">
                ${metrics.avgLoss.toFixed(2)}
              </span>
            </div>
          </div>
        </Card>

        {/* Best/Worst Trade */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Best / Worst
            </span>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Best:
              </span>
              <span className="text-sm font-bold text-green-600">
                +${metrics.bestTrade.toFixed(2)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Worst:
              </span>
              <span className="text-sm font-bold text-red-600">
                ${metrics.worstTrade.toFixed(2)}
              </span>
            </div>
          </div>
        </Card>
      </div>

      {/* Additional Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card variant="elevated" className="p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Total Trades
          </span>
          <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
            {metrics.totalTrades}
          </div>
        </Card>

        <Card variant="elevated" className="p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Avg Duration
          </span>
          <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
            {metrics.avgTradeDuration}
          </div>
        </Card>

        <Card variant="elevated" className="p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Profitable Days
          </span>
          <div className="text-lg font-bold text-green-600 mt-1">
            18/22 days
          </div>
        </Card>

        <Card variant="elevated" className="p-3">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Consecutive Wins
          </span>
          <div className="text-lg font-bold text-green-600 mt-1">
            7 trades
          </div>
        </Card>
      </div>
    </div>
  );
}
