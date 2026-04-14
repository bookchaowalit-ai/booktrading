/**
 * Activity Feed Component - Real-time bot activity tracking
 * Shows live bot activities including trades, scanning, errors, etc.
 */
'use client';

import { useState, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { BotActivity, TradeNotification } from '@/types';
import { wsService } from '@/services/websocket';
import { useToast } from '@/components/ui/Toast';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Search,
  AlertCircle,
  CheckCircle2,
  Clock,
  X,
} from 'lucide-react';

interface ActivityFeedProps {
  maxItems?: number;
  showToasts?: boolean;
  compact?: boolean;
}

interface ActivityItem {
  id: string;
  timestamp: Date;
  type: 'activity' | 'trade';
  data: BotActivity | TradeNotification;
}

export default function ActivityFeed({
  maxItems = 50,
  showToasts = true,
  compact = false,
}: ActivityFeedProps) {
  const [activities, setActivities] = useState<ActivityItem[]>([]);
  const [isVisible, setIsVisible] = useState(true);
  const containerRef = useRef<HTMLDivElement>(null);
  const { success, error, warning, info } = useToast();

  // Listen to WebSocket bot activity
  useEffect(() => {
    const cleanupActivity = wsService.onMessage((message) => {
      if (message.type === 'bot_activity') {
        const activity = message.data as BotActivity;
        const newItem: ActivityItem = {
          id: `activity_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date(activity.timestamp),
          type: 'activity',
          data: activity,
        };

        setActivities((prev) => [newItem, ...prev].slice(0, maxItems));

        // Show toast for important activities
        if (showToasts && (activity.level === 'error' || activity.level === 'success')) {
          const toastFn = activity.level === 'error' ? error : success;
          toastFn(activity.message);
        }
      } else if (message.type === 'trade_notification') {
        const trade = message.data as TradeNotification;
        const newItem: ActivityItem = {
          id: `trade_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          timestamp: new Date(trade.timestamp),
          type: 'trade',
          data: trade,
        };

        setActivities((prev) => [newItem, ...prev].slice(0, maxItems));

        // Always show toast for trades
        if (showToasts) {
          const side = trade.side === 'BUY' ? '🟢 BUY' : '🔴 SELL';
          info(`${side} ${trade.symbol} @ ${trade.price.toLocaleString()}`);
        }
      }
    });

    return () => {
      cleanupActivity();
    };
  }, [maxItems, showToasts, success, error, warning, info]);

  const clearActivities = () => {
    setActivities([]);
  };

  const formatTime = (date: Date) => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getActivityIcon = (activity: BotActivity) => {
    switch (activity.activity) {
      case 'SCANNING':
        return <Search className="w-4 h-4 text-blue-500" />;
      case 'ANALYZING':
        return <Activity className="w-4 h-4 text-purple-500" />;
      case 'WAITING':
        return <Clock className="w-4 h-4 text-gray-400" />;
      case 'PLACING_ORDER':
        return activity.level === 'success' ? (
          <CheckCircle2 className="w-4 h-4 text-green-500" />
        ) : (
          <Activity className="w-4 h-4 text-yellow-500" />
        );
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-red-500" />;
      default:
        return <Activity className="w-4 h-4 text-gray-400" />;
    }
  };

  const getTradeIcon = (trade: TradeNotification) => {
    return trade.side === 'BUY' ? (
      <TrendingUp className="w-4 h-4 text-green-500" />
    ) : (
      <TrendingDown className="w-4 h-4 text-red-500" />
    );
  };

  const getActivityColor = (level: string) => {
    switch (level) {
      case 'success':
        return 'border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10';
      case 'error':
        return 'border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10';
      case 'warning':
        return 'border-yellow-200 dark:border-yellow-800 bg-yellow-50/50 dark:bg-yellow-900/10';
      default:
        return 'border-gray-200 dark:border-gray-800 bg-white/50 dark:bg-gray-800/50';
    }
  };

  if (!isVisible) {
    return (
      <button
        onClick={() => setIsVisible(true)}
        className="fixed bottom-20 right-4 z-40 p-3 bg-purple-600 hover:bg-purple-700 text-white rounded-full shadow-lg transition-colors"
        title="Show Activity Feed"
      >
        <Activity className="w-5 h-5" />
      </button>
    );
  }

  if (compact) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-2 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-600" />
            <h3 className="text-sm font-semibold text-gray-900 dark:text-white">Recent Activity</h3>
          </div>
          {activities.length > 0 && (
            <button
              onClick={clearActivities}
              className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
            >
              Clear
            </button>
          )}
        </div>

        <div ref={containerRef} className="max-h-64 overflow-y-auto">
          <AnimatePresence>
            {activities.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-3 py-8 text-center text-sm text-gray-500 dark:text-gray-400"
              >
                No activity yet. Start the bot to see live updates.
              </motion.div>
            ) : (
              activities.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: 20 }}
                  className={`px-3 py-2 border-b border-gray-100 dark:border-gray-700 last:border-b-0 ${
                    item.type === 'activity'
                      ? getActivityColor((item.data as BotActivity).level)
                      : 'border-blue-200 dark:border-blue-800 bg-blue-50/50 dark:bg-blue-900/10'
                  }`}
                >
                  <div className="flex items-start gap-2">
                    <div className="flex-shrink-0 mt-0.5">
                      {item.type === 'activity'
                        ? getActivityIcon(item.data as BotActivity)
                        : getTradeIcon(item.data as TradeNotification)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-xs text-gray-900 dark:text-white truncate">
                        {item.data.message}
                      </p>
                      <p className="text-[10px] text-gray-500 dark:text-gray-400 mt-0.5">
                        {formatTime(item.timestamp)}
                      </p>
                    </div>
                  </div>
                </motion.div>
              ))
            )}
          </AnimatePresence>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
            <Activity className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h3 className="text-sm font-bold text-gray-900 dark:text-white">Activity Feed</h3>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {activities.length} event{activities.length !== 1 ? 's' : ''}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {activities.length > 0 && (
            <button
              onClick={clearActivities}
              className="text-xs text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 flex items-center gap-1 px-2 py-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            >
              <X className="w-3 h-3" />
              Clear
            </button>
          )}
          <button
            onClick={() => setIsVisible(false)}
            className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
            title="Hide Activity Feed"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Activity List */}
      <div ref={containerRef} className="max-h-96 overflow-y-auto">
        <AnimatePresence>
          {activities.length === 0 ? (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="px-4 py-12 text-center"
            >
              <Activity className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-sm text-gray-500 dark:text-gray-400">
                No activity yet
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
                Start the bot to see live updates
              </p>
            </motion.div>
          ) : (
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {activities.map((item) => (
                <motion.div
                  key={item.id}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 10 }}
                  className={`px-4 py-3 ${
                    item.type === 'activity'
                      ? getActivityColor((item.data as BotActivity).level)
                      : 'bg-blue-50/50 dark:bg-blue-900/10'
                  }`}
                >
                  <div className="flex items-start gap-3">
                    <div className="flex-shrink-0 mt-0.5">
                      {item.type === 'activity'
                        ? getActivityIcon(item.data as BotActivity)
                        : getTradeIcon(item.data as TradeNotification)}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {item.data.message}
                        </p>
                        <span className="text-xs text-gray-500 dark:text-gray-400 whitespace-nowrap">
                          {formatTime(item.timestamp)}
                        </span>
                      </div>
                      {item.type === 'trade' && (
                        <div className="flex items-center gap-3 mt-2 text-xs">
                          <span className="text-gray-600 dark:text-gray-400">
                            {(item.data as TradeNotification).symbol}
                          </span>
                          <span className="text-gray-400">•</span>
                          <span className="text-gray-600 dark:text-gray-400">
                            Qty: {(item.data as TradeNotification).quantity}
                          </span>
                          <span className="text-gray-400">•</span>
                          <span className="font-semibold text-gray-900 dark:text-white">
                            ${(item.data as TradeNotification).total.toFixed(2)}
                          </span>
                        </div>
                      )}
                      {item.type === 'activity' && (item.data as BotActivity).symbol && (
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {(item.data as BotActivity).symbol}
                        </p>
                      )}
                    </div>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
