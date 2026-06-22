/**
 * Backtest Dashboard Page
 * Grid trading strategy backtester with historical data
 */
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import {
  TestTube,
  Play,
  Settings,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  BarChart3,
  Calendar,
  Target,
  AlertTriangle,
  CheckCircle2,
  Clock,
} from 'lucide-react';
import { backtestService } from '@/services/backtest';
import type { BacktestConfig, BacktestResult } from '@/types/backtest';
import { DEFAULT_BACKTEST_CONFIG } from '@/types/backtest';
import Card from '@/components/ui/Card';

const INTERVALS = [
  { value: '1m', label: '1 Minute' },
  { value: '5m', label: '5 Minutes' },
  { value: '15m', label: '15 Minutes' },
  { value: '1h', label: '1 Hour' },
  { value: '4h', label: '4 Hours' },
  { value: '1d', label: '1 Day' },
];

const SYMBOLS = ['BTCTHB', 'ETHTHB'];

export default function BacktestPage() {
  const [config, setConfig] = useState<BacktestConfig>(DEFAULT_BACKTEST_CONFIG);
  const [result, setResult] = useState<BacktestResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleRunBacktest = async () => {
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const data = await backtestService.runBacktest(config);
      setResult(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  const updateConfig = (key: keyof BacktestConfig, value: any) => {
    setConfig(prev => ({ ...prev, [key]: value }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
            <TestTube className="w-6 h-6 text-indigo-600 dark:text-indigo-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Backtest Engine</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Simulate grid trading strategies on historical data
            </p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Configuration Panel */}
        <Card className="lg:col-span-1">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Settings className="w-5 h-5 text-gray-500" />
            Configuration
          </h3>

          <div className="space-y-4">
            {/* Symbol */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Symbol
              </label>
              <select
                value={config.symbol}
                onChange={(e) => updateConfig('symbol', e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                {SYMBOLS.map(sym => (
                  <option key={sym} value={sym}>{sym}</option>
                ))}
              </select>
            </div>

            {/* Days */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Backtest Period (Days)
              </label>
              <input
                type="number"
                value={config.days}
                onChange={(e) => updateConfig('days', parseInt(e.target.value) || 1)}
                min={1}
                max={365}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            {/* Interval */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Candle Interval
              </label>
              <select
                value={config.interval}
                onChange={(e) => updateConfig('interval', e.target.value)}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              >
                {INTERVALS.map(int => (
                  <option key={int.value} value={int.value}>{int.label}</option>
                ))}
              </select>
            </div>

            {/* Grid Spacing */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Grid Spacing (%)
              </label>
              <input
                type="number"
                value={config.grid_spacing_pct}
                onChange={(e) => updateConfig('grid_spacing_pct', parseFloat(e.target.value) || 0.1)}
                min={0.1}
                max={10}
                step={0.1}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            {/* Grid Levels */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Grid Levels (above/below)
              </label>
              <input
                type="number"
                value={config.grid_levels}
                onChange={(e) => updateConfig('grid_levels', parseInt(e.target.value) || 1)}
                min={1}
                max={10}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            {/* Order Size */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Order Size (base asset)
              </label>
              <input
                type="number"
                value={config.order_size}
                onChange={(e) => updateConfig('order_size', parseFloat(e.target.value) || 0.00001)}
                min={0.00001}
                step={0.00001}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            {/* Initial Capital */}
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                Initial Capital (THB)
              </label>
              <input
                type="number"
                value={config.initial_capital_thb}
                onChange={(e) => updateConfig('initial_capital_thb', parseFloat(e.target.value) || 1000)}
                min={1000}
                step={1000}
                className="w-full px-3 py-2 border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
              />
            </div>

            {/* Run Button */}
            <button
              onClick={handleRunBacktest}
              disabled={loading}
              className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-medium rounded-lg transition-colors"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  Running...
                </>
              ) : (
                <>
                  <Play className="w-5 h-5" />
                  Run Backtest
                </>
              )}
            </button>
          </div>
        </Card>

        {/* Results Panel */}
        <div className="lg:col-span-2 space-y-6">
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
              {error}
            </div>
          )}

          {!result && !loading && (
            <Card className="flex flex-col items-center justify-center py-16 text-center">
              <TestTube className="w-16 h-16 text-gray-300 dark:text-gray-600 mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">
                Ready to Backtest
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400 max-w-md">
                Configure your grid trading parameters and run a backtest to see how the strategy
                would have performed on historical data.
              </p>
            </Card>
          )}

          {loading && (
            <Card className="flex flex-col items-center justify-center py-16">
              <div className="w-12 h-12 border-4 border-indigo-600 border-t-transparent rounded-full animate-spin mb-4" />
              <p className="text-gray-600 dark:text-gray-400">Running backtest simulation...</p>
            </Card>
          )}

          {result && (
            <>
              {/* Summary Stats */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <StatCard
                  title="Net P&L"
                  value={formatPnl(result.net_pnl)}
                  icon={DollarSign}
                  color={result.net_pnl >= 0 ? 'green' : 'red'}
                />
                <StatCard
                  title="Win Rate"
                  value={`${result.win_rate.toFixed(1)}%`}
                  subtitle={`${result.winning_trades}W / ${result.losing_trades}L`}
                  icon={Target}
                  color={result.win_rate >= 50 ? 'green' : 'amber'}
                />
                <StatCard
                  title="Total Trades"
                  value={String(result.total_trades)}
                  subtitle={`${result.trades_per_day.toFixed(1)}/day`}
                  icon={Activity}
                  color="blue"
                />
                <StatCard
                  title="Max Drawdown"
                  value={`${result.max_drawdown_pct.toFixed(2)}%`}
                  subtitle={`฿${result.max_drawdown.toFixed(2)}`}
                  icon={TrendingDown}
                  color={result.max_drawdown_pct > 5 ? 'red' : 'amber'}
                />
              </div>

              {/* Performance Details */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <Card>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <BarChart3 className="w-5 h-5 text-emerald-500" />
                    Performance
                  </h3>
                  <div className="space-y-3">
                    <DetailRow label="Gross P&L" value={formatPnl(result.total_pnl)} />
                    <DetailRow label="Total Fees" value={`฿${result.total_fees.toFixed(2)}`} />
                    <DetailRow label="Net P&L" value={formatPnl(result.net_pnl)} highlight={result.net_pnl >= 0} />
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-3" />
                    <DetailRow label="Avg Win" value={formatPnl(result.avg_win)} />
                    <DetailRow label="Avg Loss" value={formatPnl(result.avg_loss)} />
                    <DetailRow label="Profit Factor" value={result.profit_factor.toFixed(2)} />
                  </div>
                </Card>

                <Card>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-blue-500" />
                    Backtest Info
                  </h3>
                  <div className="space-y-3">
                    <DetailRow label="Symbol" value={result.symbol} />
                    <DetailRow label="Duration" value={`${result.duration_days.toFixed(1)} days`} />
                    <DetailRow label="Start" value={formatDate(result.start_time)} />
                    <DetailRow label="End" value={formatDate(result.end_time)} />
                    <div className="border-t border-gray-200 dark:border-gray-700 pt-3" />
                    <DetailRow label="Grid Spacing" value={`${result.avg_grid_spacing_pct}%`} />
                    <DetailRow label="Trades/Day" value={result.trades_per_day.toFixed(2)} />
                    <DetailRow label="Capital" value={`฿${(result.config.initial_capital_thb as number)?.toLocaleString() || '—'}`} />
                  </div>
                </Card>
              </div>

              {/* Trade History */}
              {result.trades.length > 0 && (
                <Card>
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <Activity className="w-5 h-5 text-purple-500" />
                    Recent Trades ({result.trades.length})
                  </h3>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead>
                        <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                          <th className="pb-2 font-medium">Time</th>
                          <th className="pb-2 font-medium">Side</th>
                          <th className="pb-2 font-medium">Price</th>
                          <th className="pb-2 font-medium">Qty</th>
                          <th className="pb-2 font-medium">P&L</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {result.trades.slice(-20).reverse().map((trade, i) => (
                          <tr key={i} className="text-gray-900 dark:text-gray-100">
                            <td className="py-2 text-xs text-gray-500">{formatDate(trade.timestamp)}</td>
                            <td className="py-2">
                              <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                                trade.side === 'BUY'
                                  ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                  : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                              }`}>
                                {trade.side === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                                {trade.side}
                              </span>
                            </td>
                            <td className="py-2 font-mono">{formatPrice(trade.price)}</td>
                            <td className="py-2 font-mono">{trade.quantity.toFixed(6)}</td>
                            <td className={`py-2 font-mono ${trade.pnl > 0 ? 'text-green-600' : trade.pnl < 0 ? 'text-red-600' : 'text-gray-500'}`}>
                              {trade.pnl !== 0 ? formatPnl(trade.pnl) : '-'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string;
  value: string;
  subtitle?: string;
  icon: any;
  color: 'green' | 'red' | 'blue' | 'amber';
}) {
  const colors = {
    green: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    amber: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">{title}</span>
          <div className={`p-1.5 rounded-lg ${colors[color]}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
        {subtitle && (
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{subtitle}</div>
        )}
      </Card>
    </motion.div>
  );
}

function DetailRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`text-sm font-medium ${highlight ? 'text-green-600 dark:text-green-400' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </span>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}฿${value.toFixed(2)}`;
}

function formatPrice(price: number): string {
  if (price >= 1000) return `฿${Math.round(price).toLocaleString()}`;
  return `฿${price.toFixed(2)}`;
}

function formatDate(timestamp: number): string {
  if (!timestamp) return '-';
  try {
    const d = new Date(timestamp);
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return String(timestamp);
  }
}
