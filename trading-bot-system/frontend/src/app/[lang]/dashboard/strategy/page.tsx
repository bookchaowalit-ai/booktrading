/**
 * Strategy Page - Combined Intelligence Hub
 * Compact version with Shopify-style design
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { Tabs } from '@/components/ui';
import { Brain, TrendingUp, BarChart3, Zap, Settings } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

type StrategyTab = 'overview' | 'sentiment' | 'backtest' | 'configuration';

interface StrategyStats {
  accuracy: number;
  sentiment: number;
  backtestReturn: number;
}

export default function StrategyPage() {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<StrategyTab>('overview');
  const [stats, setStats] = useState<StrategyStats>({
    accuracy: 0,
    sentiment: 0,
    backtestReturn: 0,
  });
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || 'http://localhost:8000';
    const fetchStats = async () => {
      try {
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 90);
        const fmt = (d: Date) => d.toISOString().slice(0, 10);

        const [signalsRes, indicatorsRes, backtestRes] = await Promise.all([
          fetch(`${STRATEGY_URL}/api/signals`).catch(() => null),
          fetch(`${STRATEGY_URL}/api/indicators`).catch(() => null),
          fetch(`${STRATEGY_URL}/api/backtest`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ symbol: 'BTCUSDT', start_date: fmt(start), end_date: fmt(end), initial_capital: 10000 }),
          }).catch(() => null),
        ]);
        const signalsData = signalsRes ? await signalsRes.json().catch(() => null) : null;
        const indicatorsData = indicatorsRes ? await indicatorsRes.json().catch(() => null) : null;
        const backtestData = backtestRes?.ok ? await backtestRes.json().catch(() => null) : null;

        if (signalsData) {
          const signals: any[] = signalsData.signals || [];
          const accuracy = signals.length > 0
            ? Math.round((signals.filter((s: any) => s.strength > 0.6).length / signals.length) * 100)
            : 0;
          const lastSentiment = signalsData.market_sentiment ?? (indicatorsData?.sentiment ?? 0);
          setStats((prev) => ({
            ...prev,
            accuracy,
            sentiment: lastSentiment,
            backtestReturn: backtestData?.total_return_percent ?? prev.backtestReturn,
          }));
        } else if (backtestData) {
          setStats((prev) => ({ ...prev, backtestReturn: backtestData.total_return_percent ?? prev.backtestReturn }));
        }
      } catch {
        // keep defaults on error
      } finally {
        setIsLoading(false);
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 30000);
    return () => clearInterval(interval);
  }, []);

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
            <div className="text-2xl font-bold text-purple-600 mb-1">
              {isLoading ? '—' : `${stats.accuracy}%`}
            </div>
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
            <div className="text-2xl font-bold text-green-600 mb-1">
              {isLoading ? '—' : `${stats.sentiment >= 0 ? '+' : ''}${stats.sentiment.toFixed(2)}`}
            </div>
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
            <div className="text-2xl font-bold text-blue-600 mb-1">
              {isLoading ? '—' : stats.backtestReturn !== 0 ? `${stats.backtestReturn >= 0 ? '+' : ''}${stats.backtestReturn.toFixed(1)}%` : '—'}
            </div>
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
