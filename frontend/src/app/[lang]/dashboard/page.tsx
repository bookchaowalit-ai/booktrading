/**
 * Command Center - AI Trading Dashboard
 * Single source of truth from /api/command-center
 * Observe-only: AI operates, user monitors
 */
'use client';

import { useEffect, useState, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAppStore } from '@/store/store';
import { useWebSocket, useAutoRefresh } from '@/hooks';
import { useTranslation } from '@/i18n/translations';
import { api } from '@/services/api';
import Card from '@/components/ui/Card';
import {
  Shield, ShieldAlert, ShieldCheck, Activity, Zap, Eye,
  FileText, FlaskConical, Cpu, ArrowRight, Clock,
  CheckCircle2, XCircle, Loader2, Bitcoin, RefreshCw
} from 'lucide-react';

interface CommandCenterData {
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
}

const decisionConfig = {
  WAIT: { color: 'red', icon: ShieldAlert, label: 'WAIT' },
  REVIEW_SIGNALS: { color: 'yellow', icon: Activity, label: 'REVIEW SIGNALS' },
  ENABLE_DRY_RUN: { color: 'blue', icon: Zap, label: 'ENABLE DRY-RUN' },
  MONITOR: { color: 'green', icon: ShieldCheck, label: 'MONITOR' },
};

export default function CommandCenter() {
  const { t } = useTranslation();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const portfolio = useAppStore((state) => state.portfolio);
  const botStatus = useAppStore((state) => state.botStatus);

  useWebSocket();
  useAutoRefresh(5000);

  const refreshBotStatus = useAppStore((state) => state.refreshBotStatus);
  const [data, setData] = useState<CommandCenterData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [walletBalances, setWalletBalances] = useState<{ totalTHB: number; totalUSDT: number } | null>(null);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    const result = await api.getCommandCenter();
    if (result) setData(result);
    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    fetchData();
    refreshBotStatus();
    const interval = setInterval(() => fetchData(true), 30000);
    return () => clearInterval(interval);
  }, [fetchData, refreshBotStatus]);

  useEffect(() => {
    api.getAllBalances()
      .then((data) => setWalletBalances({ totalTHB: data.totalTHB, totalUSDT: data.totalUSDT }))
      .catch(() => {});
  }, []);

  const totalValue = portfolio?.reduce((sum, item) => sum + (item.balance * item.avgBuyPrice), 0) || 0;
  const totalProfit = botStatus?.totalProfit || 0;

  if (isLoading || !data) {
    return (
      <div className="space-y-4">
        <div className="p-6 bg-gray-100 dark:bg-gray-800 rounded-xl animate-pulse">
          <div className="h-6 w-48 bg-gray-200 dark:bg-gray-700 rounded mb-2" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[1,2,3,4].map(i => <div key={i} className="h-20 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />)}
        </div>
      </div>
    );
  }

  const decision = decisionConfig[data.current_decision] || decisionConfig.WAIT;
  const DecisionIcon = decision.icon;

  return (
    <div className="space-y-6">
      {/* === CURRENT DECISION BANNER === */}
      <Card variant="elevated" className={`p-5 border-l-4 ${
        data.current_decision === 'WAIT' ? 'bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border-l-red-500' :
        data.current_decision === 'REVIEW_SIGNALS' ? 'bg-gradient-to-r from-yellow-50 to-amber-50 dark:from-yellow-900/20 dark:to-amber-900/20 border-l-yellow-500' :
        data.current_decision === 'ENABLE_DRY_RUN' ? 'bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 border-l-blue-500' :
        'bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 border-l-green-500'
      }`}>
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className={`p-3 rounded-xl ${
              data.current_decision === 'WAIT' ? 'bg-red-100 dark:bg-red-900/40' :
              data.current_decision === 'REVIEW_SIGNALS' ? 'bg-yellow-100 dark:bg-yellow-900/40' :
              data.current_decision === 'ENABLE_DRY_RUN' ? 'bg-blue-100 dark:bg-blue-900/40' :
              'bg-green-100 dark:bg-green-900/40'
            }`}>
              <DecisionIcon className={`w-7 h-7 ${
                data.current_decision === 'WAIT' ? 'text-red-600 dark:text-red-400' :
                data.current_decision === 'REVIEW_SIGNALS' ? 'text-yellow-600 dark:text-yellow-400' :
                data.current_decision === 'ENABLE_DRY_RUN' ? 'text-blue-600 dark:text-blue-400' :
                'text-green-600 dark:text-green-400'
              }`} />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                Current Decision
                <span className={`px-2 py-0.5 text-xs font-bold rounded-full ${
                  data.current_decision === 'WAIT' ? 'bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300' :
                  data.current_decision === 'REVIEW_SIGNALS' ? 'bg-yellow-100 dark:bg-yellow-900/50 text-yellow-700 dark:text-yellow-300' :
                  data.current_decision === 'ENABLE_DRY_RUN' ? 'bg-blue-100 dark:bg-blue-900/50 text-blue-700 dark:text-blue-300' :
                  'bg-green-100 dark:bg-green-900/50 text-green-700 dark:text-green-300'
                }`}>
                  {decision.label}
                </span>
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                {data.current_decision === 'WAIT' && `Kill switch ${data.kill_switch.active ? 'engaged' : 'disengaged'} — Bot halted at ${data.kill_switch.drawdown_pct.toFixed(1)}% drawdown.`}
                {data.current_decision === 'REVIEW_SIGNALS' && `Reviewing signals — ${data.evidence.gates_total - data.evidence.gates_ready} gate(s) remaining.`}
                {data.current_decision === 'ENABLE_DRY_RUN' && 'Ready to enable dry-run mode.'}
                {data.current_decision === 'MONITOR' && 'Monitoring live operations.'}
              </p>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500 dark:text-gray-500">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> {new Date(data.timestamp).toLocaleString()}</span>
                <span className="flex items-center gap-1"><Eye className="w-3 h-3" /> Observe-only mode</span>
                <button
                  onClick={() => fetchData(true)}
                  disabled={isRefreshing}
                  className="flex items-center gap-1 px-2 py-0.5 rounded hover:bg-gray-100 dark:hover:bg-gray-800 disabled:opacity-50"
                >
                  <RefreshCw className={`w-3 h-3 ${isRefreshing ? 'animate-spin' : ''}`} />
                  {isRefreshing ? 'Refreshing...' : 'Refresh'}
                </button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* === NEXT TRIGGER === */}
      <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Zap className="w-5 h-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Next Trigger</div>
            <div className="text-sm font-semibold text-gray-900 dark:text-white">{data.next_trigger}</div>
          </div>
        </div>
      </div>

      {/* === KEY METRICS === */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Bitcoin className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Portfolio Value</span>
          </div>
          <div className="text-xl font-bold text-gray-900 dark:text-white">
            ฿{totalValue.toLocaleString(undefined, { maximumFractionDigits: 0 })}
          </div>
          {walletBalances?.totalTHB ? (
            <div className="text-xs text-gray-500 mt-1">
              Cash: ฿{walletBalances.totalTHB.toLocaleString(undefined, { maximumFractionDigits: 0 })}
            </div>
          ) : null}
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Total P&L</span>
          </div>
          <div className={`text-xl font-bold ${totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            ${totalProfit.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </div>
          <div className="text-xs text-gray-500 mt-1">all time</div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Zap className="w-4 h-4 text-yellow-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Grid Fills / P&L</span>
          </div>
          <div className={`text-xl font-bold ${data.grid.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {data.grid.daily_fills} fills
          </div>
          <div className="text-xs text-gray-500 mt-1">
            ฿{data.grid.daily_pnl.toLocaleString()} today
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Kill Switch</span>
          </div>
          <div className={`text-xl font-bold ${data.kill_switch.active ? 'text-red-600' : 'text-green-600'}`}>
            {data.kill_switch.active ? 'ACTIVE' : 'OFF'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {data.kill_switch.drawdown_pct.toFixed(1)}% drawdown
          </div>
        </div>
      </div>

      {/* === READINESS GATES === */}
      <div>
        <h2 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" /> Recovery Gates ({data.evidence.gates_ready}/{data.evidence.gates_total} ready)
        </h2>
        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {data.evidence.gates_ready === data.evidence.gates_total ? (
                <CheckCircle2 className="w-6 h-6 text-green-500" />
              ) : (
                <Loader2 className="w-6 h-6 text-yellow-500" />
              )}
              <div>
                <div className="text-sm font-semibold text-gray-900 dark:text-white">
                  {data.evidence.gates_ready === data.evidence.gates_total ? 'All gates ready' : 'Gates pending'}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {data.evidence.gates_total - data.evidence.gates_ready} gate(s) remaining before dry-run
                </div>
              </div>
            </div>
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {data.evidence.gates_ready}/{data.evidence.gates_total}
            </div>
          </div>
        </div>
      </div>

      {/* === POSITIONS + RESEARCH === */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <Eye className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-bold text-gray-700 dark:text-gray-300">Active Positions</span>
          </div>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">{data.positions.active}</div>
              <div className="text-xs text-gray-500">active</div>
            </div>
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">{data.positions.resolved}</div>
              <div className="text-xs text-gray-500">resolved</div>
            </div>
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-3">
            <FlaskConical className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-bold text-gray-700 dark:text-gray-300">Research</span>
          </div>
          <div className="flex items-center gap-6">
            <div>
              <div className="text-2xl font-bold text-gray-900 dark:text-white">{data.research.crypto_pairs}</div>
              <div className="text-xs text-gray-500">crypto pairs</div>
            </div>
            {data.evidence.latest && (
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-500">Latest evidence</div>
                <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                  {data.evidence.latest.title}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* === SYSTEM HEALTH === */}
      <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
        <div className="flex items-center gap-2 mb-3">
          <Cpu className="w-5 h-5 text-green-500" />
          <span className="text-sm font-bold text-gray-700 dark:text-gray-300">System Health</span>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${data.system_health.strategy_api === 'healthy' ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-gray-600 dark:text-gray-400">Strategy API</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${data.system_health.redis_connected ? 'bg-green-500' : 'bg-red-500'}`} />
            <span className="text-xs text-gray-600 dark:text-gray-400">Redis</span>
          </div>
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${data.grid.running ? 'bg-green-500' : 'bg-yellow-500'}`} />
            <span className="text-xs text-gray-600 dark:text-gray-400">Grid Bot {data.grid.running ? 'Running' : 'Stopped'}</span>
          </div>
        </div>
      </div>

      {/* === QUICK NAVIGATION === */}
      <div>
        <h2 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3">Quick Navigation</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <button
            onClick={() => router.push(`/${locale}/dashboard/evidence`)}
            className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-purple-300 dark:hover:border-purple-700 transition-colors text-left group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <FileText className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('nav.evidence')}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Kill switch log, trial results, gates</div>
              </div>
              <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-purple-500 transition-colors" />
            </div>
          </button>

          <button
            onClick={() => router.push(`/${locale}/dashboard/research`)}
            className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-blue-300 dark:hover:border-blue-700 transition-colors text-left group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <FlaskConical className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('nav.research')}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Polymarket scanner, crypto watchlist</div>
              </div>
              <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-blue-500 transition-colors" />
            </div>
          </button>

          <button
            onClick={() => router.push(`/${locale}/dashboard/system`)}
            className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 hover:border-green-300 dark:hover:border-green-700 transition-colors text-left group"
          >
            <div className="flex items-center gap-3">
              <div className="p-2 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Cpu className="w-5 h-5 text-green-600 dark:text-green-400" />
              </div>
              <div className="flex-1">
                <div className="text-sm font-semibold text-gray-900 dark:text-white">{t('nav.system')}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Health, deploy status, settings</div>
              </div>
              <ArrowRight className="w-4 h-4 text-gray-400 group-hover:text-green-500 transition-colors" />
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}
