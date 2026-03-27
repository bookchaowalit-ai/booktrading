/**
 * Trading Management Page - Clean Version
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import ExchangeSelector from '@/components/ExchangeSelector';
import TradingViewChart from '@/components/TradingViewChart';
import PnLDashboard from '@/components/PnLDashboard';
import { Zap, Play, Square, DollarSign, Activity, Percent, TrendingUp } from 'lucide-react';

export default function TradingPage() {
  const { t } = useTranslation();
  const { success, error } = useToast();

  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [botStatus, setBotStatus] = useState<any>(null);
  const [stats, setStats] = useState({
    totalProfit: 0,
    totalTrades: 0,
    activeOrders: 0,
    profitRate: 0,
  });

  useEffect(() => {
    loadBotStatus();
    const interval = setInterval(loadBotStatus, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadBotStatus = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/bot/status');
      const data = await response.json().catch(() => null);
      if (data) {
        setBotStatus(data);
        setIsRunning(data.is_active);
        setStats({
          totalProfit: data.total_profit || 0,
          totalTrades: data.total_trades || 0,
          activeOrders: data.active_orders || 0,
          profitRate: data.total_trades > 0 ? ((data.total_profit / data.total_trades) * 100) : 0,
        });
      }
    } catch (err) {
      console.error('Failed to load bot status:', err);
    }
  };

  const handleStartBot = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/bot/start', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ symbol: 'BTCUSDT', quantity: 100 }),
      });
      if (response.ok) {
        success('Trading bot started');
        setIsRunning(true);
        loadBotStatus();
      } else {
        error('Failed to start bot');
      }
    } catch (err) {
      error('Failed to start bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopBot = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/bot/stop', { method: 'POST' });
      if (response.ok) {
        success('Trading bot stopped');
        setIsRunning(false);
        loadBotStatus();
      } else {
        error('Failed to stop bot');
      }
    } catch (err) {
      error('Failed to stop bot');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
            <Zap className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">Trading Management</h1>
            <p className="text-xs text-gray-600 dark:text-gray-400">Configure and control your trading</p>
          </div>
        </div>
        <Button
          variant={isRunning ? 'danger' : 'primary'}
          size="sm"
          onClick={isRunning ? handleStopBot : handleStartBot}
          isLoading={isLoading}
          leftIcon={isRunning ? <Square className="w-4 h-4" /> : <Play className="w-4 h-4" />}
        >
          {isRunning ? 'Stop Trading' : 'Start Trading'}
        </Button>
      </div>

      {/* Exchange Selector */}
      <ExchangeSelector onExchangeChange={(provider) => console.log('Switched to', provider)} />

      {/* Price Chart */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-semibold">Price Chart</h3>
          <select className="px-2 py-1 text-xs bg-white dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-md">
            <option value="BTCUSDT">BTC/USDT</option>
            <option value="ETHUSDT">ETH/USDT</option>
          </select>
        </div>
        <TradingViewChart symbol="BINANCE:BTCUSDT" interval="60" theme="dark" height={300} />
      </Card>

      {/* P&L Dashboard */}
      <Card variant="elevated" className="p-4">
        <h3 className="text-sm font-semibold mb-3">P&L Dashboard</h3>
        <PnLDashboard />
      </Card>

      {/* Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-green-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Total Profit</span>
          </div>
          <div className={`text-lg font-bold ${stats.totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {stats.totalProfit >= 0 ? '+' : ''}${stats.totalProfit.toFixed(2)}
          </div>
        </Card>

        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-blue-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Total Trades</span>
          </div>
          <div className="text-lg font-bold text-blue-600">{stats.totalTrades}</div>
        </Card>

        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <Percent className="w-4 h-4 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Profit Rate</span>
          </div>
          <div className="text-lg font-bold text-purple-600">{stats.profitRate.toFixed(1)}%</div>
        </Card>

        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-orange-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Active Orders</span>
          </div>
          <div className="text-lg font-bold text-orange-600">{stats.activeOrders}</div>
        </Card>
      </div>

      {/* Bot Control */}
      <Card variant="elevated" className="p-4">
        <h3 className="text-sm font-semibold mb-3">Bot Control</h3>
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm text-gray-600 dark:text-gray-400">Status</span>
            <div className="flex items-center gap-2">
              <div className={`w-2.5 h-2.5 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
              <span className="text-sm font-medium">{isRunning ? 'Running' : 'Stopped'}</span>
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">Total Profit</span>
              <div className={`text-lg font-bold ${stats.totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {stats.totalProfit >= 0 ? '+' : ''}${stats.totalProfit.toFixed(2)}
              </div>
            </div>
            <div>
              <span className="text-xs text-gray-600 dark:text-gray-400">Total Trades</span>
              <div className="text-lg font-bold text-blue-600">{stats.totalTrades}</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
