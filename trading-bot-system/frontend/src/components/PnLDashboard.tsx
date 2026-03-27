/**
 * P&L Dashboard Component
 * Real-time profit and loss tracking
 */
'use client';

import { useEffect, useState } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import { TrendingUp, TrendingDown, DollarSign, Percent } from 'lucide-react';

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

  // Simulate real-time updates (replace with actual WebSocket/data fetching)
  useEffect(() => {
    const interval = setInterval(() => {
      // TODO: Fetch real P&L data from backend
      // This is just a simulation
      setPnlData((prev) => ({
        ...prev,
        totalPnL: prev.totalPnL + (Math.random() - 0.5) * 10,
        todayPnL: prev.todayPnL + (Math.random() - 0.5) * 5,
      }));
    }, 5000);

    return () => clearInterval(interval);
  }, []);

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
