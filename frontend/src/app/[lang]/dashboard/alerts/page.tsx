/**
 * Alert Notifications Page
 * Configure notification channels and view alert history
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import { AlertTriangle, Bell, CheckCircle2, XCircle, RefreshCw, Send, MessageSquare, Globe, Webhook, TrendingUp } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

interface AlertConfig {
  discord_webhook_url?: string;
  telegram_bot_token?: string;
  telegram_chat_id?: string;
  custom_webhook_url?: string;
  notify_on_trade?: boolean;
  notify_on_price?: boolean;
  notify_on_bot_start?: boolean;
  notify_on_error?: boolean;
  notify_on_risk?: boolean;
}

export default function AlertsPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning, info } = useToast();

  const [config, setConfig] = useState<AlertConfig>({
    discord_webhook_url: '',
    telegram_bot_token: '',
    telegram_chat_id: '',
    custom_webhook_url: '',
    notify_on_trade: true,
    notify_on_price: false,
    notify_on_bot_start: true,
    notify_on_error: true,
    notify_on_risk: true,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResults, setTestResults] = useState<any>({});

  const loadConfig = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/alerts/config`, {
        headers: authHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setConfig({
          discord_webhook_url: data.discord_webhook_url || '',
          telegram_bot_token: data.telegram_bot_token || '',
          telegram_chat_id: data.telegram_chat_id || '',
          custom_webhook_url: data.custom_webhook_url || '',
          notify_on_trade: data.notify_on_trade ?? true,
          notify_on_price: data.notify_on_price ?? false,
          notify_on_bot_start: data.notify_on_bot_start ?? true,
          notify_on_error: data.notify_on_error ?? true,
          notify_on_risk: data.notify_on_risk ?? true,
        });
      }
    } catch (err) {
      console.error('Failed to load alert config:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadConfig();
  }, [loadConfig]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/alerts/config`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(config),
      });
      if (!response.ok) throw new Error('Failed to save alert config');
      success('Alert configuration saved');
    } catch (err: any) {
      showError(err.message || 'Failed to save configuration');
    } finally {
      setSaving(false);
    }
  };

  const testChannel = async (channel: string) => {
    setTesting(true);
    setTestResults((prev: any) => ({ ...prev, [channel]: 'pending' }));
    try {
      const response = await fetch(`${API_BASE_URL}/api/alerts/test`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error('Test failed');
      setTestResults((prev: any) => ({ ...prev, [channel]: 'success' }));
      success(`${channel} test notification sent`);
    } catch (err: any) {
      setTestResults((prev: any) => ({ ...prev, [channel]: 'failed' }));
      showError(`${channel} test failed: ${err.message}`);
    } finally {
      setTesting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading alert settings...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-amber-500/10 rounded-xl">
            <Bell className="w-6 h-6 text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Alert Notifications</h1>
            <p className="text-gray-500 dark:text-gray-400">Configure notification channels and manage alert preferences</p>
          </div>
        </div>
        <Button onClick={handleSave} isLoading={saving} leftIcon={<CheckCircle2 className="w-4 h-4" />}>
          Save Changes
        </Button>
      </div>

      {/* Alert Status Banner */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={`w-3 h-3 rounded-full ${config.notify_on_error ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {config.notify_on_error ? 'Alerts Enabled' : 'Alerts Disabled'}
            </span>
          </div>
          <Badge variant={config.notify_on_error ? 'success' : 'error'}>
            {config.notify_on_error ? 'Active' : 'Inactive'}
          </Badge>
        </div>
      </Card>

      {/* Notification Channels */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Discord */}
        <Card variant="elevated" className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
              <MessageSquare className="w-5 h-5 text-indigo-600" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white">Discord</h3>
              <p className="text-xs text-gray-500">Webhook notifications</p>
            </div>
          </div>
          <input
            type="text"
            className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm mb-3"
            value={config.discord_webhook_url || ''}
            onChange={(e) => setConfig({ ...config, discord_webhook_url: e.target.value })}
            placeholder="https://discord.com/api/webhooks/..."
          />
          <Button
            fullWidth
            size="sm"
            variant="secondary"
            onClick={() => testChannel('Discord')}
            isLoading={testing}
            disabled={!config.discord_webhook_url}
            leftIcon={<Send className="w-4 h-4" />}
          >
            {testResults['Discord'] === 'success' ? <CheckCircle2 className="w-4 h-4 text-green-500 mr-2" /> :
              testResults['Discord'] === 'failed' ? <XCircle className="w-4 h-4 text-red-500 mr-2" /> : null}
            Test Connection
          </Button>
        </Card>

        {/* Telegram */}
        <Card variant="elevated" className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-sky-100 dark:bg-sky-900/30 rounded-lg">
              <Globe className="w-5 h-5 text-sky-600" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white">Telegram</h3>
              <p className="text-xs text-gray-500">Bot notifications</p>
            </div>
          </div>
          <input
            type="text"
            className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm mb-2"
            value={config.telegram_bot_token || ''}
            onChange={(e) => setConfig({ ...config, telegram_bot_token: e.target.value })}
            placeholder="Bot Token: 123456:ABC-DEF..."
          />
          <input
            type="text"
            className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm mb-3"
            value={config.telegram_chat_id || ''}
            onChange={(e) => setConfig({ ...config, telegram_chat_id: e.target.value })}
            placeholder="Chat ID: -1001234567890"
          />
          <Button
            fullWidth
            size="sm"
            variant="secondary"
            onClick={() => testChannel('Telegram')}
            isLoading={testing}
            disabled={!config.telegram_bot_token || !config.telegram_chat_id}
            leftIcon={<Send className="w-4 h-4" />}
          >
            {testResults['Telegram'] === 'success' ? <CheckCircle2 className="w-4 h-4 text-green-500 mr-2" /> :
              testResults['Telegram'] === 'failed' ? <XCircle className="w-4 h-4 text-red-500 mr-2" /> : null}
            Test Connection
          </Button>
        </Card>

        {/* Custom Webhook */}
        <Card variant="elevated" className="p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="p-2 bg-orange-100 dark:bg-orange-900/30 rounded-lg">
              <Webhook className="w-5 h-5 text-orange-600" />
            </div>
            <div>
              <h3 className="font-bold text-gray-900 dark:text-white">Custom Webhook</h3>
              <p className="text-xs text-gray-500">External service integration</p>
            </div>
          </div>
          <input
            type="text"
            className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm mb-3"
            value={config.custom_webhook_url || ''}
            onChange={(e) => setConfig({ ...config, custom_webhook_url: e.target.value })}
            placeholder="https://your-server.com/webhook"
          />
          <Button
            fullWidth
            size="sm"
            variant="secondary"
            onClick={() => testChannel('Webhook')}
            isLoading={testing}
            disabled={!config.custom_webhook_url}
            leftIcon={<Send className="w-4 h-4" />}
          >
            {testResults['Webhook'] === 'success' ? <CheckCircle2 className="w-4 h-4 text-green-500 mr-2" /> :
              testResults['Webhook'] === 'failed' ? <XCircle className="w-4 h-4 text-red-500 mr-2" /> : null}
            Test Connection
          </Button>
        </Card>
      </div>

      {/* Alert Types */}
      <Card variant="elevated" className="p-6">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4">Alert Types</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            { key: 'notify_on_trade', label: 'Trade Executions', desc: 'Get notified when trades are executed', icon: <TrendingUp className="w-5 h-5" /> },
            { key: 'notify_on_price', label: 'Price Alerts', desc: 'Get notified when price targets are hit', icon: <TrendingUp className="w-5 h-5" /> },
            { key: 'notify_on_bot_start', label: 'Bot Status', desc: 'Get notified when bot starts/stops', icon: <Bell className="w-5 h-5" /> },
            { key: 'notify_on_error', label: 'Errors', desc: 'Get notified when errors occur', icon: <AlertTriangle className="w-5 h-5" /> },
            { key: 'notify_on_risk', label: 'Risk Warnings', desc: 'Get notified when risk thresholds are reached', icon: <AlertTriangle className="w-5 h-5" /> },
          ].map((item) => (
            <label
              key={item.key}
              className="flex items-start gap-3 p-4 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-800 cursor-pointer transition-colors"
            >
              <input
                type="checkbox"
                className="w-5 h-5 mt-0.5 rounded border-gray-300 text-purple-600 focus:ring-purple-500"
                checked={config[item.key as keyof AlertConfig] as boolean || false}
                onChange={(e) => setConfig({ ...config, [item.key]: e.target.checked })}
              />
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-purple-600 dark:text-purple-400">{item.icon}</span>
                  <span className="font-semibold text-gray-900 dark:text-white text-sm">{item.label}</span>
                </div>
                <p className="text-xs text-gray-500 mt-1">{item.desc}</p>
              </div>
            </label>
          ))}
        </div>
      </Card>
    </div>
  );
}
