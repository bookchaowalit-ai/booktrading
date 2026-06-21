/**
 * Real Grid Trading Dashboard
 * Live monitoring of the BTCTHB grid bot running on Binance TH.
 * Polls: Go backend (/api/trade/*) + Python strategy (/strategy-api/api/real-grid/*)
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
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
} from 'lucide-react';
import { api } from '@/services/api';
import { useToast } from '@/components/ui/Toast';

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
}

interface GridStatus {
  running: boolean;
  enabled: boolean;
  symbols: Record<string, GridSymbolStatus>;
  risk?: RiskStatus;
  journal_stats?: JournalStats;
}

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

  const fetchData = useCallback(async () => {
    try {
      const [status, orders, history, bals, journal] = await Promise.all([
        api.getRealGridStatus(),
        api.getTradeOpenOrders('BTCTHB'),
        api.getRealTradeHistory(30),
        api.getTradeBalances(),
        api.getTradeJournalEntries(20),
      ]);

      setGridStatus(status);
      setOpenOrders(orders?.orders || []);
      setTradeHistory(Array.isArray(history) ? history : []);
      setBalances(bals || []);
      setJournalEntries(Array.isArray(journal) ? journal : []);
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

  const handleCancelOrder = async (orderId: number, side: string, price: string) => {
    if (!confirm(`Cancel ${side} order @ ${Number(price).toLocaleString()} THB?`)) return;
    setCancellingIds(prev => new Set(prev).add(orderId));
    try {
      await api.cancelTradeOrder('BTCTHB', orderId);
      success(`Order #${orderId} cancelled`);
      fetchData();
    } catch (e: any) {
      toastError(e.message || 'Failed to cancel order');
    } finally {
      setCancellingIds(prev => { const next = new Set(prev); next.delete(orderId); return next; });
    }
  };

  // Derived data
  const btcStatus = gridStatus?.symbols?.BTCTHB;
  const currentPrice = btcStatus?.last_price || 0;
  const buyOrders = openOrders.filter(o => o.side === 'BUY').sort((a, b) => Number(b.price) - Number(a.price));
  const sellOrders = openOrders.filter(o => o.side === 'SELL').sort((a, b) => Number(a.price) - Number(b.price));
  const thbBalance = balances.find(b => b.asset === 'THB');
  const btcBalance = balances.find(b => b.asset === 'BTC');
  const usdtBalance = balances.find(b => b.asset === 'USDT');

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
              BTCTHB
            </span>
          </h1>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Binance TH · Live orders · Auto-refresh every 10s
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

      {/* ── Stats Cards ───────────────────────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <DollarSign className="w-4 h-4 text-blue-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">BTC Price</span>
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
            {openOrders.length}
            <span className="text-sm font-normal text-gray-500 ml-1">
              ({buyOrders.length}B / {sellOrders.length}S)
            </span>
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            {btcStatus && btcStatus.daily_pnl >= 0
              ? <TrendingUp className="w-4 h-4 text-green-500" />
              : <TrendingDown className="w-4 h-4 text-red-500" />}
            <span className="text-xs text-gray-500 dark:text-gray-400">Daily PnL</span>
          </div>
          <div className={`text-lg font-bold ${
            btcStatus && btcStatus.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'
          }`}>
            {btcStatus ? formatTHB(btcStatus.daily_pnl) : '—'}
          </div>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-1">
            <Clock className="w-4 h-4 text-orange-500" />
            <span className="text-xs text-gray-500 dark:text-gray-400">Trades Today</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            {btcStatus?.daily_trades ?? 0}
          </div>
        </motion.div>
      </div>

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

      {/* ── Balances ──────────────────────────────────────────────────── */}
      <div className="grid lg:grid-cols-3 gap-4 mb-6">
        {[thbBalance, btcBalance, usdtBalance].map((bal, i) => (
          <div key={i} className="bg-white dark:bg-gray-800 rounded-xl p-4 border border-gray-200 dark:border-gray-700">
            <div className="flex items-center gap-2 mb-2">
              <Wallet className="w-4 h-4 text-gray-400" />
              <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {bal?.asset || '—'}
              </span>
            </div>
            {bal ? (
              <div className="space-y-1">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Free</span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {bal.asset === 'BTC' ? bal.free.toFixed(5) : bal.free.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Locked</span>
                  <span className="font-medium text-orange-600">
                    {bal.asset === 'BTC' ? bal.locked.toFixed(5) : bal.locked.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
                <div className="flex justify-between text-sm pt-1 border-t border-gray-100 dark:border-gray-700">
                  <span className="text-gray-500 dark:text-gray-400">Total</span>
                  <span className="font-bold text-gray-900 dark:text-white">
                    {bal.asset === 'BTC' ? bal.total.toFixed(5) : bal.total.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                  </span>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">No data</p>
            )}
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
                  <th className="text-right px-4 py-2">Qty (BTC)</th>
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
                        onClick={() => handleCancelOrder(order.orderId, 'BUY', order.price)}
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
                  <th className="text-right px-4 py-2">Qty (BTC)</th>
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
                        onClick={() => handleCancelOrder(order.orderId, 'SELL', order.price)}
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
                <th className="text-left px-4 py-2">Side</th>
                <th className="text-left px-4 py-2">Type</th>
                <th className="text-right px-4 py-2">Price</th>
                <th className="text-right px-4 py-2">Qty</th>
                <th className="text-right px-4 py-2">Executed</th>
                <th className="text-left px-4 py-2">Status</th>
              </tr>
            </thead>
            <tbody>
              {tradeHistory.length === 0 ? (
                <tr><td colSpan={7} className="px-4 py-6 text-center text-sm text-gray-400">No trades yet</td></tr>
              ) : tradeHistory.slice(0, 15).map((trade) => (
                <tr key={trade.id} className="border-b border-gray-50 dark:border-gray-700/50">
                  <td className="px-4 py-2.5 text-xs text-gray-500 dark:text-gray-400">
                    {timeAgo(trade.created_at)}
                  </td>
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
