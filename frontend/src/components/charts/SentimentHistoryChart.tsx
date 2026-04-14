/**
 * Sentiment History Chart
 * Shows sentiment score over time with trend analysis
 */
'use client';

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { SentimentHistory } from '@/types/news';
import Card from '@/components/ui/Card';

interface SentimentHistoryChartProps {
  data: SentimentHistory[];
  symbol?: string;
  height?: number;
}

export default function SentimentHistoryChart({
  data,
  symbol,
  height = 300,
}: SentimentHistoryChartProps) {
  // Format time for display
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  // Get gradient color based on sentiment
  const getGradientColor = (score: number) => {
    if (score >= 0.7) return '#10B981';
    if (score >= 0.3) return '#34D399';
    if (score >= -0.3) return '#9CA3AF';
    if (score >= -0.7) return '#F87171';
    return '#EF4444';
  };

  // Calculate statistics
  const avgSentiment = data.reduce((sum, item) => sum + item.sentiment, 0) / data.length;
  const maxSentiment = Math.max(...data.map(d => d.sentiment));
  const minSentiment = Math.min(...data.map(d => d.sentiment));
  const currentSentiment = data[data.length - 1]?.sentiment || 0;
  const trend = currentSentiment - (data[0]?.sentiment || 0);

  return (
    <Card variant="elevated" className="p-6">
      {/* Header Statistics */}
      <div className="grid grid-cols-4 gap-4 mb-6">
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Current</p>
          <p className={`text-lg font-bold ${currentSentiment >= 0.3 ? 'text-green-600' :
            currentSentiment <= -0.3 ? 'text-red-600' : 'text-gray-600'
            }`}>
            {(currentSentiment * 100).toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Average</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">
            {(avgSentiment * 100).toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">High</p>
          <p className="text-lg font-bold text-green-600">
            {(maxSentiment * 100).toFixed(0)}
          </p>
        </div>
        <div>
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Low</p>
          <p className="text-lg font-bold text-red-600">
            {(minSentiment * 100).toFixed(0)}
          </p>
        </div>
      </div>

      {/* Chart */}
      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <AreaChart
            data={data}
            margin={{ top: 10, right: 10, left: 0, bottom: 0 }}
          >
            <defs>
              <linearGradient id="sentimentGradient" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="5%"
                  stopColor={getGradientColor(currentSentiment)}
                  stopOpacity={0.3}
                />
                <stop
                  offset="95%"
                  stopColor={getGradientColor(currentSentiment)}
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>

            <CartesianGrid
              strokeDasharray="3 3"
              stroke="#374151"
              opacity={0.3}
              vertical={false}
            />

            <XAxis
              dataKey="timestamp"
              tickFormatter={formatTime}
              tick={{ fontSize: 12, fill: '#9CA3AF' }}
              axisLine={{ stroke: '#374151' }}
              tickLine={{ stroke: '#374151' }}
              minTickGap={30}
            />

            <YAxis
              domain={[-1, 1]}
              tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
              tick={{ fontSize: 12, fill: '#9CA3AF' }}
              axisLine={{ stroke: '#374151' }}
              tickLine={{ stroke: '#374151' }}
            />

            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
                color: '#F9FAFB',
                boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.5)',
              }}
              labelStyle={{ color: '#E5E7EB', fontWeight: '600' }}
              itemStyle={{ color: '#F9FAFB' }}
              labelFormatter={(label) => new Date(label).toLocaleString()}
              formatter={(value: number) => [
                `${(value * 100).toFixed(1)}%`,
                'Sentiment'
              ]}
            />

            {/* Zero line (neutral sentiment) */}
            <ReferenceLine
              y={0}
              stroke="#9CA3AF"
              strokeDasharray="3 3"
              label={{
                value: 'Neutral',
                fill: '#9CA3AF',
                fontSize: 12,
                position: 'right'
              }}
            />

            {/* Bullish threshold */}
            <ReferenceLine
              y={0.3}
              stroke="#10B981"
              strokeDasharray="3 3"
              opacity={0.5}
            />

            {/* Bearish threshold */}
            <ReferenceLine
              y={-0.3}
              stroke="#EF4444"
              strokeDasharray="3 3"
              opacity={0.5}
            />

            <Area
              type="monotone"
              dataKey="sentiment"
              stroke={getGradientColor(currentSentiment)}
              strokeWidth={2}
              fill="url(#sentimentGradient)"
              animationDuration={1500}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Trend Indicator */}
      <div className="mt-4 flex items-center justify-center gap-2">
        {trend > 0 ? (
          <div className="flex items-center gap-1 text-green-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M12 7l-5 5 5 5V7z" clipRule="evenodd" />
            </svg>
            <span className="font-medium">Uptrend</span>
          </div>
        ) : trend < 0 ? (
          <div className="flex items-center gap-1 text-red-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M8 13l5-5-5-5v10z" clipRule="evenodd" />
            </svg>
            <span className="font-medium">Downtrend</span>
          </div>
        ) : (
          <div className="text-gray-500">
            <span className="font-medium">Neutral</span>
          </div>
        )}
        <span className="text-sm text-gray-500 dark:text-gray-400">
          ({trend >= 0 ? '+' : ''}{(trend * 100).toFixed(1)}% in period)
        </span>
      </div>
    </Card>
  );
}
