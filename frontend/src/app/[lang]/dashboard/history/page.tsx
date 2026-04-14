/**
 * Trade History Page
 * View all executed trades
 */
'use client';

import { useState, useEffect } from 'react';
import { useAppStore } from '@/store/store';
import TradeHistoryPanel from '@/components/TradeHistoryPanel';
import EmptyState from '@/components/EmptyState';
import { History, TrendingUp, DollarSign, Activity } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';

export default function TradeHistoryPage() {
  const { t } = useTranslation();
  const { error } = useToast();
  const tradeHistory = useAppStore((state) => state.tradeHistory);
  const refreshTradeHistory = useAppStore((state) => state.refreshTradeHistory);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    refreshTradeHistory()
      .catch(() => error('Failed to load trade history'))
      .finally(() => setIsLoading(false));
  }, [refreshTradeHistory, error]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  // Calculate statistics
  const totalTrades = tradeHistory?.length || 0;
  const totalVolume = tradeHistory?.reduce((sum, trade) => sum + trade.total, 0) || 0;
  const buyTrades = tradeHistory?.filter(t => t.side === 'BUY').length || 0;
  const sellTrades = tradeHistory?.filter(t => t.side === 'SELL').length || 0;

  if (!tradeHistory || tradeHistory.length === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-2">
          <History className="w-5 h-5 text-purple-600" />
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">
              {t('history.title')}
            </h1>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {t('history.subtitle')}
            </p>
          </div>
        </div>
        <EmptyState
          icon={<Activity className="w-10 h-10 text-gray-400" />}
          title="No trades yet"
          description="Start trading to see your trade history here"
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compact Header */}
      <div className="flex items-center gap-2">
        <History className="w-5 h-5 text-purple-600" />
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">
            {t('history.title')}
          </h1>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            {t('history.subtitle')}
          </p>
        </div>
      </div>

      {/* Compact Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <Activity className="w-4 h-4 text-blue-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('history.total-trades')}</span>
          </div>
          <div className="text-lg font-bold text-blue-600">
            {totalTrades}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-4 h-4 text-green-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('history.buy-orders')}</span>
          </div>
          <div className="text-lg font-bold text-green-600">
            {buyTrades}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-4 h-4 text-red-600 rotate-180" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('history.sell-orders')}</span>
          </div>
          <div className="text-lg font-bold text-red-600">
            {sellTrades}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <DollarSign className="w-4 h-4 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('history.total-volume')}</span>
          </div>
          <div className="text-lg font-bold text-purple-600">
            ${totalVolume.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Trade History Panel */}
      <TradeHistoryPanel />
    </div>
  );
}
