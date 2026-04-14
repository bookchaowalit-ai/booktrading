/**
 * Strategy Page - Real API Only
 * View and configure trading strategies
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import { Bot, TrendingUp, TrendingDown, Target, BarChart3, RefreshCw, DollarSign } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function StrategyPage() {
  const { t } = useTranslation();
  const { success, error: showError } = useToast();

  const [signals, setSignals] = useState<any[]>([]);
  const [config, setConfig] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [signalsRes, configRes] = await Promise.allSettled([
        fetch(`${STRATEGY_URL}/api/signals`, { headers: authHeaders() }),
        fetch(`${STRATEGY_URL}/api/strategy/config`, { headers: authHeaders() }),
      ]);

      if (signalsRes.status === 'fulfilled' && signalsRes.value.ok) {
        const data = await signalsRes.value.json();
        setSignals(data.signals || []);
      } else {
        setSignals([]);
      }

      if (configRes.status === 'fulfilled' && configRes.value.ok) {
        const data = await configRes.value.json();
        setConfig(data);
      } else {
        setConfig({
          rsi_period: 14,
          ema_period: 14,
          rsi_oversold: 30,
          rsi_overbought: 70,
          min_signal_strength: 0.5,
        });
      }
    } catch {
      setSignals([]);
      setConfig(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const saveConfig = async () => {
    try {
      const response = await fetch(`${STRATEGY_URL}/api/strategy/config`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to save configuration');
      success('Strategy configuration saved');
    } catch (err: any) {
      showError(err.message || 'Failed to save configuration');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading strategies...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-green-500/10 rounded-xl">
            <Bot className="w-6 h-6 text-green-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Strategy</h1>
            <p className="text-gray-500 dark:text-gray-400">Configure trading strategy and view signals</p>
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={loadData} leftIcon={<RefreshCw className="w-4 h-4" />}>Refresh</Button>
          <Button onClick={saveConfig}>Save Config</Button>
        </div>
      </div>

      {/* Strategy Configuration */}
      {config && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-600" />
            Strategy Configuration
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">RSI Period</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={config.rsi_period || 14} onChange={(e) => setConfig({ ...config, rsi_period: parseInt(e.target.value) || 14 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">EMA Period</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={config.ema_period || 14} onChange={(e) => setConfig({ ...config, ema_period: parseInt(e.target.value) || 14 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">RSI Oversold</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={config.rsi_oversold || 30} onChange={(e) => setConfig({ ...config, rsi_oversold: parseFloat(e.target.value) || 30 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">RSI Overbought</label>
              <input type="number" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={config.rsi_overbought || 70} onChange={(e) => setConfig({ ...config, rsi_overbought: parseFloat(e.target.value) || 70 })} />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Min Signal Strength</label>
              <input type="number" step="0.1" className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white" value={config.min_signal_strength || 0.5} onChange={(e) => setConfig({ ...config, min_signal_strength: parseFloat(e.target.value) || 0.5 })} />
            </div>
          </div>
        </Card>
      )}

      {/* Active Signals */}
      {signals.length > 0 ? (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-purple-600" />
            Active Trading Signals
          </h3>
          <div className="space-y-3">
            {signals.map((signal, idx) => (
              <div key={idx} className="flex items-center justify-between p-4 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                <div className="flex items-center gap-3">
                  {signal.side === 'BUY' ? <TrendingUp className="w-5 h-5 text-green-600" /> : <TrendingDown className="w-5 h-5 text-red-600" />}
                  <div>
                    <p className="font-bold text-gray-900 dark:text-white">{signal.symbol}</p>
                    <p className="text-sm text-gray-500">{signal.reason}</p>
                  </div>
                </div>
                <div className="text-right">
                  <Badge variant={signal.side === 'BUY' ? 'success' : 'error'} size="sm">{signal.side}</Badge>
                  <p className="text-sm text-gray-500 mt-1">Strength: {(signal.strength * 100).toFixed(0)}%</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <EmptyState icon={<Bot className="w-16 h-16 text-gray-300 dark:text-gray-600" />} title="No Active Signals" description="Trading signals will appear when market conditions trigger them" />
      )}
    </div>
  );
}
