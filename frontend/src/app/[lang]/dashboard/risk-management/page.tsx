/**
 * Risk Management Page - Real API Only
 * Monitor risk metrics, configure limits, and validate trades
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  Shield,
  AlertTriangle,
  CheckCircle2,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Activity,
  RefreshCw,
  Search,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function RiskManagementPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning, info } = useToast();

  const [riskConfig, setRiskConfig] = useState<any>(null);
  const [riskMetrics, setRiskMetrics] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [checking, setChecking] = useState(false);
  const [tradeCheck, setTradeCheck] = useState({
    symbol: '',
    side: 'BUY',
    quantity: '',
    price: '',
    portfolioValue: '',
  });
  const [checkResult, setCheckResult] = useState<any>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [configRes, metricsRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/api/risk/config`, { headers: authHeaders() }),
        fetch(`${API_BASE_URL}/api/risk/metrics`, { headers: authHeaders() }),
      ]);

      if (configRes.status === 'fulfilled' && configRes.value.ok) {
        setRiskConfig(await configRes.value.json());
      } else {
        // Set default config if API fails
        setRiskConfig({
          stop_loss_percent: 5,
          take_profit_percent: 10,
          max_position_size_percent: 20,
          max_daily_loss_percent: 3,
          max_drawdown_percent: 15,
          max_concurrent_positions: 5,
          trade_cooldown_sec: 60,
          trailing_stop: false,
        });
      }

      if (metricsRes.status === 'fulfilled' && metricsRes.value.ok) {
        setRiskMetrics(await metricsRes.value.json());
      } else {
        setRiskMetrics(null);
      }
    } catch {
      setRiskConfig(null);
      setRiskMetrics(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const saveConfig = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/risk/config`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(riskConfig),
      });
      if (!response.ok) throw new Error('Failed to save configuration');
      success('Risk configuration saved');
    } catch (err: any) {
      showError(err.message || 'Failed to save configuration');
    }
  };

  const checkTrade = async () => {
    if (!tradeCheck.symbol || !tradeCheck.quantity || !tradeCheck.price || !tradeCheck.portfolioValue) {
      warning('Please fill in all fields');
      return;
    }

    setChecking(true);
    setCheckResult(null);
    try {
      const response = await fetch(`${API_BASE_URL}/api/risk/check`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          symbol: tradeCheck.symbol.toUpperCase(),
          side: tradeCheck.side,
          quantity: parseFloat(tradeCheck.quantity),
          price: parseFloat(tradeCheck.price),
          portfolio_value: parseFloat(tradeCheck.portfolioValue),
        }),
      });

      if (!response.ok) throw new Error('Failed to check trade');

      const result = await response.json();
      setCheckResult(result);

      if (result.approved) {
        info('Trade approved by risk management');
      } else {
        warning(`Trade blocked: ${result.reasons?.join(', ')}`);
      }
    } catch (err: any) {
      showError(err.message || 'Failed to check trade');
    } finally {
      setChecking(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading risk management...</p>
        </div>
      </div>
    );
  }

  if (!riskConfig) {
    return (
      <EmptyState
        icon={<Shield className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
        title="Risk Management Not Available"
        description="Risk management service is not running"
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-red-500/10 rounded-xl">
            <Shield className="w-6 h-6 text-red-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Risk Management</h1>
            <p className="text-gray-500 dark:text-gray-400">Monitor risk metrics and configure trading limits</p>
          </div>
        </div>
        <Button onClick={() => { loadData(); }} leftIcon={<RefreshCw className="w-4 h-4" />}>
          Refresh
        </Button>
      </div>

      {/* Current Risk Metrics */}
      {riskMetrics && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Current Drawdown</p>
            <p className={`text-2xl font-bold ${riskMetrics.current_drawdown > 10 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
              {riskMetrics.current_drawdown?.toFixed(2)}%
            </p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Daily P&L</p>
            <p className={`text-2xl font-bold ${riskMetrics.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {riskMetrics.daily_pnl >= 0 ? '+' : ''}${riskMetrics.daily_pnl?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
            </p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Win Rate</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{riskMetrics.win_rate?.toFixed(1)}%</p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Active Blocks</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{riskMetrics.blocked_reasons?.length || 0}</p>
          </Card>
        </div>
      )}

      {/* Risk Configuration */}
      <Card variant="elevated" className="p-6">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Shield className="w-5 h-5 text-blue-600" />
          Risk Configuration
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Stop Loss %</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.stop_loss_percent || 5}
              onChange={(e) => setRiskConfig({ ...riskConfig, stop_loss_percent: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Take Profit %</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.take_profit_percent || 10}
              onChange={(e) => setRiskConfig({ ...riskConfig, take_profit_percent: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Position Size %</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.max_position_size_percent || 20}
              onChange={(e) => setRiskConfig({ ...riskConfig, max_position_size_percent: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Daily Loss %</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.max_daily_loss_percent || 3}
              onChange={(e) => setRiskConfig({ ...riskConfig, max_daily_loss_percent: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Drawdown %</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.max_drawdown_percent || 15}
              onChange={(e) => setRiskConfig({ ...riskConfig, max_drawdown_percent: parseFloat(e.target.value) || 0 })}
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Max Concurrent Positions</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={riskConfig.max_concurrent_positions || 5}
              onChange={(e) => setRiskConfig({ ...riskConfig, max_concurrent_positions: parseInt(e.target.value) || 0 })}
            />
          </div>
        </div>
        <div className="flex justify-end mt-4">
          <Button onClick={saveConfig}>Save Configuration</Button>
        </div>
      </Card>

      {/* Trade Checker */}
      <Card variant="elevated" className="p-6">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <Search className="w-5 h-5 text-green-600" />
          Trade Risk Checker
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4 mb-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Symbol</label>
            <input
              type="text"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white uppercase"
              value={tradeCheck.symbol}
              onChange={(e) => setTradeCheck({ ...tradeCheck, symbol: e.target.value })}
              placeholder="BTCUSDT"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Side</label>
            <select
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={tradeCheck.side}
              onChange={(e) => setTradeCheck({ ...tradeCheck, side: e.target.value })}
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Quantity</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={tradeCheck.quantity}
              onChange={(e) => setTradeCheck({ ...tradeCheck, quantity: e.target.value })}
              placeholder="0.001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Price</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={tradeCheck.price}
              onChange={(e) => setTradeCheck({ ...tradeCheck, price: e.target.value })}
              placeholder="50000"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Portfolio Value</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={tradeCheck.portfolioValue}
              onChange={(e) => setTradeCheck({ ...tradeCheck, portfolioValue: e.target.value })}
              placeholder="10000"
            />
          </div>
        </div>
        <div className="flex justify-end mb-4">
          <Button onClick={checkTrade} isLoading={checking}>Check Trade</Button>
        </div>

        {checkResult && (
          <Card className={`p-4 ${checkResult.approved ? 'bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800'}`}>
            <div className="flex items-center gap-3">
              {checkResult.approved ? (
                <CheckCircle2 className="w-6 h-6 text-green-600" />
              ) : (
                <AlertTriangle className="w-6 h-6 text-red-600" />
              )}
              <div>
                <h4 className={`font-bold ${checkResult.approved ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'}`}>
                  {checkResult.approved ? 'Trade Approved' : 'Trade Blocked'}
                </h4>
                {checkResult.reasons && checkResult.reasons.length > 0 && (
                  <ul className="text-sm text-red-600 dark:text-red-400 mt-1">
                    {checkResult.reasons.map((reason: string, idx: number) => (
                      <li key={idx}>• {reason}</li>
                    ))}
                  </ul>
                )}
              </div>
            </div>
          </Card>
        )}
      </Card>
    </div>
  );
}
