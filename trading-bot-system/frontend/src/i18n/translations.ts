/**
 * Translation Utilities and Hooks
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { usePathname } from 'next/navigation';
import { Locale, defaultLocale, locales, getPreferredLocale, setPreferredLocale } from './config';
import { en, TranslationKey as EnKey } from './translations/en';
import { th, TranslationKey as ThKey } from './translations/th';

type TranslationKeys = EnKey | ThKey;

const translations: Record<Locale, Record<string, string>> = {
  en,
  th,
  zh: {}, // Chinese - not implemented yet
  ja: {}, // Japanese - not implemented yet
};

/** Extract locale from a URL pathname like /th/dashboard → "th" */
function localeFromPathname(pathname: string): Locale {
  const seg = pathname.split('/')[1] as Locale;
  return locales.includes(seg) ? seg : defaultLocale;
}

export function useTranslation(locale?: Locale) {
  const pathname = usePathname();

  const [currentLocale, setCurrentLocale] = useState<Locale>(
    locale ?? localeFromPathname(pathname) ?? defaultLocale
  );

  useEffect(() => {
    // Locale from URL is the source of truth
    const urlLocale = localeFromPathname(pathname);
    if (locale) {
      setCurrentLocale(locale);
    } else if (urlLocale) {
      setCurrentLocale(urlLocale);
    } else {
      const preferred = getPreferredLocale();
      if (preferred) setCurrentLocale(preferred);
    }
  }, [locale, pathname]);

  const t = useCallback(
    (key: TranslationKeys, params?: Record<string, string | number>) => {
      const localeTranslations = translations[currentLocale] || translations[defaultLocale];
      let translation = localeTranslations[key] || key;

      // Replace parameters
      if (params) {
        Object.entries(params).forEach(([paramKey, value]) => {
          translation = translation.replace(
            new RegExp(`\\{${paramKey}\\}`, 'g'),
            String(value)
          );
        });
      }

      return translation;
    },
    [currentLocale]
  );

  const changeLocale = useCallback((newLocale: Locale) => {
    setCurrentLocale(newLocale);
    setPreferredLocale(newLocale);
  }, []);

  return {
    t,
    locale: currentLocale,
    changeLocale,
  };
}

// Export TranslationKey type for use in components
export type TranslationKey = TranslationKeys;

// Helper to get all available locales
export function getAvailableLocales() {
  return [
    { code: 'en', name: 'English', nativeName: 'English' },
    { code: 'th', name: 'Thai', nativeName: 'ไทย' },
  ];
}

// Helper to format numbers based on locale
export function formatNumber(value: number, locale?: Locale, options?: Intl.NumberFormatOptions) {
  const loc = locale || defaultLocale;
  return new Intl.NumberFormat(loc === 'zh' ? 'zh-CN' : loc, options).format(value);
}

// Helper to format currency based on locale
export function formatCurrency(
  value: number,
  currency: string = 'USD',
  locale?: Locale
) {
  const loc = locale || defaultLocale;
  return new Intl.NumberFormat(loc === 'zh' ? 'zh-CN' : loc, {
    style: 'currency',
    currency,
  }).format(value);
}

// Helper to format dates based on locale
export function formatDate(date: Date | string, locale?: Locale, options?: Intl.DateTimeFormatOptions) {
  const loc = locale || defaultLocale;
  const dateObj = typeof date === 'string' ? new Date(date) : date;
  return new Intl.DateTimeFormat(loc === 'zh' ? 'zh-CN' : loc, options).format(dateObj);
}
