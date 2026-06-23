/**
 * Evidence & Gates Page
 * Polished timeline + gates checklist + latest state change card
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation, TranslationKey } from '@/i18n/translations';
import {
  Shield, CheckCircle, XCircle, AlertTriangle, Clock,
  FileText, RefreshCw, Cpu,
  Zap, Eye, Lock, CheckCircle2, Circle, Target, DollarSign,
  TrendingUp, TrendingDown, BookOpen, Bell, ScrollText,
} from 'lucide-react';
import { api } from '@/services/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface EvidenceEntry {
  date: string;
  title: string;
  status: 'pass' | 'fail' | 'info';
  type: 'log' | 'trial' | 'kill_switch' | 'signal' | 'research' | 'monitor' | 'gate';
  details: string;
}

interface Gate {
  name: string;
  status: 'ready' | 'not_ready';
  status_text: string;
  blocked_by: string;
}

interface LatestChange {
  date: string;
  title: string;
  type: string;
  status: string;
}

interface PaperTrial {
  [key: string]: any;
}

interface PaperPosition {
  position_id: string;
  question: string;
  side: 'YES' | 'NO';
  entry_price: number;
  current_price: number;
  size_usdc: number;
  pnl: number;
  pnl_pct: number;
  resolved: boolean;
  event_title?: string;
}

interface PaperStatus {
  running: boolean;
  positions: { active: number; resolved: number };
  config: { max_positions: number };
}

interface PaperPerformance {
  total_pnl: number;
  bankroll?: { current: number; peak: number; drawdown_pct: number };
}

interface JournalEntry {
  id: number;
  symbol: string;
  side: string;
  strategy: string;
  entry_reason: string;
  entry_price: number;
  quantity: number;
  exit_price: number;
  exit_reason: string;
  actual_pnl: number;
  fee: number;
  status: string;
  created_at: string;
}

interface FeedItem {
  id: string;
  date: string;
  title: string;
  type: 'alert' | 'trade' | 'note' | 'system';
  detail: string;
  status: 'pass' | 'fail' | 'info';
  meta?: string;
}

interface EvidenceData {
  evidence_entries: EvidenceEntry[];
  gates: Gate[];
  paper_trial: PaperTrial | null;
  latest_change: LatestChange | null;
  files_found: {
    evidence_log: boolean;
    readiness_checklist: boolean;
    paper_grid_json: boolean;
  };
}

// ── Type badge config ──────────────────────────────────────────────────────────

const typeConfig: Record<string, { color: string; icon: any }> = {
  monitor:     { color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',     icon: Eye },
  trial:       { color: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400', icon: Zap },
  research:    { color: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',  icon: FileText },
  gate:        { color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',  icon: Shield },
  kill_switch: { color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',         icon: Lock },
  signal:      { color: 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400',     icon: AlertTriangle },
  log:         { color: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',     icon: Clock },
};

const TypeBadge = ({ type, t }: { type: string; t: (k: TranslationKey) => string }) => {
  const cfg = typeConfig[type] || typeConfig.log;
  const Icon = cfg.icon;
  const label = t(`evidence.type.${type}` as TranslationKey) || type;
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${cfg.color}`}>
      <Icon className="w-3 h-3" />
      {label}
    </span>
  );
};

const statusIcon = (status: string) => {
  switch (status) {
    case 'pass': return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'fail': return <XCircle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function EvidencePage() {
  const { t } = useTranslation();
  const [data, setData] = useState<EvidenceData | null>(null);
  const [paperStatus, setPaperStatus] = useState<PaperStatus | null>(null);
  const [paperPositions, setPaperPositions] = useState<PaperPosition[]>([]);
  const [paperPerf, setPaperPerf] = useState<PaperPerformance | null>(null);
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchEvidence = useCallback(async () => {
    const result = await api.getEvidence();
    if (result) {
      setData(result as EvidenceData);
    }
    // Fetch paper trading data for Evidence card
    try {
      const [statusRes, posRes, perfRes] = await Promise.allSettled([
        api.getPolyPaperStatus(),
        api.getPolyPaperPositions(false),
        api.getPolyPaperPerformance(),
      ]);
      if (statusRes.status === 'fulfilled' && statusRes.value) {
        setPaperStatus(statusRes.value as PaperStatus);
      }
      if (posRes.status === 'fulfilled' && posRes.value) {
        setPaperPositions(posRes.value as PaperPosition[]);
      }
      if (perfRes.status === 'fulfilled' && perfRes.value) {
        setPaperPerf(perfRes.value as PaperPerformance);
      }
    } catch {
      // Paper trading data optional — gates still work without it
    }
    // Fetch journal entries for activity feed
    try {
      const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';
      const jRes = await fetch(`${STRATEGY_URL}/api/journal/entries?limit=20`);
      if (jRes.ok) {
        const jData = await jRes.json();
        setJournalEntries(jData.db_entries || []);
      }
    } catch {
      // Journal optional
    }
  }, []);

  useEffect(() => {
    fetchEvidence().finally(() => setIsLoading(false));
  }, [fetchEvidence]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchEvidence();
    setIsRefreshing(false);
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-6 space-y-4">
        <div className="space-y-2">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-3 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  const gates = data?.gates || [];
  const entries = data?.evidence_entries || [];
  const paperTrial = data?.paper_trial;
  const latestChange = data?.latest_change;
  const filesFound = data?.files_found || { evidence_log: false, readiness_checklist: false, paper_grid_json: false };
  const readyCount = gates.filter(g => g.status === 'ready').length;

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Shield className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('nav.evidence')}
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            {t('evidence.observeOnly')}
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          aria-label="Refresh evidence"
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? t('evidence.refreshing') : t('evidence.refresh')}
        </button>
      </div>

      {/* File Status Warning */}
      {!filesFound.evidence_log && !filesFound.readiness_checklist && (
        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/10 rounded-lg border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600" />
            <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
              {t('evidence.noFiles')}
            </span>
          </div>
          <p className="text-xs text-yellow-600 mt-1">
            {t('evidence.expectedFiles')}
          </p>
        </div>
      )}

      {/* ── Latest State Change Card ── */}
      {latestChange && (
        <div className="p-4 bg-gradient-to-r from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl border border-indigo-200 dark:border-indigo-800">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-indigo-600 dark:text-indigo-400" />
            <span className="text-xs font-semibold uppercase tracking-wide text-indigo-600 dark:text-indigo-400">
              {t('evidence.latestChange')}
            </span>
          </div>
          <div className="flex items-center gap-3 flex-wrap">
            {statusIcon(latestChange.status)}
            <span className="text-sm font-medium text-gray-900 dark:text-white">
              {latestChange.title}
            </span>
            <TypeBadge type={latestChange.type} t={t} />
            <span className="text-xs text-gray-500 dark:text-gray-400 ml-auto">
              {latestChange.date}
            </span>
          </div>
        </div>
      )}

      {/* ── Readiness Gates Checklist ── */}
      {gates.length > 0 && (
        <div>
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-gray-500" />
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
                {t('evidence.gatesTitle')}
              </h2>
            </div>
            <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
              {readyCount}/{gates.length} ready
            </span>
          </div>
          <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 divide-y divide-gray-100 dark:divide-gray-700">
            {gates.map((gate, i) => {
              const isReady = gate.status === 'ready';
              const hasBlocker = gate.blocked_by && gate.blocked_by !== '-' && gate.blocked_by.toLowerCase() !== 'none';
              return (
                <div key={i} className="flex items-center gap-3 px-4 py-3">
                  {isReady ? (
                    <CheckCircle2 className="w-5 h-5 text-green-500 shrink-0" />
                  ) : (
                    <Circle className="w-5 h-5 text-gray-300 dark:text-gray-600 shrink-0" />
                  )}
                  <span className={`text-sm font-medium flex-1 ${isReady ? 'text-green-700 dark:text-green-400' : 'text-gray-700 dark:text-gray-300'}`}>
                    {gate.name}
                  </span>
                  {hasBlocker && !isReady && (
                    <span className="text-xs text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/20 px-2 py-0.5 rounded-full">
                      {gate.blocked_by}
                    </span>
                  )}
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                    isReady
                      ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                      : 'bg-gray-100 text-gray-500 dark:bg-gray-700 dark:text-gray-400'
                  }`}>
                    {isReady ? t('evidence.allClear') : t('evidence.blocked')}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* ── Paper Trial Results ── */}
      {paperTrial && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Zap className="w-5 h-5 text-purple-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              {t('evidence.paperTrial')}
            </h2>
          </div>
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {Object.entries(paperTrial).map(([key, value]) => (
                <div key={key} className="flex gap-2 text-xs">
                  <span className="font-medium text-gray-700 dark:text-gray-300 min-w-[120px]">{key}:</span>
                  <span className="text-gray-600 dark:text-gray-400 break-all">
                    {typeof value === 'object' ? JSON.stringify(value) : String(value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* ── Paper Trading Status Card ── */}
      {paperStatus && (
        <div>
          <div className="flex items-center gap-2 mb-3">
            <Target className="w-5 h-5 text-purple-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Paper Trading Status
            </h2>
            <span className={`ml-auto text-xs font-medium px-2 py-0.5 rounded-full ${
              paperStatus.running
                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
            }`}>
              {paperStatus.running ? 'Running' : 'Stopped'}
            </span>
          </div>
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 space-y-4">
            {/* Summary stats */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <p className="text-xs text-gray-500 dark:text-gray-400">Active / Max</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {paperStatus.positions.active} / {paperStatus.config.max_positions}
                </p>
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <p className="text-xs text-gray-500 dark:text-gray-400">Resolved</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {paperStatus.positions.resolved}
                </p>
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <p className="text-xs text-gray-500 dark:text-gray-400">Bankroll</p>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  ${paperPerf?.bankroll?.current.toFixed(2) ?? '—'}
                </p>
                {paperPerf?.bankroll && (
                  <p className="text-xs text-gray-400">peak ${paperPerf.bankroll.peak.toFixed(2)}</p>
                )}
              </div>
              <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <p className="text-xs text-gray-500 dark:text-gray-400">Total P&L</p>
                <p className={`text-lg font-bold ${(paperPerf?.total_pnl ?? 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {paperPerf ? `${paperPerf.total_pnl >= 0 ? '+' : ''}$${paperPerf.total_pnl.toFixed(2)}` : '—'}
                </p>
                {paperPerf?.bankroll && (
                  <p className={`text-xs ${paperPerf.bankroll.drawdown_pct > 10 ? 'text-red-500' : 'text-gray-400'}`}>
                    DD: {paperPerf.bankroll.drawdown_pct.toFixed(1)}%
                  </p>
                )}
              </div>
            </div>

            {/* Active positions list */}
            {paperPositions.filter(p => !p.resolved).length > 0 && (
              <div>
                <p className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 uppercase tracking-wide">
                  Active Positions ({paperPositions.filter(p => !p.resolved).length})
                </p>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                  {paperPositions
                    .filter(p => !p.resolved)
                    .sort((a, b) => b.pnl - a.pnl)
                    .map((pos) => (
                      <div key={pos.position_id} className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-700/30 rounded-lg">
                        <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded ${
                          pos.side === 'YES'
                            ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                            : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                        }`}>
                          {pos.side}
                        </span>
                        <span className="text-xs text-gray-700 dark:text-gray-300 flex-1 truncate">
                          {pos.question}
                        </span>
                        <span className="text-xs text-gray-400 whitespace-nowrap">
                          ${(pos.entry_price * 100).toFixed(1)}c → ${(pos.current_price * 100).toFixed(1)}c
                        </span>
                        <span className={`text-xs font-semibold whitespace-nowrap ${
                          pos.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                        }`}>
                          {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toFixed(2)}
                        </span>
                      </div>
                    ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* ── Activity Feed (Batch 2B) ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <ScrollText className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            Activity Feed
          </h2>
          <span className="text-xs text-gray-400 ml-1">
            {journalEntries.length} trades · {entries.length} system
          </span>
        </div>
        {(() => {
          // Build unified feed: journal entries + evidence entries
          const feed: FeedItem[] = [];
          // Journal → trade items
          journalEntries.forEach((j) => {
            const isClosed = j.status === 'CLOSED';
            feed.push({
              id: `trade-${j.id}`,
              date: j.created_at
                ? new Date(j.created_at).toLocaleDateString() + ' ' + new Date(j.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
                : '',
              title: `${j.side} ${j.symbol} × ${j.quantity}`,
              type: 'trade',
              detail: j.entry_reason || j.strategy,
              status: isClosed ? (j.actual_pnl >= 0 ? 'pass' : 'fail') : 'info',
              meta: isClosed && j.actual_pnl
                ? `${j.actual_pnl >= 0 ? '+' : ''}฿${j.actual_pnl.toFixed(2)}`
                : j.status,
            });
          });
          // Evidence entries → system/note items
          entries.forEach((e, i) => {
            const isAlert = e.type === 'kill_switch' || e.type === 'signal';
            feed.push({
              id: `sys-${i}`,
              date: e.date,
              title: e.title,
              type: isAlert ? 'alert' : 'system',
              detail: e.details,
              status: e.status,
            });
          });
          // Sort by date desc (best-effort)
          feed.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
          const displayFeed = feed.slice(0, 15);

          const badgeColors: Record<string, string> = {
            alert: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
            trade: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400',
            note: 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400',
            system: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
          };
          const badgeIcons: Record<string, any> = {
            alert: Bell,
            trade: TrendingUp,
            note: FileText,
            system: Cpu,
          };

          return displayFeed.length === 0 ? (
            <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700">
              <p className="text-sm text-gray-500 dark:text-gray-400">No activity yet</p>
            </div>
          ) : (
            <div className="relative">
              <div className="absolute left-[19px] top-3 bottom-3 w-px bg-gray-200 dark:bg-gray-700" />
              <div className="space-y-2.5">
                {displayFeed.map((item) => {
                  const Icon = badgeIcons[item.type] || Clock;
                  return (
                    <div key={item.id} className="relative flex gap-4">
                      <div className="relative z-10 shrink-0 mt-1">
                        {item.status === 'pass' ? (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        ) : item.status === 'fail' ? (
                          <XCircle className="w-4 h-4 text-red-500" />
                        ) : (
                          <Icon className="w-4 h-4 text-gray-400" />
                        )}
                      </div>
                      <div className="flex-1 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
                        <div className="flex items-center gap-2 flex-wrap mb-1">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium ${badgeColors[item.type]}`}>
                            <Icon className="w-3 h-3" />
                            {item.type}
                          </span>
                          <span className="text-sm font-medium text-gray-900 dark:text-white">
                            {item.title}
                          </span>
                          {item.meta && (
                            <span className={`text-xs font-semibold ml-auto whitespace-nowrap ${
                              item.meta.startsWith('+') ? 'text-green-600 dark:text-green-400' :
                              item.meta.startsWith('-') || item.meta.startsWith('฿-') ? 'text-red-600 dark:text-red-400' :
                              'text-gray-500 dark:text-gray-400'
                            }`}>
                              {item.meta}
                            </span>
                          )}
                        </div>
                        {item.detail && (
                          <p className="text-xs text-gray-500 dark:text-gray-400 mt-0.5 line-clamp-2">{item.detail}</p>
                        )}
                        <div className="text-xs text-gray-400 mt-1.5">{item.date}</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })()}
      </div>

      {/* ── Evidence Log Timeline ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <FileText className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t('evidence.timeline')}
          </h2>
          {!filesFound.evidence_log && (
            <span className="text-xs text-gray-400 ml-2">{t('evidence.fileMissing')}</span>
          )}
        </div>
        {entries.length === 0 ? (
          <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-500 dark:text-gray-400">{t('evidence.noEntries')}</p>
          </div>
        ) : (
          <div className="relative">
            {/* Timeline line */}
            <div className="absolute left-[19px] top-3 bottom-3 w-px bg-gray-200 dark:bg-gray-700" />
            <div className="space-y-3">
              {entries.map((entry, i) => (
                <div key={i} className="relative flex gap-4">
                  {/* Timeline dot */}
                  <div className="relative z-10 shrink-0 mt-1">
                    {statusIcon(entry.status)}
                  </div>
                  {/* Card */}
                  <div className="flex-1 p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 transition-colors">
                    <div className="flex items-center gap-2 flex-wrap mb-1">
                      <TypeBadge type={entry.type} t={t} />
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {entry.title}
                      </span>
                    </div>
                    {entry.details && (
                      <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{entry.details}</p>
                    )}
                    <div className="text-xs text-gray-400 mt-2">{entry.date}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
