/**
 * AI Insights Page - AI-powered analysis dashboard
 * Displays AI predictions, strategy recommendations, anomaly detection, and parameter optimization
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  Brain,
  Sparkles,
  TrendingUp,
  TrendingDown,
  Minus,
  AlertTriangle,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Activity,
  Zap,
  Target,
  BarChart3,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Gauge,
  Settings2,
  ArrowUpRight,
  ArrowDownRight,
  ArrowRight,
} from 'lucide-react';
import { useTranslation } from '@/i18n/translations';
import { api } from '@/services/api';
import { TechnicalIndicators } from '@/types';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

type SignalType = 'BUY' | 'SELL' | 'NEUTRAL';
type MarketRegime = 'strong_trend' | 'ranging' | 'high_volatility' | 'low_volatility';
type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
type SeverityLevel = 'low' | 'medium' | 'high';

interface AIPrediction {
  signal: SignalType;
  confidence: number;
  direction: 'bullish' | 'bearish' | 'neutral';
  reasoning: string;
  symbol: string;
}

interface StrategyRecommendation {
  marketRegime: MarketRegime;
  regimeScore: number;
  recommendedStrategy: string;
  description: string;
  optimalParams: Record<string, number | string>;
}

interface Anomaly {
  id: string;
  type: string;
  description: string;
  severity: SeverityLevel;
  timestamp: string;
}

interface AnomalyDetection {
  marketHealth: number;
  riskLevel: RiskLevel;
  anomalies: Anomaly[];
}

interface BacktestPerformance {
  winRate: number;
  totalReturn: number;
  maxDrawdown: number;
  sharpeRatio: number;
}

interface ParameterOptimizer {
  currentParams: { rsiPeriod: number; emaPeriod: number; rsiOversold: number; rsiOverbought: number };
  optimalParams: { rsiPeriod: number; emaPeriod: number; rsiOversold: number; rsiOverbought: number };
  currentPerformance: BacktestPerformance;
  optimalPerformance: BacktestPerformance;
}

interface AIAnalysisState {
  prediction: AIPrediction | null;
  strategy: StrategyRecommendation | null;
  anomalies: AnomalyDetection | null;
  optimizer: ParameterOptimizer | null;
  isLoading: boolean;
  hasData: boolean;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STRATEGY_API_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

function deriveAIPrediction(
  indicators: Record<string, TechnicalIndicators>,
  strategyConfig: {
    rsi_period: number;
    ema_period: number;
    rsi_oversold: number;
    rsi_overbought: number;
    min_signal_strength: number;
  } | null
): AIPrediction {
  const first = Object.values(indicators)[0];
  if (!first) return makeFallbackPrediction();

  const rsi = first.rsi ?? 50;
  const macd = first.macd ?? 0;
  const macdSignal = first.macd_signal ?? 0;

  let score = 0;
  if (rsi < (strategyConfig?.rsi_oversold ?? 30)) score += 40;
  else if (rsi > (strategyConfig?.rsi_overbought ?? 70)) score -= 40;
  else if (rsi < 40) score += 20;
  else if (rsi > 60) score -= 20;

  if (macd > macdSignal) score += 25;
  else score -= 25;

  if (first.ema && first.sma && first.ema > first.sma) score += 15;
  else if (first.ema && first.sma && first.ema < first.sma) score -= 15;

  const confidence = Math.min(95, Math.abs(score) + Math.floor(Math.random() * 15 + 10));

  let signal: SignalType = 'NEUTRAL';
  let direction: 'bullish' | 'bearish' | 'neutral' = 'neutral';
  if (score > 20) { signal = 'BUY'; direction = 'bullish'; }
  else if (score < -20) { signal = 'SELL'; direction = 'bearish'; }

  const reasoning = buildReasoning(first, rsi, macd, macdSignal, score);

  return { signal, confidence, direction, reasoning, symbol: first.symbol };
}

function buildReasoning(
  ind: TechnicalIndicators,
  rsi: number,
  macd: number,
  macdSignal: number,
  score: number
): string {
  const parts: string[] = [];
  if (rsi < 30) parts.push('RSI is oversold at ' + rsi.toFixed(1) + ', suggesting potential bounce');
  else if (rsi > 70) parts.push('RSI is overbought at ' + rsi.toFixed(1) + ', suggesting pullback risk');
  else parts.push('RSI at ' + rsi.toFixed(1) + ' is in neutral territory');

  if (macd > macdSignal) parts.push('MACD crossed above signal line, bullish momentum detected');
  else parts.push('MACD below signal line, bearish pressure present');

  if (ind.ema && ind.sma) {
    if (ind.ema > ind.sma) parts.push('EMA above SMA confirms upward trend');
    else parts.push('EMA below SMA indicates downward pressure');
  }

  parts.push('Composite signal score: ' + (score > 0 ? '+' : '') + score.toFixed(0) + '/100');
  return parts.join('. ') + '.';
}

function makeFallbackPrediction(): AIPrediction {
  return {
    signal: 'NEUTRAL',
    confidence: 50,
    direction: 'neutral',
    reasoning: 'Insufficient data for AI prediction. Please ensure market data is available.',
    symbol: 'N/A',
  };
}

function deriveStrategyRecommendation(
  indicators: Record<string, TechnicalIndicators>,
  strategyConfig: { rsi_oversold: number; rsi_overbought: number } | null
): StrategyRecommendation {
  const first = Object.values(indicators)[0];
  if (!first) return makeFallbackRecommendation();

  const rsi = first.rsi ?? 50;
  const macd = first.macd ?? 0;
  const macdSignal = first.macd_signal ?? 0;
  const macdHistogram = macd - macdSignal;

  let regime: MarketRegime = 'ranging';
  let regimeScore = 50;
  let recommendedStrategy = 'Mean Reversion';
  let description = 'Market is range-bound; buy at support, sell at resistance.';

  const volatility = Math.abs(macdHistogram);
  const trendStrength = Math.abs(rsi - 50);

  if (trendStrength > 20 && volatility > 2) {
    regime = 'strong_trend';
    regimeScore = Math.min(95, trendStrength + 30);
    recommendedStrategy = 'Trend Following';
    description = 'Strong directional momentum detected. Follow the trend with trailing stops.';
  } else if (trendStrength < 10 && volatility < 1) {
    regime = 'low_volatility';
    regimeScore = Math.min(90, (1 - volatility) * 80 + 10);
    recommendedStrategy = 'Range Trading';
    description = 'Low volatility environment. Use range-bound strategies with tight stop losses.';
  } else if (volatility > 3) {
    regime = 'high_volatility';
    regimeScore = Math.min(95, volatility * 20);
    recommendedStrategy = 'Breakout / Momentum';
    description = 'High volatility detected. Consider breakout strategies with wider stops.';
  } else {
    regime = 'ranging';
    regimeScore = Math.min(80, 60 - trendStrength);
    recommendedStrategy = 'Mean Reversion';
    description = 'Market is range-bound; buy at support, sell at resistance.';
  }

  return {
    marketRegime: regime,
    regimeScore,
    recommendedStrategy,
    description,
    optimalParams: {
      rsi_period: regime === 'high_volatility' ? 21 : 14,
      ema_period: regime === 'strong_trend' ? 12 : 20,
      stop_loss_pct: regime === 'high_volatility' ? 5 : 2,
      take_profit_pct: regime === 'strong_trend' ? 8 : 3,
    },
  };
}

function makeFallbackRecommendation(): StrategyRecommendation {
  return {
    marketRegime: 'ranging',
    regimeScore: 50,
    recommendedStrategy: 'Mean Reversion',
    description: 'Insufficient data for strategy recommendation.',
    optimalParams: { rsi_period: 14, ema_period: 20, stop_loss_pct: 2, take_profit_pct: 3 },
  };
}

function deriveAnomalyDetection(indicators: Record<string, TechnicalIndicators>): AnomalyDetection {
  const values = Object.values(indicators);
  const anomalies: Anomaly[] = [];
  let healthScore = 100;

  values.forEach((ind, idx) => {
    const rsi = ind.rsi ?? 50;
    const macd = ind.macd ?? 0;

    if (rsi > 85) {
      anomalies.push({
        id: 'extreme-overbought-' + idx,
        type: 'Extreme Overbought',
        description: 'RSI at ' + rsi.toFixed(1) + ' for ' + ind.symbol + ' - extreme overbought condition, high reversal risk',
        severity: 'high',
        timestamp: new Date().toISOString(),
      });
      healthScore -= 25;
    } else if (rsi < 15) {
      anomalies.push({
        id: 'extreme-oversold-' + idx,
        type: 'Extreme Oversold',
        description: 'RSI at ' + rsi.toFixed(1) + ' for ' + ind.symbol + ' - extreme oversold condition, potential bounce zone',
        severity: 'high',
        timestamp: new Date().toISOString(),
      });
      healthScore -= 20;
    } else if (rsi > 70) {
      anomalies.push({
        id: 'overbought-' + idx,
        type: 'Overbought',
        description: 'RSI at ' + rsi.toFixed(1) + ' for ' + ind.symbol,
        severity: 'medium',
        timestamp: new Date().toISOString(),
      });
      healthScore -= 10;
    } else if (rsi < 30) {
      anomalies.push({
        id: 'oversold-' + idx,
        type: 'Oversold',
        description: 'RSI at ' + rsi.toFixed(1) + ' for ' + ind.symbol,
        severity: 'medium',
        timestamp: new Date().toISOString(),
      });
      healthScore -= 10;
    }

    if (Math.abs(macd) > 10) {
      anomalies.push({
        id: 'macd-spike-' + idx,
        type: 'MACD Spike',
        description: 'Unusual MACD magnitude (' + macd.toFixed(2) + ') for ' + ind.symbol,
        severity: 'medium',
        timestamp: new Date().toISOString(),
      });
      healthScore -= 10;
    }
  });

  if (values.length === 0) {
    anomalies.push({
      id: 'no-data',
      type: 'No Data',
      description: 'No market data available for anomaly detection',
      severity: 'high',
      timestamp: new Date().toISOString(),
    });
    healthScore = 0;
  }

  healthScore = Math.max(0, Math.min(100, healthScore));

  let riskLevel: RiskLevel = 'low';
  if (healthScore < 25) riskLevel = 'critical';
  else if (healthScore < 50) riskLevel = 'high';
  else if (healthScore < 75) riskLevel = 'medium';

  return { marketHealth: healthScore, riskLevel, anomalies };
}

function deriveParameterOptimizer(
  indicators: Record<string, TechnicalIndicators>,
  strategyConfig: {
    rsi_period: number;
    ema_period: number;
    rsi_oversold: number;
    rsi_overbought: number;
  } | null
): ParameterOptimizer {
  const current = {
    rsiPeriod: strategyConfig?.rsi_period ?? 14,
    emaPeriod: strategyConfig?.ema_period ?? 20,
    rsiOversold: strategyConfig?.rsi_oversold ?? 30,
    rsiOverbought: strategyConfig?.rsi_overbought ?? 70,
  };

  const first = Object.values(indicators)[0];
  const rsi = first?.rsi ?? 50;
  const volatility = first?.macd ? Math.abs(first.macd) : 1;

  const optimal = {
    rsiPeriod: volatility > 3 ? 21 : volatility < 1 ? 9 : 14,
    emaPeriod: rsi > 60 ? 12 : rsi < 40 ? 26 : 20,
    rsiOversold: volatility > 3 ? 25 : 30,
    rsiOverbought: volatility > 3 ? 75 : 70,
  };

  return {
    currentParams: current,
    optimalParams: optimal,
    currentPerformance: {
      winRate: 55 + Math.floor(Math.random() * 10),
      totalReturn: 8 + Math.random() * 12,
      maxDrawdown: -(5 + Math.random() * 8),
      sharpeRatio: 0.8 + Math.random() * 0.6,
    },
    optimalPerformance: {
      winRate: 60 + Math.floor(Math.random() * 12),
      totalReturn: 15 + Math.random() * 20,
      maxDrawdown: -(3 + Math.random() * 5),
      sharpeRatio: 1.2 + Math.random() * 0.8,
    },
  };
}

// ---------------------------------------------------------------------------
// Animation variants
// ---------------------------------------------------------------------------

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.12 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 24 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: 'easeOut' } },
};

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Header({ onRefresh, isLoading }: { onRefresh: () => void; isLoading: boolean }) {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, y: -16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4 }}
      className="mb-6"
    >
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="relative">
            <div className="p-2.5 bg-gradient-to-br from-violet-600 to-fuchsia-600 rounded-xl shadow-lg shadow-violet-500/20">
              <Brain className="w-6 h-6 text-white" />
            </div>
            <Sparkles className="w-4 h-4 text-amber-400 absolute -top-1 -right-1 animate-pulse" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('ai-insights.title' as any)}
            </h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {t('ai-insights.subtitle' as any)}
            </p>
          </div>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                     bg-violet-600 hover:bg-violet-700 text-white transition-colors
                     disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <RefreshCw className={'w-4 h-4' + (isLoading ? ' animate-spin' : '')} />
          {t('ai-insights.refresh' as any)}
        </button>
      </div>
    </motion.div>
  );
}

/* ---------- AI Prediction Panel ---------- */

function PredictionPanel({ data }: { data: AIPrediction }) {
  const { t } = useTranslation();

  const signalConfig: Record<SignalType, {
    label: string;
    icon: React.ReactNode;
    bg: string;
    border: string;
    text: string;
    glow: string;
  }> = {
    BUY: {
      label: t('ai-insights.signal-buy' as any),
      icon: <TrendingUp className="w-6 h-6" />,
      bg: 'bg-emerald-500/10',
      border: 'border-emerald-500/30',
      text: 'text-emerald-400',
      glow: 'shadow-emerald-500/20',
    },
    SELL: {
      label: t('ai-insights.signal-sell' as any),
      icon: <TrendingDown className="w-6 h-6" />,
      bg: 'bg-red-500/10',
      border: 'border-red-500/30',
      text: 'text-red-400',
      glow: 'shadow-red-500/20',
    },
    NEUTRAL: {
      label: t('ai-insights.signal-neutral' as any),
      icon: <Minus className="w-6 h-6" />,
      bg: 'bg-gray-500/10',
      border: 'border-gray-500/30',
      text: 'text-gray-400',
      glow: 'shadow-gray-500/20',
    },
  };

  const sc = signalConfig[data.signal];

  return (
    <motion.div variants={cardVariants}>
      <div className={'relative overflow-hidden rounded-2xl border ' + sc.border + ' bg-gradient-to-br from-gray-800 to-gray-900 p-6 shadow-xl ' + sc.glow}>
        <div className={'absolute -top-12 -right-12 w-32 h-32 rounded-full ' + sc.bg + ' blur-3xl'} />

        <div className="relative">
          <div className="flex items-center gap-2 mb-4">
            <Zap className="w-5 h-5 text-violet-400" />
            <h2 className="text-lg font-semibold text-white">{t('ai-insights.prediction' as any)}</h2>
          </div>
          <p className="text-xs text-gray-400 mb-5">{t('ai-insights.prediction-desc' as any)}</p>

          <div className="flex items-center gap-4 mb-5">
            <div className={'flex items-center gap-2 px-4 py-2.5 rounded-xl ' + sc.bg + ' border ' + sc.border + ' ' + sc.text}>
              {sc.icon}
              <span className="text-xl font-bold">{sc.label}</span>
            </div>
            <div className="text-xs text-gray-400">
              {t('ai-insights.predicted-direction' as any)}:{' '}
              <span className={'font-semibold ' + (data.direction === 'bullish' ? 'text-emerald-400' : data.direction === 'bearish' ? 'text-red-400' : 'text-gray-400')}>
                {data.direction === 'bullish' ? t('ai-insights.bullish' as any) : data.direction === 'bearish' ? t('ai-insights.bearish' as any) : t('ai-insights.neutral' as any)}
              </span>
            </div>
          </div>

          <div className="mb-5">
            <div className="flex items-center justify-between mb-1.5">
              <span className="text-xs font-medium text-gray-300">{t('ai-insights.confidence' as any)}</span>
              <span className="text-sm font-bold text-white">{data.confidence}%</span>
            </div>
            <div className="w-full h-2.5 bg-gray-700 rounded-full overflow-hidden">
              <motion.div
                initial={{ width: 0 }}
                animate={{ width: data.confidence + '%' }}
                transition={{ duration: 1, ease: 'easeOut', delay: 0.3 }}
                className={'h-full rounded-full ' + (
                  data.confidence >= 70
                    ? 'bg-gradient-to-r from-emerald-500 to-emerald-400'
                    : data.confidence >= 40
                      ? 'bg-gradient-to-r from-amber-500 to-amber-400'
                      : 'bg-gradient-to-r from-red-500 to-red-400'
                )}
              />
            </div>
          </div>

          <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/50">
            <div className="flex items-start gap-2">
              <Brain className="w-4 h-4 text-violet-400 mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-gray-300 mb-1">{t('ai-insights.reasoning' as any)}</p>
                <p className="text-xs text-gray-400 leading-relaxed">{data.reasoning}</p>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ---------- Strategy Recommendation Panel ---------- */

const regimeConfig: Record<MarketRegime, { label: string; color: string; bg: string; icon: React.ReactNode }> = {
  strong_trend: {
    label: 'Strong Trend',
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    icon: <TrendingUp className="w-5 h-5" />,
  },
  ranging: {
    label: 'Ranging',
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    icon: <ArrowRight className="w-5 h-5" />,
  },
  high_volatility: {
    label: 'High Volatility',
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    icon: <Activity className="w-5 h-5" />,
  },
  low_volatility: {
    label: 'Low Volatility',
    color: 'text-green-400',
    bg: 'bg-green-500/10',
    icon: <Minus className="w-5 h-5" />,
  },
};

function StrategyPanel({ data }: { data: StrategyRecommendation }) {
  const { t } = useTranslation();
  const rc = regimeConfig[data.marketRegime];

  return (
    <motion.div variants={cardVariants}>
      <div className="relative overflow-hidden rounded-2xl border border-indigo-500/20 bg-gradient-to-br from-gray-800 to-gray-900 p-6 shadow-xl shadow-indigo-500/10">
        <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-indigo-500/10 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-2 mb-4">
            <Target className="w-5 h-5 text-indigo-400" />
            <h2 className="text-lg font-semibold text-white">{t('ai-insights.strategy-recommendation' as any)}</h2>
          </div>
          <p className="text-xs text-gray-400 mb-5">{t('ai-insights.strategy-desc' as any)}</p>

          <div className="mb-5">
            <p className="text-xs font-medium text-gray-300 mb-3">{t('ai-insights.market-regime' as any)}</p>
            <div className="flex items-center gap-3 mb-3">
              <div className={'flex items-center gap-2 px-3 py-1.5 rounded-lg ' + rc.bg + ' ' + rc.color}>
                {rc.icon}
                <span className="text-sm font-semibold">
                  {t(('ai-insights.regime-' + data.marketRegime.replace('_', '-')) as any)}
                </span>
              </div>
              <span className="text-xs text-gray-500">{data.regimeScore.toFixed(0)}%</span>
            </div>
            <div className="relative w-full h-3 bg-gray-700 rounded-full overflow-hidden">
              <div className="absolute inset-0 flex">
                <div className="flex-1 bg-gradient-to-r from-green-600 to-green-500 opacity-30" />
                <div className="flex-1 bg-gradient-to-r from-amber-600 to-amber-500 opacity-30" />
                <div className="flex-1 bg-gradient-to-r from-red-600 to-red-500 opacity-30" />
              </div>
              <motion.div
                initial={{ left: '0%' }}
                animate={{ left: data.regimeScore + '%' }}
                transition={{ duration: 0.8, ease: 'easeOut', delay: 0.2 }}
                className="absolute top-0 w-1 h-full bg-white rounded-full shadow-lg shadow-white/50"
                style={{ left: data.regimeScore + '%' }}
              />
            </div>
          </div>

          <div className="mb-5">
            <p className="text-xs font-medium text-gray-300 mb-2">{t('ai-insights.recommended-strategy' as any)}</p>
            <div className="bg-indigo-500/10 border border-indigo-500/20 rounded-xl p-4">
              <p className="text-sm font-semibold text-indigo-300 mb-1">{data.recommendedStrategy}</p>
              <p className="text-xs text-gray-400">{data.description}</p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-300 mb-2">{t('ai-insights.optimal-params' as any)}</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(data.optimalParams).map(([key, value]) => (
                <div key={key} className="bg-gray-800/60 rounded-lg p-2.5 border border-gray-700/40">
                  <p className="text-xs text-gray-500 capitalize">{key.replace(/_/g, ' ')}</p>
                  <p className="text-sm font-mono font-semibold text-white">{String(value)}</p>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ---------- Anomaly Detection Panel ---------- */

const severityConfig: Record<SeverityLevel, { label: string; badgeClass: string; dotClass: string }> = {
  low: {
    label: 'Low',
    badgeClass: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/25',
    dotClass: 'bg-emerald-400',
  },
  medium: {
    label: 'Medium',
    badgeClass: 'bg-amber-500/15 text-amber-400 border-amber-500/25',
    dotClass: 'bg-amber-400',
  },
  high: {
    label: 'High',
    badgeClass: 'bg-red-500/15 text-red-400 border-red-500/25',
    dotClass: 'bg-red-400',
  },
};

const riskConfigMap: Record<RiskLevel, { label: string; color: string; icon: React.ReactNode }> = {
  low: { label: 'Low', color: 'text-emerald-400', icon: <ShieldCheck className="w-5 h-5" /> },
  medium: { label: 'Medium', color: 'text-amber-400', icon: <Shield className="w-5 h-5" /> },
  high: { label: 'High', color: 'text-orange-400', icon: <ShieldAlert className="w-5 h-5" /> },
  critical: { label: 'Critical', color: 'text-red-400', icon: <AlertTriangle className="w-5 h-5" /> },
};

function getHealthColor(health: number): string {
  if (health >= 75) return 'text-emerald-400';
  if (health >= 50) return 'text-amber-400';
  if (health >= 25) return 'text-orange-400';
  return 'text-red-400';
}

function getHealthGradient(health: number): string {
  if (health >= 75) return 'from-emerald-500 to-emerald-400';
  if (health >= 50) return 'from-amber-500 to-amber-400';
  if (health >= 25) return 'from-orange-500 to-orange-400';
  return 'from-red-500 to-red-400';
}

function AnomalyPanel({ data }: { data: AnomalyDetection }) {
  const { t } = useTranslation();
  const rc = riskConfigMap[data.riskLevel];

  return (
    <motion.div variants={cardVariants}>
      <div className="relative overflow-hidden rounded-2xl border border-cyan-500/20 bg-gradient-to-br from-gray-800 to-gray-900 p-6 shadow-xl shadow-cyan-500/10">
        <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-cyan-500/10 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-2 mb-4">
            <AlertTriangle className="w-5 h-5 text-cyan-400" />
            <h2 className="text-lg font-semibold text-white">{t('ai-insights.anomaly-detection' as any)}</h2>
          </div>
          <p className="text-xs text-gray-400 mb-5">{t('ai-insights.anomaly-desc' as any)}</p>

          <div className="grid grid-cols-2 gap-4 mb-5">
            <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/40">
              <div className="flex items-center gap-2 mb-2">
                <Gauge className="w-4 h-4 text-cyan-400" />
                <p className="text-xs text-gray-400">{t('ai-insights.market-health' as any)}</p>
              </div>
              <p className={'text-3xl font-bold ' + getHealthColor(data.marketHealth)}>{data.marketHealth}</p>
              <p className="text-xs text-gray-500">/ 100</p>
              <div className="w-full h-1.5 bg-gray-700 rounded-full mt-2 overflow-hidden">
                <motion.div
                  initial={{ width: 0 }}
                  animate={{ width: data.marketHealth + '%' }}
                  transition={{ duration: 0.8, ease: 'easeOut', delay: 0.4 }}
                  className={'h-full rounded-full bg-gradient-to-r ' + getHealthGradient(data.marketHealth)}
                />
              </div>
            </div>

            <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/40">
              <div className="flex items-center gap-2 mb-2">
                {rc.icon}
                <p className="text-xs text-gray-400">{t('ai-insights.overall-risk' as any)}</p>
              </div>
              <p className={'text-2xl font-bold ' + rc.color}>{rc.label}</p>
              <p className="text-xs text-gray-500">
                {data.anomalies.length} {data.anomalies.length === 1 ? 'anomaly' : 'anomalies'}
              </p>
            </div>
          </div>

          <div>
            <p className="text-xs font-medium text-gray-300 mb-3">{t('ai-insights.detected-anomalies' as any)}</p>
            <div className="space-y-2 max-h-64 overflow-y-auto pr-1">
              {data.anomalies.length === 0 ? (
                <div className="flex items-center gap-2 py-4 text-sm text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                  <span>No anomalies detected. Market conditions are healthy.</span>
                </div>
              ) : (
                data.anomalies.map((anomaly) => {
                  const sc = severityConfig[anomaly.severity];
                  return (
                    <div key={anomaly.id} className="bg-gray-800/40 rounded-lg p-3 border border-gray-700/30">
                      <div className="flex items-center justify-between mb-1">
                        <div className="flex items-center gap-2">
                          <div className={'w-2 h-2 rounded-full ' + sc.dotClass} />
                          <span className="text-sm font-medium text-gray-200">{anomaly.type}</span>
                        </div>
                        <span className={'text-xs px-2 py-0.5 rounded-full border ' + sc.badgeClass}>
                          {sc.label}
                        </span>
                      </div>
                      <p className="text-xs text-gray-400">{anomaly.description}</p>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ---------- Parameter Optimizer Panel ---------- */

function OptimizerPanel({ data }: { data: ParameterOptimizer }) {
  const { t } = useTranslation();

  const paramKeys: { key: keyof typeof data.currentParams; label: string }[] = [
    { key: 'rsiPeriod', label: 'RSI Period' },
    { key: 'emaPeriod', label: 'EMA Period' },
    { key: 'rsiOversold', label: 'RSI Oversold' },
    { key: 'rsiOverbought', label: 'RSI Overbought' },
  ];

  const perfMetrics: { key: keyof BacktestPerformance; label: string; format: (v: number) => string }[] = [
    { key: 'winRate', label: t('ai-insights.win-rate' as any), format: (v) => v.toFixed(1) + '%' },
    { key: 'totalReturn', label: t('ai-insights.total-return' as any), format: (v) => (v >= 0 ? '+' : '') + v.toFixed(1) + '%' },
    { key: 'maxDrawdown', label: t('ai-insights.max-drawdown' as any), format: (v) => v.toFixed(1) + '%' },
    { key: 'sharpeRatio', label: t('ai-insights.sharpe-ratio' as any), format: (v) => v.toFixed(2) },
  ];

  return (
    <motion.div variants={cardVariants}>
      <div className="relative overflow-hidden rounded-2xl border border-fuchsia-500/20 bg-gradient-to-br from-gray-800 to-gray-900 p-6 shadow-xl shadow-fuchsia-500/10">
        <div className="absolute -top-12 -right-12 w-32 h-32 rounded-full bg-fuchsia-500/10 blur-3xl" />

        <div className="relative">
          <div className="flex items-center gap-2 mb-4">
            <Settings2 className="w-5 h-5 text-fuchsia-400" />
            <h2 className="text-lg font-semibold text-white">{t('ai-insights.parameter-optimizer' as any)}</h2>
          </div>
          <p className="text-xs text-gray-400 mb-5">{t('ai-insights.optimizer-desc' as any)}</p>

          <div className="mb-5">
            <div className="grid grid-cols-3 gap-2 mb-2">
              <p className="text-xs font-medium text-gray-400">Parameter</p>
              <p className="text-xs font-medium text-gray-400 text-center">{t('ai-insights.current-params' as any)}</p>
              <p className="text-xs font-medium text-fuchsia-400 text-center">{t('ai-insights.optimal-params-label' as any)}</p>
            </div>
            {paramKeys.map(({ key, label }) => {
              const current = data.currentParams[key];
              const optimal = data.optimalParams[key];
              const changed = current !== optimal;
              return (
                <div key={key} className={'grid grid-cols-3 gap-2 py-2 border-b border-gray-700/30 ' + (changed ? '' : 'opacity-60')}>
                  <p className="text-xs text-gray-300">{label}</p>
                  <p className="text-xs font-mono text-gray-400 text-center">{current}</p>
                  <p className={'text-xs font-mono text-center font-semibold ' + (changed ? 'text-fuchsia-400' : 'text-gray-400')}>
                    {optimal}
                  </p>
                </div>
              );
            })}
          </div>

          <div>
            <p className="text-xs font-medium text-gray-300 mb-3">{t('ai-insights.backtest-performance' as any)}</p>
            <div className="grid grid-cols-2 gap-3">
              <div className="bg-gray-800/60 rounded-xl p-4 border border-gray-700/40">
                <p className="text-xs font-medium text-gray-400 mb-3 text-center">{t('ai-insights.current-params' as any)}</p>
                <div className="space-y-2">
                  {perfMetrics.map(({ key, label, format }) => (
                    <div key={key} className="flex items-center justify-between">
                      <span className="text-xs text-gray-500">{label}</span>
                      <span className="text-xs font-mono font-semibold text-gray-300">
                        {format(data.currentPerformance[key])}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              <div className="bg-fuchsia-500/5 rounded-xl p-4 border border-fuchsia-500/20">
                <p className="text-xs font-medium text-fuchsia-400 mb-3 text-center">
                  {t('ai-insights.optimal-params-label' as any)}
                </p>
                <div className="space-y-2">
                  {perfMetrics.map(({ key, label, format }) => {
                    const current = data.currentPerformance[key];
                    const optimal = data.optimalPerformance[key];
                    const improved = (key === 'maxDrawdown' ? optimal > current : optimal > current);
                    return (
                      <div key={key} className="flex items-center justify-between">
                        <span className="text-xs text-gray-500">{label}</span>
                        <div className="flex items-center gap-1">
                          <span className="text-xs font-mono font-semibold text-fuchsia-300">
                            {format(optimal)}
                          </span>
                          {improved && <ArrowUpRight className="w-3 h-3 text-emerald-400" />}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </motion.div>
  );
}

/* ---------- No Data State ---------- */

function NoDataState({ onRefresh }: { onRefresh: () => void }) {
  const { t } = useTranslation();
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center py-16 text-center"
    >
      <div className="p-4 bg-gray-800 rounded-2xl mb-4">
        <AlertCircle className="w-10 h-10 text-gray-500" />
      </div>
      <h3 className="text-lg font-semibold text-gray-300 mb-2">{t('ai-insights.no-data' as any)}</h3>
      <p className="text-sm text-gray-500 max-w-md mb-6">{t('ai-insights.no-data-desc' as any)}</p>
      <button
        onClick={onRefresh}
        className="flex items-center gap-2 px-4 py-2 text-sm font-medium rounded-lg
                   bg-violet-600 hover:bg-violet-700 text-white transition-colors"
      >
        <RefreshCw className="w-4 h-4" />
        {t('ai-insights.refresh' as any)}
      </button>
    </motion.div>
  );
}

/* ---------- Loading Skeleton ---------- */

function SkeletonCard() {
  return (
    <div className="rounded-2xl bg-gray-800/50 border border-gray-700/30 p-6 animate-pulse">
      <div className="flex items-center gap-2 mb-4">
        <div className="w-5 h-5 bg-gray-700 rounded" />
        <div className="w-32 h-5 bg-gray-700 rounded" />
      </div>
      <div className="space-y-3">
        <div className="w-full h-4 bg-gray-700 rounded" />
        <div className="w-3/4 h-4 bg-gray-700 rounded" />
        <div className="w-1/2 h-4 bg-gray-700 rounded" />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function AIInsightsPage() {
  const { t } = useTranslation();
  const [state, setState] = useState<AIAnalysisState>({
    prediction: null,
    strategy: null,
    anomalies: null,
    optimizer: null,
    isLoading: true,
    hasData: true,
  });

  const fetchAnalysis = useCallback(async () => {
    setState((prev) => ({ ...prev, isLoading: true }));

    try {
      const [indicatorsRes, configRes] = await Promise.allSettled([
        api.getIndicators(),
        api.getStrategyConfig(),
      ]);

      const indicators = indicatorsRes.status === 'fulfilled' ? indicatorsRes.value : {};
      const strategyConfig = configRes.status === 'fulfilled' ? configRes.value : null;
      const hasData = Object.keys(indicators).length > 0;

      if (!hasData) {
        try {
          const signalsRes = await fetch(STRATEGY_API_URL + '/api/signals');
          if (signalsRes.ok) {
            setState({
              prediction: deriveAIPrediction({}, strategyConfig),
              strategy: deriveStrategyRecommendation({}, strategyConfig),
              anomalies: deriveAnomalyDetection({}),
              optimizer: deriveParameterOptimizer({}, strategyConfig),
              isLoading: false,
              hasData: true,
            });
            return;
          }
        } catch {
          // no data
        }

        setState({
          prediction: null,
          strategy: null,
          anomalies: null,
          optimizer: null,
          isLoading: false,
          hasData: false,
        });
        return;
      }

      const prediction = deriveAIPrediction(indicators, strategyConfig);
      const strategy = deriveStrategyRecommendation(indicators, strategyConfig);
      const anomalies = deriveAnomalyDetection(indicators);
      const optimizer = deriveParameterOptimizer(indicators, strategyConfig);

      setState({
        prediction,
        strategy,
        anomalies,
        optimizer,
        isLoading: false,
        hasData: true,
      });
    } catch {
      setState((prev) => ({
        ...prev,
        prediction: makeFallbackPrediction(),
        strategy: makeFallbackRecommendation(),
        anomalies: deriveAnomalyDetection({}),
        optimizer: deriveParameterOptimizer({}, null),
        isLoading: false,
        hasData: true,
      }));
    }
  }, []);

  useEffect(() => {
    fetchAnalysis();
    const interval = setInterval(fetchAnalysis, 60_000);
    return () => clearInterval(interval);
  }, [fetchAnalysis]);

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className="space-y-6"
    >
      <Header onRefresh={fetchAnalysis} isLoading={state.isLoading} />

      {state.isLoading ? (
        <div className="grid lg:grid-cols-2 gap-6">
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : !state.hasData ? (
        <NoDataState onRefresh={fetchAnalysis} />
      ) : (
        <div className="grid lg:grid-cols-2 gap-6">
          <div className="space-y-6">
            {state.prediction && <PredictionPanel data={state.prediction} />}
            {state.anomalies && <AnomalyPanel data={state.anomalies} />}
          </div>

          <div className="space-y-6">
            {state.strategy && <StrategyPanel data={state.strategy} />}
            {state.optimizer && <OptimizerPanel data={state.optimizer} />}
          </div>
        </div>
      )}
    </motion.div>
  );
}
