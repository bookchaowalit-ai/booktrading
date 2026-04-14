/**
 * Asset Allocation Donut Chart
 * Shows portfolio allocation by asset category
 */
'use client';

import {
  PieChart,
  Pie,
  Cell,
  ResponsiveContainer,
  Legend,
  Tooltip,
} from 'recharts';
import { Portfolio } from '@/types';
import { getAssetCategory, ASSET_CATEGORIES } from '@/types';
import Card from '@/components/ui/Card';

interface AssetAllocationDonutChartProps {
  portfolio: Portfolio[];
  height?: number;
}

export default function AssetAllocationDonutChart({
  portfolio,
  height = 300,
}: AssetAllocationDonutChartProps) {
  // Calculate allocation by category
  const allocationByCategory = ASSET_CATEGORIES.map((category) => {
    const categoryAssets = portfolio.filter(
      (item) => getAssetCategory(item.symbol) === category.id
    );
    
    const totalValue = categoryAssets.reduce((sum, item) => {
      return sum + (item.balance * item.avgBuyPrice);
    }, 0);

    return {
      name: category.name,
      value: totalValue,
      color: category.color,
      count: categoryAssets.length,
    };
  }).filter(item => item.value > 0);

  // Calculate total portfolio value
  const totalValue = allocationByCategory.reduce((sum, item) => sum + item.value, 0);

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      const percentage = totalValue > 0 ? ((data.value / totalValue) * 100).toFixed(1) : 0;
      
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
          <p className="text-sm font-semibold text-white mb-1">{data.name}</p>
          <p className="text-xs text-gray-400 mb-2">
            {data.count} assets
          </p>
          <p className="text-lg font-bold" style={{ color: data.color }}>
            ${data.value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
          <p className="text-xs text-gray-400 mt-1">
            {percentage}% of portfolio
          </p>
        </div>
      );
    }
    return null;
  };

  if (portfolio.length === 0 || totalValue === 0) {
    return (
      <Card variant="elevated" className="p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Asset Allocation
        </h3>
        <div className="text-center py-12">
          <p className="text-gray-500 dark:text-gray-400">
            No portfolio data available
          </p>
        </div>
      </Card>
    );
  }

  return (
    <Card variant="elevated" className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Asset Allocation
      </h3>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={allocationByCategory}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={5}
              dataKey="value"
              animationDuration={1000}
            >
              {allocationByCategory.map((entry, index) => (
                <Cell 
                  key={`cell-${index}`} 
                  fill={entry.color}
                  stroke="rgba(255,255,255,0.2)"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
            <Legend 
              verticalAlign="bottom" 
              height={36}
              formatter={(value) => (
                <span className="text-sm text-gray-700 dark:text-gray-300">{value}</span>
              )}
            />
          </PieChart>
        </ResponsiveContainer>
      </div>

      {/* Allocation Summary */}
      <div className="mt-4 space-y-2">
        {allocationByCategory.map((item) => {
          const percentage = totalValue > 0 ? ((item.value / totalValue) * 100).toFixed(1) : 0;
          return (
            <div key={item.name} className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color }}
                />
                <span className="text-sm text-gray-700 dark:text-gray-300">
                  {item.name}
                </span>
              </div>
              <div className="text-right">
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {percentage}%
                </span>
                <span className="text-xs text-gray-500 dark:text-gray-400 ml-2">
                  (${item.value.toLocaleString(undefined, { maximumFractionDigits: 0 })})
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </Card>
  );
}
