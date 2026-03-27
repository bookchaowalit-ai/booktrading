/**
 * Sentiment Analysis Page
 * Comprehensive sentiment analysis and news view
 */
'use client';

import SentimentDashboard from '@/components/SentimentDashboard';
import { useTranslation } from '@/i18n/translations';
import { Activity } from 'lucide-react';

export default function SentimentPage() {
  const { t } = useTranslation();

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
