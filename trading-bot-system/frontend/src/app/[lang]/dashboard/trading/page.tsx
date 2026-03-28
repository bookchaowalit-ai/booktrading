/**
 * Trading Management Page - Clean Version
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Tabs } from '@/components/ui';
import ExchangeSelector from '@/components/ExchangeSelector';
import TradingViewChart from '@/components/TradingViewChart';
import PnLDashboard from '@/components/PnLDashboard';
import { Zap, LayoutDashboard, Settings, Shield, Activity } from 'lucide-react';

export default function TradingPage() {
  const { t } = useTranslation();
  const { success, error } = useToast();

  const [activeTab, setActiveTab] = useState<'overview' | 'config' | 'risk' | 'orders'>('overview');
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
    <div className="h-full flex flex-col gap-2">
      {/* Top Bar - Bot Control */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
            <Zap className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h1 className="text-base font-bold">Trading</h1>
            <p className="text-xs text-gray-500">Multi-exchange grid trading</p>
          </div>
        </div>
        <Button
          variant={isRunning ? 'danger' : 'primary'}
          size="sm"
          onClick={isRunning ? handleStopBot : handleStartBot}
          isLoading={isLoading}
        >
          {isRunning ? '⏹ Stop' : '▶ Start'}
        </Button>
      </div>

      {/* Tab Navigation */}
      <Tabs
        tabs={[
          { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
          { id: 'config', label: 'Grid Config', icon: <Settings className="w-3.5 h-3.5" /> },
          { id: 'risk', label: 'Risk Mgmt', icon: <Shield className="w-3.5 h-3.5" /> },
          { id: 'orders', label: 'Orders', icon: <Activity className="w-3.5 h-3.5" /> },
        ]}
        activeTab={activeTab}
        onChange={(tab) => setActiveTab(tab as typeof activeTab)}
        size="sm"
      />

      {/* Tab Content - Scrollable within fixed area */}
      <div className="flex-1 overflow-auto">
        {activeTab === 'overview' && (
          <div className="grid grid-cols-12 gap-2 h-full">
            {/* Left - Full Height Chart (8 cols = 66%) */}
            <div className="col-span-12 lg:col-span-8 h-full">
              <Card variant="elevated" className="p-2 h-full">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className="text-xs font-semibold">BTC/USDT</span>
                    <span className="text-xs text-green-600">+2.5%</span>
                  </div>
                  <div className="flex gap-1">
                    {['1m', '5m', '15m', '1h', '4h', '1d'].map((tf) => (
                      <button key={tf} className="px-2 py-0.5 text-xs hover:bg-gray-100 dark:hover:bg-gray-700 rounded">
                        {tf}
                      </button>
                    ))}
                  </div>
                </div>
                <TradingViewChart symbol="BINANCE:BTCUSDT" interval="60" theme="dark" height={520} />
              </Card>
            </div>

            {/* Right - All Metrics Stacked (4 cols = 33%) */}
            <div className="col-span-12 lg:col-span-4 flex flex-col gap-2 h-full overflow-auto">
              {/* Bot Status */}
              <Card variant="elevated" className="p-2 shrink-0">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <div className={`w-2 h-2 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
                    <span className="text-xs font-semibold">{isRunning ? 'Running' : 'Stopped'}</span>
                  </div>
                  <Button variant={isRunning ? 'danger' : 'primary'} size="sm" onClick={() => { }}>
                    {isRunning ? '⏹' : '▶'}
                  </Button>
                </div>
              </Card>

              {/* Key Metrics */}
              <div className="grid grid-cols-2 gap-2 shrink-0">
                <Card variant="elevated" className="p-2">
                  <span className="text-xs text-gray-500">Profit</span>
                  <div className={`text-sm font-bold ${stats.totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    ${stats.totalProfit.toFixed(2)}
                  </div>
                </Card>
                <Card variant="elevated" className="p-2">
                  <span className="text-xs text-gray-500">Trades</span>
                  <div className="text-sm font-bold text-blue-600">{stats.totalTrades}</div>
                </Card>
                <Card variant="elevated" className="p-2">
                  <span className="text-xs text-gray-500">Rate</span>
                  <div className="text-sm font-bold text-purple-600">{stats.profitRate.toFixed(1)}%</div>
                </Card>
                <Card variant="elevated" className="p-2">
                  <span className="text-xs text-gray-500">Orders</span>
                  <div className="text-sm font-bold text-orange-600">{stats.activeOrders}</div>
                </Card>
              </div>

              {/* P&L Dashboard */}
              <Card variant="elevated" className="p-2 flex-1">
                <PnLDashboard />
              </Card>

              {/* Exchange */}
              <Card variant="elevated" className="p-2 shrink-0">
                <span className="text-xs font-semibold mb-2 block">Exchange</span>
                <ExchangeSelector compact />
              </Card>
            </div>
          </div>
        )}

        {activeTab === 'config' && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <Settings className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Grid Configuration</p>
              <p className="text-xs mt-1">Configure your grid trading parameters</p>
            </div>
          </div>
        )}

        {activeTab === 'risk' && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <Shield className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Risk Management</p>
              <p className="text-xs mt-1">Stop-loss, take-profit, position sizing</p>
            </div>
          </div>
        )}

        {activeTab === 'orders' && (
          <div className="h-full flex items-center justify-center">
            <div className="text-center text-gray-500">
              <Activity className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p className="text-sm">Order Tracking</p>
              <p className="text-xs mt-1">Real-time order monitoring</p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
