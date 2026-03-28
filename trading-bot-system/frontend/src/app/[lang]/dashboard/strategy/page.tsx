/**
 * Strategy Page - Combined Intelligence Hub
 * Compact version with Shopify-style design
 */
'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Tabs } from '@/components/ui';
import { Brain, TrendingUp, BarChart3, Zap, Settings } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

type StrategyTab = 'overview' | 'sentiment' | 'backtest' | 'configuration';

export default function StrategyPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<StrategyTab>('overview');

  return (
    <div className="space-y-4">
      {/* Compact Header */}
      <div className="flex items-center gap-2">
        <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
          <Brain className="w-5 h-5 text-purple-600" />
        </div>
        <div>
          <h1 className="text-lg font-bold text-gray-900 dark:text-white">
            {t('strategy.title')}
          </h1>
          <p className="text-xs text-gray-600 dark:text-gray-400">
            {t('strategy.subtitle')}
          </p>
        </div>
      </div>

      {/* Compact Tabs */}
      <Tabs
        tabs={[
          { id: 'overview', label: t('strategy.ai-signals'), icon: <Zap className="w-3.5 h-3.5" /> },
          { id: 'sentiment', label: t('strategy.sentiment-score'), icon: <TrendingUp className="w-3.5 h-3.5" /> },
          { id: 'backtest', label: t('strategy.backtest-results'), icon: <BarChart3 className="w-3.5 h-3.5" /> },
          { id: 'configuration', label: t('strategy.configuration'), icon: <Settings className="w-3.5 h-3.5" /> },
        ]}
        activeTab={activeTab}
        onChange={(tab) => setActiveTab(tab as StrategyTab)}
        size="sm"
      />

      {/* Content */}
      {activeTab === 'overview' && (
        <div className="grid md:grid-cols-3 gap-3">
          <Card variant="elevated" className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-4 h-4 text-purple-600" />
              <h3 className="text-sm font-semibold">{t('strategy.ai-signals')}</h3>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
              {t('strategy.ai-signals-desc')}
            </p>
            <div className="text-2xl font-bold text-purple-600 mb-1">72%</div>
            <p className="text-xs text-gray-500">{t('strategy.accuracy')}</p>
          </Card>

          <Card variant="elevated" className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <TrendingUp className="w-4 h-4 text-green-600" />
              <h3 className="text-sm font-semibold">{t('strategy.sentiment-score')}</h3>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
              {t('strategy.sentiment-desc')}
            </p>
            <div className="text-2xl font-bold text-green-600 mb-1">+0.65</div>
            <p className="text-xs text-gray-500">{t('strategy.bullish')}</p>
          </Card>

          <Card variant="elevated" className="p-4">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="w-4 h-4 text-blue-600" />
              <h3 className="text-sm font-semibold">{t('strategy.backtest-results')}</h3>
            </div>
            <p className="text-xs text-gray-600 dark:text-gray-400 mb-3">
              {t('strategy.backtest-desc')}
            </p>
            <div className="text-2xl font-bold text-blue-600 mb-1">+127%</div>
            <p className="text-xs text-gray-500">{t('strategy.last-90-days')}</p>
          </Card>

          <Card variant="elevated" className="p-4 md:col-span-3">
            <h3 className="text-sm font-semibold mb-3">{t('strategy.quick-actions')}</h3>
            <div className="grid md:grid-cols-3 gap-3">
              <Button variant="secondary" fullWidth size="sm" leftIcon={<Brain className="w-3.5 h-3.5" />}>
                {t('strategy.view-ai')}
              </Button>
              <Button variant="secondary" fullWidth size="sm" leftIcon={<TrendingUp className="w-3.5 h-3.5" />}>
                {t('strategy.analyze-sentiment')}
              </Button>
              <Button variant="secondary" fullWidth size="sm" leftIcon={<BarChart3 className="w-3.5 h-3.5" />}>
                {t('strategy.run-backtest')}
              </Button>
            </div>
          </Card>
        </div>
      )}

      {activeTab === 'sentiment' && (
        <div className="space-y-3">
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">{t('strategy.sentiment-analysis')}</h3>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {t('strategy.sentiment-analysis-desc')}
            </p>
          </Card>
        </div>
      )}

      {activeTab === 'backtest' && (
        <div className="space-y-3">
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">{t('strategy.backtesting')}</h3>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {t('strategy.backtesting-desc')}
            </p>
          </Card>
        </div>
      )}

      {activeTab === 'configuration' && (
        <div className="space-y-3">
          <Card variant="elevated" className="p-4">
            <h3 className="text-sm font-semibold mb-3">{t('strategy.configuration')}</h3>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {t('strategy.configuration-desc')}
            </p>
          </Card>
        </div>
      )}
    </div>
  );
}
