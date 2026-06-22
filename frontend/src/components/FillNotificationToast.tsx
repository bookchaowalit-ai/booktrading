/**
 * Fill Notification Toast Component.
 * Polls the real grid bot for fill events and displays toast popups.
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { monitoringService } from '@/services/monitoring';

interface FillNotification {
  type: string;
  side: string;
  symbol: string;
  price: number;
  quantity: number;
  profit: number;
  trade_id: string;
  timestamp: string;
  message: string;
}

export default function FillNotificationToast() {
  const [notifications, setNotifications] = useState<FillNotification[]>([]);
  const [visible, setVisible] = useState<Set<string>>(new Set());
  const [seenIds, setSeenIds] = useState<Set<string>>(new Set());

  const pollNotifications = useCallback(async () => {
    const data = await monitoringService.getNotifications(10);
    if (!data || data.length === 0) return;

    const newOnes = data.filter((n: FillNotification) => !seenIds.has(n.trade_id));
    if (newOnes.length === 0) return;

    // Track seen IDs
    const newSeen = new Set(seenIds);
    newOnes.forEach((n: FillNotification) => newSeen.add(n.trade_id));
    setSeenIds(newSeen);

    // Show new notifications as toasts
    setNotifications((prev) => [...newOnes, ...prev].slice(0, 5));
    const newVisible = new Set(visible);
    newOnes.forEach((n: FillNotification) => newVisible.add(n.trade_id));
    setVisible(newVisible);

    // Auto-dismiss after 8 seconds
    newOnes.forEach((n: FillNotification) => {
      setTimeout(() => {
        setVisible((prev) => {
          const next = new Set(prev);
          next.delete(n.trade_id);
          return next;
        });
      }, 8000);
    });
  }, [seenIds, visible]);

  useEffect(() => {
    const interval = setInterval(pollNotifications, 15000); // Poll every 15s
    return () => clearInterval(interval);
  }, [pollNotifications]);

  const dismiss = (tradeId: string) => {
    setVisible((prev) => {
      const next = new Set(prev);
      next.delete(tradeId);
      return next;
    });
    setTimeout(() => {
      setNotifications((prev) => prev.filter((n) => n.trade_id !== tradeId));
    }, 300);
  };

  if (notifications.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm">
      {notifications.map((n) => (
        <div
          key={n.trade_id}
          className={`transform transition-all duration-300 ${
            visible.has(n.trade_id)
              ? 'translate-x-0 opacity-100'
              : 'translate-x-full opacity-0'
          } rounded-lg shadow-lg border p-4 ${
            n.side === 'SELL'
              ? 'bg-emerald-50 border-emerald-200 dark:bg-emerald-900/30 dark:border-emerald-800'
              : 'bg-blue-50 border-blue-200 dark:bg-blue-900/30 dark:border-blue-800'
          }`}
        >
          <div className="flex items-start justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className={`text-lg ${n.side === 'SELL' ? '' : ''}`}>
                {n.side === 'SELL' ? '💰' : '📈'}
              </span>
              <div>
                <p className={`text-sm font-semibold ${
                  n.side === 'SELL'
                    ? 'text-emerald-800 dark:text-emerald-200'
                    : 'text-blue-800 dark:text-blue-200'
                }`}>
                  {n.side === 'SELL' ? 'Sell Filled' : 'Buy Filled'}
                </p>
                <p className={`text-xs mt-0.5 ${
                  n.side === 'SELL'
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-blue-600 dark:text-blue-400'
                }`}>
                  {n.message}
                </p>
                {n.profit > 0 && (
                  <p className="text-xs font-medium text-emerald-700 dark:text-emerald-300 mt-1">
                    Profit: +{n.profit.toLocaleString()} THB
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => dismiss(n.trade_id)}
              className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-200 text-sm"
            >
              ✕
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
