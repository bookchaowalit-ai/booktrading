/**
 * AI Command Center
 * Read-only operational dashboard backed by /api/command-center.
 */
'use client';

import type { ComponentType } from 'react';
import { useCallback, useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Bitcoin,
  CheckCircle2,
  Clock,
  Cpu,
  DollarSign,
  Eye,
  FileText,
  FlaskConical,
  Loader2,
  Lock,
  RefreshCw,
  Shield,
  ShieldAlert,
  ShieldCheck,
  Sparkles,
  TrendingDown,
  Wallet,
  Zap,
} from 'lucide-react';
import { api } from '@/services/api';
import Card from '@/components/ui/Card';
import { useTranslation } from '@/i18n/translations';

interface CommandCenterData {
  ai_summary: string;
  today: {
    headline: string;
    summary: string;
    human_action: string;
    blocked_by: string[];
  };
  timestamp: string;
  current_decision: 'WAIT' | 'REVIEW_SIGNALS' | 'ENABLE_DRY_RUN' | 'MONITOR';
  next_trigger: string;
  kill_switch: {
    active: boolean;
    drawdown_pct: number;
    max_drawdown_pct: number;
  };
  positions: {
    active: number;
    resolved: number;
  };
  grid: {
    running: boolean;
    daily_fills: number;
    daily_pnl: number;
  };
  evidence: {
    latest: { date: string; title: string } | null;
    gates_ready: number;
    gates_total: number;
  };
  research: {
    crypto_pairs: number;
  };
  paper_trial: unknown | null;
  system_health: {
    strategy_api: string;
    redis_connected: boolean;
  };
  capital: {
    paper_bankroll: number;
    peak_bankroll: number;
    bankroll_pnl: number;
    active_positions: number;
    max_positions: number;
    estimated_exposure: number;
    max_allowed_exposure: number;
    drawdown_pct: number;
    max_drawdown_pct: number;
    kill_switch_active: boolean;
    grid_running: boolean;
    grid_daily_pnl: number;
  };
}

const decisionMeta = {
  WAIT: {
    label: 'Wait',
    title: 'Capital protection is active',
    tone: 'red',
    icon: ShieldAlert,
    description: 'The system is intentionally halted until exposure and evidence gates improve.',
  },
  REVIEW_SIGNALS: {
    label: 'Review signals',
    title: 'Evidence review is the next action',
    tone: 'amber',
    icon: Activity,
    description: 'Resolved positions are producing signal evidence. Review losers before any reset.',
  },
  ENABLE_DRY_RUN: {
    label: 'Enable dry-run',
    title: 'Dry-run gate is approaching',
    tone: 'blue',
    icon: Zap,
    description: 'Order flow can be validated without placing real trades.',
  },
  MONITOR: {
    label: 'Monitor',
    title: 'System is in monitoring mode',
    tone: 'green',
    icon: ShieldCheck,
    description: 'Continue observation and evidence logging.',
  },
};

const toneClasses = {
  red: {
    panel: 'border-red-200 bg-red-50/80 text-red-950 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-100',
    icon: 'bg-red-100 text-red-700 dark:bg-red-900/50 dark:text-red-300',
    badge: 'bg-red-100 text-red-700 dark:bg-red-900/60 dark:text-red-200',
    bar: 'bg-red-500',
  },
  amber: {
    panel: 'border-amber-200 bg-amber-50/80 text-amber-950 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100',
    icon: 'bg-amber-100 text-amber-700 dark:bg-amber-900/50 dark:text-amber-300',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900/60 dark:text-amber-200',
    bar: 'bg-amber-500',
  },
  blue: {
    panel: 'border-blue-200 bg-blue-50/80 text-blue-950 dark:border-blue-900/60 dark:bg-blue-950/30 dark:text-blue-100',
    icon: 'bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300',
    badge: 'bg-blue-100 text-blue-700 dark:bg-blue-900/60 dark:text-blue-200',
    bar: 'bg-blue-500',
  },
  green: {
    panel: 'border-emerald-200 bg-emerald-50/80 text-emerald-950 dark:border-emerald-900/60 dark:bg-emerald-950/30 dark:text-emerald-100',
    icon: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/50 dark:text-emerald-300',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-200',
    bar: 'bg-emerald-500',
  },
};

function formatTime(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return 'Unknown';
  return date.toLocaleString();
}

function formatTHB(value: number) {
  return `฿${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

function progressValue(ready: number, total: number) {
  if (!total) return 0;
  return Math.max(0, Math.min(100, (ready / total) * 100));
}

export default function CommandCenter() {
  const { t } = useTranslation();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const [data, setData] = useState<CommandCenterData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async (refresh = false) => {
    if (refresh) setIsRefreshing(true);
    const result = await api.getCommandCenter();
    if (result) {
      setData(result);
      setError(null);
    } else if (!refresh) {
      setError('Unable to load command center data. Retrying…');
    }
    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="h-44 rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 animate-pulse" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((item) => (
            <div key={item} className="h-28 rounded-lg border border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="mx-auto max-w-7xl space-y-5 p-6">
        <div className="flex items-center gap-3 rounded-xl border border-amber-200 bg-amber-50 p-5 dark:border-amber-800 dark:bg-amber-900/20">
          <AlertTriangle className="h-5 w-5 text-amber-600 dark:text-amber-400" />
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-300">{error || 'Unable to load dashboard data.'}</p>
            <button onClick={() => fetchData(true)} className="mt-1 text-xs text-amber-700 underline hover:no-underline dark:text-amber-400">Retry</button>
          </div>
        </div>
      </div>
    );
  }

  const meta = decisionMeta[data.current_decision] || decisionMeta.WAIT;
  const tone = toneClasses[meta.tone as keyof typeof toneClasses];
  const DecisionIcon = meta.icon;
  const gateProgress = progressValue(data.evidence.gates_ready, data.evidence.gates_total);
  const positionTargetMet = data.positions.active <= 8;
  const systemHealthy = data.system_health.strategy_api === 'healthy' && data.system_health.redis_connected;

  const nextCards = [
    {
      title: t('nav.evidence'),
      detail: data.evidence.latest?.title || 'No evidence entry yet',
      href: '/dashboard/evidence',
      icon: FileText,
      tone: 'text-indigo-600 bg-indigo-50 dark:bg-indigo-950/40 dark:text-indigo-300',
    },
    {
      title: t('nav.research'),
      detail: `${data.research.crypto_pairs} crypto pairs under watch`,
      href: '/dashboard/research',
      icon: FlaskConical,
      tone: 'text-cyan-700 bg-cyan-50 dark:bg-cyan-950/40 dark:text-cyan-300',
    },
    {
      title: t('nav.system'),
      detail: systemHealthy ? 'Core services healthy' : 'Service attention needed',
      href: '/dashboard/system',
      icon: Cpu,
      tone: 'text-emerald-700 bg-emerald-50 dark:bg-emerald-950/40 dark:text-emerald-300',
    },
  ];

  return (
    <div className="mx-auto max-w-7xl space-y-6">
      {/* Today Brief */}
      <section className="relative overflow-hidden rounded-xl border border-indigo-200/60 bg-gradient-to-br from-indigo-50 via-white to-violet-50 dark:border-indigo-800/40 dark:from-indigo-950/30 dark:via-gray-900 dark:to-violet-950/20">
        {/* Header */}
        <div className="flex flex-wrap items-center gap-3 border-b border-indigo-100 px-5 py-3 dark:border-indigo-900/50">
          <Sparkles className="h-4 w-4 text-indigo-500 dark:text-indigo-400" />
          <span className="text-sm font-semibold text-indigo-700 dark:text-indigo-300">
            {t('today.brief')}
          </span>
          <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${tone.badge}`}>
            {meta.label}
          </span>
          <span className="ml-auto text-xs text-gray-400 dark:text-gray-500">
            {formatTime(data.timestamp)}
          </span>
        </div>

        {/* 3-column body */}
        <div className="grid gap-0 divide-y md:grid-cols-3 md:divide-x md:divide-y-0 md:divide-indigo-100 dark:md:divide-indigo-900/50">
          {/* What is happening */}
          <div className="p-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <Eye className="h-3.5 w-3.5" />
              {t('today.happening')}
            </div>
            <p className="text-sm font-medium leading-snug text-gray-900 dark:text-white">
              {data.today.headline}
            </p>
            <p className="mt-2 text-xs leading-relaxed text-gray-600 dark:text-gray-400">
              {data.today.summary}
            </p>
          </div>

          {/* What should I do */}
          <div className="p-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <Zap className="h-3.5 w-3.5" />
              {t('today.humanAction')}
            </div>
            <p className="text-sm font-medium leading-snug text-gray-900 dark:text-white">
              {data.today.human_action}
            </p>
          </div>

          {/* What is blocked */}
          <div className="p-5">
            <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-gray-500 dark:text-gray-400">
              <Lock className="h-3.5 w-3.5" />
              {t('today.blockedBy')}
            </div>
            {data.today.blocked_by.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="h-4 w-4" />
                {t('today.noBlockers')}
              </div>
            ) : (
              <ul className="space-y-1.5">
                {data.today.blocked_by.map((block, i) => (
                  <li key={i} className="flex items-start gap-2 text-sm text-gray-700 dark:text-gray-300">
                    <AlertTriangle className="mt-0.5 h-3.5 w-3.5 flex-shrink-0 text-amber-500 dark:text-amber-400" />
                    {block}
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>
      </section>

      {/* Capital Snapshot + Risk Exposure */}
      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* Capital Snapshot */}
        <div className="relative overflow-hidden rounded-xl border border-emerald-200/60 bg-gradient-to-br from-emerald-50 via-white to-teal-50 dark:border-emerald-800/40 dark:from-emerald-950/30 dark:via-gray-900 dark:to-teal-950/20">
          <div className="flex items-center gap-2 border-b border-emerald-100 px-5 py-3 dark:border-emerald-900/50">
            <Wallet className="h-4 w-4 text-emerald-600 dark:text-emerald-400" />
            <span className="text-sm font-semibold text-emerald-700 dark:text-emerald-300">
              {t('today.capitalSnapshot')}
            </span>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-3 gap-4">
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.paperBankroll')}
                </div>
                <div className="mt-1 text-xl font-semibold text-gray-950 dark:text-white">
                  ${data.capital.paper_bankroll.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.peakBankroll')}
                </div>
                <div className="mt-1 text-xl font-semibold text-gray-950 dark:text-white">
                  ${data.capital.peak_bankroll.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.bankrollPnl')}
                </div>
                <div className={`mt-1 text-xl font-semibold ${
                  data.capital.bankroll_pnl >= 0
                    ? 'text-emerald-600 dark:text-emerald-400'
                    : 'text-red-600 dark:text-red-400'
                }`}>
                  {data.capital.bankroll_pnl >= 0 ? '+' : ''}${data.capital.bankroll_pnl.toFixed(2)}
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Risk Exposure */}
        <div className="relative overflow-hidden rounded-xl border border-amber-200/60 bg-gradient-to-br from-amber-50 via-white to-orange-50 dark:border-amber-800/40 dark:from-amber-950/30 dark:via-gray-900 dark:to-orange-950/20">
          <div className="flex items-center gap-2 border-b border-amber-100 px-5 py-3 dark:border-amber-900/50">
            <TrendingDown className="h-4 w-4 text-amber-600 dark:text-amber-400" />
            <span className="text-sm font-semibold text-amber-700 dark:text-amber-300">
              {t('today.riskExposure')}
            </span>
          </div>
          <div className="p-5">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.activePositions')}
                </div>
                <div className="mt-1 text-xl font-semibold text-gray-950 dark:text-white">
                  {data.capital.active_positions}
                  <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">
                    / {data.capital.max_positions} {t('today.positionsUnit')}
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.estimatedExposure')}
                </div>
                <div className="mt-1 text-xl font-semibold text-gray-950 dark:text-white">
                  ${data.capital.estimated_exposure.toFixed(2)}
                  <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">
                    / ${data.capital.max_allowed_exposure.toFixed(2)}
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.drawdown')}
                </div>
                <div className={`mt-1 text-xl font-semibold ${
                  data.capital.drawdown_pct > data.capital.max_drawdown_pct
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-gray-950 dark:text-white'
                }`}>
                  {data.capital.drawdown_pct.toFixed(2)}%
                  <span className="ml-1 text-sm font-normal text-gray-500 dark:text-gray-400">
                    {t('today.drawdownLimit')}: {data.capital.max_drawdown_pct.toFixed(1)}%
                  </span>
                </div>
              </div>
              <div>
                <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                  {t('today.killSwitchStatus')}
                </div>
                <div className="mt-1">
                  {data.capital.kill_switch_active ? (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-red-100 px-2.5 py-0.5 text-sm font-medium text-red-700 dark:bg-red-900/60 dark:text-red-200">
                      <ShieldAlert className="h-3.5 w-3.5" />
                      {t('today.killSwitchActive')}
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-100 px-2.5 py-0.5 text-sm font-medium text-emerald-700 dark:bg-emerald-900/60 dark:text-emerald-200">
                      <ShieldCheck className="h-3.5 w-3.5" />
                      {t('today.killSwitchOff')}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className={`relative overflow-hidden rounded-lg border p-6 ${tone.panel}`}>
        <div className="relative z-10 grid gap-6 lg:grid-cols-[1.5fr_1fr]">
          <div className="space-y-5">
            <div className="flex flex-wrap items-center gap-3">
              <span className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-semibold ${tone.badge}`}>
                <DecisionIcon className="h-3.5 w-3.5" />
                {meta.label}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-white/70 px-3 py-1 text-xs text-gray-600 dark:bg-gray-950/30 dark:text-gray-300">
                <Eye className="h-3.5 w-3.5" />
                Observe-only
              </span>
            </div>

            <div>
              <h1 className="max-w-3xl text-3xl font-semibold tracking-normal text-gray-950 dark:text-white">
                {meta.title}
              </h1>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-gray-700 dark:text-gray-300">
                {meta.description}
              </p>
            </div>

            <div className="rounded-lg border border-white/60 bg-white/70 p-4 dark:border-gray-800/80 dark:bg-gray-950/30">
              <div className="text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
                Next trigger
              </div>
              <div className="mt-1 text-lg font-semibold text-gray-950 dark:text-white">
                {data.next_trigger}
              </div>
            </div>
          </div>

          <div className="rounded-lg border border-white/70 bg-white/75 p-4 dark:border-gray-800/80 dark:bg-gray-950/35">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Last sync</div>
                <div className="text-sm font-medium text-gray-950 dark:text-white">{formatTime(data.timestamp)}</div>
              </div>
              <button
                onClick={() => fetchData(true)}
                disabled={isRefreshing}
                className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-gray-200 bg-white text-gray-600 hover:bg-gray-50 disabled:opacity-50 dark:border-gray-700 dark:bg-gray-900 dark:text-gray-300 dark:hover:bg-gray-800"
                aria-label="Refresh command center"
              >
                <RefreshCw className={`h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              </button>
            </div>

            <div className="mt-5 space-y-4">
              <StatusLine
                label="Kill switch"
                value={data.kill_switch.active ? 'Active' : 'Off'}
                danger={data.kill_switch.active}
              />
              <StatusLine
                label="Active positions"
                value={`${data.positions.active} / target <= 8`}
                danger={!positionTargetMet}
              />
              <StatusLine
                label="Grid observer"
                value={data.grid.running ? 'Running' : 'Stopped'}
                danger={!data.grid.running}
              />
              <StatusLine
                label="System"
                value={systemHealthy ? 'Healthy' : 'Degraded'}
                danger={!systemHealthy}
              />
            </div>
          </div>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          icon={Shield}
          label="Drawdown"
          value={`${data.kill_switch.drawdown_pct.toFixed(1)}%`}
          detail={`Limit ${data.kill_switch.max_drawdown_pct.toFixed(1)}%`}
          danger={data.kill_switch.drawdown_pct > data.kill_switch.max_drawdown_pct}
        />
        <MetricCard
          icon={Activity}
          label="Legacy exposure"
          value={`${data.positions.active}`}
          detail={`${data.positions.resolved} resolved positions`}
          danger={!positionTargetMet}
        />
        <MetricCard
          icon={Zap}
          label="Grid today"
          value={`${data.grid.daily_fills} fills`}
          detail={formatTHB(data.grid.daily_pnl)}
          danger={data.grid.daily_pnl < 0}
        />
        <MetricCard
          icon={Bitcoin}
          label="Research scope"
          value={`${data.research.crypto_pairs}`}
          detail="crypto pairs ranked"
        />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-[1.1fr_0.9fr]">
        <Card className="p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-base font-semibold text-gray-950 dark:text-white">Recovery gates</h2>
              <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                Gates stay closed until evidence supports the next mode.
              </p>
            </div>
            <div className="text-right">
              <div className="text-2xl font-semibold text-gray-950 dark:text-white">
                {data.evidence.gates_ready}/{data.evidence.gates_total}
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">ready</div>
            </div>
          </div>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-gray-100 dark:bg-gray-800">
            <div className={`h-full rounded-full ${tone.bar}`} style={{ width: `${gateProgress}%` }} />
          </div>
          <div className="mt-4 flex items-center gap-3 rounded-lg bg-gray-50 p-3 dark:bg-gray-900/70">
            {data.evidence.gates_ready === data.evidence.gates_total ? (
              <CheckCircle2 className="h-5 w-5 text-emerald-500" />
            ) : (
              <Loader2 className="h-5 w-5 text-amber-500" />
            )}
            <div>
              <div className="text-sm font-medium text-gray-950 dark:text-white">
                {data.evidence.gates_total - data.evidence.gates_ready} gate(s) remaining
              </div>
              <div className="text-xs text-gray-500 dark:text-gray-400">
                Review Evidence before any mode change.
              </div>
            </div>
          </div>
        </Card>

        <Card className="p-5">
          <h2 className="text-base font-semibold text-gray-950 dark:text-white">Operating posture</h2>
          <div className="mt-4 space-y-3">
            <PostureRow label="Trading mode" value="Capital protection" />
            <PostureRow label="Bot action" value={data.kill_switch.active ? 'Blocked by kill switch' : 'Readiness gated'} />
            <PostureRow label="Paper grid" value={data.grid.running ? 'Observing BTCTHB' : 'Idle'} />
            <PostureRow label="Human role" value="Monitor and log evidence" />
          </div>
        </Card>
      </section>

      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-semibold text-gray-700 dark:text-gray-300">Explore details</h2>
          <span className="text-xs text-gray-400">Read-only views</span>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          {nextCards.map((card) => {
            const Icon = card.icon;
            return (
              <button
                key={card.href}
                onClick={() => router.push(`/${locale}${card.href}`)}
                className="group rounded-lg border border-gray-200 bg-white p-4 text-left transition hover:border-gray-300 dark:border-gray-800 dark:bg-gray-900 dark:hover:border-gray-700"
              >
                <div className="flex items-center gap-3">
                  <span className={`inline-flex h-10 w-10 items-center justify-center rounded-md ${card.tone}`}>
                    <Icon className="h-5 w-5" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-gray-950 dark:text-white">{card.title}</div>
                    <div className="truncate text-xs text-gray-500 dark:text-gray-400">{card.detail}</div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-gray-400 transition group-hover:translate-x-0.5" />
                </div>
              </button>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function StatusLine({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="flex items-center justify-between gap-4">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`text-sm font-medium ${danger ? 'text-red-600 dark:text-red-300' : 'text-gray-950 dark:text-white'}`}>
        {value}
      </span>
    </div>
  );
}

function MetricCard({
  icon: Icon,
  label,
  value,
  detail,
  danger,
}: {
  icon: ComponentType<{ className?: string }>;
  label: string;
  value: string;
  detail: string;
  danger?: boolean;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-md bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-300">
          <Icon className="h-4 w-4" />
        </span>
        <span className={`h-2 w-2 rounded-full ${danger ? 'bg-red-500' : 'bg-emerald-500'}`} />
      </div>
      <div className="mt-4 text-xs font-medium uppercase tracking-wide text-gray-500 dark:text-gray-400">
        {label}
      </div>
      <div className="mt-1 text-2xl font-semibold text-gray-950 dark:text-white">{value}</div>
      <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">{detail}</div>
    </Card>
  );
}

function PostureRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-md bg-gray-50 px-3 py-2 dark:bg-gray-900/70">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className="text-right text-sm font-medium text-gray-950 dark:text-white">{value}</span>
    </div>
  );
}
