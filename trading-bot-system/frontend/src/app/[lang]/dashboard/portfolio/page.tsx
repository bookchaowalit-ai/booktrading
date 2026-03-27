/**
 * Portfolio Page
 * View and manage your trading portfolio
 */
'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/store/store';
import PortfolioPanel from '@/components/PortfolioPanel';
import CategorySummaryCards from '@/components/CategorySummaryCards';
import { Wallet, TrendingUp, DollarSign } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

export default function PortfolioPage() {
  const { t } = useTranslation();
  const portfolio = useAppStore((state) => state.portfolio);
  const marketData = useAppStore((state) => state.marketData);
  const refreshPortfolio = useAppStore((state) => state.refreshPortfolio);

  useEffect(() => {
    refreshPortfolio();
  }, [refreshPortfolio]);

  // Calculate total portfolio value
  const totalValue = portfolio?.reduce((sum, item) => {
    const currentPrice = marketData[item.symbol]?.price || item.avgBuyPrice;
    return sum + (item.balance * currentPrice);
  }, 0) || 0;

  const totalBalance = portfolio?.reduce((sum, item) => sum + item.balance, 0) || 0;

  // Calculate total profit/loss
  const totalCost = portfolio?.reduce((sum, item) => sum + (item.balance * item.avgBuyPrice), 0) || 0;
  const totalProfitLoss = totalValue - totalCost;
  const totalProfitLossPercent = totalCost > 0 ? ((totalValue - totalCost) / totalCost) * 100 : 0;

  return (
    <div className="space-y-4">
      {/* Compact Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Wallet className="w-5 h-5 text-purple-600" />
          <div>
            <h1 className="text-lg font-bold text-gray-900 dark:text-white">
              {t('portfolio.title')}
            </h1>
            <p className="text-xs text-gray-600 dark:text-gray-400">
              {t('portfolio.subtitle')}
            </p>
          </div>
        </div>
      </div>

      {/* Compact Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <DollarSign className="w-3.5 h-3.5 text-green-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('portfolio.total-value')}</span>
          </div>
          <div className="text-lg font-bold text-green-600">
            ${totalValue.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-blue-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">Total P&L</span>
          </div>
          <div className={`text-sm font-bold ${totalProfitLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalProfitLoss >= 0 ? '+' : ''}${totalProfitLoss.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className={`text-xs ${totalProfitLoss >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {totalProfitLoss >= 0 ? '+' : ''}{totalProfitLossPercent.toFixed(2)}%
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-lg p-3 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1.5 mb-1">
            <TrendingUp className="w-3.5 h-3.5 text-purple-600" />
            <span className="text-xs text-gray-600 dark:text-gray-400">{t('portfolio.assets')}</span>
          </div>
          <div className="text-lg font-bold text-purple-600">
            {portfolio?.length || 0}
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-3 mb-2">
            <Wallet className="w-5 h-5 text-blue-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('portfolio.total-balance')}</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {totalBalance.toFixed(6)}
          </div>
        </div>
      </div>

      {/* Category Breakdown */}
      <CategorySummaryCards portfolio={portfolio} />

      {/* Portfolio Panel */}
      <PortfolioPanel />
    </div>
  );
}
