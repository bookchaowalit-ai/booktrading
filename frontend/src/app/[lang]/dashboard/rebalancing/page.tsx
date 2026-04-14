/**
 * Portfolio Rebalancing Page
 * Set allocation targets, analyze deviations, and execute rebalance trades
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  Scale,
  Plus,
  X,
  RefreshCw,
  Play,
  AlertTriangle,
  CheckCircle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  ArrowRight,
} from 'lucide-react';

// Simple inline chart component (avoid recharts dependency issues)
function SimpleBarChart({ data }: { data: { symbol: string; current: number; target: number }[] }) {
  if (!data || data.length === 0) return null;

  const maxVal = Math.max(...data.map(d => Math.max(d.current, d.target)), 1);

  return (
    <div className="space-y-3">
      {data.map((item, idx) => (
        <div key={idx} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium text-gray-900 dark:text-white">{item.symbol}</span>
            <span className="text-xs text-gray-500">
              {item.current.toFixed(1)}% / {item.target.toFixed(1)}%
            </span>
          </div>
          <div className="flex gap-1 h-4">
            <div
              className="bg-blue-500 rounded-l transition-all"
              style={{ width: `${(item.current / maxVal) * 100}%` }}
            />
            <div
              className="bg-green-500 rounded-r transition-all"
              style={{ width: `${(item.target / maxVal) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
}

interface RebalanceTarget {
  symbol: string;
  target_percent: number;
}

interface RebalancePlan {
  total_value: number;
  current_alloc: Array<{
    symbol: string;
    current_value: number;
    current_percent: number;
    target_percent: number;
    deviation: number;
    action_needed: string;
  }>;
  required_trades: Array<{
    symbol: string;
    action: string;
    quantity: number;
    value: number;
    current_percent: number;
    target_percent: number;
  }>;
  estimated_fees: number;
  threshold_breached: boolean;
}

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function RebalancingPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning, info } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname?.split('/')[1] || 'th';

  const [targets, setTargets] = useState<RebalanceTarget[]>([]);
  const [plan, setPlan] = useState<RebalancePlan | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [hasError, setHasError] = useState(false);

  const loadTargets = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/rebalance/targets`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        // No targets configured yet is OK
        setTargets([]);
        return;
      }
      const data = await response.json();
      setTargets(Array.isArray(data) ? data : []);
    } catch {
      setTargets([]);
    }
  }, []);

  const loadHistory = useCallback(async () => {
    // Optional - not critical
    try {
      await fetch(`${API_BASE_URL}/api/rebalance/history?limit=20`, {
        headers: authHeaders(),
      });
    } catch {
      // Ignore errors for history
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    const init = async () => {
      try {
        await Promise.all([loadTargets(), loadHistory()]);
        if (mounted) setLoading(false);
      } catch {
        if (mounted) {
          setHasError(true);
          setLoading(false);
        }
      }
    };
    init();
    return () => { mounted = false; };
  }, [loadTargets, loadHistory]);

  const handleAnalyze = async () => {
    if (targets.length === 0) {
      warning('Please set allocation targets first');
      return;
    }
    setAnalyzing(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/rebalance/analyze`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        throw new Error('Failed to analyze portfolio');
      }
      const result = await response.json();
      setPlan(result);
      if (!result.required_trades || result.required_trades.length === 0) {
        info('Portfolio is already aligned with targets');
      } else {
        success(`Analysis complete: ${result.required_trades.length} trades needed`);
      }
    } catch (e: any) {
      showError(e.message || 'Failed to analyze portfolio');
    } finally {
      setAnalyzing(false);
    }
  };

  const handleExecute = async () => {
    setExecuting(true);
    try {
      const response = await fetch(
        `${API_BASE_URL}/api/rebalance/execute?triggered_by=manual`,
        {
          method: 'POST',
          headers: authHeaders(),
        }
      );
      if (!response.ok) {
        throw new Error('Failed to execute rebalance');
      }
      const result = await response.json();
      success(`Rebalance executed: ${result.trades_executed} trades, fees $${result.total_fees?.toFixed(2) || '0.00'}`);
      setPlan(null);
      loadTargets();
    } catch (e: any) {
      showError(e.message || 'Failed to execute rebalance');
    } finally {
      setExecuting(false);
    }
  };

  const totalTarget = targets.reduce((sum, t) => sum + (t.target_percent || 0), 0);
  const targetSumValid = Math.abs(totalTarget - 100) < 0.01;

  if (hasError) {
    return (
      <div className="min-h-[60vh] flex items-center justify-center">
        <EmptyState
          icon={<AlertTriangle className="w-16 h-16 text-red-400" />}
          title="Failed to load rebalancing"
          description="Please try again later or contact support"
        />
        <Button
          variant="primary"
          className="mt-4"
          onClick={() => router.push(`/${locale}/dashboard`)}
        >
          Go to Dashboard
        </Button>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading rebalancing...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/10 rounded-xl">
            <Scale className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Portfolio Rebalancing</h1>
            <p className="text-gray-500 dark:text-gray-400 text-sm">Maintain your target allocation across assets</p>
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={() => { setLoading(true); loadTargets().then(() => setLoading(false)); }}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Refresh
        </Button>
      </div>

      {/* Current vs Target Chart */}
      {plan && plan.current_alloc && plan.current_alloc.length > 0 && (
        <Card variant="elevated" className="p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5 text-blue-400" />
            Current vs Target Allocation
          </h2>
          <SimpleBarChart
            data={plan.current_alloc.map(a => ({
              symbol: a.symbol,
              current: a.current_percent,
              target: a.target_percent,
            }))}
          />
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-6 pt-4 border-t border-gray-200 dark:border-gray-700">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total Value</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-1">
                <DollarSign className="w-4 h-4 text-green-400" />
                ${(plan.total_value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Required Trades</p>
              <p className="text-lg font-bold text-gray-900 dark:text-white">
                {(plan.required_trades || []).length}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Estimated Fees</p>
              <p className="text-lg font-bold text-yellow-400">${(plan.estimated_fees || 0).toFixed(2)}</p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Threshold</p>
              <p className={`text-lg font-bold flex items-center gap-1 ${plan.threshold_breached ? 'text-red-400' : 'text-green-400'}`}>
                {plan.threshold_breached ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle className="w-4 h-4" />}
                {plan.threshold_breached ? 'Breached' : 'OK'}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Required Trades Table */}
      {plan && plan.required_trades && plan.required_trades.length > 0 && (
        <Card variant="elevated" className="p-6">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Required Trades</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                  <th className="text-left py-3 px-4 font-medium">Symbol</th>
                  <th className="text-center py-3 px-4 font-medium">Action</th>
                  <th className="text-right py-3 px-4 font-medium">Value</th>
                  <th className="text-right py-3 px-4 font-medium">Current %</th>
                  <th className="text-right py-3 px-4 font-medium">Target %</th>
                </tr>
              </thead>
              <tbody>
                {plan.required_trades.map((trade, idx) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors">
                    <td className="py-3 px-4 font-medium text-gray-900 dark:text-white">{trade.symbol}</td>
                    <td className="py-3 px-4 text-center">
                      <Badge variant={trade.action === 'SELL' ? 'error' : 'success'} size="sm">
                        {trade.action === 'SELL' ? (
                          <TrendingDown className="w-3 h-3 mr-1" />
                        ) : (
                          <TrendingUp className="w-3 h-3 mr-1" />
                        )}
                        {trade.action}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-right text-gray-700 dark:text-gray-300">
                      ${(trade.value || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-4 text-right text-gray-500">{(trade.current_percent || 0).toFixed(1)}%</td>
                    <td className="py-3 px-4 text-right text-gray-500">{(trade.target_percent || 0).toFixed(1)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="flex justify-end gap-3 p-4">
            <Button variant="ghost" onClick={() => setPlan(null)}>Dismiss</Button>
            <Button
              variant="primary"
              leftIcon={<Play className="w-4 h-4" />}
              onClick={handleExecute}
              isLoading={executing}
            >
              Execute Rebalance
            </Button>
          </div>
        </Card>
      )}

      {/* Target Allocation Editor */}
      <Card variant="elevated" className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
            <Scale className="w-5 h-5 text-blue-400" />
            Target Allocation
          </h2>
          <Button
            size="sm"
            variant="ghost"
            leftIcon={<Plus className="w-4 h-4" />}
            onClick={() => setTargets([...targets, { symbol: '', target_percent: 0 }])}
          >
            Add Asset
          </Button>
        </div>

        {targets.length === 0 ? (
          <EmptyState
            icon={<Scale className="w-12 h-12 text-gray-300 dark:text-gray-600" />}
            title="No targets configured"
            description="Add assets to define your portfolio allocation"
          />
        ) : (
          <div className="space-y-3">
            {targets.map((target, idx) => (
              <div key={idx} className="flex items-center gap-3">
                <input
                  type="text"
                  value={target.symbol}
                  onChange={(e) => {
                    const newTargets = [...targets];
                    newTargets[idx].symbol = e.target.value.toUpperCase();
                    setTargets(newTargets);
                  }}
                  placeholder="Symbol (e.g. BTC)"
                  className="w-28 px-3 py-2 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg text-gray-900 dark:text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-blue-500 text-sm"
                />
                <div className="flex-1 flex items-center gap-2">
                  <input
                    type="range"
                    min={0}
                    max={100}
                    step={0.5}
                    value={target.target_percent || 0}
                    onChange={(e) => {
                      const newTargets = [...targets];
                      newTargets[idx].target_percent = parseFloat(e.target.value) || 0;
                      setTargets(newTargets);
                    }}
                    className="flex-1 accent-blue-500"
                  />
                  <input
                    type="number"
                    value={target.target_percent || 0}
                    onChange={(e) => {
                      const newTargets = [...targets];
                      newTargets[idx].target_percent = parseFloat(e.target.value) || 0;
                      setTargets(newTargets);
                    }}
                    className="w-20 px-2 py-1 bg-gray-50 dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded text-gray-900 dark:text-white text-center text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    min={0}
                    max={100}
                    step={0.5}
                  />
                  <span className="text-sm text-gray-500 w-8">%</span>
                </div>
                <button
                  onClick={() => setTargets(targets.filter((_, i) => i !== idx))}
                  className="text-gray-400 hover:text-red-400 transition-colors"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            ))}

            {/* Total bar */}
            <div className="flex items-center justify-between pt-3 border-t border-gray-200 dark:border-gray-700">
              <span className="text-sm text-gray-500 dark:text-gray-400">Total</span>
              <div className="flex items-center gap-3">
                <span className={`text-lg font-bold ${targetSumValid ? 'text-green-600' : 'text-red-600'}`}>
                  {totalTarget.toFixed(1)}%
                </span>
                {!targetSumValid && (
                  <span className="text-xs text-red-400 flex items-center gap-1">
                    <AlertTriangle className="w-3 h-3" />
                    Must equal 100%
                  </span>
                )}
              </div>
            </div>

            {/* Action Buttons */}
            <div className="flex justify-end gap-3 pt-2">
              <Button
                variant="secondary"
                leftIcon={<RefreshCw className="w-4 h-4" />}
                onClick={handleAnalyze}
                isLoading={analyzing}
                disabled={!targetSumValid || targets.length === 0}
              >
                Analyze
              </Button>
              <Button
                variant="primary"
                onClick={async () => {
                  try {
                    const response = await fetch(`${API_BASE_URL}/api/rebalance/targets`, {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json', ...authHeaders() },
                      body: JSON.stringify({ targets }),
                    });
                    if (!response.ok) {
                      throw new Error('Failed to save targets');
                    }
                    success('Targets saved');
                    loadTargets();
                  } catch (e: any) {
                    showError(e.message || 'Failed to save targets');
                  }
                }}
                disabled={!targetSumValid || targets.length === 0}
              >
                Save Targets
              </Button>
            </div>
          </div>
        )}
      </Card>
    </div>
  );
}
