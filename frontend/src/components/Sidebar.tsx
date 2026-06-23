/**
 * Sidebar Navigation Component
 * AI Command Center — 5 main pages + Advanced group
 */
'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LayoutDashboard,
  Settings,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  BookOpen,
  FileText,
  Shield,
  FlaskConical,
  Cpu,
  Zap,
  Grid3x3,
  Repeat,
  ArrowLeftRight,
  Landmark,
  Users,
  Target,
  Wallet,
  Bitcoin,
  PiggyBank,
  Building2,
  Flag,
  BookMarked,
  Calculator,
  TestTube,
  BarChart3,
  Eye,
  Crosshair,
  Sparkles,
  Monitor,
  Clock,
  AlertTriangle,
  Newspaper,
  TrendingUp,
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

// Main navigation — always visible (5 pages)
const mainNav: NavItem[] = [
  { nameKey: 'nav.commandCenter', href: '/dashboard', icon: <LayoutDashboard className="w-5 h-5" /> },
  { nameKey: 'nav.dailyReport', href: '/dashboard/daily-report', icon: <FileText className="w-5 h-5" /> },
  { nameKey: 'nav.evidence', href: '/dashboard/evidence', icon: <Shield className="w-5 h-5" /> },
  { nameKey: 'nav.research', href: '/dashboard/research', icon: <FlaskConical className="w-5 h-5" /> },
  { nameKey: 'nav.system', href: '/dashboard/system', icon: <Cpu className="w-5 h-5" /> },
];

// Advanced pages — hidden unless NEXT_PUBLIC_ADVANCED_UI=true
const advancedGroups: MenuGroup[] = [
  {
    groupKey: 'menu.trading',
    icon: <Zap className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.trading', href: '/dashboard/trading', icon: <Zap className="w-5 h-5" /> },
      { nameKey: 'nav.gridTrading', href: '/dashboard/grid-trading', icon: <Grid3x3 className="w-5 h-5" /> },
      { nameKey: 'nav.dca', href: '/dashboard/dca', icon: <Repeat className="w-5 h-5" /> },
      { nameKey: 'nav.dex', href: '/dashboard/dex', icon: <ArrowLeftRight className="w-5 h-5" /> },
      { nameKey: 'nav.copyTrading', href: '/dashboard/copy-trading', icon: <Users className="w-5 h-5" /> },
      { nameKey: 'nav.rebalancing', href: '/dashboard/rebalancing', icon: <Landmark className="w-5 h-5" /> },
      { nameKey: 'nav.polyPaper', href: '/dashboard/polymarket', icon: <Target className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.finance',
    icon: <PiggyBank className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.wallet', href: '/dashboard/wallet', icon: <Bitcoin className="w-5 h-5" /> },
      { nameKey: 'nav.portfolio', href: '/dashboard/portfolio', icon: <Wallet className="w-5 h-5" /> },
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
    groupKey: 'menu.analysis',
    icon: <BarChart3 className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.ai-insights', href: '/dashboard/ai-insights', icon: <Sparkles className="w-5 h-5" /> },
      { nameKey: 'nav.analytics', href: '/dashboard/analytics', icon: <BarChart3 className="w-5 h-5" /> },
      { nameKey: 'nav.sentiment', href: '/dashboard/sentiment', icon: <Eye className="w-5 h-5" /> },
      { nameKey: 'nav.marketIntel', href: '/dashboard/market-intel', icon: <Crosshair className="w-5 h-5" /> },
      { nameKey: 'nav.tradeJournal', href: '/dashboard/trade-journal', icon: <BookOpen className="w-5 h-5" /> },
      { nameKey: 'nav.backtest', href: '/dashboard/backtest', icon: <TestTube className="w-5 h-5" /> },
      { nameKey: 'nav.monitoring', href: '/dashboard/monitoring', icon: <Monitor className="w-5 h-5" /> },
      { nameKey: 'nav.riskManagement', href: '/dashboard/risk-management', icon: <Shield className="w-5 h-5" /> },
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
      { nameKey: 'nav.strategy', href: '/dashboard/strategy', icon: <TrendingUp className="w-5 h-5" /> },
    ],
  },
  {
    groupKey: 'menu.settings',
    icon: <Settings className="w-4 h-4" />,
    items: [
      { nameKey: 'nav.settings', href: '/dashboard/settings', icon: <Settings className="w-5 h-5" /> },
    ],
  },
];

const isAdvancedUI = () => {
  if (typeof window === 'undefined') return false;
  return process.env.NEXT_PUBLIC_ADVANCED_UI === 'true';
};

interface SidebarProps {
  isCollapsed: boolean;
  onToggle: () => void;
  isMobileOpen: boolean;
  onMobileClose: () => void;
}

export default function Sidebar({ isCollapsed, onToggle, isMobileOpen, onMobileClose }: SidebarProps) {
  const pathname = usePathname();
  const { t } = useTranslation();
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Track which advanced groups are expanded
  const [expandedGroups, setExpandedGroups] = useState<Set<string>>(() => {
    const activeGroups = new Set<string>();
    const locale = pathname.split('/')[1] || 'th';
    for (const group of advancedGroups) {
      const isActive = group.items.some((item) => pathname === `/${locale}${item.href}`);
      if (isActive) {
        activeGroups.add(group.groupKey);
        setShowAdvanced(true);
      }
    }
    return activeGroups;
  });

  const locale = pathname.split('/')[1] || 'th';
  const advancedEnabled = isAdvancedUI();

  // Close mobile menu when route changes
  useEffect(() => {
    onMobileClose();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Auto-expand group when a child is active
  useEffect(() => {
    for (const group of advancedGroups) {
      const isActive = group.items.some((item) => pathname === `/${locale}${item.href}`);
      if (isActive) {
        setExpandedGroups((prev) => new Set(prev).add(group.groupKey));
        setShowAdvanced(true);
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
        className={`fixed left-0 top-0 h-screen bg-white dark:bg-gray-950 border-r border-gray-200 dark:border-gray-800 z-50
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
        <div className="flex items-center justify-between p-4 border-b border-gray-200 dark:border-gray-800">
          <motion.div
            animate={{ opacity: isCollapsed ? 0 : 1 }}
            className="flex items-center gap-2 overflow-hidden"
          >
            <span className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-gray-950 text-white dark:bg-white dark:text-gray-950">
              <Cpu className="w-5 h-5" />
            </span>
            <div className="flex flex-col">
              <span className="text-sm font-semibold text-gray-950 dark:text-white whitespace-nowrap leading-tight">
                {t('brand.name')}
              </span>
              <span className="text-[10px] text-gray-500 dark:text-gray-400 whitespace-nowrap leading-tight">
                {t('brand.mode')}
              </span>
            </div>
          </motion.div>
          <button
            onClick={onToggle}
            className="lg:p-2 p-3 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-900 transition-colors"
            aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          >
            {isCollapsed ? (
              <ChevronRight className="w-5 h-5 text-gray-500" />
            ) : (
              <ChevronLeft className="w-5 h-5 text-gray-500" />
            )}
          </button>
        </div>

        {/* Main Navigation */}
        <nav className="flex-1 overflow-y-auto py-4" style={{ height: 'calc(100% - 73px - 65px)' }}>
          <div className="px-2 mb-4">
            {mainNav.map((item) => (
              <Link
                key={item.nameKey}
                href={`/${locale}${item.href}`}
                aria-current={isActiveItem(item.href) ? 'page' : undefined}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-md transition-colors mb-0.5 text-sm
                  ${isActiveItem(item.href)
                    ? 'bg-gray-950 text-white dark:bg-white dark:text-gray-950 font-medium'
                    : 'text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900 hover:text-gray-950 dark:hover:text-gray-100'
                  }
                  ${isCollapsed ? 'justify-center' : ''}
                `}
                title={isCollapsed ? t(item.nameKey) : undefined}
              >
                <span className="flex-shrink-0">{item.icon}</span>
                <motion.span
                  animate={{ opacity: isCollapsed ? 0 : 1, width: isCollapsed ? 0 : 'auto' }}
                  className="whitespace-nowrap overflow-hidden flex-1 truncate"
                >
                  {t(item.nameKey)}
                </motion.span>
                {item.badge !== undefined && item.badge > 0 && (
                  <span className="bg-red-500 text-white text-[10px] px-1.5 py-0.5 rounded-full">
                    {item.badge}
                  </span>
                )}
              </Link>
            ))}
          </div>

          {/* Advanced Section */}
          {advancedEnabled && (
            <div className="border-t border-gray-200 dark:border-gray-800 pt-3 mt-3 px-2">
              <button
                onClick={() => setShowAdvanced(!showAdvanced)}
                className={`w-full flex items-center gap-2 px-3 py-2 mb-2 text-xs font-semibold uppercase tracking-wider transition-colors
                  text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400
                  ${isCollapsed ? 'justify-center' : ''}
                `}
                title={isCollapsed ? t('menu.advanced') : undefined}
              >
                <Settings className="w-3.5 h-3.5 flex-shrink-0" />
                <motion.span
                  animate={{ opacity: isCollapsed ? 0 : 1, width: isCollapsed ? 0 : 'auto' }}
                  className="whitespace-nowrap overflow-hidden flex-1 text-left"
                >
                  {t('menu.advanced')}
                </motion.span>
                {!isCollapsed && (
                  <ChevronDown
                    className={`w-3 h-3 flex-shrink-0 transition-transform duration-200 ${showAdvanced ? 'rotate-180' : ''}`}
                  />
                )}
              </button>

              <AnimatePresence initial={false}>
                {showAdvanced && !isCollapsed && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: 'auto', opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.2 }}
                    className="overflow-hidden"
                  >
                    {advancedGroups.map((group) => {
                      const isExpanded = expandedGroups.has(group.groupKey);
                      const hasActiveChild = group.items.some((item) => isActiveItem(item.href));

                      return (
                        <div key={group.groupKey} className="mb-2">
                          <button
                            onClick={() => toggleGroup(group.groupKey)}
                            className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs font-medium transition-colors
                              ${hasActiveChild
                                ? 'text-gray-950 dark:text-white'
                                : 'text-gray-400 dark:text-gray-500 hover:text-gray-600 dark:hover:text-gray-400'
                              }
                            `}
                          >
                            <span className="flex-shrink-0">{group.icon}</span>
                            <span className="whitespace-nowrap overflow-hidden flex-1 text-left text-[11px]">
                              {t(group.groupKey)}
                            </span>
                            <ChevronDown
                              className={`w-3 h-3 flex-shrink-0 transition-transform duration-200 ${isExpanded ? 'rotate-180' : ''}`}
                            />
                          </button>

                          <AnimatePresence initial={false}>
                            {isExpanded && (
                              <motion.ul
                                initial={{ height: 0, opacity: 0 }}
                                animate={{ height: 'auto', opacity: 1 }}
                                exit={{ height: 0, opacity: 0 }}
                                transition={{ duration: 0.15 }}
                                className="overflow-hidden list-none p-0 m-0 space-y-0.5"
                              >
                                {group.items.map((item) => (
                                  <li key={item.nameKey}>
                                    <Link
                                      href={`/${locale}${item.href}`}
                                      aria-current={isActiveItem(item.href) ? 'page' : undefined}
                                      className={`flex items-center gap-2 px-3 py-1.5 rounded-lg transition-colors text-xs
                                        ${isActiveItem(item.href)
                                          ? 'bg-gray-100 dark:bg-gray-900 text-gray-950 dark:text-white font-medium'
                                          : 'text-gray-500 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900 hover:text-gray-950 dark:hover:text-gray-100'
                                        }`}
                                    >
                                      <span className="flex-shrink-0 w-4 h-4">{item.icon}</span>
                                      <span className="whitespace-nowrap overflow-hidden flex-1 truncate">
                                        {t(item.nameKey)}
                                      </span>
                                    </Link>
                                  </li>
                                ))}
                              </motion.ul>
                            )}
                          </AnimatePresence>
                        </div>
                      );
                    })}
                  </motion.div>
                )}
              </AnimatePresence>
            </div>
          )}
        </nav>

        {/* Bottom Navigation */}
        <div className="absolute bottom-0 left-0 right-0 px-4 pb-4">
          <div className="border-t border-gray-200 dark:border-gray-800 pt-3">
            <Link
              href={`/${locale}/dashboard/docs`}
              className={`flex items-center gap-3 px-4 py-2 rounded-md text-gray-600 dark:text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-900 hover:text-gray-950 dark:hover:text-gray-100 transition-colors text-sm
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
