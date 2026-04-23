/**
 * Dashboard Page - Enhanced UI/UX
 * Main trading bot dashboard with real-time monitoring
 */
'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAppStore } from '@/store/store';
import { useWebSocket, useAutoRefresh } from '@/hooks';
import PriceChart from '@/components/PriceChart';
import TechnicalIndicatorsPanel from '@/components/TechnicalIndicatorsPanel';
import PortfolioPanel from '@/components/PortfolioPanel';
import TradeHistoryPanel from '@/components/TradeHistoryPanel';
import CategorySummaryCards from '@/components/CategorySummaryCards';
import StatCard from '@/components/StatCard';
import EmptyState from '@/components/EmptyState';
import { AssetCategory } from '@/types';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import { api } from '@/services/api';
import { Tabs } from '@/components/ui';
import { DollarSign, TrendingUp, Activity, Wallet, BarChart3, Zap, ArrowRight, Settings, LayoutDashboard, RefreshCw, Bitcoin } from 'lucide-react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { CompactStatsGridSkeleton, ChartSkeleton, PortfolioItemSkeleton } from '@/components/ui/Skeleton';

const SYMBOLS = ['BTCUSDT', 'ETHUSDT'];

export default function Dashboard() {
  const { t } = useTranslation();
  const { success, error } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const portfolio = useAppStore((state) => state.portfolio);
  const botStatus = useAppStore((state) => state.botStatus);
  const [activeCategory, setActiveCategory] = useState<AssetCategory | null>(null);
  const [activeTab, setActiveTab] = useState<'overview' | 'portfolio' | 'trades'>('overview');
  const [isLoading, setIsLoading] = useState(true);
  const [walletBalances, setWalletBalances] = useState<{ totalTHB: number; totalUSDT: number; exchangeCount: number } | null>(null);

  // Initialize WebSocket connection for real-time updates
  useWebSocket();

  // Auto-refresh data every 5 seconds
  useAutoRefresh(5000);

  const refreshBotStatus = useAppStore((state) => state.refreshBotStatus);
  const refreshIndicators = useAppStore((state) => state.refreshIndicators);
  const [winRate, setWinRate] = useState(0);

  useEffect(() => {
    const init = async () => {
      try {
        await Promise.allSettled([refreshBotStatus(), refreshIndicators()]);
      } catch (err) {
        error('Failed to load bot status');
      } finally {
        setIsLoading(false);
      }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Fetch win rate from performance API
  useEffect(() => {
    import('@/services/api').then(({ api }) => {
      api.getPerformance()
        .then((p) => setWinRate(p.winRate || 0))
        .catch(() => setWinRate(0));
    });
  }, []);

  // Fetch wallet balances (lightweight, cached)
  useEffect(() => {
    api.getAllBalances()
      .then((data) => {
        console.log('[Dashboard] Wallet balances:', data);
        setWalletBalances({
          totalTHB: data.totalTHB,
          totalUSDT: data.totalUSDT,
          exchangeCount: data.exchangeCount,
        });
      })
      .catch((err) => {
        console.warn('[Dashboard] Wallet fetch failed:', err);
        error('Failed to load wallet balances');
      });
  }, []);

  // Calculate portfolio metrics
  const totalValue = portfolio?.reduce((sum, item) => {
    return sum + (item.balance * item.avgBuyPrice);
  }, 0) || 0;

  const totalProfit = botStatus?.totalProfit || 0;
  const totalTrades = botStatus?.totalTrades || 0;

  if (isLoading) {
    return (
      <div className="space-y-4">
        {/* Trading Control Banner Skeleton */}
        <div className="p-4 bg-gray-100 dark:bg-gray-800 rounded-xl">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-gray-200 dark:bg-gray-700 rounded-md animate-pulse" />
            <div className="flex-1 space-y-2">
              <div className="h-4 w-32 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              <div className="h-3 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            </div>
          </div>
        </div>

        {/* Stats Grid Skeleton */}
        <CompactStatsGridSkeleton />

        {/* Category Summary Skeleton */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
              <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
              <div className="h-6 w-24 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            </div>
          ))}
        </div>

        {/* Main Grid Skeleton */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2">
            <ChartSkeleton height={300} />
          </div>
          <div>
            <PortfolioItemSkeleton count={4} />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Compact Trading Control Banner */}
      <Card variant="elevated" className="p-4 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-md">
              <Settings className="w-5 h-5 text-purple-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-gray-900 dark:text-white">
                Trading Controls
              </h2>
              <p className="text-xs text-gray-600 dark:text-gray-400">
                Start/stop trading and configure strategy
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="sm"
            onClick={() => router.push(`/${locale}/dashboard/trading`)}
            gradient
          >
            Configure
          </Button>
        </div>
      </Card>

      {/* Compact Stats Grid */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
        <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Total Value</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            ${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <TrendingUp className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Profit</span>
          </div>
          <div className={`text-lg font-bold ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-gray-500 mt-1">all time</div>
        </div>

        <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Trades</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">{totalTrades}</div>
          <div className="text-xs text-blue-600 mt-1">{winRate}% win rate</div>
        </div>

        <div className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Wallet className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Portfolio</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">{portfolio?.length || 0}</div>
          <div className="text-xs text-gray-500 mt-1">items</div>
        </div>

        {/* Wallet Balances */}
        <button
          onClick={() => router.push(`/${locale}/dashboard/wallet`)}
          className="p-3 bg-gradient-to-br from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20 rounded-lg border border-purple-200 dark:border-purple-800 hover:border-purple-300 dark:hover:border-purple-700 transition-colors cursor-pointer group"
        >
          <div className="flex items-center gap-2 mb-1">
            <Bitcoin className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Wallet</span>
            {walletBalances?.exchangeCount !== undefined && (
              <span className="ml-auto text-[10px] text-gray-400">{walletBalances.exchangeCount} exh</span>
            )}
          </div>
          {!walletBalances ? (
            <div className="text-sm font-bold text-gray-400">Loading...</div>
          ) : walletBalances.totalTHB > 0 || walletBalances.totalUSDT > 0 ? (
            <div className="space-y-1">
              {walletBalances.totalTHB > 0 && (
                <div className="text-sm font-bold text-green-600 dark:text-green-400">
                  ฿{walletBalances.totalTHB.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
              )}
              {walletBalances.totalUSDT > 0 && (
                <div className="text-sm font-bold text-blue-600 dark:text-blue-400">
                  ${walletBalances.totalUSDT.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </div>
              )}
            </div>
          ) : (
            <div className="text-sm font-bold text-gray-400">No balance</div>
          )}
          <div className="text-[10px] text-purple-400 mt-1 group-hover:text-purple-600 dark:group-hover:text-purple-300 flex items-center gap-1">
            View All <ArrowRight className="w-3 h-3" />
          </div>
        </button>
      </div>

      {/* Category Summary Cards */}
      {portfolio && portfolio.length > 0 && (
        <div>
          <div className="flex items-center gap-3 mb-4">
            <BarChart3 className="w-5 h-5 text-purple-600" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Allocation by Category
            </h2>
          </div>
          <CategorySummaryCards
            portfolio={portfolio}
            onCategoryClick={setActiveCategory}
          />
        </div>
      )}

      {/* Main Grid Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Portfolio */}
        <div className="space-y-6">
          <PortfolioPanel />
        </div>

        {/* Middle Column - Charts */}
        <div className="lg:col-span-2 space-y-6">
          {SYMBOLS.map((symbol) => (
            <PriceChart key={symbol} symbol={symbol} />
          ))}
        </div>
      </div>

      {/* Technical Indicators */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <BarChart3 className="w-5 h-5 text-purple-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Technical Analysis
          </h2>
        </div>
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {SYMBOLS.map((symbol) => (
            <TechnicalIndicatorsPanel key={symbol} symbol={symbol} />
          ))}
        </div>
      </div>

      {/* Trade History */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <Activity className="w-5 h-5 text-purple-600" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Recent Trades
          </h2>
        </div>
        <TradeHistoryPanel />
      </div>
    </div>
  );
}
