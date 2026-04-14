/**
 * Sentiment Analysis Page
 * Comprehensive sentiment analysis and news view
 */
'use client';

import { useState, useEffect } from 'react';
import SentimentDashboard from '@/components/SentimentDashboard';
import EmptyState from '@/components/EmptyState';
import { useTranslation } from '@/i18n/translations';
import { Activity } from 'lucide-react';

export default function SentimentPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);
  const [hasData, setHasData] = useState(true);

  useEffect(() => {
    // Give child component time to load
    const timer = setTimeout(() => setIsLoading(false), 1500);
    return () => clearTimeout(timer);
  }, []);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading...</p>
        </div>
      </div>
    );
  }

  if (!hasData) {
    return (
      <div className="space-y-4">
        <div className="mb-8">
          <div className="flex items-center gap-3 mb-2">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Activity className="w-8 h-8 text-purple-600" />
            </div>
            <div>
              <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
                {t('sentiment.title')}
              </h1>
              <p className="text-gray-600 dark:text-gray-400">
                AI-powered market sentiment analysis and trading signals
              </p>
            </div>
          </div>
        </div>
        <EmptyState
          icon={<Activity className="w-10 h-10 text-gray-400" />}
          title="No sentiment data yet"
          description="Sentiment analysis will appear once market data is available"
        />
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-3 mb-2">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Activity className="w-8 h-8 text-purple-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              {t('sentiment.title')}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              AI-powered market sentiment analysis and trading signals
            </p>
          </div>
        </div>
      </div>

      {/* Sentiment Dashboard */}
      <SentimentDashboard />
    </div>
  );
}
