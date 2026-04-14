/**
 * P&L Dashboard Component
 * Real-time profit and loss tracking
 */
'use client';

import { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { TrendingUp, TrendingDown, DollarSign, Percent } from 'lucide-react';
import { api } from '@/services/api';
import { useAppStore } from '@/store/store';

interface PnLData {
  totalPnL: number;
  totalPnLPercent: number;
  unrealizedPnL: number;
  realizedPnL: number;
  todayPnL: number;
  todayPnLPercent: number;
}

interface PnLDashboardProps {
  initialData?: PnLData;
}

export default function PnLDashboard({ initialData }: PnLDashboardProps) {
  const [pnlData, setPnlData] = useState<PnLData>(
    initialData || {
      totalPnL: 0,
      totalPnLPercent: 0,
      unrealizedPnL: 0,
      realizedPnL: 0,
      todayPnL: 0,
      todayPnLPercent: 0,
    }
  );

  const marketData = useAppStore((state) => state.marketData);

  const fetchPnL = async () => {
    try {
      // Realized P&L from performance service (computed from trade history)
      const perf = await api.getPerformance();

      // Unrealized P&L from portfolio positions × current market prices
      const balances = await api.getPortfolio();
      let unrealized = 0;
      balances.forEach((b) => {
        const balance = b.balance ?? 0;
        const avgBuy = b.avgBuyPrice ?? 0;
        const currentPrice = marketData[b.symbol]?.price ?? 0;
        if (avgBuy > 0 && currentPrice > 0) {
          unrealized += (currentPrice - avgBuy) * balance;
        }
      });

      setPnlData({
        totalPnL: perf.totalPnL ?? 0,
        totalPnLPercent: perf.totalPnLPercent ?? 0,
        unrealizedPnL: parseFloat(unrealized.toFixed(2)),
        realizedPnL: perf.totalPnL ?? 0,
        todayPnL: 0,
        todayPnLPercent: 0,
      });
    } catch {
      // ignore - keep previous values
    }
  };

  useEffect(() => {
    if (!initialData) {
      fetchPnL();
    }
    const interval = setInterval(fetchPnL, 30000);
    return () => clearInterval(interval);
  }, [initialData]); // eslint-disable-line react-hooks/exhaustive-deps

  const formatPnL = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}$${value.toFixed(2)}`;
  };

  const formatPercent = (value: number) => {
    const sign = value >= 0 ? '+' : '';
    return `${sign}${value.toFixed(2)}%`;
  };

  const getPnLColor = (value: number) => {
    return value >= 0 ? 'text-green-600' : 'text-red-600';
  };

  const getPnLBgColor = (value: number) => {
    return value >= 0 ? 'bg-green-100 dark:bg-green-900/20' : 'bg-red-100 dark:bg-red-900/20';
  };

  return (
    <div className="space-y-3">
      {/* Total P&L */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Total P&L</span>
          </div>
          <Badge variant={pnlData.totalPnL >= 0 ? 'success' : 'error'} size="sm">
            {formatPercent(pnlData.totalPnLPercent)}
          </Badge>
        </div>
        <div className={`text-2xl font-bold ${getPnLColor(pnlData.totalPnL)}`}>
          {formatPnL(pnlData.totalPnL)}
        </div>
      </Card>

      {/* Today's P&L */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Today's P&L</span>
          </div>
          <Badge variant={pnlData.todayPnL >= 0 ? 'success' : 'error'} size="sm">
            {formatPercent(pnlData.todayPnLPercent)}
          </Badge>
        </div>
        <div className={`text-xl font-bold ${getPnLColor(pnlData.todayPnL)}`}>
          {formatPnL(pnlData.todayPnL)}
        </div>
      </Card>

      {/* Unrealized vs Realized */}
      <div className="grid grid-cols-2 gap-3">
        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <Percent className="w-3.5 h-3.5 text-blue-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Unrealized</span>
          </div>
          <div className={`text-lg font-bold ${getPnLColor(pnlData.unrealizedPnL)}`}>
            {formatPnL(pnlData.unrealizedPnL)}
          </div>
        </Card>

        <Card variant="elevated" className="p-3">
          <div className="flex items-center gap-1.5 mb-1">
            <DollarSign className="w-3.5 h-3.5 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Realized</span>
          </div>
          <div className={`text-lg font-bold ${getPnLColor(pnlData.realizedPnL)}`}>
            {formatPnL(pnlData.realizedPnL)}
          </div>
        </Card>
      </div>
    </div>
  );
}
