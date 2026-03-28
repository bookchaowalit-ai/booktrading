/**
 * Bot Control Page
 * Advanced bot control and monitoring
 */
'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/store/store';
import { Bot, Play, Square, Settings, Activity, ArrowRight } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';

export default function BotControlPage() {
  const { t, locale } = useTranslation();
  const botStatus = useAppStore((state) => state.botStatus);
  const refreshBotStatus = useAppStore((state) => state.refreshBotStatus);

  useEffect(() => {
    refreshBotStatus();
  }, [refreshBotStatus]);

  return (
    <div>
      {/* Trading Control Banner */}
      <Card variant="elevated" className="p-6 mb-8 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Settings className="w-8 h-8 text-purple-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Bot Controls
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Start/stop bot and configure settings from the centralized trading page
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="lg"
            onClick={() => window.location.href = `/${locale}/dashboard/trading`}
            rightIcon={<ArrowRight className="w-5 h-5" />}
            gradient
          >
            Go to Trading Page
          </Button>
        </div>
      </Card>

      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-3">
          <Bot className="w-8 h-8 text-purple-600" />
          {t('nav.bot')} - View Only
        </h1>
        <p className="text-gray-600 dark:text-gray-400">
          Monitor your bot status - Controls moved to Trading page
        </p>
      </div>

      {/* Status Overview */}
      <div className="grid md:grid-cols-3 gap-6 mb-8">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('bot.status-label')}</span>
          </div>
          <div className={`text-2xl font-bold ${botStatus?.isActive ? 'text-green-600' : 'text-gray-600 dark:text-gray-400'
            }`}>
            {botStatus?.isActive ? t('bot.running') : t('bot.stopped')}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3 mb-2">
            <Play className="w-5 h-5 text-green-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('bot.total-trades')}</span>
          </div>
          <div className="text-2xl font-bold text-green-600">
            {botStatus?.totalTrades || 0}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3 mb-2">
            <Settings className="w-5 h-5 text-purple-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('bot.total-profit')}</span>
          </div>
          <div className={`text-2xl font-bold ${(botStatus?.totalProfit || 0) >= 0 ? 'text-green-600' : 'text-red-600'
            }`}>
            ${(botStatus?.totalProfit || 0).toFixed(2)}
          </div>
        </div>
      </div>

      {/* Bot Status - View Only */}
      <div className="grid lg:grid-cols-2 gap-6">
        <Card variant="elevated" className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Bot Status
          </h2>
          <div className="space-y-4">
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <span className="text-gray-600 dark:text-gray-400">Status</span>
              <span className={`font-semibold ${botStatus?.isActive ? 'text-green-600' : 'text-gray-600'}`}>
                {botStatus?.isActive ? 'Running' : 'Stopped'}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <span className="text-gray-600 dark:text-gray-400">Total Trades</span>
              <span className="font-semibold text-gray-900 dark:text-white">
                {botStatus?.totalTrades || 0}
              </span>
            </div>
            <div className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-700 rounded-lg">
              <span className="text-gray-600 dark:text-gray-400">Total Profit</span>
              <span className={`font-semibold ${(botStatus?.totalProfit || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                ${(botStatus?.totalProfit || 0).toFixed(2)}
              </span>
            </div>
          </div>
        </Card>

        <Card variant="elevated" className="p-6">
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4">
            Quick Actions
          </h2>
          <div className="space-y-4">
            <Button
              variant="primary"
              fullWidth
              size="lg"
              onClick={() => window.location.href = `/${locale}/dashboard/trading`}
              rightIcon={<ArrowRight className="w-5 h-5" />}
            >
              Go to Trading Page
            </Button>
            <Button
              variant="secondary"
              fullWidth
              onClick={() => window.location.href = '/dashboard/settings/api-keys'}
            >
              Configure API Keys
            </Button>
            <Button
              variant="ghost"
              fullWidth
              onClick={() => window.location.href = '/dashboard/analytics'}
            >
              View Analytics
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}
