/**
 * Settings Page - Consolidated Settings Hub
 * Combines: General Settings, API Keys, and Preferences
 */
'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { useTheme } from '@/contexts/ThemeProvider';
import { Settings, Key, Bell, Shield, Database } from 'lucide-react';
import { Toggle, Dropdown, Badge } from '@/components/ui';
import APIKeysPage from './api-keys/page';
import SystemHealthCheck from '@/components/SystemHealthCheck';
import { api } from '@/services/api';

type SettingsTab = 'general' | 'api-keys' | 'notifications' | 'advanced';

interface UserPreferences {
  language: string;
  theme: string;
  notifications: {
    trade_executions: boolean;
    price_alerts: boolean;
    bot_status: boolean;
    errors: boolean;
  };
}

export default function SettingsPage() {
  const router = useRouter();
  const { success, error } = useToast();
  const { theme: currentTheme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
  const [resetConfirm, setResetConfirm] = useState(false);
  const [preferences, setPreferences] = useState<UserPreferences>({
    language: 'en',
    theme: 'system',
    notifications: {
      trade_executions: true,
      price_alerts: false,
      bot_status: true,
      errors: true,
    },
  });
  const [isLoading, setIsLoading] = useState(false);

  // Load preferences on mount
  useEffect(() => {
    loadPreferences();
  }, []);

  // Update theme when preferences change
  useEffect(() => {
    if (preferences.theme !== currentTheme) {
      setTheme(preferences.theme as 'light' | 'dark' | 'system');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [preferences.theme]);

  const loadPreferences = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
    // First, load saved preference from localStorage (for immediate UI update)
    const savedLang = localStorage.getItem('preferred_locale');
    if (savedLang) {
      setPreferences(prev => ({
        ...prev,
        language: savedLang,
      }));
    }

    // Then try to load from backend (will override if different)
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/preferences`);
      if (response.ok) {
        const data = await response.json();
        setPreferences(data);
        // Also update localStorage to match backend
        localStorage.setItem('preferred_locale', data.language);
      }
    } catch {
      // silently fail — use localStorage fallback
    }
  };

  const handleSavePreferences = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/preferences`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(preferences),
      });

      if (response.ok) {
        // Apply theme immediately
        setTheme(preferences.theme as 'light' | 'dark' | 'system');

        // Save to localStorage for i18n
        localStorage.setItem('preferred_locale', preferences.language);
        localStorage.setItem('theme', preferences.theme);

        success('Settings saved successfully');

        // Navigate if language changed
        const currentLang = window.location.pathname.split('/')[1];
        if (currentLang !== preferences.language) {
          setTimeout(() => {
            router.push(`/${preferences.language}/dashboard/settings`);
          }, 1000);
        }
      } else {
        error('Failed to save settings');
      }
    } catch {
      error('Failed to save settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportData = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/export`, {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        success(data.message || 'Data exported successfully');
      } else {
        error('Failed to export data');
      }
    } catch {
      error('Failed to export data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSettings = async () => {
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
    setIsLoading(true);
    setResetConfirm(false);
    try {
      const response = await fetch(`${API_BASE_URL}/api/settings/reset`, {
        method: 'POST',
      });

      if (response.ok) {
        success('Settings reset successfully');
        loadPreferences();
      } else {
        error('Failed to reset settings');
      }
    } catch {
      error('Failed to reset settings');
    } finally {
      setIsLoading(false);
    }
  };

  const toggleNotification = (key: keyof typeof preferences.notifications) => {
    setPreferences(prev => ({
      ...prev,
      notifications: {
        ...prev.notifications,
        [key]: !prev.notifications[key],
      },
    }));
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2">
          Settings
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Manage your trading bot configuration and preferences
        </p>
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 border-b border-gray-200 dark:border-gray-700 overflow-x-auto">
        <button
          onClick={() => setActiveTab('general')}
          className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === 'general'
            ? 'text-purple-600 border-b-2 border-purple-600'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
            }`}
        >
          <div className="flex items-center gap-1.5">
            <Settings className="w-3.5 h-3.5" />
            General
          </div>
        </button>
        <button
          onClick={() => setActiveTab('api-keys')}
          className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === 'api-keys'
            ? 'text-purple-600 border-b-2 border-purple-600'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
            }`}
        >
          <div className="flex items-center gap-1.5">
            <Key className="w-3.5 h-3.5" />
            API Keys
          </div>
        </button>
        <button
          onClick={() => setActiveTab('notifications')}
          className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === 'notifications'
            ? 'text-purple-600 border-b-2 border-purple-600'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
            }`}
        >
          <div className="flex items-center gap-1.5">
            <Bell className="w-3.5 h-3.5" />
            Notifications
          </div>
        </button>
        <button
          onClick={() => setActiveTab('advanced')}
          className={`px-3 py-1.5 text-xs font-medium transition-colors whitespace-nowrap ${activeTab === 'advanced'
            ? 'text-purple-600 border-b-2 border-purple-600'
            : 'text-gray-600 dark:text-gray-400 hover:text-gray-900'
            }`}
        >
          <div className="flex items-center gap-1.5">
            <Shield className="w-3.5 h-3.5" />
            Advanced
          </div>
        </button>
      </div>

      {/* Content */}
      {activeTab === 'general' && (
        <div className="space-y-4">
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">General Settings</h3>
            <div className="space-y-3">
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  Language
                </label>
                <Dropdown
                  options={[
                    { value: 'en', label: 'English' },
                    { value: 'th', label: 'ไทย (Thai)' },
                  ]}
                  value={preferences.language}
                  onChange={(value) => setPreferences({ ...preferences, language: value })}
                  size="sm"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-gray-700 dark:text-gray-300 mb-1.5">
                  Theme
                </label>
                <Dropdown
                  options={[
                    { value: 'system', label: 'System' },
                    { value: 'light', label: 'Light' },
                    { value: 'dark', label: 'Dark' },
                  ]}
                  value={preferences.theme}
                  onChange={(value) => setPreferences({ ...preferences, theme: value })}
                  size="sm"
                />
              </div>
              <div className="pt-2">
                <Button onClick={handleSavePreferences} isLoading={isLoading} size="sm">
                  Save Changes
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'api-keys' && (
        <APIKeysPage />
      )}

      {activeTab === 'notifications' && (
        <div className="space-y-4">
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">Notification Preferences</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2">
                <div>
                  <p className="text-sm font-medium">Trade Executions</p>
                  <p className="text-xs text-gray-500">Get notified when trades are executed</p>
                </div>
                <Toggle
                  checked={preferences.notifications.trade_executions}
                  onChange={(checked) => toggleNotification('trade_executions')}
                  size="sm"
                />
              </div>
              <div className="flex items-center justify-between py-2 border-t border-gray-200 dark:border-gray-700">
                <div>
                  <p className="text-sm font-medium">Price Alerts</p>
                  <p className="text-xs text-gray-500">Get notified when price targets are hit</p>
                </div>
                <Toggle
                  checked={preferences.notifications.price_alerts}
                  onChange={(checked) => toggleNotification('price_alerts')}
                  size="sm"
                />
              </div>
              <div className="pt-3">
                <Button onClick={handleSavePreferences} isLoading={isLoading} size="sm">
                  Save Preferences
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'advanced' && (
        <div className="space-y-4">
          {/* System Health Check */}
          <SystemHealthCheck />

          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">Advanced Settings</h3>
            <div className="space-y-3">
              {/* Export/Import Configuration */}
              <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                <h4 className="text-sm font-medium text-gray-900 dark:text-white mb-2">
                  Export / Import Configuration
                </h4>
                <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
                  Backup your bot configuration or import settings from another instance
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={async () => {
                      try {
                        const data = await api.exportConfig();
                        const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement('a');
                        a.href = url;
                        a.download = `trading-bot-config-${new Date().toISOString().split('T')[0]}.json`;
                        a.click();
                        URL.revokeObjectURL(url);
                        success('Configuration exported');
                      } catch (e) {
                        error('Failed to export configuration');
                      }
                    }}
                  >
                    Export Config
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      const input = document.createElement('input');
                      input.type = 'file';
                      input.accept = '.json';
                      input.onchange = async (e: any) => {
                        const file = e.target.files[0];
                        if (!file) return;
                        try {
                          const text = await file.text();
                          const config = JSON.parse(text);
                          await api.importConfig(config);
                          success('Configuration imported successfully');
                        } catch (e: any) {
                          error(e.message || 'Failed to import configuration');
                        }
                      };
                      input.click();
                    }}
                  >
                    Import Config
                  </Button>
                </div>
              </div>

              {/* Database Backup */}
              <div className="flex items-center justify-between py-2 border-t border-gray-200 dark:border-gray-700 pt-3">
                <div>
                  <p className="text-sm font-medium">Database Backup</p>
                  <p className="text-xs text-gray-500">Export your trading data</p>
                </div>
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={handleExportData}
                  isLoading={isLoading}
                >
                  Export
                </Button>
              </div>

              {/* Danger Zone */}
              <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="error">Danger Zone</Badge>
                </div>
                {resetConfirm ? (
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-gray-600 dark:text-gray-400">Reset all settings?</span>
                    <Button variant="danger" size="sm" onClick={handleResetSettings} isLoading={isLoading}>Yes, reset</Button>
                    <Button variant="secondary" size="sm" onClick={() => setResetConfirm(false)}>Cancel</Button>
                  </div>
                ) : (
                  <Button variant="danger" size="sm" onClick={() => setResetConfirm(true)} isLoading={isLoading}>
                    Reset All Settings
                  </Button>
                )}
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
