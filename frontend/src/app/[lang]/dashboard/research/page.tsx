/**
 * Research Page — Candidate Review Board
 * Narrows attention: which markets deserve focus, which are filtered out.
 * No trade/start/execute buttons — observe-only.
 * Part of AI Command Center
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation, TranslationKey } from '@/i18n/translations';
import { api } from '@/services/api';
import {
  FlaskConical, RefreshCw, AlertTriangle,
  Eye, XCircle, Clock, TrendingUp, Target, Filter, CheckCircle2, Ban,
  Brain, Zap, Globe, BarChart3, Activity, TrendingDown, Minus, ShieldAlert,
} from 'lucide-react';

// ── Types ──────────────────────────────────────────────────────────────────────

interface CryptoPair {
  rank: number;
  score: number;
  exchange: string;
  symbol: string;
  price: string;
  volume: string;
  vol_pct: string;
  spread: string;
  depth: string;
}

interface ReviewedMarket {
  rank: number;
  market: string;
  resolution: string;
  category_leak: string;
  data_source: string;
  signal: string;
  decision: string;
}

interface ResearchSummary {
  trade_candidates: number;
  crypto_watch_count: number;
  polymarket_status: 'blocked' | 'active';
  blocklist_active: boolean;
  min_volume: string;
  min_liquidity: string;
}

interface ResearchData {
  crypto: {
    pairs: CryptoPair[];
    meta: {
      last_scan?: string;
      pairs_scanned?: number;
      min_volume?: string;
    };
    files_found: boolean;
  };
  polymarket: {
    candidates: any[];
    reviewed: ReviewedMarket[];
    meta: {
      last_scan?: string;
      candidates_summary?: string;
      filters?: { key: string; value: string }[];
    };
    files_found: boolean;
  };
  summary: ResearchSummary;
}

// ── Intelligence Types (Batch 2A extraction) ───────────────────────────────────

interface IndicatorData {
  symbol: string;
  rsi: number;
  ema: number;
  sma: number;
  macd: number;
  macd_signal: number;
}

interface AISignalSummary {
  signal: 'BUY' | 'SELL' | 'NEUTRAL';
  confidence: number;
  direction: 'bullish' | 'bearish' | 'neutral';
  reasoning: string;
  regime: string;
}

interface MarketMoodData {
  sentiment: number; // -1 to 1
  label: string;
  riskLevel: 'low' | 'medium' | 'high' | 'critical';
  anomaliesCount: number;
}

interface MarketAlert {
  id: string;
  symbol: string;
  market: string;
  severity: string;
  title: string;
  confidence: number;
  timestamp: string;
}

interface MarketIntelSummary {
  sources: { name: string; market_type: string; enabled: boolean }[];
  alerts: MarketAlert[];
  opportunities: { market: string; count: number }[];
}

interface HighLevelMetrics {
  gates_ready: number;
  gates_total: number;
  bankroll: number;
  drawdown_pct: number;
  kill_switch: boolean;
  active_positions: number;
  total_pnl: number;
}

const STRATEGY_API_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

// ── Helpers ────────────────────────────────────────────────────────────────────

function deriveSignal(indicators: Record<string, IndicatorData>): AISignalSummary {
  const first = Object.values(indicators)[0];
  if (!first) return { signal: 'NEUTRAL', confidence: 50, direction: 'neutral', reasoning: 'No indicator data', regime: 'ranging' };

  const rsi = first.rsi ?? 50;
  const macd = first.macd ?? 0;
  const macdSig = first.macd_signal ?? 0;
  let score = 0;
  if (rsi < 30) score += 40; else if (rsi > 70) score -= 40;
  else if (rsi < 40) score += 20; else if (rsi > 60) score -= 20;
  if (macd > macdSig) score += 25; else score -= 25;
  if (first.ema && first.sma && first.ema > first.sma) score += 15;
  else if (first.ema && first.sma && first.ema < first.sma) score -= 15;

  const confidence = Math.min(95, Math.abs(score) + 10);
  let signal: 'BUY' | 'SELL' | 'NEUTRAL' = 'NEUTRAL';
  let direction: 'bullish' | 'bearish' | 'neutral' = 'neutral';
  if (score > 20) { signal = 'BUY'; direction = 'bullish'; }
  else if (score < -20) { signal = 'SELL'; direction = 'bearish'; }

  const vol = Math.abs(macd - macdSig);
  const trend = Math.abs(rsi - 50);
  let regime = 'ranging';
  if (trend > 20 && vol > 2) regime = 'strong_trend';
  else if (trend < 10 && vol < 1) regime = 'low_volatility';
  else if (vol > 3) regime = 'high_volatility';

  const parts: string[] = [];
  if (rsi < 30) parts.push('RSI oversold (' + rsi.toFixed(0) + ')');
  else if (rsi > 70) parts.push('RSI overbought (' + rsi.toFixed(0) + ')');
  else parts.push('RSI neutral (' + rsi.toFixed(0) + ')');
  if (macd > macdSig) parts.push('MACD bullish');
  else parts.push('MACD bearish');

  return { signal, confidence, direction, reasoning: parts.join(', '), regime };
}

const scoreColor = (score: number): string => {
  if (score >= 8) return 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20';
  if (score >= 6) return 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20';
  return 'text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-900/20';
};

const decisionBadge = (decision: string, signal: string, t: (k: TranslationKey) => string) => {
  const d = decision.toUpperCase();
  if (d === 'REJECT') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
        <XCircle className="w-3 h-3" />
        {t('research.badge.rejected')}
      </span>
    );
  }
  if (signal.toLowerCase().includes('watch')) {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
        <Eye className="w-3 h-3" />
        {t('research.badge.watch')}
      </span>
    );
  }
  if (d === 'WATCH' || d === 'REVIEW') {
    return (
      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
        <Clock className="w-3 h-3" />
        {t('research.badge.review')}
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
      <CheckCircle2 className="w-3 h-3" />
      {t('research.badge.candidate')}
    </span>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function ResearchPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<ResearchData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Batch 2A: Intelligence summary data
  const [aiSignal, setAiSignal] = useState<AISignalSummary | null>(null);
  const [marketMood, setMarketMood] = useState<MarketMoodData | null>(null);
  const [intelSummary, setIntelSummary] = useState<MarketIntelSummary | null>(null);
  const [hlMetrics, setHlMetrics] = useState<HighLevelMetrics | null>(null);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    try {
    const result = await api.getResearch();
    if (result) setData(result as ResearchData);

    // Fetch intelligence data in parallel (all optional)
    const [indRes, sigRes, intelOverview, intelAlerts, intelSources, ccRes] = await Promise.allSettled([
      fetch(STRATEGY_API_URL + '/api/indicators'),
      fetch(STRATEGY_API_URL + '/api/signals'),
      fetch(STRATEGY_API_URL + '/api/market-intel/overview'),
      fetch(STRATEGY_API_URL + '/api/market-intel/alerts?limit=5'),
      fetch(STRATEGY_API_URL + '/api/market-intel/sources'),
      fetch(STRATEGY_API_URL + '/api/command-center'),
    ]);

    // AI Signal from indicators
    if (indRes.status === 'fulfilled' && indRes.value.ok) {
      try {
        const indicators = await indRes.value.json();
        setAiSignal(deriveSignal(indicators));
      } catch {}
    }

    // Market mood from signals
    if (sigRes.status === 'fulfilled' && sigRes.value.ok) {
      try {
        const sigData = await sigRes.value.json();
        const sentiment = sigData.market_sentiment ?? 0;
        const label = sentiment > 0.3 ? 'Bullish' : sentiment < -0.3 ? 'Bearish' : 'Neutral';
        setMarketMood({ sentiment, label, riskLevel: 'medium', anomaliesCount: 0 });
      } catch {}
    }

    // Market intel summary
    try {
      const [overviewData, alertsData, sourcesData] = await Promise.all([
        intelOverview.status === 'fulfilled' && intelOverview.value.ok ? intelOverview.value.json() : Promise.resolve(null),
        intelAlerts.status === 'fulfilled' && intelAlerts.value.ok ? intelAlerts.value.json() : Promise.resolve(null),
        intelSources.status === 'fulfilled' && intelSources.value.ok ? intelSources.value.json() : Promise.resolve(null),
      ]);
      const opps: { market: string; count: number }[] = [];
      if (overviewData) {
        Object.entries(overviewData).forEach(([key, val]: [string, any]) => {
          opps.push({ market: key, count: val.opportunities || 0 });
        });
      }
      setIntelSummary({
        sources: sourcesData?.sources || [],
        alerts: (alertsData?.alerts || []).slice(0, 5),
        opportunities: opps,
      });
    } catch {}

    // High-level metrics from command-center
    if (ccRes.status === 'fulfilled' && ccRes.value.ok) {
      try {
        const cc = await ccRes.value.json();
        setHlMetrics({
          gates_ready: cc.evidence?.gates_ready ?? 0,
          gates_total: cc.evidence?.gates_total ?? 4,
          bankroll: cc.risk_sources?.paper_bot?.bankroll ?? cc.capital?.bankroll_usdc ?? 0,
          drawdown_pct: cc.risk_sources?.paper_bot?.drawdown_pct ?? cc.capital?.drawdown_pct ?? 0,
          kill_switch: cc.kill_switch?.active ?? false,
          active_positions: cc.risk_sources?.paper_bot?.active_positions ?? cc.positions?.active ?? 0,
          total_pnl: cc.paper_trial?.performance?.total_pnl ?? 0,
        });
      } catch {}
    }

    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 60000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-6 space-y-4">
        <div className="space-y-2">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-3 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  const summary = data?.summary;
  const cryptoPairs = data?.crypto.pairs || [];
  const polyReviewed = data?.polymarket.reviewed || [];
  const polyMeta = data?.polymarket.meta;
  const cryptoMeta = data?.crypto.meta;
  const noFiles = data && !data.crypto.files_found && !data.polymarket.files_found;

  // Show error banner if data failed to load
  if (!data) {
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-6">
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-900/20">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">Unable to load research data.</p>
            <button onClick={() => fetchData(true)} className="mt-1 text-xs text-amber-700 underline hover:no-underline dark:text-amber-400">Retry</button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <FlaskConical className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('research.title')}
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('research.subtitle')}
          </p>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={isRefreshing}
          aria-label="Refresh research"
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? t('research.refreshing') : t('research.refresh')}
        </button>
      </div>

      {/* No files warning */}
      {noFiles && (
        <div className="flex items-center gap-3 p-4 bg-yellow-50 dark:bg-yellow-900/10 rounded-lg border border-yellow-200 dark:border-yellow-800">
          <AlertTriangle className="w-5 h-5 text-yellow-600" />
          <div>
            <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
              {t('research.noFiles')}
            </span>
            <p className="text-xs text-yellow-600 mt-0.5">{t('research.noFilesHint')}</p>
          </div>
        </div>
      )}

      {/* ── Batch 2A: Intelligence Summary Cards ── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Card 1: AI Signal Summary */}
        {aiSignal && (
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <Brain className="w-4 h-4 text-violet-500" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">AI Signal</span>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                aiSignal.signal === 'BUY' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : aiSignal.signal === 'SELL' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
              }`}>
                {aiSignal.signal === 'BUY' ? <TrendingUp className="w-3 h-3" /> : aiSignal.signal === 'SELL' ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                {aiSignal.signal}
              </span>
              <span className="text-xs text-gray-500">{aiSignal.confidence}% conf</span>
              <span className={`text-xs px-2 py-0.5 rounded-full ${
                aiSignal.regime === 'strong_trend' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                : aiSignal.regime === 'high_volatility' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                : aiSignal.regime === 'low_volatility' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400'
              }`}>{aiSignal.regime.replace('_', ' ')}</span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{aiSignal.reasoning}</p>
          </div>
        )}

        {/* Card 2: Market Mood */}
        {marketMood && (
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Market Mood</span>
            </div>
            <div className="flex items-center gap-3 mb-2">
              <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-bold ${
                marketMood.label === 'Bullish' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : marketMood.label === 'Bearish' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
              }`}>
                {marketMood.label === 'Bullish' ? <TrendingUp className="w-3 h-3" /> : marketMood.label === 'Bearish' ? <TrendingDown className="w-3 h-3" /> : <Minus className="w-3 h-3" />}
                {marketMood.label}
              </span>
              <span className="text-xs text-gray-500">
                Score: {marketMood.sentiment > 0 ? '+' : ''}{marketMood.sentiment.toFixed(2)}
              </span>
            </div>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              {marketMood.sentiment === 0 ? 'No strong sentiment signal — market is neutral' : `Sentiment leaning ${marketMood.label.toLowerCase()}`}
            </p>
          </div>
        )}

        {/* Card 3: Notable Events */}
        {intelSummary && (
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <Globe className="w-4 h-4 text-indigo-500" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Notable Events</span>
              {intelSummary.sources.length > 0 && (
                <span className="text-xs text-gray-400 ml-auto">{intelSummary.sources.filter(s => s.enabled).length} sources</span>
              )}
            </div>
            {intelSummary.alerts.length > 0 ? (
              <div className="space-y-1.5 max-h-24 overflow-y-auto">
                {intelSummary.alerts.map(alert => (
                  <div key={alert.id} className="flex items-center gap-2 text-xs">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                      alert.severity === 'critical' ? 'bg-red-500' : alert.severity === 'high' ? 'bg-orange-500' : alert.severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                    }`} />
                    <span className="text-gray-700 dark:text-gray-300 truncate">{alert.title}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-gray-500">No active alerts — markets quiet</p>
            )}
            {intelSummary.opportunities.length > 0 && (
              <div className="flex gap-2 mt-2 flex-wrap">
                {intelSummary.opportunities.map(opp => (
                  <span key={opp.market} className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded-full capitalize">
                    {opp.market}: {opp.count} opp
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Card 4: High-Level Metrics */}
        {hlMetrics && (
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-3">
              <BarChart3 className="w-4 h-4 text-emerald-500" />
              <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">Key Metrics</span>
            </div>
            <div className="grid grid-cols-3 gap-3">
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Gates</p>
                <p className={`text-lg font-bold ${hlMetrics.gates_ready === hlMetrics.gates_total ? 'text-green-600 dark:text-green-400' : 'text-amber-600 dark:text-amber-400'}`}>
                  {hlMetrics.gates_ready}/{hlMetrics.gates_total}
                </p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Bankroll</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">${hlMetrics.bankroll.toFixed(0)}</p>
              </div>
              <div>
                <p className="text-xs text-gray-500 dark:text-gray-400">Drawdown</p>
                <p className={`text-lg font-bold ${hlMetrics.drawdown_pct > 10 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
                  {hlMetrics.drawdown_pct.toFixed(1)}%
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2 mt-2">
              {hlMetrics.kill_switch && (
                <span className="inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
                  <ShieldAlert className="w-3 h-3" /> Kill Switch
                </span>
              )}
              <span className="text-xs text-gray-500">{hlMetrics.active_positions} positions</span>
              <span className={`text-xs ml-auto font-medium ${hlMetrics.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {hlMetrics.total_pnl >= 0 ? '+' : ''}${hlMetrics.total_pnl.toFixed(2)} P&L
              </span>
            </div>
          </div>
        )}
      </div>

      {/* ── Summary Card ── */}
      {summary && (
        <div className="p-4 bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 rounded-xl border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2 mb-3">
            <Eye className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            <span className="text-xs font-semibold uppercase tracking-wide text-purple-600 dark:text-purple-400">
              {t('research.summary')}
            </span>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            {/* Trade Candidates */}
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${summary.trade_candidates === 0 ? 'bg-green-100 dark:bg-green-900/30' : 'bg-amber-100 dark:bg-amber-900/30'}`}>
                {summary.trade_candidates === 0 ? (
                  <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                ) : (
                  <Target className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                )}
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {summary.trade_candidates}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {t('research.tradeCandidates')}
                </div>
              </div>
            </div>

            {/* Crypto Watch Pairs */}
            <div className="flex items-center gap-3">
              <div className="p-2 rounded-lg bg-blue-100 dark:bg-blue-900/30">
                <TrendingUp className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div>
                <div className="text-2xl font-bold text-gray-900 dark:text-white">
                  {summary.crypto_watch_count}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {t('research.cryptoWatch')}
                </div>
              </div>
            </div>

            {/* Polymarket Status */}
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${summary.polymarket_status === 'blocked' ? 'bg-red-100 dark:bg-red-900/30' : 'bg-green-100 dark:bg-green-900/30'}`}>
                {summary.polymarket_status === 'blocked' ? (
                  <Ban className="w-5 h-5 text-red-600 dark:text-red-400" />
                ) : (
                  <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
                )}
              </div>
              <div>
                <div className="text-lg font-bold text-gray-900 dark:text-white">
                  {summary.polymarket_status === 'blocked' ? t('research.blocked') : t('research.active')}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {t('research.polymarketStatus')}
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ── Filter Status Card ── */}
      {summary && (
        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <Filter className="w-4 h-4 text-gray-500" />
            <span className="text-sm font-semibold text-gray-700 dark:text-gray-300">
              {t('research.filterStatus')}
            </span>
          </div>
          <div className="flex flex-wrap gap-3">
            <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium ${
              summary.blocklist_active
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
            }`}>
              {summary.blocklist_active ? <CheckCircle2 className="w-3 h-3" /> : <XCircle className="w-3 h-3" />}
              {summary.blocklist_active ? t('research.blocklistActive') : t('research.blocklistInactive')}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              {t('research.minVolume')}: {summary.min_volume}
            </span>
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300">
              {t('research.minLiquidity')}: {summary.min_liquidity}
            </span>
          </div>
        </div>
      )}

      {/* ── Crypto Candidates Table ── */}
      {cryptoPairs.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <TrendingUp className="w-5 h-5 text-purple-500" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('research.cryptoTable')}
              </h2>
            </div>
            {cryptoMeta?.last_scan && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {t('research.lastScan')}: {cryptoMeta.last_scan}
              </span>
            )}
          </div>
          <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Score</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Exchange</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Volume</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Spread</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Depth</th>
                  <th className="px-3 py-2.5 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {cryptoPairs.map((pair) => (
                  <tr key={pair.rank} className="bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{pair.rank}</td>
                    <td className="px-3 py-2.5">
                      <span className={`inline-flex items-center justify-center w-8 h-5 rounded text-xs font-bold ${scoreColor(pair.score)}`}>
                        {pair.score}
                      </span>
                    </td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300">{pair.exchange}</td>
                    <td className="px-3 py-2.5 font-medium text-gray-900 dark:text-white">{pair.symbol}</td>
                    <td className="px-3 py-2.5 text-gray-700 dark:text-gray-300">{pair.volume}</td>
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{pair.spread}</td>
                    <td className="px-3 py-2.5 text-gray-500 dark:text-gray-400">{pair.depth}</td>
                    <td className="px-3 py-2.5">
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
                        <Eye className="w-3 h-3" />
                        {t('research.badge.watch')}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Polymarket Rejected Board ── */}
      {polyReviewed.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Target className="w-5 h-5 text-blue-500" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('research.rejectedBoard')}
              </h2>
            </div>
            {polyMeta?.last_scan && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {t('research.lastScan')}: {polyMeta.last_scan}
              </span>
            )}
          </div>

          {/* "All filtered" message when 0 candidates */}
          {summary?.trade_candidates === 0 && (
            <div className="p-3 mb-3 bg-green-50 dark:bg-green-900/10 rounded-lg border border-green-200 dark:border-green-800">
              <div className="flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 text-green-600 dark:text-green-400" />
                <span className="text-sm text-green-700 dark:text-green-400">
                  {t('research.noCandidates')}
                </span>
              </div>
            </div>
          )}

          <div className="space-y-2">
            {polyReviewed.map((market) => (
              <div
                key={market.rank}
                className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors"
              >
                <div className="flex items-center justify-between gap-3">
                  <div className="flex items-center gap-2 min-w-0">
                    <span className="text-xs text-gray-400 shrink-0">#{market.rank}</span>
                    <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                      {market.market}
                    </span>
                  </div>
                  {decisionBadge(market.decision, market.signal, t)}
                </div>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-4 gap-y-1 mt-2 text-xs text-gray-500 dark:text-gray-400">
                  <div><span className="font-medium text-gray-600 dark:text-gray-300">Resolution:</span> {market.resolution}</div>
                  <div><span className="font-medium text-gray-600 dark:text-gray-300">Category:</span> {market.category_leak.replace(/\*\*/g, '')}</div>
                  <div><span className="font-medium text-gray-600 dark:text-gray-300">Source:</span> {market.data_source}</div>
                  <div><span className="font-medium text-gray-600 dark:text-gray-300">Signal:</span> {market.signal}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
