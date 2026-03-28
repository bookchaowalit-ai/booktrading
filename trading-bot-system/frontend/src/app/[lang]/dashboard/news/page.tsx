/**
 * News Page
 * Full-page crypto news feed with filters and sentiment analysis
 */
'use client';

import { useTranslation } from '@/i18n/translations';
import NewsFeed from '@/components/NewsFeed';

export default function NewsPage() {
    const { t } = useTranslation();

    return (
        <div className="p-6 space-y-6">
            <div>
                <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
                    {t('nav.news')}
                </h1>
                <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    {t('news.title')}
                </p>
            </div>

            <NewsFeed showFilters={true} limit={20} />
        </div>
    );
}
