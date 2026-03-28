/**
 * Sidebar Navigation Component
 * Modern collapsible sidebar for dashboard navigation
 */
'use client';

import { useEffect } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  LayoutDashboard,
  Settings,
  Wallet,
  ChevronLeft,
  ChevronRight,
  Bot,
  BookOpen,
  Zap
} from 'lucide-react';
import { useTranslation, TranslationKey } from '@/i18n/translations';

interface NavItem {
  nameKey: TranslationKey;
  href: string;
  icon: React.ReactNode;
  badge?: number;
}

const navItems: NavItem[] = [
  {
    nameKey: 'nav.dashboard',
    href: '/dashboard',
    icon: <LayoutDashboard className="w-5 h-5" />
  },
  {
    nameKey: 'nav.trading',
    href: '/dashboard/trading',
    icon: <Zap className="w-5 h-5" />,
    badge: 0 // Active bot indicator
  },
  {
    nameKey: 'nav.portfolio',
    href: '/dashboard/portfolio',
    icon: <Wallet className="w-5 h-5" />
  },
  {
    nameKey: 'nav.strategy',
    href: '/dashboard/strategy',
    icon: <Bot className="w-5 h-5" />
  },
  {
    nameKey: 'nav.settings',
    href: '/dashboard/settings',
    icon: <Settings className="w-5 h-5" />
  }
];

const bottomNavItems: NavItem[] = [
  {
    nameKey: 'nav.docs',
    href: '/dashboard/docs',
    icon: <BookOpen className="w-5 h-5" />
  }
];

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  isMobileOpen: boolean;
  onMobileClose: () => void;
}

export default function Sidebar({ isCollapsed, onToggle, isMobileOpen, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useTranslation();

  // Extract locale from pathname, e.g. /en/dashboard → "en"
  const locale = pathname.split('/')[1] || 'th';

  // Close mobile menu when route changes
  useEffect(() => {
    onMobileClose();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  return (
    <div className="relative">
      {/* Mobile Overlay */}
      {isMobileOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onMobileClose}
          aria-hidden="true"
        />
      )}

      <motion.aside
        initial={false}
        animate={{ width: isCollapsed ? 80 : 280 }}
        className={`fixed left-0 top-0 h-screen bg-white dark:bg-gray-800 border-r border-gray-200 dark:border-gray-700 z-50 shadow-lg 
          transform transition-transform duration-300 lg:translate-x-0
          ${isMobileOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}
        `}
        role="navigation"
        aria-label="Main navigation"
      >
        {/* Mobile close button */}
        <button
          onClick={onMobileClose}
          className="lg:hidden absolute top-4 right-4 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
          aria-label="Close menu"
        >
          <ChevronLeft className="w-6 h-6" />
        </button>

        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-700">
          <motion.div
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            className="flex items-center gap-2 overflow-hidden"
          >
            <TrendingUp className="w-8 h-8 text-purple-600 flex-shrink-0" />
            <span className="text-xl font-bold text-gray-900 dark:text-white whitespace-nowrap">
              TradeBot Pro
            </span>
          </motion.div>
          <button
            onClick={onToggle}
            className="lg:p-2 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronLeft className="w-5 h-5 text-gray-500" />
            )}
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto" style={{ height: '100%' }}>
          {/* Main Navigation */}
          <ul className="space-y-2 list-none p-0 m-0">
            {navItems.map((item) => (
              <li key={item.nameKey}>
              <Link
                href={`/${locale}${item.href}`}
                aria-current={pathname === `/${locale}${item.href}` ? 'page' : undefined}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-colors relative ${pathname === `/${locale}${item.href}`
                  ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400'
                  : 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700'
                  }`}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                <motion.span
                  animate={{ opacity: isCollapsed ? 0 : 1 }}
                  className="whitespace-nowrap overflow-hidden flex-1"
                >
                  {t(item.nameKey)}
                </motion.span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="bg-red-500 text-white text-xs px-2 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
                {pathname === `/${locale}${item.href}` && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute left-0 top-0 bottom-0 w-1 bg-purple-600 rounded-r"
                  />
                )}
              </Link>
              </li>
            ))}
          </ul>

          {/* Bottom Navigation */}
          <div className="absolute bottom-4 left-0 right-0 px-4">
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
              {/* Documentation Link Only */}
              <Link
                key={bottomNavItems[0].nameKey}
                href={`/${locale}${bottomNavItems[0].href}`}
                className="flex items-center gap-3 px-4 py-3 rounded-lg text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
              >
                <span className="flex-shrink-0">{bottomNavItems[0].icon}</span>
                <motion.span
                  animate={{ opacity: isCollapsed ? 0 : 1 }}
                  className="whitespace-nowrap overflow-hidden"
                >
                  {t(bottomNavItems[0].nameKey)}
                </motion.span>
              </Link>
            </div>
          </div>
        </nav>
      </motion.aside>
    </div>
  );
}
