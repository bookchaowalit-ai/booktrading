/**
 * Market Sentiment Pie Chart
 * Shows sentiment distribution across asset classes
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
import Card from '@/components/ui/Card';

interface MarketSentimentData {
  name: string;
  value: number;
  sentiment: number;
  color: string;
}

interface MarketSentimentPieChartProps {
  crypto: number;
  stocks: number;
  forex: number;
  commodities: number;
  height?: number;
}

export default function MarketSentimentPieChart({
  crypto,
  stocks,
  forex,
  commodities,
  height = 300,
}: MarketSentimentPieChartProps) {
  // Convert sentiment scores to chart data
  const data: MarketSentimentData[] = [
    {
      name: 'Crypto',
      value: Math.abs(crypto) * 100,
      sentiment: crypto,
      color: crypto >= 0.3 ? '#10B981' : crypto <= -0.3 ? '#EF4444' : '#F59E0B'
    },
    {
      name: 'Stocks',
      value: Math.abs(stocks) * 100,
      sentiment: stocks,
      color: stocks >= 0.3 ? '#10B981' : stocks <= -0.3 ? '#EF4444' : '#F59E0B'
    },
    {
      name: 'Forex',
      value: Math.abs(forex) * 100,
      sentiment: forex,
      color: forex >= 0.3 ? '#10B981' : forex <= -0.3 ? '#EF4444' : '#F59E0B'
    },
    {
      name: 'Commodities',
      value: Math.abs(commodities) * 100,
      sentiment: commodities,
      color: commodities >= 0.3 ? '#10B981' : commodities <= -0.3 ? '#EF4444' : '#F59E0B'
    },
  ];

  // Calculate average sentiment
  const avgSentiment = (crypto + stocks + forex + commodities) / 4;

  const getSentimentLabel = (score: number) => {
    if (score >= 0.7) return 'Very Bullish';
    if (score >= 0.3) return 'Bullish';
    if (score >= -0.3) return 'Neutral';
    if (score >= -0.7) return 'Bearish';
    return 'Very Bearish';
  };

  const CustomTooltip = ({ active, payload }: any) => {
    if (active && payload && payload.length) {
      const data = payload[0].payload;
      return (
        <div className="bg-gray-800 border border-gray-700 rounded-lg p-3 shadow-xl">
          <p className="text-sm font-semibold text-white mb-1">{data.name}</p>
          <p className="text-xs text-gray-400 mb-2">
            Sentiment: {getSentimentLabel(data.sentiment)}
          </p>
          <div className="flex items-center gap-2">
            <div className="text-2xl font-bold" style={{ color: data.color }}>
              {(data.sentiment * 100).toFixed(0)}%
            </div>
          </div>
        </div>
      );
    }
    return null;
  };

  return (
    <Card variant="elevated" className="p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Market Sentiment by Asset Class
      </h3>

      <div style={{ width: '100%', height }}>
        <ResponsiveContainer>
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="50%"
              innerRadius={60}
              outerRadius={100}
              paddingAngle={5}
              dataKey="value"
              animationDuration={1000}
            >
              {data.map((entry, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={entry.color}
                  stroke="rgba(255,255,255,0.2)"
                  strokeWidth={2}
                />
              ))}
            </Pie>
            <Tooltip
              content={<CustomTooltip />}
              contentStyle={{
                backgroundColor: '#1F2937',
                border: '1px solid #374151',
                borderRadius: '8px',
              }}
            />
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

      {/* Overall Sentiment */}
      <div className="mt-4 text-center">
        <p className="text-sm text-gray-600 dark:text-gray-400 mb-1">
          Overall Market Sentiment
        </p>
        <p
          className={`text-2xl font-bold ${avgSentiment >= 0.3 ? 'text-green-600' :
              avgSentiment <= -0.3 ? 'text-red-600' : 'text-gray-600'
            }`}
        >
          {getSentimentLabel(avgSentiment)}
        </p>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Score: {(avgSentiment * 100).toFixed(1)}%
        </p>
      </div>
    </Card>
  );
}
