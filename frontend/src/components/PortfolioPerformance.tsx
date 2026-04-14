/**
 * Portfolio Performance Chart
 * Shows portfolio value over time with profit/loss visualization
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts';
import { TrendingUp, TrendingDown, DollarSign, Percent, BarChart3 } from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface PerformanceData {
  date: string;
  value: number;
  profit: number;
  profitPercent: number;
}

interface PortfolioPerformanceProps {
  data?: PerformanceData[];
}

export default function PortfolioPerformance({ data: propData }: PortfolioPerformanceProps) {
  const [data, setData] = useState<PerformanceData[]>(propData || []);
  const [timeRange, setTimeRange] = useState<'7d' | '30d' | '90d' | '1y' | 'all'>('30d');
  const [loading, setLoading] = useState(!propData);

  // Fetch real performance data from API
  useEffect(() => {
    if (propData) {
      setData(propData);
      setLoading(false);
      return;
    }

    const fetchPerformance = async () => {
      try {
        // Fetch real trade history from backend
        const response = await fetch('/api/trades?limit=100', {
          headers: { 'Authorization': `Bearer ${localStorage.getItem('auth_token') || ''}` }
        });

        if (!response.ok) {
          throw new Error('Failed to fetch trade history');
        }

        const trades = await response.json();

        if (!trades || trades.length === 0) {
          // No trades yet - show empty state
          setData([]);
          setLoading(false);
          return;
        }

        // Build real performance curve from trade history
        let cumulativeValue = 10000; // Starting balance
        const performanceData: PerformanceData[] = [];

        trades.forEach((trade: any) => {
          const date = trade.executed_at || trade.createdAt || new Date().toISOString();
          const pnl = trade.pnl || trade.profit || 0;
          cumulativeValue += pnl;
          const profit = cumulativeValue - 10000;
          const profitPercent = (profit / 10000) * 100;

          performanceData.push({
            date: date.split('T')[0],
            value: cumulativeValue,
            profit,
            profitPercent
          });
        });

        // If we have data points, add initial point
        if (performanceData.length > 0) {
          performanceData.unshift({
            date: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
            value: 10000,
            profit: 0,
            profitPercent: 0
          });
        }

        setData(performanceData);
      } catch (err) {
        console.error('Failed to fetch performance data:', err);
        setData([]);
      } finally {
        setLoading(false);
      }
    };

    fetchPerformance();
  }, [timeRange, propData]);

  // Show empty state if no data
  if (!loading && data.length === 0) {
    return (
      <Card variant="elevated" className="p-6">
        <div className="text-center py-12">
          <BarChart3 className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Performance Data Yet</h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">Start trading to see your portfolio performance</p>
          <Button onClick={() => window.location.href = '/th/dashboard/trading'}>
            Go to Trading
          </Button>
        </div>
      </Card>
    );
  }

  const currentData = data[data.length - 1];
  const initialData = data[0];
  const totalProfit = currentData?.profit || 0;
  const totalProfitPercent = currentData?.profitPercent || 0;
  const isProfit = totalProfit >= 0;

  if (loading) {
    return (
      <Card variant="elevated" className="p-6">
        <div className="flex items-center justify-center h-64">
          <div className="text-center">
            <div className="w-12 h-12 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
            <p className="text-gray-600 dark:text-gray-400">Loading performance data...</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card variant="elevated" className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-bold text-gray-900 dark:text-white">Portfolio Performance</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400">Track your portfolio value over time</p>
        </div>
        <div className="flex items-center gap-2">
          {(['7d', '30d', '90d', '1y', 'all'] as const).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={`px-3 py-1 text-xs font-medium rounded transition-colors ${timeRange === range
                ? 'bg-purple-600 text-white'
                : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-700'
                }`}
            >
              {range}
            </button>
          ))}
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Current Value</span>
          </div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            ${currentData?.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            {isProfit ? <TrendingUp className="w-4 h-4 text-green-500" /> : <TrendingDown className="w-4 h-4 text-red-500" />}
            <span className="text-xs text-gray-600 dark:text-gray-400">Total P&L</span>
          </div>
          <div className={`text-xl font-bold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
            {isProfit ? '+' : ''}${Math.abs(totalProfit).toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <Percent className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Return %</span>
          </div>
          <div className={`text-xl font-bold ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
            {isProfit ? '+' : ''}{totalProfitPercent.toFixed(2)}%
          </div>
        </div>

        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Initial</span>
          </div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            $10,000.00
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="h-80">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data}>
            <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" className="dark:stroke-gray-700" />
            <XAxis
              dataKey="date"
              stroke="#9ca3af"
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => {
                const date = new Date(value);
                return `${date.getMonth() + 1}/${date.getDate()}`;
              }}
            />
            <YAxis
              stroke="#9ca3af"
              tick={{ fontSize: 12 }}
              tickFormatter={(value) => `$${value.toLocaleString()}`}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: 'rgba(17, 24, 39, 0.9)',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#fff'
              }}
              formatter={(value: any, name: string) => {
                if (name === 'value') return [`$${Number(value).toLocaleString(undefined, { minimumFractionDigits: 2 })}`, 'Value'];
                return [value, name];
              }}
              labelFormatter={(label) => {
                const date = new Date(label);
                return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
              }}
            />
            <ReferenceLine y={10000} stroke="#9ca3af" strokeDasharray="3 3" label="Initial" />
            <Area
              type="monotone"
              dataKey="value"
              stroke={isProfit ? '#10b981' : '#ef4444'}
              fill={isProfit ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)'}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
