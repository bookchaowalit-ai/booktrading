/**
 * Category Icon Component
 * Displays appropriate icon based on asset category
 */
'use client';

import { Bitcoin, Building, Coins, Box, TrendingUp } from 'lucide-react';
import { AssetCategory, getCategoryInfo } from '@/types';

interface CategoryIconProps {
  category: AssetCategory;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  showLabel?: boolean;
}

export default function CategoryIcon({
  category,
  size = 'md',
  className = '',
  showLabel = false,
}: CategoryIconProps) {
  const categoryInfo = getCategoryInfo(category);
  
  const sizeClasses = {
    sm: 'w-4 h-4',
    md: 'w-6 h-6',
    lg: 'w-8 h-8',
  };

  const icons: Record<AssetCategory, React.ReactNode> = {
    crypto: <Bitcoin className={sizeClasses[size]} />,
    stock: <Building className={sizeClasses[size]} />,
    forex: <Coins className={sizeClasses[size]} />,
    commodity: <Box className={sizeClasses[size]} />,
    index: <TrendingUp className={sizeClasses[size]} />,
  };

  return (
    <div
      className={`inline-flex items-center gap-2 ${className}`}
    >
      <span
        className={`inline-flex items-center justify-center rounded-full ${showLabel ? 'p-1' : 'p-2'}`}
        style={{
          backgroundColor: `${categoryInfo.color}20`,
          color: categoryInfo.color,
        }}
      >
        {icons[category]}
      </span>
      {showLabel && (
        <span className="text-sm font-medium" style={{ color: categoryInfo.color }}>
          {categoryInfo.name}
        </span>
      )}
    </div>
  );
}
