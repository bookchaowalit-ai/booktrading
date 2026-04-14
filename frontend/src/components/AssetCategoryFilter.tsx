/**
 * Asset Category Filter Component
 * Allows users to filter assets by category with visual indicators
 */
'use client';

import { motion } from 'framer-motion';
import { ASSET_CATEGORIES, AssetCategory } from '@/types';
import { Bitcoin, Building, Coins, Box, TrendingUp, Globe } from 'lucide-react';
import { useTranslation } from '@/i18n/translations';

interface AssetCategoryFilterProps {
  selectedCategories: AssetCategory[];
  onCategoryToggle: (category: AssetCategory) => void;
  onSelectAll: () => void;
  className?: string;
}

const categoryIcons: Record<AssetCategory, React.ReactNode> = {
  crypto: <Bitcoin className="w-4 h-4" />,
  stock: <Building className="w-4 h-4" />,
  forex: <Coins className="w-4 h-4" />,
  commodity: <Box className="w-4 h-4" />,
  index: <TrendingUp className="w-4 h-4" />,
};

export default function AssetCategoryFilter({
  selectedCategories,
  onCategoryToggle,
  onSelectAll,
  className = '',
}: AssetCategoryFilterProps) {
  const { t } = useTranslation();
  const allSelected = selectedCategories.length === ASSET_CATEGORIES.length;

  return (
    <div className={`flex flex-wrap gap-2 ${className}`}>
      {/* All Button */}
      <motion.button
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        onClick={onSelectAll}
        className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 ${allSelected
          ? 'bg-gradient-to-r from-purple-600 to-blue-600 text-white shadow-lg'
          : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700'
          }`}
      >
        <Globe className="w-4 h-4" />
        {t('category.all')}
      </motion.button>

      {/* Category Buttons */}
      {ASSET_CATEGORIES.map((category) => {
        const isSelected = selectedCategories.includes(category.id);

        return (
          <motion.button
            key={category.id}
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={() => onCategoryToggle(category.id)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all flex items-center gap-2 border-2 ${isSelected
              ? 'text-white shadow-lg'
              : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 border-transparent hover:border-gray-300 dark:hover:border-gray-600'
              }`}
            style={{
              backgroundColor: isSelected ? category.color : undefined,
              borderColor: isSelected ? category.color : undefined,
            }}
          >
            {categoryIcons[category.id]}
            {t(`category.${category.id}`)}
          </motion.button>
        );
      })}
    </div>
  );
}
