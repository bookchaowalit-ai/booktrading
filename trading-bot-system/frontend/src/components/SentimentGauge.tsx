/**
 * Sentiment Gauge Component
 * Visual gauge showing market sentiment score
 */
'use client';

import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus, Zap, Activity } from 'lucide-react';
import { SentimentAnalysis, PositionDirection } from '@/types/news';
import Card from './ui/Card';
import Button from './ui/Button';

interface SentimentGaugeProps {
  sentiment?: SentimentAnalysis;
  onTrade?: (direction: PositionDirection, leverage: number) => void;
  showActions?: boolean;
}

export default function SentimentGauge({ sentiment, onTrade, showActions = true }: SentimentGaugeProps) {
  if (!sentiment) {
    return (
      <Card padding="lg" className="text-center">
        <p className="text-gray-500 dark:text-gray-400">No sentiment data available</p>
      </Card>
    );
  }

  const { overallSentiment, sentimentLabel, confidence, recommendation, leverageSuggestion, analysis } = sentiment;

  // Calculate gauge rotation (-90 to 90 degrees)
  const gaugeRotation = overallSentiment * 90;

  // Get gradient based on sentiment
  const getGradient = () => {
    if (overallSentiment >= 0.7) return 'from-emerald-500 to-green-600';
    if (overallSentiment >= 0.3) return 'from-green-400 to-emerald-500';
    if (overallSentiment >= -0.3) return 'from-gray-400 to-gray-500';
    if (overallSentiment >= -0.7) return 'from-orange-400 to-red-500';
    return 'from-red-500 to-rose-600';
  };

  const getLabelColor = () => {
    if (overallSentiment >= 0.7) return 'text-emerald-600';
    if (overallSentiment >= 0.3) return 'text-green-600';
    if (overallSentiment >= -0.3) return 'text-gray-600';
    if (overallSentiment >= -0.7) return 'text-orange-600';
    return 'text-red-600';
  };

  const getRecommendationColor = () => {
    if (recommendation === 'LONG') return 'text-green-600 bg-green-50 dark:bg-green-900/20';
    if (recommendation === 'SHORT') return 'text-red-600 bg-red-50 dark:bg-red-900/20';
    return 'text-gray-600 bg-gray-50 dark:bg-gray-800';
  };

  const analysisMetrics = [
    { name: 'Technical', value: analysis.technical, color: '#3B82F6' },
    { name: 'Fundamental', value: analysis.fundamental, color: '#10B981' },
    { name: 'Social', value: analysis.social, color: '#8B5CF6' },
    { name: 'News', value: analysis.news, color: '#F59E0B' },
  ];

  return (
    <Card variant="elevated" gradient className="p-6">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div className="flex items-center gap-2">
          <Activity className="w-5 h-5 text-purple-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            Sentiment Analysis
          </h3>
        </div>
        <div className="flex items-center gap-1 text-sm text-gray-500 dark:text-gray-400">
          <Zap className="w-4 h-4 text-yellow-500" />
          AI Powered
        </div>
      </div>

      {/* Gauge */}
      <div className="relative mb-6">
        {/* Gauge Background */}
        <div className="h-4 bg-gradient-to-r from-red-500 via-gray-400 to-emerald-500 rounded-full overflow-hidden">
          <div className="absolute inset-0 bg-gradient-to-r from-red-500/20 via-gray-400/20 to-emerald-500/20" />
        </div>

        {/* Gauge Needle */}
        <motion.div
          initial={{ rotate: -90 }}
          animate={{ rotate: gaugeRotation }}
          transition={{ duration: 1, ease: 'easeOut' }}
          className="absolute top-1/2 left-1/2 w-1 h-8 -ml-0.5 -mt-1 origin-bottom"
          style={{ transformOrigin: 'bottom center' }}
        >
          <div className={`w-full h-full bg-gradient-to-t ${getGradient()} rounded-full shadow-lg`} />
        </motion.div>

        {/* Center Point */}
        <div className="absolute top-1/2 left-1/2 w-4 h-4 -ml-2 -mt-2 bg-white dark:bg-gray-800 rounded-full border-4 border-gray-300 dark:border-gray-600 shadow-md" />

        {/* Labels */}
        <div className="flex justify-between mt-2 text-xs text-gray-500 dark:text-gray-400">
          <span>Very Bearish</span>
          <span>Neutral</span>
          <span>Very Bullish</span>
        </div>
      </div>

      {/* Sentiment Score */}
      <div className="text-center mb-6">
        <motion.div
          initial={{ scale: 0.8, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          className={`text-4xl font-bold ${getLabelColor()} mb-1`}
        >
          {(overallSentiment * 100).toFixed(0)}
        </motion.div>
        <div className="text-sm text-gray-600 dark:text-gray-400 capitalize">
          {sentimentLabel.replace('_', ' ')} Sentiment
        </div>
        <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
          {(confidence * 100).toFixed(0)}% Confidence
        </div>
      </div>

      {/* Recommendation Badge */}
      <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-lg mb-6 ${getRecommendationColor()}`}>
        {recommendation === 'LONG' ? (
          <TrendingUp className="w-5 h-5" />
        ) : recommendation === 'SHORT' ? (
          <TrendingDown className="w-5 h-5" />
        ) : (
          <Minus className="w-5 h-5" />
        )}
        <div>
          <div className="text-xs opacity-75">AI Recommendation</div>
          <div className="font-bold">
            {recommendation} {leverageSuggestion && `${leverageSuggestion}x Leverage`}
          </div>
        </div>
      </div>

      {/* Analysis Breakdown */}
      <div className="mb-6">
        <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">
          Analysis Breakdown
        </h4>
        <div className="space-y-2">
          {analysisMetrics.map((metric) => (
            <div key={metric.name} className="flex items-center gap-3">
              <span className="text-xs text-gray-600 dark:text-gray-400 w-20">
                {metric.name}
              </span>
              <div className="flex-1 h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: `${((metric.value + 1) / 2) * 100}%` }}
                  transition={{ duration: 0.5, delay: 0.2 }}
                  className="h-full rounded-full"
                  style={{ backgroundColor: metric.color }}
                />
              </div>
              <span className="text-xs font-medium text-gray-700 dark:text-gray-300 w-8 text-right">
                {((metric.value + 1) / 2 * 100).toFixed(0)}%
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* Action Buttons */}
      {showActions && onTrade && (
        <div className="grid grid-cols-2 gap-3">
          <Button
            variant="success"
            fullWidth
            onClick={() => onTrade('LONG', leverageSuggestion || 1)}
            leftIcon={<TrendingUp className="w-4 h-4" />}
          >
            Long {leverageSuggestion}x
          </Button>
          <Button
            variant="danger"
            fullWidth
            onClick={() => onTrade('SHORT', leverageSuggestion || 1)}
            leftIcon={<TrendingDown className="w-4 h-4" />}
          >
            Short {leverageSuggestion}x
          </Button>
        </div>
      )}
    </Card>
  );
}
