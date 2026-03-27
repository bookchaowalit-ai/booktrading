/**
 * Backtesting & Paper Trading Page
 * Test strategies historically and practice with virtual money
 */
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { 
  BarChart3, 
  TrendingUp, 
  Play, 
  Pause, 
  RotateCcw,
  Download,
  Calendar,
  DollarSign,
  Activity,
  Target,
  Shield
} from 'lucide-react';

export default function BacktestPage() {
  const { success, error, info } = useToast();
  const [isRunning, setIsRunning] = useState(false);
  const [mode, setMode] = useState<'backtest' | 'paper'>('backtest');
  const [config, setConfig] = useState({
    symbol: 'BTCUSDT',
    startDate: '2024-01-01',
    endDate: '2024-12-31',
    initialCapital: 10000,
    leverage: 3,
    strategy: 'moderate',
    commission: 0.001,
    slippage: 0.0005,
  });

  const [results, setResults] = useState<any>(null);

  const handleRunBacktest = async () => {
    setIsRunning(true);
    // Simulate backtest running
    setTimeout(() => {
      setResults({
        totalReturn: 2450,
        totalReturnPercent: 24.5,
        totalTrades: 45,
        winRate: 64.4,
        profitFactor: 2.1,
        maxDrawdown: 8.5,
        sharpeRatio: 1.8,
        sortinoRatio: 2.3,
        avgWin: 125,
        avgLoss: 65,
        bestTrade: 450,
        worstTrade: -180,
      });
      setIsRunning(false);
      success('Backtest completed successfully');
    }, 3000);
  };

  const handleStartPaperTrading = () => {
    success('Paper trading started with $10,000 virtual balance');
    setMode('paper');
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <BarChart3 className="w-8 h-8 text-purple-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Backtesting & Paper Trading
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Test strategies historically and practice risk-free
            </p>
          </div>
        </div>
      </div>

      {/* Mode Selector */}
      <div className="flex gap-4">
        <button
          onClick={() => setMode('backtest')}
          className={`flex-1 p-4 rounded-xl border-2 transition-all ${
            mode === 'backtest'
              ? 'border-purple-600 bg-purple-50 dark:bg-purple-900/20'
              : 'border-gray-200 dark:border-gray-700 hover:border-purple-300'
          }`}
        >
          <div className="flex items-center gap-3 mb-2">
            <Calendar className="w-6 h-6 text-purple-600" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Backtesting
            </h3>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Test your strategy on historical data to see how it would have performed
          </p>
        </button>

        <button
          onClick={() => setMode('paper')}
          className={`flex-1 p-4 rounded-xl border-2 transition-all ${
            mode === 'paper'
              ? 'border-green-600 bg-green-50 dark:bg-green-900/20'
              : 'border-gray-200 dark:border-gray-700 hover:border-green-300'
          }`}
        >
          <div className="flex items-center gap-3 mb-2">
            <DollarSign className="w-6 h-6 text-green-600" />
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              Paper Trading
            </h3>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Practice with virtual money in real-time market conditions
          </p>
        </button>
      </div>

      {mode === 'backtest' ? (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Configuration */}
          <Card variant="elevated" className="p-6">
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-6 flex items-center gap-2">
              <Target className="w-5 h-5 text-purple-600" />
              Backtest Configuration
            </h2>

            <div className="space-y-4">
              {/* Symbol */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Trading Pair
                </label>
                <select
                  value={config.symbol}
                  onChange={(e) => setConfig({ ...config, symbol: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  <option value="BTCUSDT">BTC/USDT</option>
                  <option value="ETHUSDT">ETH/USDT</option>
                  <option value="BTCTHB">BTC/THB</option>
                </select>
              </div>

              {/* Date Range */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    Start Date
                  </label>
                  <input
                    type="date"
                    value={config.startDate}
                    onChange={(e) => setConfig({ ...config, startDate: e.target.value })}
                    className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                    End Date
                  </label>
                  <input
                    type="date"
                    value={config.endDate}
                    onChange={(e) => setConfig({ ...config, endDate: e.target.value })}
                    className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                  />
                </div>
              </div>

              {/* Initial Capital */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Initial Capital (USDT)
                </label>
                <input
                  type="number"
                  value={config.initialCapital}
                  onChange={(e) => setConfig({ ...config, initialCapital: parseFloat(e.target.value) })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              {/* Leverage */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Leverage
                </label>
                <select
                  value={config.leverage}
                  onChange={(e) => setConfig({ ...config, leverage: parseInt(e.target.value) })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  <option value={1}>1x</option>
                  <option value={2}>2x</option>
                  <option value={3}>3x</option>
                  <option value={5}>5x</option>
                </select>
              </div>

              {/* Strategy */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Strategy
                </label>
                <select
                  value={config.strategy}
                  onChange={(e) => setConfig({ ...config, strategy: e.target.value })}
                  className="w-full px-4 py-2.5 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  <option value="conservative">Conservative</option>
                  <option value="moderate">Moderate</option>
                  <option value="aggressive">Aggressive</option>
                </select>
              </div>

              {/* Advanced Settings */}
              <div className="pt-4 border-t border-gray-200 dark:border-gray-700">
                <details className="text-sm">
                  <summary className="cursor-pointer text-gray-700 dark:text-gray-300 mb-3">
                    Advanced Settings
                  </summary>
                  <div className="space-y-3 mt-3">
                    <div>
                      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Commission Rate
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        value={config.commission}
                        onChange={(e) => setConfig({ ...config, commission: parseFloat(e.target.value) })}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-sm"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">
                        Slippage Rate
                      </label>
                      <input
                        type="number"
                        step="0.0001"
                        value={config.slippage}
                        onChange={(e) => setConfig({ ...config, slippage: parseFloat(e.target.value) })}
                        className="w-full px-3 py-2 bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded text-sm"
                      />
                    </div>
                  </div>
                </details>
              </div>

              {/* Run Button */}
              <Button
                fullWidth
                gradient
                onClick={handleRunBacktest}
                isLoading={isRunning}
                leftIcon={isRunning ? null : <Play className="w-4 h-4" />}
              >
                {isRunning ? 'Running Backtest...' : 'Run Backtest'}
              </Button>
            </div>
          </Card>

          {/* Results */}
          <div className="lg:col-span-2 space-y-6">
            {results ? (
              <>
                {/* Key Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                  <Card variant="elevated" className="p-4 text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Return</p>
                    <p className={`text-2xl font-bold ${results.totalReturn >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {results.totalReturn >= 0 ? '+' : ''}{results.totalReturnPercent.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      ${results.totalReturn.toLocaleString()}
                    </p>
                  </Card>

                  <Card variant="elevated" className="p-4 text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Win Rate</p>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {results.winRate.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      {results.totalTrades} trades
                    </p>
                  </Card>

                  <Card variant="elevated" className="p-4 text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Profit Factor</p>
                    <p className="text-2xl font-bold text-purple-600">
                      {results.profitFactor.toFixed(2)}
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Gross P/L Ratio
                    </p>
                  </Card>

                  <Card variant="elevated" className="p-4 text-center">
                    <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Max Drawdown</p>
                    <p className="text-2xl font-bold text-red-600">
                      {results.maxDrawdown.toFixed(1)}%
                    </p>
                    <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                      Largest peak decline
                    </p>
                  </Card>
                </div>

                {/* Detailed Metrics */}
                <Card variant="elevated" className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                    <Activity className="w-5 h-5 text-purple-600" />
                    Performance Metrics
                  </h3>

                  <div className="grid md:grid-cols-2 gap-6">
                    <div>
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Risk Metrics
                      </h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Sharpe Ratio</span>
                          <span className="font-medium text-gray-900 dark:text-white">{results.sharpeRatio.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Sortino Ratio</span>
                          <span className="font-medium text-gray-900 dark:text-white">{results.sortinoRatio.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Avg Win</span>
                          <span className="font-medium text-green-600">${results.avgWin.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Avg Loss</span>
                          <span className="font-medium text-red-600">${results.avgLoss.toFixed(2)}</span>
                        </div>
                      </div>
                    </div>

                    <div>
                      <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                        Trade Statistics
                      </h4>
                      <div className="space-y-2 text-sm">
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Best Trade</span>
                          <span className="font-medium text-green-600">+${results.bestTrade.toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Worst Trade</span>
                          <span className="font-medium text-red-600">-${Math.abs(results.worstTrade).toFixed(2)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Winning Trades</span>
                          <span className="font-medium text-gray-900 dark:text-white">{Math.round(results.totalTrades * results.winRate / 100)}</span>
                        </div>
                        <div className="flex justify-between">
                          <span className="text-gray-600 dark:text-gray-400">Losing Trades</span>
                          <span className="font-medium text-gray-900 dark:text-white">{results.totalTrades - Math.round(results.totalTrades * results.winRate / 100)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                </Card>

                {/* Actions */}
                <div className="flex gap-4">
                  <Button
                    variant="secondary"
                    leftIcon={<Download className="w-4 h-4" />}
                  >
                    Export Results
                  </Button>
                  <Button
                    variant="secondary"
                    onClick={() => setResults(null)}
                    leftIcon={<RotateCcw className="w-4 h-4" />}
                  >
                    New Backtest
                  </Button>
                </div>
              </>
            ) : (
              <Card variant="elevated" className="p-12 text-center">
                <BarChart3 className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
                  No Backtest Results Yet
                </h3>
                <p className="text-gray-600 dark:text-gray-400 mb-6">
                  Configure your backtest parameters and run a test to see performance metrics
                </p>
                <Button
                  gradient
                  onClick={handleRunBacktest}
                  leftIcon={<Play className="w-4 h-4" />}
                >
                  Run Your First Backtest
                </Button>
              </Card>
            )}
          </div>
        </div>
      ) : (
        /* Paper Trading View */
        <PaperTradingView onStart={handleStartPaperTrading} />
      )}
    </div>
  );
}

// Paper Trading Component
function PaperTradingView({ onStart }: { onStart: () => void }) {
  const { success } = useToast();
  const [isActive, setIsActive] = useState(false);

  const handleToggle = () => {
    if (!isActive) {
      onStart();
    }
    setIsActive(!isActive);
  };

  return (
    <Card variant="elevated" className="p-6">
      <div className="flex items-center justify-between mb-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-green-600" />
          Paper Trading Account
        </h2>
        <Button
          variant={isActive ? 'danger' : 'success'}
          onClick={handleToggle}
          leftIcon={isActive ? <Pause className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        >
          {isActive ? 'Stop Paper Trading' : 'Start Paper Trading'}
        </Button>
      </div>

      {!isActive ? (
        <div className="text-center py-12">
          <Shield className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
            Paper Trading is Inactive
          </h3>
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            Start paper trading to practice with $10,000 in virtual money
          </p>
          <Button
            gradient
            onClick={handleToggle}
            leftIcon={<Play className="w-4 h-4" />}
          >
            Start Paper Trading
          </Button>
        </div>
      ) : (
        <div className="space-y-6">
          <div className="grid md:grid-cols-3 gap-6">
            <div className="text-center p-4 bg-green-50 dark:bg-green-900/20 rounded-lg">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Virtual Balance</p>
              <p className="text-3xl font-bold text-green-600">$10,000.00</p>
            </div>
            <div className="text-center p-4 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Unrealized P&L</p>
              <p className="text-3xl font-bold text-blue-600">$0.00</p>
            </div>
            <div className="text-center p-4 bg-purple-50 dark:bg-purple-900/20 rounded-lg">
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">Total Trades</p>
              <p className="text-3xl font-bold text-purple-600">0</p>
            </div>
          </div>

          <div className="text-center py-8">
            <p className="text-gray-600 dark:text-gray-400">
              Paper trading is active. Execute trades from the Grid Trading or Sentiment pages.
            </p>
          </div>
        </div>
      )}
    </Card>
  );
}
