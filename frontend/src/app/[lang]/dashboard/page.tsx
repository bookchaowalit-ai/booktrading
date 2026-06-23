/**
 * Command Center - AI Trading Dashboard
 * Capital Protection & Evidence Collection view
 * Observe-only: AI operates, user monitors
 */
'use client';

import { useEffect, useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useAppStore } from '@/store/store';
import { useWebSocket, useAutoRefresh } from '@/hooks';
import { useTranslation } from '@/i18n/translations';
import { api } from '@/services/api';
import Card from '@/components/ui/Card';
import {
  Shield, ShieldAlert, ShieldCheck, Activity, Zap, Eye,
  FileText, FlaskConical, Cpu, ArrowRight, Clock,
  AlertTriangle, CheckCircle2, XCircle, Loader2, Bitcoin
} from 'lucide-react';

// --- Static config (will be replaced by API) ---
const PAPER_GRID_STATUS = {
  pair: 'BTCTHB',
  status: 'OBSERVING' as const, // RUNNING | PASSED | FAILED | OBSERVING
  duration: '1D+ live observation',
  gridLevels: { buy: [2023578, 2065736], sell: [2150052, 2192210] },
  baseline: { price: 2107894, at: '2026-06-23T00:50:23Z' },
  fills: 0,
  pnl: 0,
};

const RECOVERY_GATES = [
  { id: 'kill_switch', label: 'Kill Switch Reset', status: 'PENDING' as const, detail: 'Manual reset required after 15.8% drawdown' },
  { id: 'paper_trial', label: 'Paper Grid Trial', status: 'PASS' as const, detail: '30min + 1D observation completed, 0 errors' },
  { id: 'recovery_gate', label: 'Recovery Gate', status: 'PENDING' as const, detail: 'Need 3 consecutive profitable days on paper' },
  { id: 'capital_preserve', label: 'Capital Preservation', status: 'ACTIVE' as const, detail: 'Bot halted — no new orders' },
];

export default function CommandCenter() {
  const { t } = useTranslation();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const portfolio = useAppStore((state) => state.portfolio);
  const botStatus = useAppStore((state) => state.botStatus);
  const [isLoading, setIsLoading] = useState(true);
  const [walletBalances, setWalletBalances] = useState<{ totalTHB: number; totalUSDT: number } | null>(null);
  const [realPnl, setRealPnl] = useState<{ totalPnl: number; totalTrades: number } | null>(null);

  useWebSocket();
  useAutoRefresh(5000);

  const refreshBotStatus = useAppStore((state) => state.refreshBotStatus);

  useEffect(() => {
    const init = async () => {
      try {
        await Promise.allSettled([refreshBotStatus()]);
      } catch { /* ignore */ }
      finally { setIsLoading(false); }
    };
    init();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    api.getAllBalances()
      .then((data) => setWalletBalances({ totalTHB: data.totalTHB, totalUSDT: data.totalUSDT }))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const fetchPnl = async () => {
      try {
        const res = await fetch('/strategy-api/api/real-grid/status');
        if (!res.ok) return;
        const data = await res.json();
        const symbols = data.symbols || {};
        let totalPnl = 0, totalTrades = 0;
        for (const s of Object.values(symbols) as any[]) {
          totalPnl += s.daily_pnl || 0;
          totalTrades += s.daily_trades || 0;
        }
        setRealPnl({ totalPnl, totalTrades });
      } catch { /* ignore */ }
    };
    fetchPnl();
    const interval = setInterval(fetchPnl, 30000);
    return () => clearInterval(interval);
  }, []);

  const totalValue = portfolio?.reduce((sum, item) => sum + (item.balance * item.avgBuyPrice), 0) || 0;
  const totalProfit = botStatus?.totalProfit || 0;

  if (isLoading) {
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

  return (
    <div className="space-y-6">
      {/* === CAPITAL PROTECTION BANNER === */}
      <Card variant="elevated" className="p-5 bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/20 dark:to-orange-900/20 border-l-4 border-l-red-500">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-4">
            <div className="p-3 bg-red-100 dark:bg-red-900/40 rounded-xl">
              <ShieldAlert className="w-7 h-7 text-red-600 dark:text-red-400" />
            </div>
            <div>
              <h1 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                Capital Protection Mode
                <span className="px-2 py-0.5 text-xs font-bold bg-red-100 dark:bg-red-900/50 text-red-700 dark:text-red-300 rounded-full">
                  ACTIVE
                </span>
              </h1>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-1">
                Kill switch engaged — Bot halted at 15.8% drawdown. No new orders. Collecting evidence for recovery.
              </p>
              <div className="flex items-center gap-4 mt-3 text-xs text-gray-500 dark:text-gray-500">
                <span className="flex items-center gap-1"><Clock className="w-3 h-3" /> Since 2026-06-23</span>
                <span className="flex items-center gap-1"><Eye className="w-3 h-3" /> Observe-only mode</span>
              </div>
            </div>
          </div>
        </div>
      </Card>

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
            <span className="text-xs text-gray-500 dark:text-gray-400">Real Grid P&L</span>
          </div>
          <div className={`text-xl font-bold ${realPnl && realPnl.totalPnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {realPnl ? `฿${realPnl.totalPnl.toLocaleString()}` : '—'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {realPnl ? `${realPnl.totalTrades} fills today` : 'no data'}
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-4 h-4 text-gray-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Drawdown</span>
          </div>
          <div className="text-xl font-bold text-red-600">-15.8%</div>
          <div className="text-xs text-red-500 mt-1">triggered kill switch</div>
        </div>
      </div>

      {/* === READINESS GATES === */}
      <div>
        <h2 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
          <ShieldCheck className="w-4 h-4" /> Recovery Readiness Gates
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {RECOVERY_GATES.map((gate) => (
            <div key={gate.id} className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 flex items-start gap-3">
              {gate.status === 'PASS' ? (
                <CheckCircle2 className="w-5 h-5 text-green-500 mt-0.5 shrink-0" />
              ) : gate.status === 'ACTIVE' ? (
                <XCircle className="w-5 h-5 text-red-500 mt-0.5 shrink-0" />
              ) : (
                <Loader2 className="w-5 h-5 text-yellow-500 mt-0.5 shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-gray-900 dark:text-white">{gate.label}</span>
                  <span className={`px-1.5 py-0.5 text-[10px] font-bold rounded-full ${
                    gate.status === 'PASS' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                    gate.status === 'ACTIVE' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                    'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                  }`}>
                    {gate.status}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">{gate.detail}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* === PAPER GRID TRIAL === */}
      <div>
        <h2 className="text-sm font-bold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
          <FlaskConical className="w-4 h-4" /> Paper Grid Trial — {PAPER_GRID_STATUS.pair}
        </h2>
        <Card className="p-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Status</div>
              <div className="text-sm font-bold text-blue-600 flex items-center gap-1 mt-1">
                <Eye className="w-3 h-3" /> {PAPER_GRID_STATUS.status}
              </div>
            </div>
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Duration</div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{PAPER_GRID_STATUS.duration}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Fills</div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white mt-1">{PAPER_GRID_STATUS.fills}</div>
            </div>
            <div>
              <div className="text-xs text-gray-500 dark:text-gray-400">Paper P&L</div>
              <div className="text-sm font-semibold text-gray-900 dark:text-white mt-1">฿{PAPER_GRID_STATUS.pnl.toLocaleString()}</div>
            </div>
          </div>
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Grid Levels</div>
            <div className="flex flex-wrap gap-2 text-xs">
              <span className="px-2 py-1 bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 rounded">
                BUY ฿{PAPER_GRID_STATUS.gridLevels.buy[0].toLocaleString()} / ฿{PAPER_GRID_STATUS.gridLevels.buy[1].toLocaleString()}
              </span>
              <span className="px-2 py-1 bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 rounded">
                SELL ฿{PAPER_GRID_STATUS.gridLevels.sell[0].toLocaleString()} / ฿{PAPER_GRID_STATUS.gridLevels.sell[1].toLocaleString()}
              </span>
            </div>
          </div>
        </Card>
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
