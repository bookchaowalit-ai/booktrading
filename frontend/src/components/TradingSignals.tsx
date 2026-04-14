/**
 * Trading Signals Component
 * Displays AI-powered trading signals with leverage and direction recommendations
 */
'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { newsService, getSentimentGradient } from '@/services/news';
import { TradingSignal, SentimentAnalysis } from '@/types/news';
import Card from './ui/Card';
import Button from './ui/Button';
import {
  TrendingUp,
  TrendingDown,
  Zap,
  Target,
  Shield,
  Activity,
  Clock,
  ChevronRight,
  AlertTriangle,
  CheckCircle,
  Minus,
} from 'lucide-react';
import CategoryIcon from './CategoryIcon';
import { getAssetCategory } from '@/types';
import { useToast } from './ui/Toast';

interface TradingSignalsProps {
  symbol?: string;
  onSignalSelect?: (signal: TradingSignal) => void;
}

export default function TradingSignals({ symbol, onSignalSelect }: TradingSignalsProps) {
  const { success } = useToast();
  const [signals, setSignals] = useState<TradingSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    loadSignals();
  }, [symbol]);

  const loadSignals = async () => {
    setIsLoading(true);
    try {
      const response = await newsService.getTradingSignals(symbol);
      setSignals(response.signals.filter((s) => s.status === 'active'));
    } catch (error) {
      console.error('Failed to load signals:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleExecuteSignal = (signal: TradingSignal) => {
    success(`Executing ${signal.direction} ${signal.symbol} with ${signal.leverage}x leverage`);
    onSignalSelect?.(signal);
  };

  // Static Tailwind class maps — avoids production purging of dynamic class names
  const directionClasses: Record<string, { badge: string; bg: string; text: string }> = {
    LONG: { badge: 'bg-green-500 text-white', bg: 'bg-green-100 dark:bg-green-900/30', text: 'text-green-700 dark:text-green-400' },
    SHORT: { badge: 'bg-red-500 text-white', bg: 'bg-red-100 dark:bg-red-900/30', text: 'text-red-700 dark:text-red-400' },
    HOLD: { badge: 'bg-gray-500 text-white', bg: 'bg-gray-100 dark:bg-gray-700', text: 'text-gray-700 dark:text-gray-300' },
  };
  const strengthClasses: Record<string, string> = {
    very_strong: 'text-purple-600 dark:text-purple-400',
    strong: 'text-green-600 dark:text-green-400',
    moderate: 'text-yellow-600 dark:text-yellow-400',
    weak: 'text-gray-500 dark:text-gray-400',
  };
  const confidenceClass = (c: number) =>
    c >= 0.8 ? 'bg-green-500' : c >= 0.6 ? 'bg-yellow-500' : 'bg-red-500';

  const getDirectionIcon = (direction: string) => {
    if (direction === 'LONG') return <TrendingUp className="w-5 h-5" />;
    if (direction === 'SHORT') return <TrendingDown className="w-5 h-5" />;
    return <Minus className="w-5 h-5" />;
  };

  if (isLoading) {
    return (
      <div className="space-y-4">
        {Array.from({ length: 2 }).map((_, i) => (
          <Card key={i} className="p-6">
            <div className="animate-pulse space-y-4">
              <div className="h-6 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-3/4" />
              <div className="h-4 bg-gray-200 dark:bg-gray-700 rounded w-1/2" />
            </div>
          </Card>
        ))}
      </div>
    );
  }

  if (signals.length === 0) {
    return (
      <Card padding="lg" className="text-center">
        <Activity className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
          No Active Signals
        </h3>
        <p className="text-gray-500 dark:text-gray-400">
          Our AI is analyzing the market. Check back soon for trading opportunities.
        </p>
      </Card>
    );
  }

  return (
    <div className="space-y-4">
      {signals.map((signal, index) => {
        const dir = directionClasses[signal.direction] || directionClasses.HOLD;
        const category = getAssetCategory(signal.symbol);

        return (
          <motion.div
            key={signal.id}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card variant="elevated" className="overflow-hidden" gradient>
              {/* Signal Header */}
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <CategoryIcon category={category} size="md" />
                  <div>
                    <div className="flex items-center gap-2">
                      <h3 className="text-lg font-bold text-gray-900 dark:text-white">
                        {signal.symbol}
                      </h3>
                      <span className={`px-2.5 py-0.5 rounded-full text-xs font-bold ${dir.badge}`}>
                        {signal.direction}
                      </span>
                    </div>
                    <div className="flex items-center gap-2 mt-1">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded ${dir.bg} ${dir.text}`}>
                        {signal.leverage}x Leverage
                      </span>
                      <span className="text-xs text-gray-500 dark:text-gray-400">
                        {signal.timeframe} trading
                      </span>
                    </div>
                  </div>
                </div>

                <div className="text-right">
                  <div className="flex items-center gap-1 justify-end mb-1">
                    <Activity className={`w-4 h-4 ${strengthClasses[signal.strength] || strengthClasses.weak}`} />
                    <span className={`text-xs font-medium capitalize ${strengthClasses[signal.strength] || strengthClasses.weak}`}>
                      {signal.strength.replace('_', ' ')} Signal
                    </span>
                  </div>
                  <div className="flex items-center gap-1 justify-end">
                    <div className={`w-2 h-2 rounded-full ${confidenceClass(signal.confidence)}`} />
                    <span className="text-xs font-medium text-gray-600 dark:text-gray-400">
                      {(signal.confidence * 100).toFixed(0)}% Confidence
                    </span>
                  </div>
                </div>
              </div>

              {/* Entry Price */}
              {signal.entryPrice && (
                <div className="bg-white/50 dark:bg-gray-800/50 rounded-lg p-3 mb-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-600 dark:text-gray-400">Entry Price</span>
                    <span className="text-lg font-bold text-gray-900 dark:text-white">
                      ${signal.entryPrice.toLocaleString()}
                    </span>
                  </div>
                </div>
              )}

              {/* Targets and Stop Loss */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-green-50 dark:bg-green-900/20 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Target className="w-4 h-4 text-green-600" />
                    <span className="text-xs font-medium text-green-700 dark:text-green-400">
                      Targets
                    </span>
                  </div>
                  <div className="space-y-1">
                    {signal.targetPrices.slice(0, 3).map((target, i) => (
                      <div key={i} className="text-sm font-semibold text-green-700 dark:text-green-400">
                        T{i + 1}: ${target.toLocaleString()}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="bg-red-50 dark:bg-red-900/20 rounded-lg p-3">
                  <div className="flex items-center gap-2 mb-2">
                    <Shield className="w-4 h-4 text-red-600" />
                    <span className="text-xs font-medium text-red-700 dark:text-red-400">
                      Stop Loss
                    </span>
                  </div>
                  {signal.stopLoss && (
                    <div className="text-lg font-bold text-red-700 dark:text-red-400">
                      ${signal.stopLoss.toLocaleString()}
                    </div>
                  )}
                  {signal.riskRewardRatio && (
                    <div className="text-xs text-red-600 dark:text-red-400 mt-1">
                      R:R {signal.riskRewardRatio.toFixed(2)}
                    </div>
                  )}
                </div>
              </div>

              {/* Reasoning */}
              <div className="mb-4">
                <h4 className="text-xs font-semibold text-gray-700 dark:text-gray-300 mb-2 flex items-center gap-1">
                  <Zap className="w-3 h-3 text-yellow-500" />
                  AI Reasoning
                </h4>
                <ul className="space-y-1">
                  {signal.reasoning.slice(0, 3).map((reason, i) => (
                    <li key={i} className="text-sm text-gray-600 dark:text-gray-400 flex items-start gap-2">
                      <CheckCircle className="w-3 h-3 text-green-500 mt-0.5 flex-shrink-0" />
                      {reason}
                    </li>
                  ))}
                </ul>
              </div>

              {/* Expiry */}
              {signal.expiresAt && (
                <div className="flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400 mb-4">
                  <Clock className="w-3 h-3" />
                  Expires in {Math.floor((new Date(signal.expiresAt).getTime() - Date.now()) / 3600000)}h
                </div>
              )}

              {/* Action Button */}
              <Button
                fullWidth
                gradient
                onClick={() => handleExecuteSignal(signal)}
                leftIcon={getDirectionIcon(signal.direction)}
              >
                Execute {signal.direction} with {signal.leverage}x Leverage
              </Button>
            </Card>
          </motion.div>
        );
      })}
    </div>
  );
}
