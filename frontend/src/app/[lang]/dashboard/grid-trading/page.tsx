/**
 * Real Grid Trading Dashboard
 * Live monitoring of multi-symbol grid bot running on Binance TH.
 * Polls: Go backend (/api/trade/*) + Python strategy (/strategy-api/api/real-grid/*)
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Grid3X3,
  Activity,
  DollarSign,
  TrendingUp,
  TrendingDown,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Wallet,
  Clock,
  XCircle,
  CheckCircle2,
  AlertTriangle,
  Power,
  PowerOff,
  Shield,
  BookOpen,
  BarChart3,
  Target,
  Zap,
  Heart,
  Layers,
  Brain,
} from 'lucide-react';
import { api } from '@/services/api';
import { backtestService } from '@/services/backtest';
import type { PerformanceData, SweepResultItem } from '@/types/backtest';
import { useToast } from '@/components/ui/Toast';
import GridConfigPanel from '@/components/GridConfigPanel';

// ── Types ──────────────────────────────────────────────────────────────────────

interface OpenOrder {
  orderId: number;
  symbol: string;
  side: 'BUY' | 'SELL';
  price: string;
  origQty: string;
  status: string;
  time: number;
}

interface TradeRecord {
  id: string;
  symbol: string;
  side: string;
  type: string;
  quantity: number;
  price: number;
  executed_qty: number;
  executed_price: number;
  status: string;
  fee: number;
  created_at: string;
  filled_at?: string;
}

interface BalanceItem {
  asset: string;
  free: number;
  locked: number;
  total: number;
}

interface GridSymbolStatus {
  last_price: number;
  active_buys: number;
  active_sells: number;
  trades_executed: number;
  daily_pnl: number;
  daily_trades: number;
  halted: boolean;
  // Auto-compounding metrics
  cumulative_pnl: number;
  current_order_size: number;
  base_order_size: number;
  compound_multiplier: number;
}

interface GridStatus {
  running: boolean;
  enabled: boolean;
  symbols: Record<string, GridSymbolStatus>;
  totalCumulative_pnl?: number;
  risk?: RiskStatus;
  journal_stats?: JournalStats;
}

// Active symbols (concentrated capital strategy)
const ALL_SYMBOLS = ['BTCTHB', 'ETHTHB'];
const PARKED_SYMBOLS = ['BNBTHB', 'SOLTHB', 'XRPTHB'];

interface RiskStatus {
  halted: boolean;
  halt_reason: string;
  daily_pnl: number;
  daily_trades: number;
  daily_wins: number;
  daily_losses: number;
  consecutive_losses: number;
  max_consecutive_losses: number;
  current_drawdown_pct: number;
  max_drawdown_pct: number;
  peak_equity: number;
  total_trades: number;
  win_rate_pct: number;
  config: {
    max_daily_loss_thb: number;
    max_drawdown_pct: number;
    max_order_size_thb: number;
    risk_per_trade_pct: number;
    max_consecutive_losses: number;
    max_open_orders: number;
  };
  recent_events: Array<{ time: number; type: string; message: string }>;
}

interface JournalStats {
  total_entries: number;
  open_entries: number;
  closed_entries: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  total_fees: number;
}

interface JournalEntry {
  id: number;
  symbol: string;
  side: string;
  strategy: string;
  entry_reason: string;
  entry_price: number;
  quantity: number;
  expected_risk_thb: number;
  expected_reward_thb: number;
  exit_price: number;
  exit_reason: string;
  actual_pnl: number;
  fee: number;
  exchange_order_id: string;
  status: string;
  created_at: string;
  closed_at?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

function formatTHB(value: number): string {
  return new Intl.NumberFormat('th-TH', {
    style: 'currency',
    currency: 'THB',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatBTC(value: number): string {
  return `${value.toFixed(5)} BTC`;
}

function timeAgo(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

// ── Component ──────────────────────────────────────────────────────────────────

export default function GridTradingPage() {
  const { success, error: toastError } = useToast();

  const [gridStatus, setGridStatus] = useState<GridStatus | null>(null);
  const [openOrders, setOpenOrders] = useState<OpenOrder[]>([]);
  const [tradeHistory, setTradeHistory] = useState<TradeRecord[]>([]);
  const [balances, setBalances] = useState<BalanceItem[]>([]);
  const [journalEntries, setJournalEntries] = useState<JournalEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
  const [killing, setKilling] = useState(false);
  const [enabling, setEnabling] = useState(false);
  const [cancellingIds, setCancellingIds] = useState<Set<number>>(new Set());
  const [showJournal, setShowJournal] = useState(false);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTCTHB');
  // Performance & Backtest state
  const [perfData, setPerfData] = useState<PerformanceData | null>(null);
  const [showPerfPanel, setShowPerfPanel] = useState(true);
  const [sweepResults, setSweepResults] = useState<SweepResultItem[]>([]);
  const [sweepLoading, setSweepLoading] = useState(false);
  const [sweepSymbol, setSweepSymbol] = useState('BTCTHB');
  const [sweepVolMode, setSweepVolMode] = useState<'fixed' | 'atr'>('fixed');
  const [sweepDone, setSweepDone] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      // Fetch open orders for ALL symbols in parallel
      const [status, ...ordersResults] = await Promise.all([
        api.getRealGridStatus(),
        ...ALL_SYMBOLS.map(sym => api.getTradeOpenOrders(sym).catch(() => ({ orders: [] }))),
        api.getRealTradeHistory(50),
        api.getTradeBalances(),
        api.getTradeJournalEntries(20),
        api.getRealGridPerformance(),
      ]);

      // Combine orders from all symbols
      const allOrders = ordersResults
        .slice(0, ALL_SYMBOLS.length)
        .flatMap((result: any) => result?.orders || []);

      const history = ordersResults[ALL_SYMBOLS.length];
      const bals = ordersResults[ALL_SYMBOLS.length + 1];
      const journal = ordersResults[ALL_SYMBOLS.length + 2];
      const perf = ordersResults[ALL_SYMBOLS.length + 3];

      setGridStatus(status);
      setOpenOrders(allOrders);
      setTradeHistory(Array.isArray(history) ? history : []);
      setBalances(bals || []);
      setJournalEntries(Array.isArray(journal) ? journal : []);
      if (perf?.symbols) setPerfData(perf);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to fetch grid data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // poll every 10s
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleKill = async () => {
    if (!confirm('⚠️ KILL SWITCH: This will halt ALL real trading. Continue?')) return;
    setKilling(true);
    try {
      await api.killRealGrid();
      success('Grid bot killed — all trading halted');
      fetchData();
    } catch (e: any) {
      toastError(e.message || 'Failed to kill grid bot');
    } finally {
      setKilling(false);
    }
  };

  const handleEnable = async () => {
    setEnabling(true);
    try {
      await api.enableRealGrid();
      success('Grid bot re-enabled — trading resumed');
      fetchData();
    } catch (e: any) {
      toastError(e.message || 'Failed to enable grid bot');
    } finally {
      setEnabling(false);
    }
  };

  const handleCancelOrder = async (orderId: number, symbol: string, side: string, price: string) => {
    if (!confirm(`Cancel ${symbol} ${side} order @ ${Number(price).toLocaleString()} THB?`)) return;
    setCancellingIds(prev => new Set(prev).add(orderId));
    try {
      await api.cancelTradeOrder(symbol, orderId);
      success(`Order #${orderId} cancelled`);
      fetchData();
    } catch (e: any) {
      toastError(e.message || 'Failed to cancel order');
    } finally {
      setCancellingIds(prev => { const next = new Set(prev); next.delete(orderId); return next; });
    }
  };

  const handleRunSweep = async () => {
    setSweepLoading(true);
    setSweepDone(false);
    setSweepResults([]);
    try {
      const result = await backtestService.runParameterSweep({
        symbol: sweepSymbol,
        days: 30,
        interval: '1h',
        volatility_mode: sweepVolMode,
      });
      setSweepResults(result.results || []);
      setSweepDone(true);
      success(`Sweep complete: ${result.total_combinations} combinations tested`);
    } catch (e: any) {
      toastError(e.message || 'Parameter sweep failed');
    } finally {
      setSweepLoading(false);
    }
  };

  // Derived data - aggregate across all symbols
  const symbols = gridStatus?.symbols || {};
  const selectedStatus = symbols[selectedSymbol];
  const currentPrice = selectedStatus?.last_price || 0;
  
  // Filter orders by selected symbol
  const symbolOrders = openOrders.filter(o => o.symbol === selectedSymbol);
  const buyOrders = symbolOrders.filter(o => o.side === 'BUY').sort((a, b) => Number(b.price) - Number(a.price));
  const sellOrders = symbolOrders.filter(o => o.side === 'SELL').sort((a, b) => Number(a.price) - Number(b.price));
  
  // Aggregate stats across all symbols
  const totalDailyPnl = Object.values(symbols).reduce((sum, s) => sum + (s.daily_pnl || 0), 0);
  const totalDailyTrades = Object.values(symbols).reduce((sum, s) => sum + (s.daily_trades || 0), 0);
  const totalCumulativePnl = gridStatus?.totalCumulative_pnl || Object.values(symbols).reduce((sum, s) => sum + (s.cumulative_pnl || 0), 0);
  const activeSymbolsCount = Object.keys(symbols).length;
  
  const thbBalance = balances.find(b => b.asset === 'THB');
  const btcBalance = balances.find(b => b.asset === 'BTC');
  const ethBalance = balances.find(b => b.asset === 'ETH');
  const bnbBalance = balances.find(b => b.asset === 'BNB');
  const solBalance = balances.find(b => b.asset === 'SOL');
  const usdtBalance = balances.find(b => b.asset === 'USDT');
  const displayBalances = [thbBalance, btcBalance, ethBalance, bnbBalance, solBalance, usdtBalance].filter(Boolean) as BalanceItem[];

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <RefreshCw className="w-8 h-8 text-purple-600 animate-spin" />
        <span className="ml-3 text-gray-500 dark:text-gray-400">Loading real trading data...</span>
      </div>
    );
  }

  return (
    <div>
      {/* ── Header + Controls ─────────────────────────────────────────── */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white flex items-center gap-3">
            <Grid3X3 className="w-7 h-7 text-purple-600" />
            Real Grid Trading
            <span className="text-sm font-normal px-2 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300">
              {activeSymbolsCount} symbols
            </span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Binance TH · Multi-symbol · Auto-refresh every 10s
            {lastRefresh && ` · Last: ${lastRefresh.toLocaleTimeString()}`}
          </p>
        </div>

        <div className="flex items-center gap-3">
          {/* Bot status indicator */}
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
            gridStatus?.enabled
              ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
              : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
          }`}>
            {gridStatus?.enabled ? (
              <><CheckCircle2 className="w-4 h-4" /> Running</>
            ) : (
              <><AlertTriangle className="w-4 h-4" /> Halted</>
            )}
          </div>

          <button
            onClick={fetchData}
            className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-400"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>

          {gridStatus?.enabled ? (
            <button
              onClick={handleKill}
              disabled={killing}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg font-medium text-sm disabled:opacity-50"
            >
              <PowerOff className="w-4 h-4" />
              {killing ? 'Killing...' : 'Kill Switch'}
            </button>
          ) : (
            <button
              onClick={handleEnable}
              disabled={enabling}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-medium text-sm disabled:opacity-50"
            >
              <Power className="w-4 h-4" />
              {enabling ? 'Enabling...' : 'Re-enable'}
            </button>
          )}
        </div>
      </div>

      {/* ── Symbol Tabs ──────────────────────────────────────────────── */}
      <div className="flex gap-2 mb-6 overflow-x-auto pb-2">
        {ALL_SYMBOLS.map(sym => {
          const symStatus = symbols[sym];
          const isActive = selectedSymbol === sym;
          const symPnl = symStatus?.daily_pnl || 0;
          return (
            <button
              key={sym}
              onClick={() => setSelectedSymbol(sym)}
              className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium text-sm whitespace-nowrap transition-all ${
                isActive
                  ? 'bg-purple-600 text-white shadow-lg shadow-purple-600/20'
                  : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
              }`}
            >
              {sym}
              {symStatus?.halted && (
                <span className="w-2 h-2 rounded-full bg-red-500" title="Halted" />
              )}
              {symPnl !== 0 && (
                <span className={`text-xs ${
                  isActive ? 'text-purple-200' : symPnl >= 0 ? 'text-green-500' : 'text-red-500'
                }`}>
                  {symPnl >= 0 ? '+' : ''}{symPnl.toFixed(0)}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* ── Performance Summary Strip (always visible) ──────────────── */}
      {perfData?.summary && (
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3 mb-6">
          <div className="bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/20 dark:to-indigo-900/20 rounded-xl p-3 border border-purple-100 dark:border-purple-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <TrendingUp className="w-3.5 h-3.5 text-purple-500" />
              <span className="text-xs text-purple-600 dark:text-purple-400 font-medium">Profit Velocity</span>
            </div>
            <div className="text-lg font-bold text-purple-700 dark:text-purple-300">
              ฿{perfData.summary.total_profit_velocity?.toFixed(0) || '0'}/day
            </div>
          </div>
          <div className="bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/20 dark:to-emerald-900/20 rounded-xl p-3 border border-green-100 dark:border-green-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Target className="w-3.5 h-3.5 text-green-500" />
              <span className="text-xs text-green-600 dark:text-green-400 font-medium">Avg Fill Rate</span>
            </div>
            <div className="text-lg font-bold text-green-700 dark:text-green-300">
              {perfData.summary.avg_fill_rate?.toFixed(1) || '0'}%
            </div>
          </div>
          <div className="bg-gradient-to-r from-blue-50 to-cyan-50 dark:from-blue-900/20 dark:to-cyan-900/20 rounded-xl p-3 border border-blue-100 dark:border-blue-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <BarChart3 className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-xs text-blue-600 dark:text-blue-400 font-medium">Avg Sharpe</span>
            </div>
            <div className={`text-lg font-bold ${
              (perfData.summary.avg_sharpe_ratio || 0) > 0 ? 'text-blue-700 dark:text-blue-300' : 'text-gray-500'
            }`}>
              {perfData.summary.avg_sharpe_ratio?.toFixed(2) || '0.00'}
            </div>
          </div>
          <div className="bg-gradient-to-r from-rose-50 to-pink-50 dark:from-rose-900/20 dark:to-pink-900/20 rounded-xl p-3 border border-rose-100 dark:border-rose-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Activity className="w-3.5 h-3.5 text-rose-500" />
              <span className="text-xs text-rose-600 dark:text-rose-400 font-medium">Avg Sortino</span>
            </div>
            <div className={`text-lg font-bold ${
              (perfData.summary.avg_sortino_ratio || 0) > 0 ? 'text-rose-700 dark:text-rose-300' : 'text-gray-500'
            }`}>
              {perfData.summary.avg_sortino_ratio?.toFixed(2) || '0.00'}
            </div>
          </div>
          <div className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-900/20 dark:to-orange-900/20 rounded-xl p-3 border border-amber-100 dark:border-amber-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <CheckCircle2 className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-xs text-amber-600 dark:text-amber-400 font-medium">Best Filler</span>
            </div>
            <div className="text-lg font-bold text-amber-700 dark:text-amber-300">
              {perfData.summary.best_fill_symbol || '—'}
            </div>
          </div>
          <div className="bg-gradient-to-r from-teal-50 to-emerald-50 dark:from-teal-900/20 dark:to-emerald-900/20 rounded-xl p-3 border border-teal-100 dark:border-teal-800/30">
            <div className="flex items-center gap-1.5 mb-0.5">
              <Zap className="w-3.5 h-3.5 text-teal-500" />
              <span className="text-xs text-teal-600 dark:text-teal-400 font-medium">Needs Work</span>
            </div>
            <div className="text-lg font-bold text-teal-700 dark:text-teal-300">
              {perfData.summary.worst_fill_symbol || '—'}
            </div>
          </div>
        </div>
      )}

      {/* ── Stats Cards ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-blue-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">{selectedSymbol} Price</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            {currentPrice > 0 ? formatTHB(currentPrice) : '—'}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Activity className="w-4 h-4 text-purple-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Open Orders</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            {symbolOrders.length}
            <span className="text-sm font-normal text-gray-500 ml-1">
              ({buyOrders.length}B / {sellOrders.length}S)
            </span>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            {totalDailyPnl >= 0
              ? <TrendingUp className="w-4 h-4 text-green-500" />
              : <TrendingDown className="w-4 h-4 text-red-500" />}
            <span className="text-xs text-gray-500 dark:text-gray-400">Daily PnL (All)</span>
          </div>
          <div className={`text-lg font-bold ${
            totalDailyPnl >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatTHB(totalDailyPnl)}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">{totalDailyTrades} trades today</div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Layers className="w-4 h-4 text-indigo-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Cumulative PnL</span>
          </div>
          <div className={`text-lg font-bold ${
            totalCumulativePnl >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {formatTHB(totalCumulativePnl)}
          </div>
          <div className="text-xs text-gray-400 mt-0.5">All-time compound</div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Zap className="w-4 h-4 text-amber-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Compound ({selectedSymbol})</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            {selectedStatus?.compound_multiplier?.toFixed(2) || '1.00'}x
          </div>
          <div className="text-xs text-gray-400 mt-0.5">
            Size: {selectedStatus?.current_order_size?.toFixed(6) || '—'}
          </div>
        </motion.div>
      </div>

      {/* ── Strategy Intelligence ──────────────────────────────────── */}
      {perfData?.symbols && (
        <div className="bg-gradient-to-r from-indigo-50 via-purple-50 to-pink-50 dark:from-indigo-900/20 dark:via-purple-900/20 dark:to-pink-900/20 rounded-xl border border-indigo-100 dark:border-indigo-800/30 p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Brain className="w-5 h-5 text-indigo-500" />
              Strategy Intelligence
            </h3>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">Fee floor: 0.5%</span>
              <span className="text-xs px-1.5 py-0.5 rounded bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400">Active</span>
            </div>
          </div>

          {/* Regime overview */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-4">
            {Object.entries(perfData.symbols).map(([sym, data]) => {
              const regimeConfig: Record<string, { label: string; color: string; action: string; bg: string }> = {
                low_vol: { label: 'Low Volatility', color: 'text-green-700 dark:text-green-300', action: 'Tightened grid, more levels', bg: 'bg-green-100 dark:bg-green-900/40' },
                normal: { label: 'Normal', color: 'text-blue-700 dark:text-blue-300', action: 'Standard grid parameters', bg: 'bg-blue-100 dark:bg-blue-900/40' },
                high_vol: { label: 'High Volatility', color: 'text-yellow-700 dark:text-yellow-300', action: 'Widened grid, fewer levels', bg: 'bg-yellow-100 dark:bg-yellow-900/40' },
                extreme: { label: 'EXTREME', color: 'text-red-700 dark:text-red-300', action: 'HALTED — too dangerous', bg: 'bg-red-100 dark:bg-red-900/40' },
              };
              const rc = regimeConfig[data.regime] || regimeConfig.normal;
              return (
                <div key={sym} className="bg-white/60 dark:bg-gray-800/60 rounded-lg p-3 border border-white/50 dark:border-gray-700/50">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-sm font-bold text-gray-800 dark:text-white">{sym}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${rc.bg} ${rc.color}`}>
                      {rc.label}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div className="text-gray-500 dark:text-gray-400">ATR %ile</div>
                      <div className="font-semibold text-gray-700 dark:text-gray-300">{data.atr_percentile?.toFixed(0) || '0'}%</div>
                    </div>
                    <div>
                      <div className="text-gray-500 dark:text-gray-400">Allocation</div>
                      <div className={`font-semibold ${data.allocation_weight > 1.2 ? 'text-green-600' : data.allocation_weight < 0.8 ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'}`}>
                        {data.allocation_weight?.toFixed(1) || '1.0'}x
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-500 dark:text-gray-400">Grid Levels</div>
                      <div className="font-semibold text-gray-700 dark:text-gray-300">{data.current_grid_levels || '—'}</div>
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-gray-500 dark:text-gray-400 italic">
                    {rc.action}
                  </div>
                </div>
              );
            })}
          </div>

          {/* Capital allocation ranking */}
          <div className="bg-white/60 dark:bg-gray-800/60 rounded-lg p-3 border border-white/50 dark:border-gray-700/50">
            <div className="text-xs font-medium text-gray-600 dark:text-gray-300 mb-2 flex items-center gap-1.5">
              <BarChart3 className="w-3.5 h-3.5 text-purple-500" />
              Capital Allocation Ranking
              <span className="text-gray-400 font-normal">(composite: 40% Sharpe + 30% Fill Rate + 30% Velocity)</span>
            </div>
            <div className="flex gap-3">
              {Object.entries(perfData.symbols)
                .sort((a, b) => (b[1].allocation_score || 0) - (a[1].allocation_score || 0))
                .map(([sym, data], idx) => (
                  <div key={sym} className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
                    idx === 0 ? 'bg-green-100 dark:bg-green-900/30 border border-green-200 dark:border-green-800' :
                    'bg-gray-100 dark:bg-gray-700/50 border border-gray-200 dark:border-gray-600'
                  }`}>
                    <span className={`text-xs font-bold ${idx === 0 ? 'text-green-700 dark:text-green-300' : 'text-gray-500'}`}>
                      #{idx + 1}
                    </span>
                    <span className="text-sm font-semibold text-gray-800 dark:text-white">{sym}</span>
                    <span className="text-xs text-gray-500 dark:text-gray-400">
                      Score: {data.allocation_score?.toFixed(2) || '0.00'}
                    </span>
                  </div>
                ))}
            </div>
            <div className="mt-2 text-xs text-gray-400">
              Allocation adjusts daily — top performer gets 1.5x grid levels, lowest gets 0.5x
            </div>
          </div>

          {/* Parked symbols notice */}
          {PARKED_SYMBOLS.length > 0 && (
            <div className="mt-3 text-xs text-gray-400 dark:text-gray-500 flex items-center gap-1.5">
              <Shield className="w-3 h-3" />
              Parked symbols (not trading): {PARKED_SYMBOLS.join(', ')} — capital concentrated for better returns
            </div>
          )}
        </div>
      )}

      {/* ── Risk Manager ─────────────────────────────────────────────── */}
      {gridStatus?.risk && (
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-4 mb-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
              <Shield className="w-5 h-5 text-indigo-500" />
              Risk Manager
              {gridStatus.risk.halted && (
                <span className="text-xs px-2 py-0.5 rounded bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400">
                  HALTED: {gridStatus.risk.halt_reason}
                </span>
              )}
            </h3>
            {gridStatus.risk.halted && (
              <button
                onClick={async () => {
                  try {
                    await api.resetRisk();
                    success('Risk manager reset');
                    fetchData();
                  } catch (e: any) {
                    toastError(e.message || 'Failed to reset');
                  }
                }}
                className="text-xs px-3 py-1 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg"
              >
                Reset Kill Switch
              </button>
            )}
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
            {/* Win Rate */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Win Rate</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                {gridStatus.risk.win_rate_pct}%
              </div>
              <div className="text-xs text-gray-400">{gridStatus.risk.daily_wins}W / {gridStatus.risk.daily_losses}L today</div>
            </div>

            {/* Drawdown */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Drawdown</div>
              <div className={`text-lg font-bold ${
                gridStatus.risk.current_drawdown_pct > 3 ? 'text-red-600' : 'text-gray-900 dark:text-white'
              }`}>
                {gridStatus.risk.current_drawdown_pct}%
              </div>
              <div className="text-xs text-gray-400">Max: {gridStatus.risk.max_drawdown_pct}%</div>
            </div>

            {/* Consecutive Losses */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Consec. Losses</div>
              <div className={`text-lg font-bold ${
                gridStatus.risk.consecutive_losses >= 3 ? 'text-orange-600' : 'text-gray-900 dark:text-white'
              }`}>
                {gridStatus.risk.consecutive_losses}
              </div>
              <div className="text-xs text-gray-400">Max: {gridStatus.risk.max_consecutive_losses}</div>
            </div>

            {/* Total Trades */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Trades</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                {gridStatus.risk.total_trades}
              </div>
              <div className="text-xs text-gray-400">{gridStatus.risk.daily_trades} today</div>
            </div>

            {/* Daily P&L */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Daily P&L</div>
              <div className={`text-lg font-bold ${
                gridStatus.risk.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'
              }`}>
                {formatTHB(gridStatus.risk.daily_pnl)}
              </div>
              <div className="text-xs text-gray-400">Limit: {formatTHB(gridStatus.risk.config.max_daily_loss_thb)}</div>
            </div>

            {/* Risk Events */}
            <div className="bg-gray-50 dark:bg-gray-700/50 rounded-lg p-3">
              <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Recent Events</div>
              <div className="text-lg font-bold text-gray-900 dark:text-white">
                {gridStatus.risk.recent_events?.length || 0}
              </div>
              <div className="text-xs text-gray-400">Last 24h</div>
            </div>
          </div>

          {/* Recent Risk Events */}
          {gridStatus.risk.recent_events?.length > 0 && (
            <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
              <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Recent Risk Events</div>
              <div className="space-y-1 max-h-24 overflow-y-auto">
                {gridStatus.risk.recent_events.slice(-5).reverse().map((evt, i) => (
                  <div key={i} className="text-xs flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full ${
                      evt.type === 'HALT' ? 'bg-red-500' :
                      evt.type === 'ORDER_PLACED' ? 'bg-green-500' :
                      evt.type === 'TRADE_RESULT' ? 'bg-blue-500' : 'bg-gray-400'
                    }`} />
                    <span className="text-gray-500 dark:text-gray-400">
                      {new Date(evt.time * 1000).toLocaleTimeString()}
                    </span>
                    <span className="text-gray-700 dark:text-gray-300">{evt.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Grid Config Panel ────────────────────────────────────────── */}
      <div className="mb-6">
        <GridConfigPanel symbols={ALL_SYMBOLS} />
      </div>

      {/* ── Balances ──────────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        {displayBalances.map((bal, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-2">
              <Wallet className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {bal.asset}
              </span>
            </div>
            <div className="space-y-1">
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Free</span>
                <span className="font-medium text-gray-900 dark:text-white text-right">
                  {['BTC','ETH','BNB','SOL'].includes(bal.asset) ? bal.free.toFixed(5) : bal.free.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Locked</span>
                <span className="font-medium text-orange-600 text-right">
                  {['BTC','ETH','BNB','SOL'].includes(bal.asset) ? bal.locked.toFixed(5) : bal.locked.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex justify-between text-sm pt-1 border-t border-gray-100 dark:border-gray-700">
                <span className="text-gray-500 dark:text-gray-400">Total</span>
                <span className="font-bold text-gray-900 dark:text-white text-right">
                  {['BTC','ETH','BNB','SOL'].includes(bal.asset) ? bal.total.toFixed(5) : bal.total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* ── Open Orders ───────────────────────────────────────────────── */}
      <div className="grid lg:grid-cols-2 gap-6 mb-6">
        {/* Buy Orders */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h3 className="font-semibold text-green-700 dark:text-green-400 flex items-center gap-2">
              <TrendingDown className="w-4 h-4" />
              Buy Orders ({buyOrders.length})
            </h3>
            <span className="text-xs text-gray-400">Below market</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left px-4 py-2">Price (THB)</th>
                  <th className="text-right px-4 py-2">Qty ({selectedSymbol.replace('THB','')})</th>
                  <th className="text-right px-4 py-2">Notional</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {buyOrders.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-400">No buy orders</td></tr>
                ) : buyOrders.map(order => (
                  <tr key={order.orderId} className="border-b border-gray-50 dark:border-gray-700/50 hover:bg-green-50 dark:hover:bg-green-900/10">
                    <td className="px-4 py-2.5 text-sm font-medium text-green-700 dark:text-green-400">
                      ฿{Number(order.price).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                      {Number(order.origQty).toFixed(5)}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-500 dark:text-gray-400">
                      ฿{(Number(order.price) * Number(order.origQty)).toFixed(0)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => handleCancelOrder(order.orderId, order.symbol, 'BUY', order.price)}
                        disabled={cancellingIds.has(order.orderId)}
                        className="text-red-400 hover:text-red-600 disabled:opacity-50"
                        title="Cancel order"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        {/* Sell Orders */}
        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
            <h3 className="font-semibold text-red-700 dark:text-red-400 flex items-center gap-2">
              <TrendingUp className="w-4 h-4" />
              Sell Orders ({sellOrders.length})
            </h3>
            <span className="text-xs text-gray-400">Above market</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left px-4 py-2">Price (THB)</th>
                  <th className="text-right px-4 py-2">Qty ({selectedSymbol.replace('THB','')})</th>
                  <th className="text-right px-4 py-2">Notional</th>
                  <th className="px-4 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {sellOrders.length === 0 ? (
                  <tr><td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-400">No sell orders</td></tr>
                ) : sellOrders.map(order => (
                  <tr key={order.orderId} className="border-b border-gray-50 dark:border-gray-700/50 hover:bg-red-50 dark:hover:bg-red-900/10">
                    <td className="px-4 py-2.5 text-sm font-medium text-red-700 dark:text-red-400">
                      ฿{Number(order.price).toLocaleString()}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                      {Number(order.origQty).toFixed(5)}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-500 dark:text-gray-400">
                      ฿{(Number(order.price) * Number(order.origQty)).toFixed(0)}
                    </td>
                    <td className="px-4 py-2.5 text-right">
                      <button
                        onClick={() => handleCancelOrder(order.orderId, order.symbol, 'SELL', order.price)}
                        disabled={cancellingIds.has(order.orderId)}
                        className="text-red-400 hover:text-red-600 disabled:opacity-50"
                        title="Cancel order"
                      >
                        <XCircle className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* ── Trade History ─────────────────────────────────────────────── */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Clock className="w-4 h-4 text-gray-400" />
            Trade History
          </h3>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                <th className="text-left px-4 py-2">Time</th>
                <th className="text-left px-4 py-2">Symbol</th>
                <th className="text-left px-4 py-2">Side</th>
                <th className="text-left px-4 py-2">Type</th>
                <th className="text-right px-4 py-2">Price</th>
                <th className="text-right px-4 py-2">Qty</th>
                <th className="text-right px-4 py-2">Executed</th>
                <th className="text-left px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {(tradeHistory?.length ?? 0) === 0 ? (
                <tr><td colSpan={8} className="px-4 py-6 text-center text-sm text-gray-400">No trades yet</td></tr>
              ) : tradeHistory.slice(0, 15).map((trade) => (
                <tr key={trade.id} className="border-b border-gray-50 dark:border-gray-700/50">
                  <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {timeAgo(trade.created_at)}
                  </td>
                  <td className="px-4 py-2.5 text-xs font-medium text-gray-700 dark:text-gray-300">{trade.symbol}</td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                      trade.side === 'BUY'
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                        : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                    }`}>
                      {trade.side}
                    </span>
                  </td>
                  <td className="px-4 py-2.5 text-xs text-gray-600 dark:text-gray-400">{trade.type}</td>
                  <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                    ฿{trade.price.toLocaleString()}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                    {trade.quantity.toFixed(5)}
                  </td>
                  <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                    {trade.executed_qty > 0 ? trade.executed_qty.toFixed(5) : '—'}
                  </td>
                  <td className="px-4 py-2.5">
                    <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                      trade.status === 'FILLED'
                        ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                        : trade.status === 'NEW'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                          : trade.status === 'CANCELLED'
                            ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                            : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                    }`}>
                      {trade.status}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── Performance & Backtest Panel ───────────────────────────── */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden mt-6">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-purple-500" />
            Performance & Backtest
            {perfData?.summary && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400">
                Avg Fill: {perfData.summary.avg_fill_rate}%
              </span>
            )}
          </h3>
          <button
            onClick={() => setShowPerfPanel(!showPerfPanel)}
            className="text-xs text-purple-600 dark:text-purple-400 hover:underline"
          >
            {showPerfPanel ? 'Hide' : 'Show'}
          </button>
        </div>

        {showPerfPanel && (
          <div className="p-4 space-y-6">
            {/* Performance Metrics per Symbol */}
            <div>
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                <Activity className="w-4 h-4 text-green-500" />
                Production Performance
                {perfData?.summary && (
                  <span className="text-xs font-normal text-gray-500">
                    Velocity: ฿{perfData.summary.total_profit_velocity?.toFixed(0)}/day across {Object.keys(perfData.symbols).length} symbols
                  </span>
                )}
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                {perfData?.symbols ? Object.entries(perfData.symbols).map(([sym, data]) => {
                  const fillPct = Math.min(data.fill_rate, 100);
                  const fillColor = fillPct >= 60 ? 'bg-green-500' : fillPct >= 30 ? 'bg-yellow-500' : 'bg-red-400';
                  const atrRange = data.atr_spacing_max - data.atr_spacing_min;
                  const atrPos = atrRange > 0 ? ((data.atr_spacing_avg - data.atr_spacing_min) / atrRange) * 100 : 50;
                  return (
                  <div key={sym} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-700/50 border border-gray-100 dark:border-gray-600">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm font-bold text-gray-800 dark:text-white">{sym}</span>
                      <span className={`text-xs px-1.5 py-0.5 rounded font-semibold ${
                        data.compound_recommendation === 'increase_threshold' ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' :
                        data.compound_recommendation === 'hold' ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400' :
                        data.compound_recommendation === 'decrease_threshold' ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400' :
                        'bg-gray-100 dark:bg-gray-600 text-gray-600 dark:text-gray-400'
                      }`}>
                        {data.compound_recommendation === 'increase_threshold' ? '⬆ Increase' :
                         data.compound_recommendation === 'hold' ? '➡ Hold' :
                         data.compound_recommendation === 'decrease_threshold' ? '⬇ Decrease' :
                         data.compound_recommendation}
                      </span>
                    </div>

                    {/* Fill Rate with progress bar */}
                    <div className="mb-2">
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-gray-500 dark:text-gray-400">Fill Rate</span>
                        <span className="font-semibold text-gray-700 dark:text-gray-300">{data.fill_rate}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full overflow-hidden">
                        <div className={`h-full ${fillColor} rounded-full transition-all duration-500`} style={{ width: `${fillPct}%` }} />
                      </div>
                      <div className="flex justify-between text-xs mt-0.5">
                        <span className="text-gray-400">{data.orders_filled} filled</span>
                        <span className="text-gray-400">{data.orders_placed} placed</span>
                      </div>
                    </div>

                    {/* ATR Spacing with range indicator */}
                    <div className="mb-2">
                      <div className="flex justify-between text-xs mb-0.5">
                        <span className="text-gray-500 dark:text-gray-400">ATR Spacing</span>
                        <span className="font-semibold text-gray-700 dark:text-gray-300">
                          {data.atr_spacing_avg > 0 ? `${data.atr_spacing_avg.toFixed(2)}%` : 'N/A'}
                        </span>
                      </div>
                      {data.atr_spacing_samples > 0 && (
                        <div className="relative">
                          <div className="w-full h-1.5 bg-gray-200 dark:bg-gray-600 rounded-full" />
                          <div className="absolute top-0 h-1.5 bg-indigo-400 rounded-full" style={{
                            left: `${Math.max(0, atrPos - 15)}%`,
                            width: '30%',
                          }} />
                          <div className="flex justify-between text-xs mt-0.5">
                            <span className="text-gray-400">{data.atr_spacing_min.toFixed(1)}%</span>
                            <span className="text-gray-400">σ={data.atr_spacing_stddev.toFixed(2)}</span>
                            <span className="text-gray-400">{data.atr_spacing_max.toFixed(1)}%</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Key metrics row */}
                    <div className="grid grid-cols-2 gap-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Velocity</div>
                        <div className={`text-sm font-semibold ${data.profit_velocity_thb_per_day > 0 ? 'text-green-600' : 'text-gray-500'}`}>
                          ฿{data.profit_velocity_thb_per_day.toFixed(0)}/d
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">Compound</div>
                        <div className="text-sm font-semibold text-gray-700 dark:text-gray-300">{data.current_compound_multiplier.toFixed(1)}x</div>
                      </div>
                    </div>

                    {/* Risk-adjusted returns */}
                    {(data.sharpe_ratio !== undefined || data.sortino_ratio !== undefined) && (
                      <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Sharpe</div>
                          <div className={`text-sm font-semibold ${
                            data.sharpe_ratio > 1 ? 'text-green-600' : data.sharpe_ratio > 0 ? 'text-yellow-600' : 'text-red-500'
                          }`}>
                            {data.sharpe_ratio?.toFixed(2) || '0.00'}
                          </div>
                        </div>
                        <div>
                          <div className="text-xs text-gray-500 dark:text-gray-400">Sortino</div>
                          <div className={`text-sm font-semibold ${
                            data.sortino_ratio > 1 ? 'text-green-600' : data.sortino_ratio > 0 ? 'text-yellow-600' : 'text-red-500'
                          }`}>
                            {data.sortino_ratio?.toFixed(2) || '0.00'}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Auto-tuned threshold */}
                    {data.auto_tuned_compound_threshold !== undefined && (
                      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500 dark:text-gray-400">Auto-tuned Threshold</span>
                          <span className="font-medium text-gray-700 dark:text-gray-300">
                            ฿{data.auto_tuned_compound_threshold?.toFixed(0) || '500'}
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Regime & Capital Allocation */}
                    {data.regime !== undefined && (
                      <div className="mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-500 dark:text-gray-400">Regime</span>
                          <span className={`font-semibold px-1.5 py-0.5 rounded text-xs ${
                            data.regime === 'low_vol' ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300' :
                            data.regime === 'normal' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300' :
                            data.regime === 'high_vol' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300' :
                            'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
                          }`}>
                            {data.regime === 'low_vol' ? 'Low Vol' :
                             data.regime === 'normal' ? 'Normal' :
                             data.regime === 'high_vol' ? 'High Vol' : 'EXTREME'}
                          </span>
                        </div>
                        <div className="flex justify-between text-xs mb-1">
                          <span className="text-gray-500 dark:text-gray-400">ATR %ile</span>
                          <span className="font-medium text-gray-700 dark:text-gray-300">
                            {data.atr_percentile?.toFixed(0) || '50'}%
                          </span>
                        </div>
                        <div className="flex justify-between text-xs">
                          <span className="text-gray-500 dark:text-gray-400">Allocation</span>
                          <span className={`font-semibold ${
                            data.allocation_weight > 1.2 ? 'text-green-600' :
                            data.allocation_weight < 0.8 ? 'text-red-500' : 'text-gray-700 dark:text-gray-300'
                          }`}>
                            {data.allocation_weight?.toFixed(1) || '1.0'}x
                          </span>
                        </div>
                      </div>
                    )}

                    {/* Last fill age */}
                    {data.last_fill_age_sec != null && (
                      <div className="flex justify-between text-xs mt-2 pt-2 border-t border-gray-200 dark:border-gray-600">
                        <span className="text-gray-500 dark:text-gray-400">Last Fill</span>
                        <span className={`font-medium ${
                          data.last_fill_age_sec < 3600 ? 'text-green-600' :
                          data.last_fill_age_sec < 86400 ? 'text-yellow-600' : 'text-red-500'
                        }`}>
                          {data.last_fill_age_sec < 3600 ? `${Math.floor(data.last_fill_age_sec / 60)}m ago` :
                           data.last_fill_age_sec < 86400 ? `${Math.floor(data.last_fill_age_sec / 3600)}h ago` :
                           `${Math.floor(data.last_fill_age_sec / 86400)}d ago`}
                        </span>
                      </div>
                    )}

                    {/* Tracking days */}
                    {data.performance_tracking_days > 0 && (
                      <div className="text-xs text-gray-400 mt-1 text-right">
                        Tracking: {data.performance_tracking_days}d
                      </div>
                    )}
                  </div>
                  );
                }) : (
                  <div className="col-span-4 text-sm text-gray-400 text-center py-4">
                    No performance data yet — bot needs to run for a while
                  </div>
                )}
              </div>
            </div>

            {/* Parameter Sweep */}
            <div className="border-t border-gray-200 dark:border-gray-700 pt-4">
              <h4 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3 flex items-center gap-2">
                <Target className="w-4 h-4 text-orange-500" />
                Parameter Sweep (Backtest)
                <span className="text-xs font-normal text-gray-500">Test 20 spacing×levels combos against historical data</span>
              </h4>
              <div className="flex flex-wrap items-end gap-3 mb-4">
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Symbol</label>
                  <select
                    value={sweepSymbol}
                    onChange={e => setSweepSymbol(e.target.value)}
                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    {ALL_SYMBOLS.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="block text-xs text-gray-500 dark:text-gray-400 mb-1">Mode</label>
                  <select
                    value={sweepVolMode}
                    onChange={e => setSweepVolMode(e.target.value as 'fixed' | 'atr')}
                    className="px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  >
                    <option value="fixed">Fixed Spacing</option>
                    <option value="atr">ATR Dynamic</option>
                  </select>
                </div>
                <button
                  onClick={handleRunSweep}
                  disabled={sweepLoading}
                  className="px-4 py-1.5 text-sm font-medium rounded-lg bg-purple-600 hover:bg-purple-700 text-white disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {sweepLoading ? (
                    <><RefreshCw className="w-3.5 h-3.5 animate-spin" /> Running...</>
                  ) : (
                    <><Zap className="w-3.5 h-3.5" /> Run Sweep</>
                  )}
                </button>
              </div>

              {/* Sweep Results Table */}
              {(sweepResults.length > 0 || sweepLoading) && (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                        <th className="text-left px-3 py-2">#</th>
                        <th className="text-right px-3 py-2">Spacing %</th>
                        <th className="text-right px-3 py-2">Levels</th>
                        <th className="text-right px-3 py-2">Net PnL</th>
                        <th className="text-right px-3 py-2">Win Rate</th>
                        <th className="text-right px-3 py-2">Trades/Day</th>
                        <th className="text-right px-3 py-2">Max DD%</th>
                        <th className="text-right px-3 py-2">Profit Factor</th>
                        <th className="text-right px-3 py-2">ATR Avg%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {sweepLoading ? (
                        <tr><td colSpan={9} className="px-4 py-6 text-center text-sm text-gray-400">
                          <RefreshCw className="w-4 h-4 animate-spin inline mr-2" />Running backtests...
                        </td></tr>
                      ) : sweepResults.map((r, idx) => (
                        <tr key={idx} className={`border-b border-gray-50 dark:border-gray-700/50 ${
                          idx === 0 ? 'bg-green-50 dark:bg-green-900/10' : ''
                        }`}>
                          <td className="px-3 py-2 text-xs text-gray-500 dark:text-gray-400">
                            {idx === 0 ? '🏆' : idx + 1}
                          </td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.grid_spacing_pct}%</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.grid_levels}</td>
                          <td className={`px-3 py-2 text-sm text-right font-medium ${
                            r.net_pnl > 0 ? 'text-green-600' : r.net_pnl < 0 ? 'text-red-600' : 'text-gray-500'
                          }`}>฿{r.net_pnl.toFixed(0)}</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.win_rate.toFixed(0)}%</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.trades_per_day.toFixed(1)}</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.max_drawdown_pct.toFixed(1)}%</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">{r.profit_factor.toFixed(2)}</td>
                          <td className="px-3 py-2 text-sm text-right text-gray-700 dark:text-gray-300">
                            {r.atr_spacing_avg > 0 ? `${r.atr_spacing_avg.toFixed(2)}%` : '—'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  {sweepDone && sweepResults.length > 0 && (
                    <div className="mt-2 px-3 py-2 text-xs text-gray-500 dark:text-gray-400 bg-gray-50 dark:bg-gray-700/50 rounded">
                      Best config: spacing={sweepResults[0].grid_spacing_pct}%, levels={sweepResults[0].grid_levels} → 
                      PnL=฿{sweepResults[0].net_pnl.toFixed(0)}, Win Rate={sweepResults[0].win_rate.toFixed(0)}%
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* ── Trade Journal ─────────────────────────────────────────────── */}
      <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden mt-6">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <BookOpen className="w-4 h-4 text-indigo-400" />
            Trade Journal
            {journalEntries.length > 0 && (
              <span className="text-xs px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400">
                {journalEntries.length}
              </span>
            )}
          </h3>
          <button
            onClick={() => setShowJournal(!showJournal)}
            className="text-xs text-indigo-600 dark:text-indigo-400 hover:underline"
          >
            {showJournal ? 'Hide' : 'Show'}
          </button>
        </div>

        {showJournal && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="text-xs text-gray-500 dark:text-gray-400 border-b border-gray-100 dark:border-gray-700">
                  <th className="text-left px-4 py-2">Time</th>
                  <th className="text-left px-4 py-2">Symbol</th>
                  <th className="text-left px-4 py-2">Side</th>
                  <th className="text-left px-4 py-2">Strategy</th>
                  <th className="text-left px-4 py-2">Entry Reason</th>
                  <th className="text-right px-4 py-2">Entry Price</th>
                  <th className="text-right px-4 py-2">Qty</th>
                  <th className="text-right px-4 py-2">Risk/Reward</th>
                  <th className="text-right px-4 py-2">Exit Price</th>
                  <th className="text-right px-4 py-2">P&L</th>
                  <th className="text-left px-4 py-2">Status</th>
                </tr>
              </thead>
              <tbody>
                {journalEntries.length === 0 ? (
                  <tr><td colSpan={11} className="px-4 py-6 text-center text-sm text-gray-400">No journal entries yet</td></tr>
                ) : journalEntries.slice(0, 20).map((entry) => (
                  <tr key={entry.id} className="border-b border-gray-50 dark:border-gray-700/50">
                    <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                      {timeAgo(entry.created_at)}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-gray-700 dark:text-gray-300">{entry.symbol}</td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                        entry.side === 'BUY'
                          ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400'
                          : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'
                      }`}>
                        {entry.side}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-gray-600 dark:text-gray-400">{entry.strategy}</td>
                    <td className="px-4 py-2.5 text-xs text-gray-600 dark:text-gray-400 max-w-[120px] truncate" title={entry.entry_reason}>
                      {entry.entry_reason || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                      ฿{entry.entry_price?.toLocaleString() || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                      {entry.quantity?.toFixed(5) || '—'}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-right text-gray-500 dark:text-gray-400">
                      {entry.expected_risk_thb ? `${formatTHB(entry.expected_risk_thb)}` : '—'}
                      {entry.expected_reward_thb ? ` / ${formatTHB(entry.expected_reward_thb)}` : ''}
                    </td>
                    <td className="px-4 py-2.5 text-sm text-right text-gray-700 dark:text-gray-300">
                      {entry.exit_price ? `฿${entry.exit_price.toLocaleString()}` : '—'}
                    </td>
                    <td className={`px-4 py-2.5 text-sm text-right font-medium ${
                      entry.actual_pnl > 0 ? 'text-green-600' :
                      entry.actual_pnl < 0 ? 'text-red-600' : 'text-gray-500'
                    }`}>
                      {entry.actual_pnl != null ? formatTHB(entry.actual_pnl) : '—'}
                    </td>
                    <td className="px-4 py-2.5">
                      <span className={`text-xs font-medium px-1.5 py-0.5 rounded ${
                        entry.status === 'OPEN'
                          ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                          : entry.status === 'CLOSED'
                            ? 'bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400'
                            : 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                      }`}>
                        {entry.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
