/**
 * Notification Center Component
 * Manage and view all notifications
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import Toggle from '@/components/ui/Toggle';
import { Bell, Check, Trash2, Settings, AlertCircle, TrendingUp, DollarSign } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';
import { api } from '@/services/api';

interface Notification {
  id: string;
  type: 'ORDER_FILLED' | 'PRICE_ALERT' | 'BOT_STATUS' | 'PNL_ALERT' | 'ERROR';
  title: string;
  message: string;
  timestamp: Date;
  read: boolean;
  priority: 'LOW' | 'MEDIUM' | 'HIGH';
}

interface NotificationSettings {
  orderFilled: boolean;
  priceAlerts: boolean;
  botStatusChanges: boolean;
  pnlThreshold: boolean;
  pnlThresholdPercent: number;
  emailNotifications: boolean;
  telegramNotifications: boolean;
  lineNotifications: boolean;
}

export default function NotificationCenter() {
  const { success } = useToast();
  const [notifications, setNotifications] = useState<Notification[]>([]);

  const [settings, setSettings] = useState<NotificationSettings>({
    orderFilled: true,
    priceAlerts: true,
    botStatusChanges: true,
    pnlThreshold: true,
    pnlThresholdPercent: 10,
    emailNotifications: false,
    telegramNotifications: false,
    lineNotifications: false,
  });

  const [showSettings, setShowSettings] = useState(false);

  const fetchNotifications = useCallback(async () => {
    try {
      const raw = await api.getNotifications();
      const mapped: Notification[] = (raw as any[]).map((n: any) => ({
        id: n.id,
        type: n.type as Notification['type'],
        title: n.title,
        message: n.message,
        timestamp: new Date(n.timestamp),
        read: n.read,
        priority: n.priority as Notification['priority'],
      }));
      setNotifications(mapped);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchNotifications();
    const interval = setInterval(fetchNotifications, 15000);
    return () => clearInterval(interval);
  }, [fetchNotifications]);

  const unreadCount = notifications.filter((n) => !n.read).length;

  const handleMarkAsRead = async (id: string) => {
    await api.markNotificationRead(id).catch(() => { });
    setNotifications((prev) =>
      prev.map((n) => (n.id === id ? { ...n, read: true } : n))
    );
  };

  const handleMarkAllAsRead = async () => {
    await api.markAllNotificationsRead().catch(() => { });
    setNotifications((prev) => prev.map((n) => ({ ...n, read: true })));
    success('All notifications marked as read');
  };

  const handleDeleteNotification = async (id: string) => {
    await api.deleteNotification(id).catch(() => { });
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  };

  const handleClearAll = async () => {
    await api.clearAllNotifications().catch(() => { });
    setNotifications([]);
    success('All notifications cleared');
  };

  const getNotificationIcon = (type: Notification['type']) => {
    switch (type) {
      case 'ORDER_FILLED':
        return <Check className="w-4 h-4 text-green-600" />;
      case 'PRICE_ALERT':
        return <TrendingUp className="w-4 h-4 text-blue-600" />;
      case 'BOT_STATUS':
        return <Settings className="w-4 h-4 text-purple-600" />;
      case 'PNL_ALERT':
        return <DollarSign className="w-4 h-4 text-green-600" />;
      case 'ERROR':
        return <AlertCircle className="w-4 h-4 text-red-600" />;
    }
  };

  const getPriorityColor = (priority: Notification['priority']) => {
    switch (priority) {
      case 'HIGH':
        return 'border-l-4 border-l-red-600';
      case 'MEDIUM':
        return 'border-l-4 border-l-amber-600';
      case 'LOW':
        return 'border-l-4 border-l-blue-600';
    }
  };

  const getTimeAgo = (date: Date) => {
    const seconds = Math.floor((new Date().getTime() - date.getTime()) / 1000);
    if (seconds < 60) return 'Just now';
    if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`;
    if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`;
    return `${Math.floor(seconds / 86400)}d ago`;
  };

  return (
    <Card variant="elevated" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <Bell className="w-4 h-4 text-purple-600" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            Notifications
          </h3>
          {unreadCount > 0 && (
            <Badge variant="error" size="sm">
              {unreadCount}
            </Badge>
          )}
        </div>
        <div className="flex gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSettings(!showSettings)}
          >
            <Settings className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={handleMarkAllAsRead}>
            Mark all read
          </Button>
          <Button variant="ghost" size="sm" onClick={handleClearAll}>
            Clear all
          </Button>
        </div>
      </div>

      {/* Notification Settings */}
      {showSettings && (
        <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg space-y-3">
          <h4 className="text-xs font-semibold text-gray-900 dark:text-white mb-2">
            Notification Preferences
          </h4>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Order Filled
            </span>
            <Toggle
              checked={settings.orderFilled}
              onChange={(checked) =>
                setSettings((prev) => ({ ...prev, orderFilled: checked }))
              }
              size="sm"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Price Alerts
            </span>
            <Toggle
              checked={settings.priceAlerts}
              onChange={(checked) =>
                setSettings((prev) => ({ ...prev, priceAlerts: checked }))
              }
              size="sm"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              Bot Status Changes
            </span>
            <Toggle
              checked={settings.botStatusChanges}
              onChange={(checked) =>
                setSettings((prev) => ({ ...prev, botStatusChanges: checked }))
              }
              size="sm"
            />
          </div>

          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-600 dark:text-gray-400">
              P&L Threshold ({settings.pnlThresholdPercent}%)
            </span>
            <Toggle
              checked={settings.pnlThreshold}
              onChange={(checked) =>
                setSettings((prev) => ({ ...prev, pnlThreshold: checked }))
              }
              size="sm"
            />
          </div>

          <div className="border-t border-gray-200 dark:border-gray-700 pt-3 mt-3">
            <h5 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2">
              Delivery Channels
            </h5>

            <div className="flex items-center justify-between">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Email
              </span>
              <Toggle
                checked={settings.emailNotifications}
                onChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    emailNotifications: checked,
                  }))
                }
                size="sm"
              />
            </div>

            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                Telegram
              </span>
              <Toggle
                checked={settings.telegramNotifications}
                onChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    telegramNotifications: checked,
                  }))
                }
                size="sm"
              />
            </div>

            <div className="flex items-center justify-between mt-2">
              <span className="text-xs text-gray-600 dark:text-gray-400">
                LINE
              </span>
              <Toggle
                checked={settings.lineNotifications}
                onChange={(checked) =>
                  setSettings((prev) => ({
                    ...prev,
                    lineNotifications: checked,
                  }))
                }
                size="sm"
              />
            </div>
          </div>
        </div>
      )}

      {/* Notifications List */}
      <div className="space-y-2 max-h-96 overflow-auto">
        {notifications.map((notification) => (
          <div
            key={notification.id}
            className={`p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg ${getPriorityColor(
              notification.priority
            )} ${notification.read ? 'opacity-60' : ''}`}
          >
            <div className="flex items-start justify-between mb-1">
              <div className="flex items-center gap-2">
                {getNotificationIcon(notification.type)}
                <span
                  className={`text-sm font-medium ${notification.read
                    ? 'text-gray-600 dark:text-gray-400'
                    : 'text-gray-900 dark:text-white'
                    }`}
                >
                  {notification.title}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">
                  {getTimeAgo(notification.timestamp)}
                </span>
                {!notification.read && (
                  <button
                    onClick={() => handleMarkAsRead(notification.id)}
                    className="text-blue-600 hover:text-blue-700"
                  >
                    <Check className="w-3.5 h-3.5" />
                  </button>
                )}
                <button
                  onClick={() => handleDeleteNotification(notification.id)}
                  className="text-red-600 hover:text-red-700"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {notification.message}
            </p>
          </div>
        ))}

        {notifications.length === 0 && (
          <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
            <Bell className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No notifications</p>
          </div>
        )}
      </div>
    </Card>
  );
}
