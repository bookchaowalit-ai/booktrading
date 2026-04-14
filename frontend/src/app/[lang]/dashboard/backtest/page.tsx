/**
 * Backtesting Page - Real API Only
 * Test strategies on historical data
 */
'use client';

import { useState } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  TestTube,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Activity,
  BarChart3,
  Loader2,
} from 'lucide-react';

const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function BacktestPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning } = useToast();

  const [config, setConfig] = useState({
    symbol: 'BTCUSDT',
    start_date: '2024-01-01',
    end_date: '2024-12-31',
    initial_capital: 10000,
    strategy: 'rsi',
    commission: 0.001,
    slippage: 0.0005,
  });

  const [result, setResult] = useState<any>(null);
  const [loading, setLoading] = useState(false);

  const runBacktest = async () => {
    if (!config.symbol || !config.start_date || !config.end_date) {
      warning('Please fill in all required fields');
      return;
    }

    setLoading(true);
    setResult(null);

    try {
      const response = await fetch(`${STRATEGY_URL}/api/backtest`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(config),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Backtest failed' }));
        throw new Error(err.error || 'Backtest failed');
      }

      const data = await response.json();
      setResult(data);
      success('Backtest complete');
    } catch (err: any) {
      showError(err.message || 'Backtest failed');
    } finally {
      setLoading(false);
    }
  };

  if (!result) {
    return (
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-purple-500/10 rounded-xl">
              <TestTube className="w-6 h-6 text-purple-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Strategy Backtesting</h1>
              <p className="text-gray-500 dark:text-gray-400">Test your trading strategy on historical data</p>
            </div>
          </div>
        </div>

        {/* Configuration Form */}
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Configuration</h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Symbol</label>
              <select
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.symbol}
                onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
              >
                <option value="BTCUSDT">BTCUSDT</option>
                <option value="ETHUSDT">ETHUSDT</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Start Date</label>
              <input
                type="date"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.start_date}
                onChange={(e) => setConfig({ ...config, start_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">End Date</label>
              <input
                type="date"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.end_date}
                onChange={(e) => setConfig({ ...config, end_date: e.target.value })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Initial Capital</label>
              <input
                type="number"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.initial_capital}
                onChange={(e) => setConfig({ ...config, initial_capital: parseFloat(e.target.value) || 0 })}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Strategy</label>
              <select
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.strategy}
                onChange={(e) => setConfig({ ...config, strategy: e.target.value })}
              >
                <option value="rsi">RSI</option>
                <option value="ema_cross">EMA Cross</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Commission %</label>
              <input
                type="number"
                step="0.0001"
                className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                value={config.commission}
                onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) || 0 })}
              />
            </div>
          </div>
          <div className="flex justify-end mt-6">
            <Button onClick={runBacktest} isLoading={loading} leftIcon={<TestTube className="w-4 h-4" />}>
              Run Backtest
            </Button>
          </div>
        </Card>

        {/* Empty State */}
        <EmptyState
          icon={<TestTube className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
          title="No Backtest Results Yet"
          description="Configure your strategy parameters and run a backtest to see results"
        />
      </div>
    );
  }

  // Show Results
  const totalReturn = result.total_return_percent || 0;
  const winRate = result.win_rate || 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Backtest Results</h1>
          <p className="text-gray-500 dark:text-gray-400">{config.symbol} | {config.start_date} to {config.end_date}</p>
        </div>
        <Button onClick={() => setResult(null)} variant="ghost">
          New Backtest
        </Button>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Return</p>
          <p className={`text-2xl font-bold ${totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalReturn >= 0 ? '+' : ''}{totalReturn.toFixed(2)}%
          </p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Final Capital</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            ${result.final_capital?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Max Drawdown</p>
          <p className="text-2xl font-bold text-red-600">{result.max_drawdown?.toFixed(2)}%</p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Sharpe Ratio</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{result.sharpe_ratio?.toFixed(2)}</p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Win Rate</p>
          <p className={`text-2xl font-bold ${winRate >= 50 ? 'text-green-600' : 'text-red-600'}`}>{winRate.toFixed(1)}%</p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Trades</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{result.total_trades || 0}</p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Profit Factor</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{result.profit_factor?.toFixed(2)}</p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Sortino Ratio</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{result.sortino_ratio?.toFixed(2)}</p>
        </Card>
      </div>

      {/* Trades Table */}
      {result.trades && result.trades.length > 0 && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-600" />
            Trade Log ({result.trades.length} trades)
          </h3>
          <div className="overflow-x-auto max-h-96 overflow-y-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-gray-50 dark:bg-gray-800">
                <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                  <th className="text-left py-2 px-3 font-medium">Symbol</th>
                  <th className="text-center py-2 px-3 font-medium">Side</th>
                  <th className="text-right py-2 px-3 font-medium">Entry</th>
                  <th className="text-right py-2 px-3 font-medium">Exit</th>
                  <th className="text-right py-2 px-3 font-medium">P&L</th>
                  <th className="text-center py-2 px-3 font-medium">Duration</th>
                </tr>
              </thead>
              <tbody>
                {result.trades.map((trade: any, idx: number) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 px-3 font-medium text-gray-900 dark:text-white">{trade.symbol}</td>
                    <td className="py-2 px-3 text-center">
                      <Badge variant={trade.side === 'BUY' ? 'success' : 'error'} size="sm">{trade.side}</Badge>
                    </td>
                    <td className="py-2 px-3 text-right text-gray-700 dark:text-gray-300">${trade.entry_price?.toLocaleString()}</td>
                    <td className="py-2 px-3 text-right text-gray-700 dark:text-gray-300">${trade.exit_price?.toLocaleString()}</td>
                    <td className={`py-2 px-3 text-right font-bold ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {trade.pnl >= 0 ? '+' : ''}{trade.pnl?.toFixed(2)}
                    </td>
                    <td className="py-2 px-3 text-center text-gray-500">{trade.duration || '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}
    </div>
  );
}
