/**
 * Sidebar Navigation Component
 * Modern collapsible sidebar with grouped menu and sub-menus
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  LayoutDashboard,
  Settings,
  Wallet,
  Bitcoin,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  Bot,
  BookOpen,
  Zap,
  Newspaper,
  PiggyBank,
  Calculator,
  Target,
  BookMarked,
  Sparkles,
  BarChart3,
  Clock,
  Grid3x3,
  Repeat,
  Users,
  Shield,
  Eye,
  TestTube,
  AlertTriangle,
  Landmark,
  Building2,
  Flag,
  ArrowLeftRight,
} from 'lucide-react';
import { useTranslation, TranslationKey } from '@/i18n/translations';

interface NavItem {
  nameKey: TranslationKey;
  href: string;
  icon: React.ReactNode;
  badge?: number;
}

interface MenuGroup {
  groupKey: TranslationKey;
  icon: React.ReactNode;
  items: NavItem[];
}

const menuGroups: MenuGroup[] = [
  {
    groupKey: 'menu.core',
    icon: <LayoutDashboard className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.dashboard', href: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
      { nameKey: 'nav.trading', href: '/dashboard/trading', icon: <Zap className="w-5 h-5" />, badge: 0 },
      { nameKey: 'nav.portfolio', href: '/dashboard/portfolio', icon: <Wallet className="w-5 h-5" /> },
      { nameKey: 'nav.wallet', href: '/dashboard/wallet', icon: <Bitcoin className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.strategy',
    icon: <Bot className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.strategy', href: '/dashboard/strategy', icon: <Bot className="w-5 h-5" /> },
      { nameKey: 'nav.dex', href: '/dashboard/dex', icon: <ArrowLeftRight className="w-5 h-5" /> },
      { nameKey: 'nav.gridTrading', href: '/dashboard/grid-trading', icon: <Grid3x3 className="w-5 h-5" /> },
      { nameKey: 'nav.dca', href: '/dashboard/dca', icon: <Repeat className="w-5 h-5" /> },
      { nameKey: 'nav.copyTrading', href: '/dashboard/copy-trading', icon: <Users className="w-5 h-5" /> },
      { nameKey: 'nav.rebalancing', href: '/dashboard/rebalancing', icon: <Landmark className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.analysis',
    icon: <BarChart3 className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.ai-insights', href: '/dashboard/ai-insights', icon: <Sparkles className="w-5 h-5" /> },
      { nameKey: 'nav.analytics', href: '/dashboard/analytics', icon: <BarChart3 className="w-5 h-5" /> },
      { nameKey: 'nav.sentiment', href: '/dashboard/sentiment', icon: <Eye className="w-5 h-5" /> },
      { nameKey: 'nav.backtest', href: '/dashboard/backtest', icon: <TestTube className="w-5 h-5" /> },
      { nameKey: 'nav.riskManagement', href: '/dashboard/risk-management', icon: <Shield className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.finance',
    icon: <PiggyBank className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.finance', href: '/dashboard/finance', icon: <PiggyBank className="w-5 h-5" /> },
      { nameKey: 'nav.financeAccounts', href: '/dashboard/finance/accounts', icon: <Building2 className="w-5 h-5" /> },
      { nameKey: 'nav.financeAssets', href: '/dashboard/finance/assets', icon: <Landmark className="w-5 h-5" /> },
      { nameKey: 'nav.financeBudgets', href: '/dashboard/finance/budgets', icon: <Target className="w-5 h-5" /> },
      { nameKey: 'nav.financeGoals', href: '/dashboard/finance/goals', icon: <Flag className="w-5 h-5" /> },
      { nameKey: 'nav.financeDiary', href: '/dashboard/finance/diary', icon: <BookMarked className="w-5 h-5" /> },
      { nameKey: 'nav.financeCalculators', href: '/dashboard/finance/calculators', icon: <Calculator className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.activity',
    icon: <Clock className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.history', href: '/dashboard/history', icon: <Clock className="w-5 h-5" /> },
      { nameKey: 'nav.alerts', href: '/dashboard/alerts', icon: <AlertTriangle className="w-5 h-5" /> },
      { nameKey: 'nav.paperTrading', href: '/dashboard/paper-trading', icon: <TestTube className="w-5 h-5" /> },
      { nameKey: 'nav.news', href: '/dashboard/news', icon: <Newspaper className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.system',
    icon: <Settings className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.settings', href: '/dashboard/settings', icon: <Settings className="w-5 h-5" /> },
    ],
  },
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

  // Track which groups are expanded
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const activeGroups = new Set<string>();
    const locale = pathname.split('/')[1] || 'th';
    for (const group of menuGroups) {
      const isActive = group.items.some((item) => pathname === `/${locale}${item.href}`);
      if (isActive) activeGroups.add(group.groupKey);
    }
    return activeGroups;
  });

  // Extract locale from pathname
  const locale = pathname.split('/')[1] || 'th';

  // Close mobile menu when route changes
  useEffect(() => {
    onMobileClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Auto-expand group when a child is active
  useEffect(() => {
    for (const group of menuGroups) {
      const isActive = group.items.some((item) => pathname === `/${locale}${item.href}`);
      if (isActive) {
        setExpandedGroups((prev) => new Set(prev).add(group.groupKey));
      }
    }
  }, [pathname, locale]);

  const toggleGroup = (groupKey: string) => {
    setExpandedGroups((prev) => {
      const next = new Set(prev);
      if (next.has(groupKey)) {
        next.delete(groupKey);
      } else {
        next.add(groupKey);
      }
      return next;
    });
  };

  const isActiveItem = (href: string) => pathname === `/${locale}${href}`;

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
        <nav className="flex-1 overflow-y-auto py-4" style={{ height: 'calc(100% - 73px - 65px)' }}>
          {menuGroups.map((group) => {
            const isExpanded = expandedGroups.has(group.groupKey);
            const hasActiveChild = group.items.some((item) => isActiveItem(item.href));

            return (
              <div key={group.groupKey} className="mb-2">
                {/* Group Header */}
                <button
                  onClick={() => toggleGroup(group.groupKey)}
                  className={`w-full flex items-center gap-3 px-4 py-2 text-xs font-semibold uppercase tracking-wider transition-colors
                    ${hasActiveChild
                      ? 'text-purple-600 dark:text-purple-400'
                      : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400'
                    }
                    ${isCollapsed ? 'justify-center' : ''}
                  `}
                  title={isCollapsed ? t(group.groupKey) : undefined}
                >
                  <span className="flex-shrink-0">{group.icon}</span>
                  <motion.span
                    animate={{ opacity: isCollapsed ? 0 : 1, width: isCollapsed ? 0 : 'auto' }}
                    className="whitespace-nowrap overflow-hidden flex-1 text-left"
                  >
                    {t(group.groupKey)}
                  </motion.span>
                  {!isCollapsed && (
                    <ChevronDown
                      className={`w-4 h-4 flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                    />
                  )}
                </button>

                {/* Group Items */}
                <AnimatePresence initial={false}>
                  {isExpanded && !isCollapsed && (
                    <motion.ul
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: 'auto', opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.2 }}
                      className="overflow-hidden list-none p-0 m-0 space-y-0.5 px-2"
                    >
                      {group.items.map((item) => (
                        <li key={item.nameKey}>
                          <Link
                            href={`/${locale}${item.href}`}
                            aria-current={isActiveItem(item.href) ? 'page' : undefined}
                            className={`flex items-center gap-3 px-3 py-2 rounded-lg transition-colors relative text-sm
                              ${isActiveItem(item.href)
                                ? 'bg-purple-100 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 font-medium'
                                : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-200'
                              }`}
                          >
                            <span className="flex-shrink-0">{item.icon}</span>
                            <span className="whitespace-nowrap overflow-hidden flex-1 truncate">
                              {t(item.nameKey)}
                            </span>
                            {item.badge !== undefined && item.badge > 0 && (
                              <span className="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">
                                {item.badge}
                              </span>
                            )}
                          </Link>
                        </li>
                      ))}
                    </motion.ul>
                  )}
                </AnimatePresence>
              </div>
            );
          })}
        </nav>

        {/* Bottom Navigation */}
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-4">
          <div className="border-t border-gray-200 dark:border-gray-700 pt-3">
            <Link
              href={`/${locale}/dashboard/docs`}
              className={`flex items-center gap-3 px-4 py-2 rounded-lg text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-700 hover:text-gray-900 dark:hover:text-gray-200 transition-colors text-sm
                ${isCollapsed ? 'justify-center' : ''}
              `}
              title={isCollapsed ? t('nav.docs') : undefined}
            >
              <span className="flex-shrink-0"><BookOpen className="w-5 h-5" /></span>
              <motion.span
                animate={{ opacity: isCollapsed ? 0 : 1, width: isCollapsed ? 0 : 'auto' }}
                className="whitespace-nowrap overflow-hidden"
              >
                {t('nav.docs')}
              </motion.span>
            </Link>
          </div>
        </div>
      </motion.aside>
    </div>
  );
}
