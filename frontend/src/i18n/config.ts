/**
 * Internationalization (i18n) Configuration
 * Supports multiple languages for the trading bot interface
 */

export const locales = ['en', 'th'] as const;
export type Locale = (typeof locales)[number];

export const localeNames: Record<Locale, string> = {
  en: 'English',
  th: 'ไทย',
};

export const defaultLocale: Locale = 'th';

// Locale detection from browser
export function getBrowserLocale(): Locale {
  if (typeof window === 'undefined') return defaultLocale;
  
  const browserLang = navigator.language.toLowerCase();
  
  for (const locale of locales) {
    if (browserLang.startsWith(locale)) {
      return locale;
    }
  }
  
  return defaultLocale;
}

// Save/load preferred locale
export function setPreferredLocale(locale: Locale): void {
  localStorage.setItem('preferred_locale', locale);
}

export function getPreferredLocale(): Locale {
  if (typeof window === 'undefined') return defaultLocale;
  
  const saved = localStorage.getItem('preferred_locale') as Locale;
  if (saved && locales.includes(saved)) {
    return saved;
  }
  
  return getBrowserLocale();
}
