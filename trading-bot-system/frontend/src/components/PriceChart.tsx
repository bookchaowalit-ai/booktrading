/**
 * Price Chart Component using Recharts.
 * Displays real-time price data with candlestick or line chart.
 */
'use client';

import { useEffect, useState } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import { useMarketData, useIndicators, useRSIStatus } from '@/hooks';
import { MarketData } from '@/types';

interface PriceChartProps {
  symbol: string;
  height?: number;
}

export default function PriceChart({ symbol, height = 300 }: PriceChartProps) {
  const marketData = useMarketData(symbol);
  const indicators = useIndicators(symbol);
  const rsiStatus = useRSIStatus(indicators?.rsi ?? null);
  
  const [chartData, setChartData] = useState<Array<MarketData & { time: string }>>([]);

  // Update chart data when new market data arrives
  useEffect(() => {
    if (marketData) {
      setChartData((prev) => {
        const newData = [...prev, { ...marketData, time: new Date(marketData.timestamp).toLocaleTimeString() }];
        // Keep last 50 data points
        return newData.slice(-50);
      });
    }
  }, [marketData]);

  const currentPrice = marketData?.price ?? 0;
  const previousPrice = chartData.length > 1 ? chartData[chartData.length - 2]?.price : currentPrice;
  const priceChange = currentPrice - previousPrice;
  const priceChangePercent = previousPrice > 0 ? (priceChange / previousPrice) * 100 : 0;

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <div className="flex justify-between items-center mb-4">
        <div>
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">{symbol}</h3>
          <div className="flex items-center gap-2">
            <span className="text-2xl font-bold text-gray-900 dark:text-white">
              ${currentPrice.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
            </span>
            <span className={`text-sm font-medium ${priceChange >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {priceChange >= 0 ? '+' : ''}{priceChange.toFixed(2)} ({priceChangePercent.toFixed(2)}%)
            </span>
          </div>
        </div>
        
        {indicators?.rsi && (
          <div className={`px-3 py-1 rounded-full text-sm font-medium bg-${rsiStatus.color}-100 text-${rsiStatus.color}-800`}>
            RSI: {indicators.rsi.toFixed(2)} ({rsiStatus.status})
          </div>
        )}
      </div>
      
      <div style={{ height: `${height}px` }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={chartData}>
            <CartesianGrid strokeDasharray="3 3" stroke="#374151" opacity={0.3} />
            <XAxis 
              dataKey="time" 
              stroke="#9CA3AF"
              tick={{ fontSize: 12 }}
            />
            <YAxis 
              stroke="#9CA3AF"
              tick={{ fontSize: 12 }}
              domain={['auto', 'auto']}
            />
            <Tooltip
              contentStyle={{
                backgroundColor: '#1F2937',
                border: 'none',
                borderRadius: '8px',
                color: '#F9FAFB',
              }}
              formatter={(value: number) => [`$${value.toFixed(2)}`, 'Price']}
            />
            {indicators?.ema && (
              <ReferenceLine 
                y={indicators.ema} 
                stroke="#F59E0B" 
                strokeDasharray="3 3"
                label={{ value: `EMA: ${indicators.ema}`, fill: '#F59E0B', fontSize: 12 }}
              />
            )}
            <Line 
              type="monotone" 
              dataKey="price" 
              stroke={priceChange >= 0 ? '#10B981' : '#EF4444'} 
              strokeWidth={2}
              dot={false}
              animationDuration={300}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
