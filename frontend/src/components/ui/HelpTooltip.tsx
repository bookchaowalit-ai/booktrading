/**
 * Help Tooltip Component
 * Specialized tooltip for trading terminology and form field help
 */
'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { HelpCircle, Info } from 'lucide-react';

interface HelpTooltipProps {
  content: string;
  title?: string;
  children?: React.ReactNode;
  position?: 'top' | 'bottom' | 'left' | 'right';
  variant?: 'icon' | 'text' | 'custom';
}

export default function HelpTooltip({
  content,
  title,
  children,
  position = 'top',
  variant = 'icon',
}: HelpTooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  const positionClasses = {
    top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
    left: 'right-full top-1/2 -translate-y-1/2 mr-2',
    right: 'left-full top-1/2 -translate-y-1/2 ml-2',
  };

  const arrowClasses = {
    top: 'bottom-[-4px] left-1/2 -translate-x-1/2',
    bottom: 'top-[-4px] left-1/2 -translate-x-1/2',
    left: 'right-[-4px] top-1/2 -translate-y-1/2',
    right: 'left-[-4px] top-1/2 -translate-y-1/2',
  };

  return (
    <div
      className="relative inline-block"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {variant === 'icon' ? (
        <button
          type="button"
          className="inline-flex items-center justify-center w-4 h-4 text-gray-400 hover:text-purple-600 dark:hover:text-purple-400 transition-colors focus:outline-none"
          aria-label="Help"
        >
          <HelpCircle className="w-4 h-4" />
        </button>
      ) : variant === 'text' ? (
        <span className="text-xs text-purple-600 dark:text-purple-400 underline decoration-dotted cursor-help">
          {children || 'What is this?'}
        </span>
      ) : (
        children
      )}

      <AnimatePresence>
        {isVisible && (
          <motion.div
            initial={{ opacity: 0, scale: 0.9, y: 4 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 4 }}
            transition={{ duration: 0.15 }}
            className={`absolute z-50 min-w-[200px] max-w-xs ${positionClasses[position]}`}
          >
            <div className="bg-gray-900 dark:bg-gray-700 text-white rounded-lg shadow-xl p-3 text-sm">
              {title && (
                <div className="font-semibold text-purple-300 mb-1 text-xs uppercase tracking-wide">
                  {title}
                </div>
              )}
              <div className="text-gray-100 dark:text-gray-200 leading-relaxed">
                {content}
              </div>
              {/* Arrow */}
              <div
                className={`absolute w-2 h-2 bg-gray-900 dark:bg-gray-700 transform rotate-45 ${arrowClasses[position]}`}
              />
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}

// Pre-defined trading terminology tooltips
export const TradingTooltips = {
  gridLevels: {
    title: 'Grid Levels',
    content: 'Number of price levels in your grid. More levels = more trades but smaller profit per trade.',
  },
  lowerPrice: {
    title: 'Lower Price',
    content: 'The bottom price of your grid range. Buy orders will be placed as price decreases toward this level.',
  },
  upperPrice: {
    title: 'Upper Price',
    content: 'The top price of your grid range. Sell orders will be placed as price increases toward this level.',
  },
  investmentAmount: {
    title: 'Investment Amount',
    content: 'Total amount to invest in this grid. This will be divided equally across all grid levels.',
  },
  arithmeticGrid: {
    title: 'Arithmetic Grid',
    content: 'Equal price spacing between levels. Example: $1000, $1100, $1200, $1300...',
  },
  geometricGrid: {
    title: 'Geometric Grid',
    content: 'Equal percentage spacing between levels. Example: $1000, $1100 (+10%), $1210 (+10%)...',
  },
  stopLoss: {
    title: 'Stop Loss',
    content: 'Automatically sell when price drops to this level to limit losses.',
  },
  takeProfit: {
    title: 'Take Profit',
    content: 'Automatically sell when price reaches this level to secure profits.',
  },
  positionSizing: {
    title: 'Position Sizing',
    content: 'How much to invest per trade based on your risk tolerance and account balance.',
  },
  winRate: {
    title: 'Win Rate',
    content: 'Percentage of profitable trades. A 60%+ win rate is generally considered good.',
  },
  profitFactor: {
    title: 'Profit Factor',
    content: 'Gross profit divided by gross loss. Above 1.5 indicates a profitable strategy.',
  },
  sharpeRatio: {
    title: 'Sharpe Ratio',
    content: 'Risk-adjusted return metric. Above 1.0 is good, above 2.0 is excellent.',
  },
  drawdown: {
    title: 'Max Drawdown',
    content: 'Largest peak-to-trough decline. Lower is better - indicates less risk.',
  },
  RSI: {
    title: 'RSI (Relative Strength Index)',
    content: 'Momentum indicator (0-100). Below 30 = oversold (buy signal), above 70 = overbought (sell signal).',
  },
  MACD: {
    title: 'MACD',
    content: 'Trend-following momentum indicator. Bullish when MACD line crosses above signal line.',
  },
  bollingerBands: {
    title: 'Bollinger Bands',
    content: 'Volatility bands. Price touching lower band may indicate oversold conditions.',
  },
};

// Pre-built tooltip trigger components
interface TradingHelpIconProps {
  term: keyof typeof TradingTooltips;
}

export function TradingHelpIcon({ term }: TradingHelpIconProps) {
  const tooltip = TradingTooltips[term];
  return (
    <HelpTooltip
      content={tooltip.content}
      title={tooltip.title}
      variant="icon"
    />
  );
}
