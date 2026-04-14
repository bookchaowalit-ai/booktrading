/**
 * Portfolio Panel Component.
 * Displays current portfolio holdings with category filtering.
 */
'use client';

import { useEffect, useState, useMemo } from 'react';
import { useAppStore } from '@/store/store';
import { AssetCategory, getAssetCategory, getCategoryInfo } from '@/types';
import AssetCategoryFilter from './AssetCategoryFilter';
import CategoryIcon from './CategoryIcon';
import { TrendingUp, TrendingDown, RefreshCw, Search } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from './ui/Toast';
import EmptyState, { NoHoldingsEmptyState } from './EmptyState';
import { TableSkeleton } from './ui/Skeleton';
import Button from './ui/Button';

export default function PortfolioPanel() {
  const { t } = useTranslation();
  const { success } = useToast();
  const portfolio = useAppStore((state) => state.portfolio);
  const marketData = useAppStore((state) => state.marketData);
  const refreshPortfolio = useAppStore((state) => state.refreshPortfolio);

  const [selectedCategories, setSelectedCategories] = useState<AssetCategory[]>(
    ['crypto', 'stock', 'forex', 'commodity', 'index']
  );
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'value' | 'name' | 'profit'>('value');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshPortfolio]);

  // Filter and sort portfolio
  const filteredPortfolio = useMemo(() => {
    if (!portfolio) return [];

    let filtered = portfolio.filter((item) => {
      const category = item.category || getAssetCategory(item.symbol);
      const matchesCategory = selectedCategories.includes(category);
      const matchesSearch = item.symbol.toLowerCase().includes(searchQuery.toLowerCase());
      return matchesCategory && matchesSearch;
    });

    // Sort
    filtered.sort((a, b) => {
      const aValue = a.balance * a.avgBuyPrice;
      const bValue = b.balance * b.avgBuyPrice;

      let comparison = 0;
      if (sortBy === 'value') {
        comparison = bValue - aValue;
      } else if (sortBy === 'name') {
        comparison = a.symbol.localeCompare(b.symbol);
      } else if (sortBy === 'profit') {
        const aPrice = marketData[a.symbol]?.price || a.avgBuyPrice;
        const bPrice = marketData[b.symbol]?.price || b.avgBuyPrice;
        const aProfit = (aPrice - a.avgBuyPrice) * a.balance;
        const bProfit = (bPrice - b.avgBuyPrice) * b.balance;
        comparison = bProfit - aProfit;
      }

      return sortOrder === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [portfolio, selectedCategories, searchQuery, sortBy, sortOrder, marketData]);

  const handleCategoryToggle = (category: AssetCategory) => {
    setSelectedCategories((prev) => {
      if (prev.includes(category)) {
        return prev.filter((c) => c !== category);
      }
      return [...prev, category];
    });
  };

  const handleSelectAll = () => {
    setSelectedCategories(['crypto', 'stock', 'forex', 'commodity', 'index']);
  };

  const handleRefresh = async () => {
    setIsLoading(true);
    await refreshPortfolio();
    setIsLoading(false);
    success('Portfolio refreshed');
  };

  const handleStartTrading = () => {
    // Navigate to grid trading or show modal
    success('Navigate to Grid Trading to start');
  };

  const formatCurrency = (value: number) => {
    return value.toLocaleString(undefined, {
      style: 'currency',
      currency: 'USD',
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  };

  const calculatePnL = (item: typeof portfolio[0]) => {
    const currentPrice = marketData[item.symbol]?.price || item.avgBuyPrice;
    const pnl = (currentPrice - item.avgBuyPrice) * item.balance;
    const pnlPercent = ((currentPrice - item.avgBuyPrice) / item.avgBuyPrice) * 100;
    return { pnl, pnlPercent, currentPrice };
  };

  const toggleSort = (field: 'value' | 'name' | 'profit') => {
    if (sortBy === field) {
      setSortOrder(sortOrder === 'asc' ? 'desc' : 'asc');
    } else {
      setSortBy(field);
      setSortOrder('desc');
    }
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-xl shadow-lg p-6 border border-gray-200 dark:border-gray-700">
      <div className="flex justify-between items-center mb-6">
        <h2 className="text-xl font-semibold text-gray-900 dark:text-white flex items-center gap-2">
          {t('portfolio.title')}
        </h2>
        <Button
          onClick={handleRefresh}
          variant="ghost"
          size="sm"
          isLoading={isLoading}
          leftIcon={<RefreshCw className="w-4 h-4" />}
        >
          Refresh
        </Button>
      </div>

      {/* Category Filter */}
      <div className="mb-4">
        <AssetCategoryFilter
          selectedCategories={selectedCategories}
          onCategoryToggle={handleCategoryToggle}
          onSelectAll={handleSelectAll}
        />
      </div>

      {/* Search Bar */}
      <div className="mb-6">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400" />
          <input
            type="text"
            placeholder={t('portfolio.search')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 rounded-lg border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-purple-500 focus:border-transparent transition-all"
          />
        </div>
      </div>

      {isLoading ? (
        <TableSkeleton rows={5} />
      ) : !portfolio || portfolio.length === 0 ? (
        <NoHoldingsEmptyState onAction={handleStartTrading} />
      ) : filteredPortfolio.length === 0 ? (
        <EmptyState
          title={t('portfolio.no-match')}
          description="Try adjusting your filters or search query"
          action={{
            label: "Clear Filters",
            onClick: handleSelectAll,
          }}
        />
      ) : (
        <div className="space-y-3">
          {/* Header */}
          <div className="grid grid-cols-12 gap-4 px-4 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 uppercase tracking-wider border-b border-gray-200 dark:border-gray-700">
            <div className="col-span-3 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300" onClick={() => toggleSort('name')}>
              Asset {sortBy === 'name' && (sortOrder === 'asc' ? '↑' : '↓')}
            </div>
            <div className="col-span-2 text-right">Category</div>
            <div className="col-span-2 text-right cursor-pointer hover:text-gray-700 dark:hover:text-gray-300" onClick={() => toggleSort('value')}>
              Balance {sortBy === 'value' && (sortOrder === 'asc' ? '↑' : '↓')}
            </div>
            <div className="col-span-2 text-right">Price</div>
            <div className="col-span-3 text-right cursor-pointer hover:text-gray-700 dark:hover:text-gray-300" onClick={() => toggleSort('profit')}>
              P&L {sortBy === 'profit' && (sortOrder === 'asc' ? '↑' : '↓')}
            </div>
          </div>

          {/* Portfolio Items */}
          {filteredPortfolio.map((item) => {
            const { pnl, pnlPercent, currentPrice } = calculatePnL(item);
            const isProfit = pnl >= 0;
            const category = item.category || getAssetCategory(item.symbol);

            return (
              <div
                key={item.symbol}
                className="grid grid-cols-12 gap-4 px-4 py-3 bg-gray-50 dark:bg-gray-700 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-600 transition-colors items-center"
              >
                <div className="col-span-3">
                  <div className="flex items-center gap-2">
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {item.symbol}
                    </span>
                  </div>
                </div>
                <div className="col-span-2 flex justify-end">
                  <CategoryIcon category={category} size="sm" />
                </div>
                <div className="col-span-2 text-right">
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    {item.balance.toFixed(6)}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Locked: {item.locked.toFixed(4)}
                  </div>
                </div>
                <div className="col-span-2 text-right">
                  <div className="text-sm font-medium text-gray-900 dark:text-white">
                    {formatCurrency(currentPrice)}
                  </div>
                  <div className="text-xs text-gray-500 dark:text-gray-400">
                    Avg: {formatCurrency(item.avgBuyPrice)}
                  </div>
                </div>
                <div className="col-span-3 text-right">
                  <div className={`flex items-center justify-end gap-1 ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                    {isProfit ? (
                      <TrendingUp className="w-4 h-4" />
                    ) : (
                      <TrendingDown className="w-4 h-4" />
                    )}
                    <span className="font-medium">
                      {isProfit ? '+' : ''}{formatCurrency(pnl)}
                    </span>
                  </div>
                  <div className={`text-xs ${isProfit ? 'text-green-600' : 'text-red-600'}`}>
                    {isProfit ? '+' : ''}{pnlPercent.toFixed(2)}%
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
