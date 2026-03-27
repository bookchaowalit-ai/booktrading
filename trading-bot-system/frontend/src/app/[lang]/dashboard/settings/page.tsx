/**
 * Settings Page - Consolidated Settings Hub
 * Combines: General Settings, API Keys, and Preferences
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { useToast } from '@/components/ui/Toast';
import { useTheme } from '@/contexts/ThemeProvider';
import { Settings, Key, Bell, Shield, Database } from 'lucide-react';
import { Toggle, Dropdown, Badge } from '@/components/ui';

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
  const { success, error } = useToast();
  const { theme: currentTheme, setTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<SettingsTab>('general');
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
  }, [preferences.theme]);

  const loadPreferences = async () => {
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
      const response = await fetch('http://localhost:8080/api/settings/preferences');
      if (response.ok) {
        const data = await response.json();
        setPreferences(data);
        // Also update localStorage to match backend
        localStorage.setItem('preferred_locale', data.language);
      }
    } catch (err) {
      console.error('Failed to load preferences from backend:', err);
    }
  };

  const handleSavePreferences = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/settings/preferences', {
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

        // Reload page if language changed to apply new language
        const currentLang = window.location.pathname.split('/')[1];
        if (currentLang !== preferences.language) {
          setTimeout(() => {
            window.location.href = `/${preferences.language}/dashboard/settings`;
          }, 1000);
        }
      } else {
        error('Failed to save settings');
      }
    } catch (err) {
      error('Failed to save settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleExportData = async () => {
    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/settings/export', {
        method: 'POST',
      });

      if (response.ok) {
        const data = await response.json();
        success(data.message || 'Data exported successfully');
      } else {
        error('Failed to export data');
      }
    } catch (err) {
      error('Failed to export data');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetSettings = async () => {
    if (!confirm('Are you sure? This will reset all settings to defaults.')) {
      return;
    }

    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/settings/reset', {
        method: 'POST',
      });

      if (response.ok) {
        success('Settings reset successfully');
        loadPreferences();
      } else {
        error('Failed to reset settings');
      }
    } catch (err) {
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
        <div className="space-y-6">
          <Card variant="elevated" className="p-6">
            <h3 className="text-lg font-semibold mb-4">Exchange API Keys</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400 mb-6">
              Configure your exchange API credentials for automated trading. Your keys are encrypted and stored securely.
            </p>

            {/* API Keys content - you can import the existing API Keys page component here */}
            <div className="text-center py-8">
              <Key className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
              <p className="text-gray-500 dark:text-gray-400">
                API Keys management interface
              </p>
              <p className="text-sm text-gray-400 mt-2">
                (Import from existing API Keys page)
              </p>
            </div>
          </Card>
        </div>
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
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">Advanced Settings</h3>
            <div className="space-y-3">
              <div className="flex items-center justify-between py-2">
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
              <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
                <div className="flex items-center gap-2 mb-2">
                  <Badge variant="error">Danger Zone</Badge>
                </div>
                <Button
                  variant="danger"
                  size="sm"
                  onClick={handleResetSettings}
                  isLoading={isLoading}
                >
                  Reset All Settings
                </Button>
              </div>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
