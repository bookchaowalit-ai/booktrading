/**
 * Daily Report Dashboard Page
 * Comprehensive daily P&L summary, risk status, open positions, and filled trades
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  FileText,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Pause,
  Play,
  Shield,
  BarChart3,
  Clock,
  Zap,
  Layers,
  Target,
  Cpu,
  Globe,
} from 'lucide-react';
import { tradeJournalService } from '@/services/trade-journal';
import { api } from '@/services/api';
import type { DailyReport } from '@/types/trade-journal';
import Card from '@/components/ui/Card';

const REAL_SYMBOLS = (process.env.NEXT_PUBLIC_REAL_SYMBOLS || 'BTCTHB,ETHTHB,BNBTHB,SOLTHB,XRPTHB').split(',').map(s => s.trim());

export default function DailyReportPage() {
  const [reports, setReports] = useState<DailyReport[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedSymbol, setSelectedSymbol] = useState(REAL_SYMBOLS[0]);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Multi-engine summary state
  const [engineSummary, setEngineSummary] = useState<{
    paperPortfolio?: { total_pnl: number; total_trades: number; win_trades: number; loss_trades: number; current_balance: number; total_pnl_percent: number };
    paperGrid?: { running: boolean; symbols: Record<string, any> };
    polyPaper?: { running: boolean; total_pnl?: number; total_trades?: number };
    arbPaper?: { running: boolean; total_pnl?: number; total_trades?: number };
    realGrid?: { running: boolean; halted: boolean; daily_pnl?: number };
    commandCenter?: { kill_switch?: { active: boolean }; current_decision?: string };
  }>({});

  const fetchEngineSummary = useCallback(async () => {
    const [paperRes, gridRes, polyRes, arbRes, realGridRes, ccRes] = await Promise.allSettled([
      api.getPaperPortfolio(),
      api.getPaperGridStatus(),
      api.getPolyPaperStatus(),
      api.getArbPaperStatus(),
      api.getRealGridStatus(),
      api.getCommandCenter(),
    ]);
    const summary: any = {};
    if (paperRes.status === 'fulfilled' && paperRes.value) {
      const p = paperRes.value as any;
      summary.paperPortfolio = { total_pnl: p.total_pnl, total_trades: p.total_trades, win_trades: p.win_trades, loss_trades: p.loss_trades, current_balance: p.current_balance, total_pnl_percent: p.total_pnl_percent };
    }
    if (gridRes.status === 'fulfilled' && gridRes.value) {
      const g = gridRes.value as any;
      summary.paperGrid = { running: g.running, symbols: g.symbols || {} };
    }
    if (polyRes.status === 'fulfilled' && polyRes.value) {
      const pp = polyRes.value as any;
      summary.polyPaper = { running: pp.running, total_pnl: pp.total_pnl, total_trades: pp.total_trades };
    }
    if (arbRes.status === 'fulfilled' && arbRes.value) {
      const a = arbRes.value as any;
      summary.arbPaper = { running: a.running, total_pnl: a.total_pnl, total_trades: a.total_trades };
    }
    if (realGridRes.status === 'fulfilled' && realGridRes.value) {
      const rg = realGridRes.value as any;
      summary.realGrid = { running: rg.running, halted: rg.halted, daily_pnl: rg.daily_pnl };
    }
    if (ccRes.status === 'fulfilled' && ccRes.value) {
      const cc = ccRes.value as any;
      summary.commandCenter = { kill_switch: cc.kill_switch, current_decision: cc.current_decision };
    }
    setEngineSummary(summary);
  }, []);

  const fetchReport = useCallback(async () => {
    try {
      setError(null);
      const data = await tradeJournalService.getDailyReport(selectedSymbol);
      setReports(prev => {
        const others = prev.filter(r => r.symbol !== selectedSymbol);
        return [...others, data];
      });
      setLastRefresh(new Date());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch daily report');
    } finally {
      setLoading(false);
    }
  }, [selectedSymbol]);

  useEffect(() => {
    fetchReport();
    fetchEngineSummary();
    const interval = setInterval(() => { fetchReport(); fetchEngineSummary(); }, 30000);
    return () => clearInterval(interval);
  }, [fetchReport, fetchEngineSummary]);

  const report = reports.find(r => r.symbol === selectedSymbol);

  if (loading && !report) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-28 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
            <FileText className="w-6 h-6 text-amber-600 dark:text-amber-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Daily Report</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              {selectedSymbol} — {new Date().toLocaleDateString()}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {lastRefresh && (
            <span className="text-xs text-gray-400 flex items-center gap-1">
              <Clock className="w-3 h-3" />
              {lastRefresh.toLocaleTimeString()}
            </span>
          )}
          {/* Symbol Selector */}
          {REAL_SYMBOLS.length > 1 && (
            <select
              value={selectedSymbol}
              onChange={(e) => { setSelectedSymbol(e.target.value); setLoading(true); }}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-3 py-2 bg-white dark:bg-gray-800 text-gray-900 dark:text-white"
            >
              {REAL_SYMBOLS.map(sym => (
                <option key={sym} value={sym}>{sym}</option>
              ))}
            </select>
          )}
          <button
            onClick={() => { setLoading(true); fetchReport(); fetchEngineSummary(); }}
            className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
          >
            <RefreshCw className={`w-5 h-5 text-gray-500 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {/* Multi-Engine Summary */}
      <Card>
        <div className="flex items-center gap-2 mb-4">
          <Globe className="w-5 h-5 text-indigo-500" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Multi-Engine Summary</h3>
          {engineSummary.commandCenter?.kill_switch?.active && (
            <span className="ml-auto flex items-center gap-1 text-xs px-2 py-0.5 rounded-full bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
              <AlertTriangle className="w-3 h-3" /> KILL SWITCH ACTIVE
            </span>
          )}
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-3">
          {/* Paper Trading Engine */}
          <div className="p-3 rounded-lg border border-purple-200 dark:border-purple-800/50 bg-purple-50/50 dark:bg-purple-900/10">
            <div className="flex items-center gap-1.5 mb-2">
              <Cpu className="w-3.5 h-3.5 text-purple-500" />
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Paper Trading</span>
            </div>
            {engineSummary.paperPortfolio ? (
              <div className="space-y-1">
                <div className={`text-sm font-bold ${engineSummary.paperPortfolio.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {engineSummary.paperPortfolio.total_pnl >= 0 ? '+' : ''}${engineSummary.paperPortfolio.total_pnl.toFixed(2)}
                </div>
                <div className="text-[10px] text-gray-500">{engineSummary.paperPortfolio.total_trades} trades ({engineSummary.paperPortfolio.win_trades}W/{engineSummary.paperPortfolio.loss_trades}L)</div>
                <div className="text-[10px] text-gray-500">Bal: ${engineSummary.paperPortfolio.current_balance.toFixed(2)}</div>
              </div>
            ) : <span className="text-xs text-gray-400">No data</span>}
          </div>

          {/* Paper Grid Bot */}
          <div className="p-3 rounded-lg border border-blue-200 dark:border-blue-800/50 bg-blue-50/50 dark:bg-blue-900/10">
            <div className="flex items-center gap-1.5 mb-2">
              <Layers className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Paper Grid</span>
              {engineSummary.paperGrid?.running ? (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500" />
              ) : (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-red-500" />
              )}
            </div>
            {engineSummary.paperGrid ? (
              <div className="space-y-1">
                <div className="text-[10px] text-gray-500">
                  {Object.keys(engineSummary.paperGrid.symbols).length} pairs
                </div>
                <div className="text-[10px] text-gray-500">
                  {Object.values(engineSummary.paperGrid.symbols).reduce((s: number, d: any) => s + (d.trades_executed || 0), 0)} total trades
                </div>
                <div className={`text-xs font-medium ${engineSummary.paperGrid.running ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {engineSummary.paperGrid.running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
            ) : <span className="text-xs text-gray-400">No data</span>}
          </div>

          {/* Polymarket Paper */}
          <div className="p-3 rounded-lg border border-emerald-200 dark:border-emerald-800/50 bg-emerald-50/50 dark:bg-emerald-900/10">
            <div className="flex items-center gap-1.5 mb-2">
              <Target className="w-3.5 h-3.5 text-emerald-500" />
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Polymarket</span>
              {engineSummary.polyPaper?.running ? (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500" />
              ) : (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-red-500" />
              )}
            </div>
            {engineSummary.polyPaper ? (
              <div className="space-y-1">
                {engineSummary.polyPaper.total_pnl != null && (
                  <div className={`text-sm font-bold ${engineSummary.polyPaper.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {engineSummary.polyPaper.total_pnl >= 0 ? '+' : ''}${engineSummary.polyPaper.total_pnl.toFixed(2)}
                  </div>
                )}
                <div className="text-[10px] text-gray-500">{engineSummary.polyPaper.total_trades || 0} trades</div>
                <div className={`text-xs font-medium ${engineSummary.polyPaper.running ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {engineSummary.polyPaper.running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
            ) : <span className="text-xs text-gray-400">No data</span>}
          </div>

          {/* Arbitrage Paper */}
          <div className="p-3 rounded-lg border border-amber-200 dark:border-amber-800/50 bg-amber-50/50 dark:bg-amber-900/10">
            <div className="flex items-center gap-1.5 mb-2">
              <Zap className="w-3.5 h-3.5 text-amber-500" />
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Arbitrage</span>
              {engineSummary.arbPaper?.running ? (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500" />
              ) : (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-red-500" />
              )}
            </div>
            {engineSummary.arbPaper ? (
              <div className="space-y-1">
                {engineSummary.arbPaper.total_pnl != null && (
                  <div className={`text-sm font-bold ${engineSummary.arbPaper.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {engineSummary.arbPaper.total_pnl >= 0 ? '+' : ''}${engineSummary.arbPaper.total_pnl.toFixed(2)}
                  </div>
                )}
                <div className="text-[10px] text-gray-500">{engineSummary.arbPaper.total_trades || 0} trades</div>
                <div className={`text-xs font-medium ${engineSummary.arbPaper.running ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {engineSummary.arbPaper.running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
            ) : <span className="text-xs text-gray-400">No data</span>}
          </div>

          {/* Real Grid */}
          <div className="p-3 rounded-lg border border-cyan-200 dark:border-cyan-800/50 bg-cyan-50/50 dark:bg-cyan-900/10">
            <div className="flex items-center gap-1.5 mb-2">
              <Activity className="w-3.5 h-3.5 text-cyan-500" />
              <span className="text-xs font-semibold text-gray-700 dark:text-gray-300">Real Grid</span>
              {engineSummary.realGrid?.running ? (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-green-500" />
              ) : (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-red-500" />
              )}
            </div>
            {engineSummary.realGrid ? (
              <div className="space-y-1">
                {engineSummary.realGrid.daily_pnl != null && (
                  <div className={`text-sm font-bold ${engineSummary.realGrid.daily_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {engineSummary.realGrid.daily_pnl >= 0 ? '+' : ''}${engineSummary.realGrid.daily_pnl.toFixed(2)}
                  </div>
                )}
                <div className={`text-xs font-medium ${engineSummary.realGrid.halted ? 'text-red-600 dark:text-red-400' : engineSummary.realGrid.running ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                  {engineSummary.realGrid.halted ? 'HALTED' : engineSummary.realGrid.running ? 'RUNNING' : 'STOPPED'}
                </div>
              </div>
            ) : <span className="text-xs text-gray-400">No data</span>}
          </div>
        </div>
        {engineSummary.commandCenter?.current_decision && (
          <div className="mt-3 pt-3 border-t border-gray-100 dark:border-gray-700">
            <span className="text-xs text-gray-500 dark:text-gray-400">Decision: </span>
            <span className="text-sm font-bold text-gray-900 dark:text-white">{engineSummary.commandCenter.current_decision}</span>
          </div>
        )}
      </Card>

      {report && (
        <>
          {/* Bot Status Banner */}
          <Card>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {report.bot_enabled ? (
                  <Play className="w-5 h-5 text-green-500" />
                ) : (
                  <Pause className="w-5 h-5 text-red-500" />
                )}
                <div>
                  <span className={`font-semibold ${report.bot_enabled ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    Bot {report.bot_enabled ? 'Active' : 'Disabled'}
                  </span>
                  <span className="text-gray-500 dark:text-gray-400 text-sm ml-2">
                    {report.bot_running ? 'Running' : 'Stopped'}
                  </span>
                </div>
              </div>
              {report.symbol_state && 'halted' in report.symbol_state && report.symbol_state.halted && (
                <span className="flex items-center gap-1 text-red-600 dark:text-red-400 text-sm font-medium bg-red-50 dark:bg-red-900/30 px-3 py-1 rounded-full">
                  <AlertTriangle className="w-4 h-4" /> HALTED
                </span>
              )}
            </div>
          </Card>

          {/* Stats Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Daily P&L */}
            <StatCard
              title="Daily P&L"
              value={formatPnl(report.symbol_state && 'daily_pnl' in report.symbol_state ? report.symbol_state.daily_pnl : 0)}
              icon={DollarSign}
              color={
                report.symbol_state && 'daily_pnl' in report.symbol_state && report.symbol_state.daily_pnl >= 0
                  ? 'green' : 'red'
              }
            />
            {/* Daily Trades */}
            <StatCard
              title="Daily Trades"
              value={String(report.symbol_state && 'daily_trades' in report.symbol_state ? report.symbol_state.daily_trades : 0)}
              icon={Activity}
              color="blue"
            />
            {/* Open Orders */}
            <StatCard
              title="Open Orders"
              value={String(report.open_orders?.length || 0)}
              subtitle={report.symbol_state && 'active_buys' in report.symbol_state
                ? `${report.symbol_state.active_buys}B / ${report.symbol_state.active_sells}S`
                : undefined}
              icon={Zap}
              color="purple"
            />
            {/* Win Rate */}
            <StatCard
              title="Win Rate"
              value={`${report.journal_stats?.win_rate?.toFixed(1) || '0.0'}%`}
              subtitle={report.journal_stats ? `${report.journal_stats.winning_trades}W / ${report.journal_stats.losing_trades}L` : undefined}
              icon={BarChart3}
              color="amber"
            />
          </div>

          {/* Risk Panel */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <Card>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <Shield className="w-5 h-5 text-blue-500" />
                Risk Status
              </h3>
              <div className="space-y-3">
                <RiskRow
                  label="Halted"
                  value={report.risk?.halted ? 'Yes' : 'No'}
                  danger={report.risk?.halted}
                />
                {report.risk?.halt_reason && (
                  <RiskRow label="Halt Reason" value={report.risk.halt_reason} danger />
                )}
                <RiskRow
                  label="Daily P&L"
                  value={formatPnl(report.risk?.daily_pnl || 0)}
                  danger={(report.risk?.daily_pnl || 0) < 0}
                />
                <RiskRow label="Daily Trades" value={String(report.risk?.daily_trades || 0)} />
                <RiskRow
                  label="Consecutive Losses"
                  value={String(report.risk?.consecutive_losses || 0)}
                  danger={(report.risk?.consecutive_losses || 0) >= 3}
                />
                <RiskRow
                  label="Drawdown"
                  value={`${(report.risk?.current_drawdown_pct || 0).toFixed(2)}%`}
                  danger={(report.risk?.current_drawdown_pct || 0) > 5}
                />
              </div>
            </Card>

            {/* Journal Stats */}
            <Card>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <BarChart3 className="w-5 h-5 text-emerald-500" />
                Journal Stats
              </h3>
              <div className="space-y-3">
                <RiskRow label="Total Entries" value={String(report.journal_stats?.total_entries || 0)} />
                <RiskRow label="Closed Trades" value={String(report.journal_stats?.closed_entries || 0)} />
                <RiskRow
                  label="Total P&L"
                  value={formatPnl(report.journal_stats?.total_pnl || 0)}
                  danger={(report.journal_stats?.total_pnl || 0) < 0}
                />
                <RiskRow
                  label="Profit Factor"
                  value={(report.journal_stats?.profit_factor || 0).toFixed(2)}
                />
                <RiskRow
                  label="Avg Win"
                  value={formatPnl(report.journal_stats?.avg_win || 0)}
                />
                <RiskRow
                  label="Avg Loss"
                  value={formatPnl(report.journal_stats?.avg_loss || 0)}
                />
              </div>
            </Card>
          </div>

          {/* Open Orders Table */}
          <Card>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Zap className="w-5 h-5 text-purple-500" />
              Open Orders ({report.open_orders?.length || 0})
            </h3>
            {report.open_orders && report.open_orders.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-2 font-medium">Side</th>
                      <th className="pb-2 font-medium">Price</th>
                      <th className="pb-2 font-medium">Qty</th>
                      <th className="pb-2 font-medium">Status</th>
                      <th className="pb-2 font-medium">Created</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {report.open_orders.map((order, i) => (
                      <tr key={order.order_id || i} className="text-gray-900 dark:text-gray-100">
                        <td className="py-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                            order.side === 'BUY'
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          }`}>
                            {order.side === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                            {order.side}
                          </span>
                        </td>
                        <td className="py-2 font-mono">{formatPrice(order.price)}</td>
                        <td className="py-2 font-mono">{order.quantity?.toFixed(6)}</td>
                        <td className="py-2">
                          <span className="text-xs px-2 py-0.5 rounded bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                            {order.status}
                          </span>
                        </td>
                        <td className="py-2 text-gray-500 text-xs">{formatDate(order.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No open orders" />
            )}
          </Card>

          {/* Filled Trades Table */}
          <Card>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <CheckCircle2 className="w-5 h-5 text-green-500" />
              Filled Trades ({report.filled_trades?.length || 0})
            </h3>
            {report.filled_trades && report.filled_trades.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      <th className="pb-2 font-medium">Side</th>
                      <th className="pb-2 font-medium">Price</th>
                      <th className="pb-2 font-medium">Qty</th>
                      <th className="pb-2 font-medium">Fee</th>
                      <th className="pb-2 font-medium">Time</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {report.filled_trades.map((trade, i) => (
                      <tr key={trade.order_id || i} className="text-gray-900 dark:text-gray-100">
                        <td className="py-2">
                          <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-medium ${
                            trade.side === 'BUY'
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          }`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="py-2 font-mono">{formatPrice(trade.price)}</td>
                        <td className="py-2 font-mono">{trade.quantity?.toFixed(6)}</td>
                        <td className="py-2 font-mono text-gray-500">{trade.fee?.toFixed(4) || '0'}</td>
                        <td className="py-2 text-gray-500 text-xs">{formatDate(trade.created_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <EmptyState message="No filled trades today" />
            )}
          </Card>

          {/* Risk Events */}
          {report.risk_events && report.risk_events.length > 0 && (
            <Card>
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
                <AlertTriangle className="w-5 h-5 text-orange-500" />
                Risk Events ({report.risk_events.length})
              </h3>
              <div className="space-y-2">
                {report.risk_events.slice(-10).reverse().map((event, i) => (
                  <div key={i} className="flex items-start gap-3 text-sm p-2 rounded bg-gray-50 dark:bg-gray-800/50">
                    <span className="text-gray-400 text-xs whitespace-nowrap mt-0.5">
                      {formatDate(event.timestamp)}
                    </span>
                    <span className={`px-1.5 py-0.5 rounded text-xs font-medium ${
                      event.event_type === 'kill_switch' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400' :
                      event.event_type === 'loss_streak' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' :
                      'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                    }`}>
                      {event.event_type}
                    </span>
                    <span className="text-gray-700 dark:text-gray-300">{event.message}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </>
      )}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string;
  value: string;
  subtitle?: string;
  icon: any;
  color: 'green' | 'red' | 'blue' | 'purple' | 'amber';
}) {
  const colors = {
    green: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
    purple: 'bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400',
    amber: 'bg-amber-100 dark:bg-amber-900/30 text-amber-600 dark:text-amber-400',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">{title}</span>
          <div className={`p-1.5 rounded-lg ${colors[color]}`}>
            <Icon className="w-4 h-4" />
          </div>
        </div>
        <div className="text-2xl font-bold text-gray-900 dark:text-white">{value}</div>
        {subtitle && (
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">{subtitle}</div>
        )}
      </Card>
    </motion.div>
  );
}

function RiskRow({ label, value, danger }: { label: string; value: string; danger?: boolean }) {
  return (
    <div className="flex items-center justify-between py-1">
      <span className="text-sm text-gray-500 dark:text-gray-400">{label}</span>
      <span className={`text-sm font-medium ${danger ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
        {value}
      </span>
    </div>
  );
}

function EmptyState({ message }: { message: string }) {
  return (
    <div className="text-center py-8 text-gray-400 dark:text-gray-500">
      <XCircle className="w-8 h-8 mx-auto mb-2 opacity-50" />
      <p className="text-sm">{message}</p>
    </div>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}฿${value.toFixed(2)}`;
}

function formatPrice(price: number): string {
  if (price >= 1000) return `฿${Math.round(price).toLocaleString()}`;
  return `฿${price.toFixed(2)}`;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return '-';
  try {
    const d = new Date(dateStr);
    if (isNaN(d.getTime())) return dateStr;
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return dateStr;
  }
}
