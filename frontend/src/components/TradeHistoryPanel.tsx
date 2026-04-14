/**
 * Trade History Component.
 * Displays the list of executed trades.
 */
'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/store/store';
import { TradeHistory } from '@/types';

export default function TradeHistoryPanel() {
  const tradeHistory = useAppStore((state) => state.tradeHistory);
  const refreshTradeHistory = useAppStore((state) => state.refreshTradeHistory);

  useEffect(() => {
    refreshTradeHistory();
  }, [refreshTradeHistory]);

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString();
  };

  const formatCurrency = (value: number) => {
    return value.toLocaleString(undefined, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
          Trade History
        </h2>
        <button
          onClick={() => refreshTradeHistory()}
          className="text-sm text-blue-600 hover:text-blue-700 dark:text-blue-400"
        >
          Refresh
        </button>
      </div>

      {!tradeHistory || tradeHistory.length === 0 ? (
        <p className="text-gray-500 dark:text-gray-400 text-center py-8">
          No trades yet
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Time
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Symbol
                </th>
                <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Side
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Quantity
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Price
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Total
                </th>
                <th className="text-right py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                  Fee
                </th>
              </tr>
            </thead>
            <tbody>
              {tradeHistory.slice().reverse().map((trade) => (
                <tr
                  key={trade.id}
                  className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                    {formatDate(trade.executedAt)}
                  </td>
                  <td className="py-3 px-4 text-sm font-medium text-gray-900 dark:text-white">
                    {trade.symbol}
                  </td>
                  <td className="py-3 px-4">
                    <span className={`px-2 py-1 rounded text-xs font-medium ${trade.side === 'BUY'
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
