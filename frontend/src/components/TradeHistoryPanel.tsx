/**
 * Trade History Component.
 * Displays both paper trades and real Binance TH trades.
 */
'use client';

import { useEffect, useState } from 'react';
import { useAppStore } from '@/store/store';
import { TradeHistory, RealTrade } from '@/types';

type TabKey = 'real' | 'paper';

export default function TradeHistoryPanel() {
  const tradeHistory = useAppStore((state) => state.tradeHistory);
  const realTrades = useAppStore((state) => state.realTrades);
  const refreshTradeHistory = useAppStore((state) => state.refreshTradeHistory);
  const refreshRealTrades = useAppStore((state) => state.refreshRealTrades);
  const [activeTab, setActiveTab] = useState<TabKey>('real');

  useEffect(() => {
    refreshTradeHistory();
    refreshRealTrades();
  }, [refreshTradeHistory, refreshRealTrades]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatNumber = (value: number, decimals = 2) => {
    return value.toLocaleString(undefined, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
  };

  const formatCurrency = (value: number) => {
    return value.toLocaleString(undefined, {
      style: 'currency',
      currency: 'THB',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
  };

  const displayTrades = activeTab === 'real' ? realTrades : tradeHistory;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Trade History
        </h2>
        <div className="flex items-center gap-3">
          {/* Tab switcher */}
          <div className="flex rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
            <button
              onClick={() => setActiveTab('real')}
              className={`px-3 py-1 text-sm font-medium transition-colors ${
                activeTab === 'real'
                  ? 'bg-blue-600 text-white'
                  : 'bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              Real ({realTrades.length})
            </button>
            <button
              onClick={() => setActiveTab('paper')}
              className={`px-3 py-1 text-sm font-medium transition-colors ${
                activeTab === 'paper'
                  ? 'bg-blue-600 text-white'
                  : 'bg-transparent text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700'
              }`}
            >
              Paper ({tradeHistory.length})
            </button>
          </div>
          <button
            onClick={() => activeTab === 'real' ? refreshRealTrades() : refreshTradeHistory()}
            className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            Refresh
          </button>
        </div>
      </div>

      {!displayTrades || displayTrades.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400 text-center py-8">
          No {activeTab} trades yet
        </p>
      ) : activeTab === 'real' ? (
        /* ── Real trades table ── */
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Time</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Side</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Status</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Qty</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Price</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Total</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Fee</th>
              </tr>
            </thead>
            <tbody>
              {(displayTrades as RealTrade[]).slice().reverse().map((t) => {
                const total = t.quantity * t.price;
                return (
                  <tr key={t.id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                    <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                      {formatDate(t.created_at)}
                    </td>
                    <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">
                      {t.symbol}
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        t.side === 'BUY'
                          ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                          : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                      }`}>
                        {t.side}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        t.status === 'FILLED'
                          ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900 dark:text-emerald-200'
                          : t.status === 'NEW'
                          ? 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200'
                          : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-300'
                      }`}>
                        {t.status}
                      </span>
                    </td>
                    <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                      {t.quantity.toFixed(6)}
                    </td>
                    <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                      {formatNumber(t.price)}
                    </td>
                    <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                      {formatCurrency(total)}
                    </td>
                    <td className="py-3 px-4 text-sm text-right text-gray-500 dark:text-gray-400">
                      {formatCurrency(t.fee || 0)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ) : (
        /* ── Paper trades table ── */
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Time</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Side</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Qty</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Price</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Total</th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">Fee</th>
              </tr>
            </thead>
            <tbody>
              {(displayTrades as TradeHistory[]).slice().reverse().map((trade) => (
                <tr key={trade.id} className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700">
                  <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                    {formatDate(trade.executedAt)}
                  </td>
                  <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">
                    {trade.symbol}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${
                      trade.side === 'BUY'
                        ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                        : 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                    {trade.quantity.toFixed(6)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                    {formatCurrency(trade.price)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-gray-900 dark:text-white">
                    {formatCurrency(trade.total)}
                  </td>
                  <td className="py-3 px-4 text-sm text-right text-gray-500 dark:text-gray-400">
                    {formatCurrency(trade.fee)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
