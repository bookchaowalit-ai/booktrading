/**
 * Category Summary Cards Component
 * Displays portfolio summary by asset category
 */
'use client';

import { motion } from 'framer-motion';
import { Portfolio, AssetCategory, ASSET_CATEGORIES, getAssetCategory } from '@/types';
import CategoryIcon from './CategoryIcon';
import { DollarSign, TrendingUp, TrendingDown } from 'lucide-react';

interface CategorySummaryCardsProps {
  portfolio: Portfolio[];
  onCategoryClick?: (category: AssetCategory) => void;
}

interface CategorySummary {
  category: AssetCategory;
  totalValue: number;
  totalBalance: number;
  totalProfitLoss: number;
  profitLossPercent: number;
  assetCount: number;
}

export default function CategorySummaryCards({
  portfolio,
  onCategoryClick,
}: CategorySummaryCardsProps) {
  // Calculate summary by category
  const summaries: CategorySummary[] = ASSET_CATEGORIES.map((cat) => {
    const categoryAssets = portfolio.filter(
      (item) => (item.category || getAssetCategory(item.symbol)) === cat.id
    );

    const totalValue = categoryAssets.reduce((sum, item) => {
      const currentValue = item.currentValue || item.balance * item.avgBuyPrice;
      return sum + currentValue;
    }, 0);

    const totalCost = categoryAssets.reduce((sum, item) => {
      return sum + item.balance * item.avgBuyPrice;
    }, 0);

    const totalProfitLoss = totalValue - totalCost;
    const profitLossPercent = totalCost > 0 ? (totalProfitLoss / totalCost) * 100 : 0;

    return {
      category: cat.id,
      totalValue,
      totalBalance: categoryAssets.reduce((sum, item) => sum + item.balance, 0),
      totalProfitLoss,
      profitLossPercent,
      assetCount: categoryAssets.length,
    };
  }).filter((s) => s.totalValue > 0 || s.assetCount > 0);

  if (summaries.length === 0) {
    return null;
  }

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
      {summaries.map((summary, index) => {
        const isProfit = summary.totalProfitLoss >= 0;
        
        return (
          <motion.div
            key={summary.category}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
            whileHover={{ scale: 1.02, y: -2 }}
            onClick={() => onCategoryClick?.(summary.category)}
            className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700 cursor-pointer shadow-sm hover:shadow-md transition-all"
          >
            <div className="flex items-center justify-between mb-3">
              <CategoryIcon category={summary.category} size="sm" />
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {summary.assetCount} assets
              </span>
            </div>
            
            <div className="space-y-2">
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                ${summary.totalValue.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </div>
              
              <div className={`flex items-center gap-1 text-sm ${
                isProfit ? 'text-green-600' : 'text-red-600'
              }`}>
                {isProfit ? (
                  <TrendingUp className="w-3 h-3" />
                ) : (
                  <TrendingDown className="w-3 h-3" />
                )}
                <span className="font-medium">
                  {isProfit ? '+' : ''}{summary.totalProfitLoss.toFixed(2)} ({summary.profitLossPercent.toFixed(2)}%)
                </span>
              </div>
            </div>
          </motion.div>
        );
      })}
    </div>
  );
}
