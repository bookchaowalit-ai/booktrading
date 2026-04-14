/**
 * Technical Indicators Panel Component.
 * Displays RSI, EMA, and other technical indicators.
 */
'use client';

import { useIndicators, useRSIStatus } from '@/hooks';

interface TechnicalIndicatorsPanelProps {
  symbol: string;
}

export default function TechnicalIndicatorsPanel({ symbol }: TechnicalIndicatorsPanelProps) {
  const indicators = useIndicators(symbol);
  const rsiStatus = useRSIStatus(indicators?.rsi ?? null);

  if (!indicators) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
          Technical Indicators - {symbol}
        </h3>
        <p className="text-gray-500 dark:text-gray-400">Loading indicators...</p>
      </div>
    );
  }

  const getRSIColor = () => {
    if (indicators.rsi === null) return 'text-gray-400';
    if (indicators.rsi < 30) return 'text-green-600';
    if (indicators.rsi > 70) return 'text-red-600';
    return 'text-gray-600';
  };

  const getRSIBgColor = () => {
    if (indicators.rsi === null) return 'bg-gray-100 dark:bg-gray-700';
    if (indicators.rsi < 30) return 'bg-green-100 dark:bg-green-900';
    if (indicators.rsi > 70) return 'bg-red-100 dark:bg-red-900';
    return 'bg-gray-100 dark:bg-gray-700';
  };

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
        Technical Indicators - {symbol}
      </h3>
      
      <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
        {/* RSI */}
        <div className={`${getRSIBgColor()} rounded-lg p-4`}>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">RSI (14)</p>
          <p className={`text-2xl font-bold ${getRSIColor()}`}>
            {indicators.rsi?.toFixed(2) ?? 'N/A'}
          </p>
          <p className={`text-xs mt-1 ${rsiStatus.color === 'green' ? 'text-green-600' : rsiStatus.color === 'red' ? 'text-red-600' : 'text-gray-500'}`}>
            {rsiStatus.status === 'oversold' ? 'Oversold (Buy Signal)' : 
             rsiStatus.status === 'overbought' ? 'Overbought (Sell Signal)' : 
             'Neutral'}
          </p>
        </div>
        
        {/* EMA */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">EMA (14)</p>
          <p className="text-2xl font-bold text-amber-600">
            {indicators.ema?.toFixed(2) ?? 'N/A'}
          </p>
        </div>
        
        {/* SMA */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">SMA (14)</p>
          <p className="text-2xl font-bold text-blue-600">
            {indicators.sma?.toFixed(2) ?? 'N/A'}
          </p>
        </div>
        
        {/* MACD */}
        <div className="bg-gray-50 dark:bg-gray-700 rounded-lg p-4 col-span-2 md:col-span-1">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-1">MACD</p>
          <p className="text-xl font-bold text-purple-600">
            {indicators.macd?.toFixed(2) ?? 'N/A'}
          </p>
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Signal: {indicators.macd_signal?.toFixed(2) ?? 'N/A'}
          </p>
        </div>
      </div>
      
      {/* Strategy Info */}
      <div className="mt-4 p-3 bg-blue-50 dark:bg-blue-900/20 rounded-lg">
        <p className="text-sm text-blue-800 dark:text-blue-300">
          <strong>Strategy:</strong> RSI &lt; 30 = Buy Signal | RSI &gt; 70 = Sell Signal
        </p>
      </div>
    </div>
  );
}
