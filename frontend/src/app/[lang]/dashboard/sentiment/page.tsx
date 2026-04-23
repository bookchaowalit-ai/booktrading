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
import { ChartSkeleton, CompactListSkeleton } from '@/components/ui/Skeleton';

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
      <div className="p-6 space-y-6">
        {/* Header Skeleton */}
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="space-y-2">
            <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-4 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        </div>
        {/* Sentiment Gauges Skeleton */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
              <div className="h-4 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse mb-4" />
              <div className="w-32 h-32 mx-auto bg-gray-200 dark:bg-gray-700 rounded-full animate-pulse" />
            </div>
          ))}
        </div>
        {/* News List Skeleton */}
        <CompactListSkeleton items={5} />
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
