/**
 * Dashboard Analytics Page - Real API Only
 * Comprehensive analytics dashboard with real trading data
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  TrendingUp, TrendingDown, DollarSign, Percent, Activity,
  BarChart3, Target, AlertTriangle, CheckCircle2
} from 'lucide-react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import PortfolioPerformance from '@/components/PortfolioPerformance';
import { useTranslation } from '@/i18n/translations';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function AnalyticsPage() {
  const { t } = useTranslation();

  const [stats, setStats] = useState({
    totalTrades: 0,
    winRate: 0,
    avgWin: 0,
    avgLoss: 0,
    profitFactor: 0,
    sharpeRatio: 0,
    maxDrawdown: 0,
    totalProfit: 0,
  });
  const [loading, setLoading] = useState(true);
  const [hasData, setHasData] = useState(false);

  const loadAnalytics = useCallback(async () => {
    try {
      setLoading(true);

      // Fetch real performance data from backend
      const [performanceRes, tradesRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/api/performance`, { headers: authHeaders() }),
        fetch(`${API_BASE_URL}/api/trades?limit=1000`, { headers: authHeaders() }),
      ]);

      let totalTrades = 0;
      let winRate = 0;
      let avgWin = 0;
      let avgLoss = 0;
      let totalProfit = 0;

      if (tradesRes.status === 'fulfilled' && tradesRes.value.ok) {
        const trades = await tradesRes.value.json();
        if (Array.isArray(trades) && trades.length > 0) {
          setHasData(true);
          totalTrades = trades.length;

          const wins = trades.filter((t: any) => (t.pnl || t.profit || 0) > 0);
          const losses = trades.filter((t: any) => (t.pnl || t.profit || 0) <= 0);

          winRate = totalTrades > 0 ? (wins.length / totalTrades) * 100 : 0;
          avgWin = wins.length > 0 ? wins.reduce((sum: number, t: any) => sum + (t.pnl || t.profit || 0), 0) / wins.length : 0;
          avgLoss = losses.length > 0 ? losses.reduce((sum: number, t: any) => sum + (t.pnl || t.profit || 0), 0) / losses.length : 0;
          totalProfit = trades.reduce((sum: number, t: any) => sum + (t.pnl || t.profit || 0), 0);
        }
      }

      // If performance endpoint exists, use it for additional metrics
      if (performanceRes.status === 'fulfilled' && performanceRes.value.ok) {
        const perf = await performanceRes.value.json();
        setStats({
          totalTrades: perf.totalTrades || totalTrades,
          winRate: perf.winRate || winRate,
          avgWin: perf.avgWin || avgWin,
          avgLoss: perf.avgLoss || avgLoss,
          profitFactor: perf.profitFactor || (avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0),
          sharpeRatio: perf.sharpeRatio || 0,
          maxDrawdown: perf.maxDrawdown || 0,
          totalProfit: perf.totalProfit || totalProfit,
        });
      } else {
        // Calculate from trades data
        setStats({
          totalTrades,
          winRate,
          avgWin,
          avgLoss,
          profitFactor: avgLoss !== 0 ? Math.abs(avgWin / avgLoss) : 0,
          sharpeRatio: 0,
          maxDrawdown: 0,
          totalProfit,
        });
      }
    } catch {
      setStats({
        totalTrades: 0,
        winRate: 0,
        avgWin: 0,
        avgLoss: 0,
        profitFactor: 0,
        sharpeRatio: 0,
        maxDrawdown: 0,
        totalProfit: 0,
      });
      setHasData(false);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAnalytics();
  }, [loadAnalytics]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading analytics...</p>
        </div>
      </div>
    );
  }

  if (!hasData || stats.totalTrades === 0) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics Dashboard</h1>
            <p className="text-gray-500 dark:text-gray-400">Comprehensive trading analytics and insights</p>
          </div>
        </div>
        <EmptyState
          icon={<BarChart3 className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
          title="No Analytics Data Yet"
          description="Start trading to see analytics and performance metrics here"
          action={{ label: "Go to Trading", onClick: () => window.location.href = '/th/dashboard/trading' }}
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-purple-500/10 rounded-xl">
            <BarChart3 className="w-6 h-6 text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Analytics Dashboard</h1>
            <p className="text-gray-500 dark:text-gray-400">Comprehensive trading analytics and insights</p>
          </div>
        </div>
      </div>

      {/* Key Metrics Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5 text-blue-500" />
            <span className="text-sm text-gray-600 dark:text-gray-400">Total Trades</span>
          </div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white">{stats.totalTrades}</div>
          <div className="text-xs text-gray-500 mt-1">All time</div>
        </Card>

        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-green-500" />
            <span className="text-sm text-gray-600 dark:text-gray-400">Win Rate</span>
          </div>
          <div className={`text-2xl font-bold ${stats.winRate >= 50 ? 'text-green-600' : 'text-red-600'}`}>
            {stats.winRate.toFixed(1)}%
          </div>
          <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1.5 mt-2">
            <div
              className={`h-1.5 rounded-full ${stats.winRate >= 50 ? 'bg-green-500' : 'bg-red-500'}`}
              style={{ width: `${Math.min(stats.winRate, 100)}%` }}
            />
          </div>
        </Card>

        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <DollarSign className="w-5 h-5 text-purple-500" />
            <span className="text-sm text-gray-600 dark:text-gray-400">Profit Factor</span>
          </div>
          <div className={`text-2xl font-bold ${stats.profitFactor >= 1.5 ? 'text-green-600' : 'text-yellow-600'}`}>
            {stats.profitFactor.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {stats.profitFactor >= 1.5 ? '✅ Good' : '⚠️ Needs improvement'}
          </div>
        </Card>

        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-2 mb-2">
            <Percent className="w-5 h-5 text-blue-500" />
            <span className="text-sm text-gray-600 dark:text-gray-400">Sharpe Ratio</span>
          </div>
          <div className={`text-2xl font-bold ${stats.sharpeRatio >= 1 ? 'text-green-600' : 'text-yellow-600'}`}>
            {stats.sharpeRatio.toFixed(2)}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {stats.sharpeRatio >= 1.5 ? '🟢 Excellent' : stats.sharpeRatio >= 1 ? '🟡 Good' : '🔴 Poor'}
          </div>
        </Card>
      </div>

      {/* Portfolio Performance Chart */}
      <PortfolioPerformance />

      {/* Trading Statistics */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Trading Statistics</h3>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Average Win</span>
              <span className="text-sm font-bold text-green-600">+${stats.avgWin.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Average Loss</span>
              <span className="text-sm font-bold text-red-600">${stats.avgLoss.toFixed(2)}</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Max Drawdown</span>
              <span className="text-sm font-bold text-red-600">{stats.maxDrawdown.toFixed(2)}%</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-600 dark:text-gray-400">Total Profit</span>
              <span className={`text-sm font-bold ${stats.totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.totalProfit >= 0 ? '+' : ''}${stats.totalProfit.toFixed(2)}
              </span>
            </div>
          </div>
        </Card>

        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Performance Grade</h3>
          <div className="flex items-center justify-center mb-4">
            <div className="relative w-32 h-32">
              <svg className="w-32 h-32 transform -rotate-90" viewBox="0 0 36 36">
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke="#e5e7eb"
                  strokeWidth="3"
                  className="dark:stroke-gray-700"
                />
                <path
                  d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831"
                  fill="none"
                  stroke={stats.winRate >= 50 ? '#10b981' : '#ef4444'}
                  strokeWidth="3"
                  strokeDasharray={`${stats.winRate}, 100`}
                  strokeLinecap="round"
                />
              </svg>
              <div className="absolute inset-0 flex items-center justify-center">
                <span className="text-3xl font-bold text-gray-900 dark:text-white">
                  {stats.winRate >= 60 ? 'A' : stats.winRate >= 50 ? 'B' : stats.winRate >= 40 ? 'C' : 'D'}
                </span>
              </div>
            </div>
          </div>
          <div className="text-center">
            <Badge variant={stats.winRate >= 60 ? 'success' : stats.winRate >= 50 ? 'warning' : 'error'}>
              {stats.winRate >= 60 ? '🟢 Excellent Performance' : stats.winRate >= 50 ? '🟡 Good Performance' : '🔴 Needs Improvement'}
            </Badge>
          </div>
        </Card>
      </div>
    </div>
  );
}
