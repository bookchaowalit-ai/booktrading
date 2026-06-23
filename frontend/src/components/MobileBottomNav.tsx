/**
 * Mobile Bottom Navigation
 * Mobile-friendly navigation bar
 */
'use client';

import { usePathname } from 'next/navigation';
import Link from 'next/link';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  FileText,
  Shield,
  FlaskConical,
  Cpu,
} from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

const navItems = [
  {
    id: 'command-center',
    labelKey: 'nav.commandCenter' as const,
    href: '/dashboard',
    icon: LayoutDashboard,
  },
  {
    id: 'daily-report',
    labelKey: 'nav.dailyReport' as const,
    href: '/dashboard/daily-report',
    icon: FileText,
  },
  {
    id: 'evidence',
    labelKey: 'nav.evidence' as const,
    href: '/dashboard/evidence',
    icon: Shield,
  },
  {
    id: 'research',
    labelKey: 'nav.research' as const,
    href: '/dashboard/research',
    icon: FlaskConical,
  },
  {
    id: 'system',
    labelKey: 'nav.system' as const,
    href: '/dashboard/system',
    icon: Cpu,
  },
];

export default function MobileBottomNav() {
  const pathname = usePathname();
  const { t } = useTranslation();

  // Extract locale from pathname
  const locale = pathname.split('/')[1] || 'th';

  return (
    <nav
      className="fixed bottom-0 left-0 right-0 bg-white/95 dark:bg-gray-950/95 backdrop-blur border-t border-gray-200 dark:border-gray-800 md:hidden z-50"
      style={{ paddingBottom: 'env(safe-area-inset-bottom)' }}
    >
      <div className="grid grid-cols-5 gap-1">
        {navItems.map((item) => {
          const Icon = item.icon;
          const href = `/${locale}${item.href}`;
          const isActive = pathname === href;

          return (
            <Link
              key={item.id}
              href={href}
              className={`flex flex-col items-center justify-center py-3 px-1 transition-colors ${isActive
                ? 'text-gray-950 dark:text-white'
                : 'text-gray-500 dark:text-gray-400'
                }`}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="relative">
                <Icon className="w-5 h-5" />
                {isActive && (
                  <motion.div
                    layoutId="mobile-nav-indicator"
                    className="absolute -bottom-1 left-1/2 -translate-x-1/2 w-1 h-1 bg-gray-950 dark:bg-white rounded-full"
                  />
                )}
              </div>
              <span className="text-[10px] mt-1 max-w-full truncate">{t(item.labelKey)}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
