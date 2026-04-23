/**
 * News Page
 * Full-page crypto news feed with filters and sentiment analysis
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import EmptyState from '@/components/EmptyState';
import NewsFeed from '@/components/NewsFeed';
import { Newspaper } from 'lucide-react';
import { CompactListSkeleton } from '@/components/ui/Skeleton';

export default function NewsPage() {
    const { t } = useTranslation();
    const [isLoading, setIsLoading] = useState(true);

    useEffect(() => {
        // Give child component time to load
        const timer = setTimeout(() => setIsLoading(false), 1500);
        return () => clearTimeout(timer);
    }, []);

    if (isLoading) {
        return (
            <div className="p-6 space-y-4">
                <div className="space-y-2">
                    <div className="h-7 w-40 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                    <div className="h-4 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
                </div>
                <CompactListSkeleton items={8} />
            </div>
        );
    }

    return (
        <div className="p-6 space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {t('nav.news')}
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    Latest crypto news and market updates
                </p>
            </div>

            <NewsFeed showFilters={true} limit={20} />
        </div>
    );
}
