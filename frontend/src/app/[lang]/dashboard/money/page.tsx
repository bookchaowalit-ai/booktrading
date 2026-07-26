/**
 * Money Dashboard - Real-time PnL from all trading bots
 * Shows combined profits from arbitrage, grid, polymarket, and paper trading
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  DollarSign,
  TrendingUp,
  TrendingDown,
  Activity,
  Bot,
  RefreshCw,
  Wallet,
  BarChart3,
  Zap,
  Target,
  Trophy,
  AlertTriangle,
} from 'lucide-react';

interface BotPnL {
  name: string;
  type: 'paper' | 'real';
  status: string;
  total_trades: number;
  win_rate_pct: number;
  pnl_thb: number;
  capital_thb: number;
  last_activity: string;
}

interface PortfolioSummary {
  initial_balance: number;
  current_value: number;
  total_pnl: number;
  total_pnl_pct: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
}

interface MoneyDashboardData {
  timestamp: string;
  total_paper_pnl_thb: number;
  total_real_pnl_thb: number;
  grand_total_pnl_thb: number;
  bots: BotPnL[];
  paper_portfolio: PortfolioSummary | null;
  real_balances: { asset: string; free: number; total: number }[] | null;
}

function formatTHB(value: number): string {
  return new Intl.NumberFormat('th-TH', {
    style: 'currency',
    currency: 'THB',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function getStrategyBadge(name: string): { label: string; color: string } {
  if (name.startsWith('DCA')) return { label: 'DCA', color: 'bg-orange-900/50 text-orange-400' };
  if (name.startsWith('Trend')) return { label: 'TREND', color: 'bg-cyan-900/50 text-cyan-400' };
  if (name.startsWith('Futures')) return { label: 'FUTURES', color: 'bg-red-900/50 text-red-400' };
  if (name.startsWith('Grid')) return { label: 'GRID', color: 'bg-yellow-900/50 text-yellow-400' };
  if (name.includes('Arbitrage')) return { label: 'ARB', color: 'bg-green-900/50 text-green-400' };
  if (name.includes('Polymarket')) return { label: 'POLY', color: 'bg-pink-900/50 text-pink-400' };
  return { label: 'BOT', color: 'bg-gray-900/50 text-gray-400' };
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('en-US').format(value);
}

export default function MoneyDashboardPage() {
  const [data, setData] = useState<MoneyDashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  const fetchData = useCallback(async () => {
    try {
      setError(null);
      const res = await fetch('/api/dashboard/money');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const json = await res.json();
      setData(json);
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading && !data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="animate-pulse text-green-400 text-xl">Loading money dashboard...</div>
      </div>
    );
  }

  if (error && !data) {
    return (
      <div className="min-h-screen bg-gray-950 flex items-center justify-center">
        <div className="text-red-400 text-xl">Error: {error}</div>
      </div>
    );
  }

  const grandPnL = data?.grand_total_pnl_thb ?? 0;
  const isProfit = grandPnL >= 0;

  return (
    <div className="min-h-screen bg-gray-950 text-white p-4 md:p-8">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold flex items-center gap-3">
              <DollarSign className="text-green-400" size={32} />
              Money Dashboard
            </h1>
            <p className="text-gray-400 mt-1">
              Real-time PnL across all trading bots
              {lastRefresh && (
                <span className="ml-2 text-xs">
                  Updated: {lastRefresh.toLocaleTimeString()}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={fetchData}
            className="flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 rounded-lg transition-colors"
          >
            <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
            Refresh
          </button>
        </div>

        {/* Grand Total PnL */}
        <motion.div
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`rounded-2xl p-8 ${
            isProfit
              ? 'bg-gradient-to-br from-green-900/40 to-emerald-900/20 border border-green-700/50'
              : 'bg-gradient-to-br from-red-900/40 to-orange-900/20 border border-red-700/50'
          }`}
        >
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-400 text-sm uppercase tracking-wider mb-2">
                Grand Total PnL
              </p>
              <p className={`text-5xl font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                {isProfit ? '+' : ''}{formatTHB(grandPnL)}
              </p>
              <p className="text-gray-500 mt-2 text-sm">
                Paper: {formatTHB(data?.total_paper_pnl_thb ?? 0)} | Real: {formatTHB(data?.total_real_pnl_thb ?? 0)}
              </p>
            </div>
            <div className="text-right">
              {isProfit ? (
                <Trophy className="text-yellow-400" size={64} />
              ) : (
                <AlertTriangle className="text-red-400" size={64} />
              )}
            </div>
          </div>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Paper Trading Portfolio */}
          {data?.paper_portfolio && (
            <motion.div
              initial={{ y: 20, opacity: 0 }}
              animate={{ y: 0, opacity: 1 }}
              transition={{ delay: 0.1 }}
              className="bg-gray-900 border border-gray-800 rounded-xl p-6"
            >
              <div className="flex items-center gap-2 mb-4">
                <BarChart3 className="text-blue-400" size={20} />
                <h3 className="font-semibold text-gray-300">Paper Portfolio</h3>
              </div>
              <p className="text-2xl font-bold text-green-400">
                +{formatTHB(data.paper_portfolio.total_pnl)}
              </p>
              <p className="text-gray-500 text-sm mt-1">
                +{data.paper_portfolio.total_pnl_pct.toFixed(1)}% return
              </p>
              <div className="mt-4 space-y-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-gray-400">Initial</span>
                  <span>{formatTHB(data.paper_portfolio.initial_balance)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Current</span>
                  <span className="text-green-300">{formatTHB(data.paper_portfolio.current_value)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Trades</span>
                  <span>{formatNumber(data.paper_portfolio.total_trades)}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-400">Win Rate</span>
                  <span className="text-green-400">
                    {((data.paper_portfolio.win_trades / data.paper_portfolio.total_trades) * 100).toFixed(1)}%
                  </span>
                </div>
              </div>
            </motion.div>
          )}

          {/* Strategy Summary */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.2 }}
            className="bg-gray-900 border border-gray-800 rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <Bot className="text-purple-400" size={20} />
              <h3 className="font-semibold text-gray-300">Strategies</h3>
            </div>
            <p className="text-2xl font-bold text-white">
              {data?.bots.length ?? 0}
            </p>
            <p className="text-gray-500 text-sm mt-1">bots running</p>
            <div className="mt-4 space-y-3 text-sm">
              {(() => {
                const groups: Record<string, { count: number; pnl: number }> = {};
                data?.bots.forEach((bot) => {
                  const badge = getStrategyBadge(bot.name);
                  if (!groups[badge.label]) groups[badge.label] = { count: 0, pnl: 0 };
                  groups[badge.label].count++;
                  groups[badge.label].pnl += bot.pnl_thb;
                });
                return Object.entries(groups).map(([label, { count, pnl }]) => (
                  <div key={label} className="flex justify-between items-center">
                    <span className="text-gray-400 flex items-center gap-2">
                      <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${
                        label === 'DCA' ? 'bg-orange-900/50 text-orange-400' :
                        label === 'TREND' ? 'bg-cyan-900/50 text-cyan-400' :
                        label === 'ARB' ? 'bg-green-900/50 text-green-400' :
                        label === 'POLY' ? 'bg-pink-900/50 text-pink-400' :
                        'bg-gray-800 text-gray-400'
                      }`}>{label}</span>
                      ×{count}
                    </span>
                    <span className={pnl >= 0 ? 'text-green-400' : 'text-red-400'}>
                      {pnl >= 0 ? '+' : ''}{formatTHB(pnl)}
                    </span>
                  </div>
                ));
              })()}
            </div>
          </motion.div>

          {/* Real Account */}
          <motion.div
            initial={{ y: 20, opacity: 0 }}
            animate={{ y: 0, opacity: 1 }}
            transition={{ delay: 0.3 }}
            className="bg-gray-900 border border-gray-800 rounded-xl p-6"
          >
            <div className="flex items-center gap-2 mb-4">
              <Wallet className="text-yellow-400" size={20} />
              <h3 className="font-semibold text-gray-300">Real Account (Binance TH)</h3>
            </div>
            <p className="text-2xl font-bold text-yellow-400">
              {formatTHB(data?.total_real_pnl_thb ?? 0)}
            </p>
            <p className="text-gray-500 text-sm mt-1">real trading PnL</p>
            <div className="mt-4 space-y-2 text-sm">
              {data?.real_balances && data.real_balances.length > 0 ? (
                data.real_balances.map((bal) => (
                  <div key={bal.asset} className="flex justify-between">
                    <span className="text-gray-400">{bal.asset}</span>
                    <span>{bal.total.toFixed(6)}</span>
                  </div>
                ))
              ) : (
                <p className="text-gray-500 italic">Real orders just started — first fill incoming!</p>
              )}
            </div>
          </motion.div>
        </div>

        {/* Bot Details Table */}
        <motion.div
          initial={{ y: 20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ delay: 0.4 }}
          className="bg-gray-900 border border-gray-800 rounded-xl overflow-hidden"
        >
          <div className="p-6 border-b border-gray-800">
            <h3 className="text-lg font-semibold flex items-center gap-2">
              <Activity className="text-green-400" size={20} />
              Bot Performance Details
            </h3>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-800/50">
                <tr>
                  <th className="text-left p-4 text-gray-400 font-medium">Bot</th>
                  <th className="text-left p-4 text-gray-400 font-medium">Type</th>
                  <th className="text-left p-4 text-gray-400 font-medium">Status</th>
                  <th className="text-right p-4 text-gray-400 font-medium">Trades</th>
                  <th className="text-right p-4 text-gray-400 font-medium">Win Rate</th>
                  <th className="text-right p-4 text-gray-400 font-medium">PnL</th>
                  <th className="text-right p-4 text-gray-400 font-medium">Capital</th>
                </tr>
              </thead>
              <tbody>
                {data?.bots.map((bot, i) => (
                  <tr key={i} className="border-t border-gray-800/50 hover:bg-gray-800/30">
                    <td className="p-4 font-medium">
                      <div className="flex items-center gap-2">
                        <span className={`px-1.5 py-0.5 rounded text-[10px] font-bold ${getStrategyBadge(bot.name).color}`}>
                          {getStrategyBadge(bot.name).label}
                        </span>
                        {bot.name}
                      </div>
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-1 rounded text-xs ${
                        bot.type === 'real'
                          ? 'bg-green-900/50 text-green-400'
                          : 'bg-blue-900/50 text-blue-400'
                      }`}>
                        {bot.type}
                      </span>
                    </td>
                    <td className="p-4">
                      <span className={`flex items-center gap-1 ${
                        bot.status === 'running' ? 'text-green-400' : 'text-red-400'
                      }`}>
                        <span className={`w-2 h-2 rounded-full ${
                          bot.status === 'running' ? 'bg-green-400' : 'bg-red-400'
                        }`} />
                        {bot.status}
                      </span>
                    </td>
                    <td className="p-4 text-right">{formatNumber(bot.total_trades)}</td>
                    <td className="p-4 text-right">
                      {bot.win_rate_pct > 0 ? `${bot.win_rate_pct.toFixed(1)}%` : '—'}
                    </td>
                    <td className={`p-4 text-right font-bold ${
                      bot.pnl_thb >= 0 ? 'text-green-400' : 'text-red-400'
                    }`}>
                      {bot.pnl_thb >= 0 ? '+' : ''}{formatTHB(bot.pnl_thb)}
                    </td>
                    <td className="p-4 text-right text-gray-400">
                      {bot.capital_thb > 0 ? formatTHB(bot.capital_thb) : '—'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </motion.div>

        {/* Strategy Guide */}
        <div className="bg-blue-900/20 border border-blue-800/50 rounded-xl p-6">
          <div className="flex items-start gap-3">
            <Zap className="text-blue-400 flex-shrink-0 mt-1" size={20} />
            <div>
              <h4 className="font-semibold text-blue-300 mb-2">Multi-Strategy Bear-Market Ready</h4>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>• <strong className="text-green-400">Arbitrage (ARB)</strong> — cross-exchange spread harvesting, +{formatTHB(data?.bots.find(b => b.name.includes('Arbitrage'))?.pnl_thb ?? 0)} on paper</li>
                <li>• <strong className="text-orange-400">DCA</strong> — accumulate BTC/ETH on dips, smart buying at -3%/-7% levels, profit-taking on +10% spikes</li>
                <li>• <strong className="text-cyan-400">Trend Following</strong> — EMA crossover + ADX filter, rides trends in any market direction</li>
                <li>• <strong className="text-yellow-400">Grid</strong> — geometric grid on BTCTHB/ETHTHB for sideways markets</li>
                <li>• <strong className="text-pink-400">Polymarket</strong> — prediction market arbitrage (paper)</li>
                <li>• <strong className="text-blue-400">Paper Portfolio</strong> — turned 50K → {formatTHB(data?.paper_portfolio?.current_value ?? 0)} THB (+{data?.paper_portfolio?.total_pnl_pct?.toFixed(0) ?? 0}%)</li>
              </ul>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
