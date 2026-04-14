/**
 * Signal Strength Bar Chart
 * Shows distribution of trading signals by strength
 */
'use client';

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from 'recharts';
import { TradingSignal } from '@/types/news';
import Card from '@/components/ui/Card';

interface SignalStrengthBarChartProps {
  signals: TradingSignal[];
  height?: number;
}

export default function SignalStrengthBarChart({
  signals,
  height = 300,
}: SignalStrengthBarChartProps) {
  // Group signals by strength
  const strengthCounts = {
    very_strong: signals.filter(s => s.strength === 'very_strong').length,
    strong: signals.filter(s => s.strength === 'strong').length,
    moderate: signals.filter(s => s.strength === 'moderate').length,
    weak: signals.filter(s => s.strength === 'weak').length,
  };

  const data = [
    { name: 'Very Strong', value: strengthCounts.very_strong, color: '#8B5CF6' },
    { name: 'Strong', value: strengthCounts.strong, color: '#10B981' },
    { name: 'Moderate', value: strengthCounts.moderate, color: '#F59E0B' },
    { name: 'Weak', value: strengthCounts.weak, color: '#9CA3AF' },
  ];

  // Group by direction
  const longSignals = signals.filter(s => s.direction === 'LONG').length;
  const shortSignals = signals.filter(s => s.direction === 'SHORT').length;

  const directionData = [
    { name: 'LONG', value: longSignals, color: '#10B981' },
    { name: 'SHORT', value: shortSignals, color: '#EF4444' },
  ];

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
          <p className="text-sm font-semibold text-white mb-1">{data.name}</p>
          <p className="text-2xl font-bold" style={{ color: data.color }}>
            {data.value}
          </p>
          <p className="text-xs text-gray-400 mt-1">signals</p>
        </div>
      );
    }
    return null;
  };

  return (
    <Card variant="elevated" className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-6">
        Trading Signals Analysis
      </h3>

      <div className="grid grid-cols-2 gap-6">
        {/* Signal Strength Distribution */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            By Strength
          </h4>
          <div style={{ width: '100%', height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={data} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 12, fill: '#9CA3AF' }}
                  axisLine={false}
                  tickLine={false}
                  width={70}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                  {data.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="right"
                    fill="#9CA3AF"
                    fontSize={12}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Direction Distribution */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-4">
            By Direction
          </h4>
          <div style={{ width: '100%', height: 200 }}>
            <ResponsiveContainer>
              <BarChart data={directionData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} horizontal={false} />
                <XAxis type="number" hide />
                <YAxis
                  dataKey="name"
                  type="category"
                  tick={{ fontSize: 12, fill: '#9CA3AF' }}
                  axisLine={false}
                  tickLine={false}
                  width={70}
                />
                <Tooltip content={<CustomTooltip />} />
                <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={20}>
                  {directionData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                  <LabelList
                    dataKey="value"
                    position="right"
                    fill="#9CA3AF"
                    fontSize={12}
                  />
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-700">
        <div className="grid grid-cols-3 gap-4 text-center">
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Signals</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {signals.length}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Strong Signals</p>
            <p className="text-2xl font-bold text-purple-600">
              {strengthCounts.very_strong + strengthCounts.strong}
            </p>
          </div>
          <div>
            <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Long/Short Ratio</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {longSignals > 0 && shortSignals > 0 
                ? (longSignals / shortSignals).toFixed(1)
                : longSignals > 0 ? '∞' : shortSignals > 0 ? '0' : '0'
              }:1
            </p>
          </div>
        </div>
      </div>
    </Card>
  );
}
