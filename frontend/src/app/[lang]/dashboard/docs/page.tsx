/**
 * Documentation Page
 * Simple placeholder for documentation
 */
'use client';

import { BookOpen, ExternalLink } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

export default function DocsPage() {
  const { t } = useTranslation();

  return (
    <div>
      <div className="bg-white dark:bg-gray-800 rounded-xl p-8 border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3 mb-6">
          <BookOpen className="w-8 h-8 text-purple-600" />
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">{t('docs.title')}</h1>
        </div>

        <div className="prose dark:prose-invert max-w-none">
          <p className="text-gray-600 dark:text-gray-400 mb-6">
            {t('docs.intro')}
          </p>

          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
            {t('docs.quick-start')}
          </h2>
          <ol className="list-decimal list-inside space-y-2 text-gray-700 dark:text-gray-300 mb-6">
            <li>{t('docs.step1')}</li>
            <li>{t('docs.step2')}</li>
            <li>{t('docs.step3')}</li>
            <li>{t('docs.step4')}</li>
            <li>{t('docs.step5')}</li>
          </ol>

          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
            {t('docs.features-title')}
          </h2>
          <ul className="list-disc list-inside space-y-2 text-gray-700 dark:text-gray-300 mb-6">
            <li>{t('docs.feat1')}</li>
            <li>{t('docs.feat2')}</li>
            <li>{t('docs.feat3')}</li>
            <li>{t('docs.feat4')}</li>
            <li>{t('docs.feat5')}</li>
            <li>{t('docs.feat6')}</li>
          </ul>

          <h2 className="text-2xl font-semibold text-gray-900 dark:text-white mb-4">
            {t('docs.external-resources')}
          </h2>
          <div className="space-y-4">
            <a
              href="https://github.com/golang-migrate/migrate"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-purple-600 hover:text-purple-700 dark:text-purple-400"
            >
              <ExternalLink className="w-4 h-4" />
              {t('docs.db-migrations')}
            </a>
            <a
              href="https://nextjs.org/docs"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 text-purple-600 hover:text-purple-700 dark:text-purple-400"
            >
              <ExternalLink className="w-4 h-4" />
              {t('docs.nextjs-docs')}
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
