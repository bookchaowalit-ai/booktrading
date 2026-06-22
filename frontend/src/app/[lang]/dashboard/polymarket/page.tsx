/**
 * Polymarket Paper Trading Dashboard
 * Prediction market simulation with confidence-based DCA strategy
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Target,
  RefreshCw,
  DollarSign,
  Activity,
  Clock,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Zap,
  Eye,
} from 'lucide-react';
import api from '@/services/api';
import Card from '@/components/ui/Card';

interface PolyStatus {
  running: boolean;
  uptime_seconds: number;
  scan_count: number;
  scan_interval: number;
  last_scan_time: number;
  config: {
    max_positions: number;
    position_size_usdc: number;
    min_deviation: number;
    min_liquidity: number;
    min_volume: number;
    scan_interval: number;
  };
  positions: {
    active: number;
    resolved: number;
    total: number;
  };
  performance: {
    total_pnl: number;
    total_trades: number;
    winning_trades: number;
    win_rate_pct: number;
    opportunities_found: number;
  };
}

interface PolyPosition {
  position_id: string;
  market_id: string;
  question: string;
  side: 'YES' | 'NO';
  entry_price: number;
  current_price: number;
  size_usdc: number;
  shares: number;
  entry_time: number;
  last_update_time: number;
  event_title: string;
  end_date: string | null;
  resolved: boolean;
  pnl: number;
  pnl_pct: number;
}

interface PolyTrade {
  trade_id: string;
  position_id: string;
  market_id: string;
  question: string;
  side: 'YES' | 'NO';
  action: 'OPEN' | 'CLOSE';
  price: number;
  size_usdc: number;
  shares: number;
  pnl: number;
  timestamp: number;
}

interface PolyPerformance {
  total_pnl: number;
  realized_pnl: number;
  unrealized_pnl: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate_pct: number;
  avg_hold_hours: number;
  yes_positions: number;
  no_positions: number;
  bankroll?: {
    current: number;
    peak: number;
    drawdown_pct: number;
  };
}

interface PolyNotification {
  level: string;
  message: string;
  timestamp: number;
}

interface PolySignal {
  signal_type: string;
  market_id: string;
  question: string;
  side: 'YES' | 'NO';
  confidence: number;
  price: number;
  reason: string;
  metadata: Record<string, unknown>;
}

function formatTime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${seconds % 60}s`;
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  return `${hours}h ${mins}m`;
}

function formatTimestamp(ts: number): string {
  return new Date(ts * 1000).toLocaleString();
}

export default function PolymarketPage() {
  const [status, setStatus] = useState<PolyStatus | null>(null);
  const [positions, setPositions] = useState<PolyPosition[]>([]);
  const [trades, setTrades] = useState<PolyTrade[]>([]);
  const [performance, setPerformance] = useState<PolyPerformance | null>(null);
  const [notifications, setNotifications] = useState<PolyNotification[]>([]);
  const [signals, setSignals] = useState<PolySignal[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'positions' | 'trades' | 'signals' | 'activity'>('positions');

  const fetchData = useCallback(async () => {
    try {
      const [statusData, positionsData, tradesData, perfData, notifData, signalsData] = await Promise.all([
        api.getPolyPaperStatus(),
        api.getPolyPaperPositions(false),
        api.getPolyPaperTrades(50),
        api.getPolyPaperPerformance(),
        api.getPolyPaperNotifications(20),
        api.getPolyPaperSignals(30),
      ]);
      setStatus(statusData);
      setPositions(positionsData || []);
      setTrades(tradesData || []);
      setPerformance(perfData);
      setNotifications(notifData || []);
      setSignals(signalsData || []);
    } catch (err) {
      console.error('Failed to fetch polymarket data:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Polymarket Paper Trading</h1>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map((i) => (
            <Card key={i} className="animate-pulse">
              <div className="h-20 bg-gray-200 dark:bg-gray-700 rounded" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  const activePositions = positions.filter((p) => !p.resolved);
  const resolvedPositions = positions.filter((p) => p.resolved);
  const config = status?.config;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Target className="w-6 h-6 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Polymarket Paper Trading</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Multi-signal alpha engine: mispricing, momentum, time-decay, extreme value, volume, cross-market
            </p>
          </div>
        </div>
        <button
          onClick={fetchData}
          className="flex items-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Status Banner */}
      {status && (
        <div
          className={`flex items-center gap-3 p-4 rounded-lg border ${
            status.running
              ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800'
              : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'
          }`}
        >
          {status.running ? (
            <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400" />
          ) : (
            <XCircle className="w-5 h-5 text-red-600 dark:text-red-400" />
          )}
          <div className="flex-1">
            <span className={`font-medium ${status.running ? 'text-green-700 dark:text-green-300' : 'text-red-700 dark:text-red-300'}`}>
              {status.running ? 'Bot Running' : 'Bot Stopped'}
            </span>
            <span className="ml-3 text-sm text-gray-600 dark:text-gray-400">
              Uptime: {formatTime(status.uptime_seconds)} | Scans: {status.scan_count} | Last scan: {status.last_scan_time ? formatTimestamp(status.last_scan_time) : 'Never'}
            </span>
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <Activity className="w-5 h-5 text-blue-600 dark:text-blue-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Active Positions</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {status?.positions.active || 0} / {status?.config.max_positions || 10}
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className={`p-2 rounded-lg ${(performance?.total_pnl || 0) >= 0 ? 'bg-green-100 dark:bg-green-900/30' : 'bg-red-100 dark:bg-red-900/30'}`}>
              <DollarSign className={`w-5 h-5 ${(performance?.total_pnl || 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`} />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Total P&L</p>
              <p className={`text-xl font-bold ${(performance?.total_pnl || 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                ${(performance?.total_pnl || 0).toFixed(2)}
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <BarChart3 className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Win Rate</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {status?.performance.win_rate_pct.toFixed(1) || 0}%
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {status?.performance.winning_trades || 0}W / {status?.performance.total_trades || 0} total
              </p>
            </div>
          </div>
        </Card>

        <Card>
          <div className="flex items-center gap-3">
            <div className="p-2 bg-amber-100 dark:bg-amber-900/30 rounded-lg">
              <Zap className="w-5 h-5 text-amber-600 dark:text-amber-400" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Opportunities Found</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {status?.performance.opportunities_found || 0}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Performance Breakdown */}
      {performance && (
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <BarChart3 className="w-5 h-5" />
            Performance Breakdown
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Realized P&L</p>
              <p className={`text-lg font-semibold ${performance.realized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                ${performance.realized_pnl.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Unrealized P&L</p>
              <p className={`text-lg font-semibold ${performance.unrealized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                ${performance.unrealized_pnl.toFixed(2)}
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Avg Hold Time</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {performance.avg_hold_hours.toFixed(1)}h
              </p>
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">YES / NO Positions</p>
              <p className="text-lg font-semibold text-gray-900 dark:text-white">
                {performance.yes_positions} / {performance.no_positions}
              </p>
            </div>
            {performance.bankroll && (
              <>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Bankroll (Kelly)</p>
                  <p className="text-lg font-semibold text-gray-900 dark:text-white">
                    ${performance.bankroll.current.toFixed(2)}
                  </p>
                </div>
                <div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">Drawdown</p>
                  <p className={`text-lg font-semibold ${performance.bankroll.drawdown_pct > 10 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
                    {performance.bankroll.drawdown_pct.toFixed(1)}%
                  </p>
                </div>
              </>
            )}
          </div>
        </Card>
      )}

      {/* Tabs */}
      <div className="border-b border-gray-200 dark:border-gray-700">
        <nav className="flex gap-6">
          {[
            { id: 'positions' as const, label: 'Positions', count: positions.length },
            { id: 'signals' as const, label: 'Alpha Signals', count: signals.length },
            { id: 'trades' as const, label: 'Trades', count: trades.length },
            { id: 'activity' as const, label: 'Activity', count: notifications.length },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 py-3 border-b-2 transition-colors ${
                activeTab === tab.id
                  ? 'border-purple-600 text-purple-600 dark:text-purple-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              }`}
            >
              {tab.label}
              <span className="px-2 py-0.5 text-xs bg-gray-100 dark:bg-gray-700 rounded-full">
                {tab.count}
              </span>
            </button>
          ))}
        </nav>
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        {activeTab === 'positions' && (
          <motion.div
            key="positions"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            className="space-y-4"
          >
            {positions.length === 0 ? (
              <Card className="text-center py-8">
                <Eye className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                <p className="text-gray-500 dark:text-gray-400">No positions yet. The bot is scanning for opportunities...</p>
              </Card>
            ) : (
              <>
                {activePositions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Active ({activePositions.length})
                    </h3>
                    <div className="space-y-2">
                      {activePositions.map((pos) => (
                        <Card key={pos.position_id}>
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                                  pos.side === 'YES'
                                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                }`}>
                                  {pos.side}
                                </span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  Entry: ${(pos.entry_price * 100).toFixed(1)}c
                                </span>
                                <span className="text-xs text-gray-500 dark:text-gray-400">
                                  Now: ${(pos.current_price * 100).toFixed(1)}c
                                </span>
                              </div>
                              <p className="text-sm font-medium text-gray-900 dark:text-white">
                                {pos.question}
                              </p>
                              {pos.event_title && (
                                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                  {pos.event_title}
                                </p>
                              )}
                            </div>
                            <div className="text-right ml-4">
                              <p className={`text-sm font-semibold ${pos.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toFixed(2)}
                              </p>
                              <p className={`text-xs ${pos.pnl_pct >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                {pos.pnl_pct >= 0 ? '+' : ''}{pos.pnl_pct.toFixed(1)}%
                              </p>
                              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                                ${pos.size_usdc.toFixed(2)} · {pos.shares.toFixed(1)} shares
                              </p>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}

                {resolvedPositions.length > 0 && (
                  <div>
                    <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400 mb-2">
                      Resolved ({resolvedPositions.length})
                    </h3>
                    <div className="space-y-2">
                      {resolvedPositions.slice(0, 10).map((pos) => (
                        <Card key={pos.position_id} className="opacity-75">
                          <div className="flex items-start justify-between">
                            <div className="flex-1">
                              <div className="flex items-center gap-2 mb-1">
                                <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                                  pos.side === 'YES'
                                    ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                    : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                                }`}>
                                  {pos.side}
                                </span>
                                <CheckCircle2 className="w-3 h-3 text-gray-400" />
                              </div>
                              <p className="text-sm text-gray-700 dark:text-gray-300">
                                {pos.question}
                              </p>
                            </div>
                            <div className="text-right ml-4">
                              <p className={`text-sm font-semibold ${pos.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                {pos.pnl >= 0 ? '+' : ''}${pos.pnl.toFixed(2)}
                              </p>
                            </div>
                          </div>
                        </Card>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </motion.div>
        )}

        {activeTab === 'trades' && (
          <motion.div
            key="trades"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {trades.length === 0 ? (
              <Card className="text-center py-8">
                <Clock className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                <p className="text-gray-500 dark:text-gray-400">No trades yet.</p>
              </Card>
            ) : (
              <Card>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                        <th className="pb-2 pr-4">Time</th>
                        <th className="pb-2 pr-4">Action</th>
                        <th className="pb-2 pr-4">Market</th>
                        <th className="pb-2 pr-4">Side</th>
                        <th className="pb-2 pr-4 text-right">Price</th>
                        <th className="pb-2 pr-4 text-right">Size</th>
                        <th className="pb-2 text-right">P&L</th>
                      </tr>
                    </thead>
                    <tbody>
                      {trades.map((trade) => (
                        <tr key={trade.trade_id} className="border-b border-gray-100 dark:border-gray-700/50">
                          <td className="py-3 pr-4 text-gray-600 dark:text-gray-400 whitespace-nowrap">
                            {formatTimestamp(trade.timestamp)}
                          </td>
                          <td className="py-3 pr-4">
                            <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                              trade.action === 'OPEN'
                                ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400'
                                : 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'
                            }`}>
                              {trade.action}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-gray-900 dark:text-white max-w-xs truncate">
                            {trade.question}
                          </td>
                          <td className="py-3 pr-4">
                            <span className={`px-1.5 py-0.5 text-xs rounded ${
                              trade.side === 'YES'
                                ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                                : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                            }`}>
                              {trade.side}
                            </span>
                          </td>
                          <td className="py-3 pr-4 text-right text-gray-900 dark:text-white">
                            ${(trade.price * 100).toFixed(1)}c
                          </td>
                          <td className="py-3 pr-4 text-right text-gray-900 dark:text-white">
                            ${trade.size_usdc.toFixed(2)}
                          </td>
                          <td className={`py-3 text-right font-medium ${trade.pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                            {trade.pnl !== 0 ? `${trade.pnl >= 0 ? '+' : ''}$${trade.pnl.toFixed(2)}` : '-'}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Card>
            )}
          </motion.div>
        )}

        {activeTab === 'signals' && (
          <motion.div
            key="signals"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {signals.length === 0 ? (
              <Card className="text-center py-8">
                <Zap className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                <p className="text-gray-500 dark:text-gray-400">No alpha signals detected yet. The engine scans every 2 minutes...</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {signals.map((sig, idx) => (
                  <Card key={idx}>
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                            sig.signal_type === 'mispricing' ? 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400' :
                            sig.signal_type === 'momentum' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
                            sig.signal_type === 'time_decay' ? 'bg-orange-100 text-orange-700 dark:bg-orange-900/30 dark:text-orange-400' :
                            sig.signal_type === 'extreme_value' ? 'bg-pink-100 text-pink-700 dark:bg-pink-900/30 dark:text-pink-400' :
                            sig.signal_type === 'volume_spike' ? 'bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400' :
                            sig.signal_type === 'news_sentiment' ? 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900/30 dark:text-indigo-400' :
                            sig.signal_type === 'liquidity_alpha' ? 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400' :
                            'bg-teal-100 text-teal-700 dark:bg-teal-900/30 dark:text-teal-400'
                          }`}>
                            {sig.signal_type.replace('_', ' ')}
                          </span>
                          <span className={`px-2 py-0.5 text-xs font-medium rounded ${
                            sig.side === 'YES'
                              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                          }`}>
                            {sig.side}
                          </span>
                          <span className="text-xs text-gray-500 dark:text-gray-400">
                            {(sig.confidence * 100).toFixed(0)}% confidence
                          </span>
                        </div>
                        <p className="text-sm font-medium text-gray-900 dark:text-white">
                          {sig.question}
                        </p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {sig.reason}
                        </p>
                      </div>
                      <div className="text-right ml-4">
                        <p className="text-sm font-semibold text-gray-900 dark:text-white">
                          ${(sig.price * 100).toFixed(1)}c
                        </p>
                        {/* Confidence bar */}
                        <div className="w-16 h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full mt-1">
                          <div
                            className={`h-full rounded-full ${
                              sig.confidence >= 0.7 ? 'bg-green-500' :
                              sig.confidence >= 0.5 ? 'bg-amber-500' : 'bg-red-500'
                            }`}
                            style={{ width: `${sig.confidence * 100}%` }}
                          />
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {activeTab === 'activity' && (
          <motion.div
            key="activity"
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
          >
            {notifications.length === 0 ? (
              <Card className="text-center py-8">
                <AlertCircle className="w-12 h-12 mx-auto text-gray-400 dark:text-gray-500 mb-3" />
                <p className="text-gray-500 dark:text-gray-400">No activity yet.</p>
              </Card>
            ) : (
              <div className="space-y-2">
                {notifications.map((notif, idx) => (
                  <Card key={idx}>
                    <div className="flex items-start gap-3">
                      {notif.level === 'info' ? (
                        <AlertCircle className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                      ) : notif.level === 'success' ? (
                        <CheckCircle2 className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                      ) : (
                        <AlertCircle className="w-5 h-5 text-amber-500 flex-shrink-0 mt-0.5" />
                      )}
                      <div className="flex-1">
                        <p className="text-sm text-gray-900 dark:text-white">{notif.message}</p>
                        <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                          {formatTimestamp(notif.timestamp)}
                        </p>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {/* Config Card */}
      {config && (
        <Card>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Zap className="w-5 h-5" />
            Bot Configuration
          </h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-sm">
            <div>
              <p className="text-gray-500 dark:text-gray-400">Position Size</p>
              <p className="font-medium text-gray-900 dark:text-white">${config.position_size_usdc}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Min Deviation</p>
              <p className="font-medium text-gray-900 dark:text-white">{(config.min_deviation * 100).toFixed(0)}%</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Min Liquidity</p>
              <p className="font-medium text-gray-900 dark:text-white">${config.min_liquidity}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Min Volume</p>
              <p className="font-medium text-gray-900 dark:text-white">${config.min_volume}</p>
            </div>
            <div>
              <p className="text-gray-500 dark:text-gray-400">Scan Interval</p>
              <p className="font-medium text-gray-900 dark:text-white">{config.scan_interval}<span className="text-gray-500"> sec</span></p>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}
