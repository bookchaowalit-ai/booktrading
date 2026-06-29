/**
 * Arbitrage Paper Trading Dashboard
 * Cross-exchange arbitrage simulation (Binance Global, Binance TH, Bitkub)
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  ArrowLeftRight,
  RefreshCw,
  DollarSign,
  Activity,
  Clock,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Zap,
  TrendingUp,
  TrendingDown,
  RotateCcw,
} from 'lucide-react';
import { api } from '@/services/api';
import Card from '@/components/ui/Card';

interface ArbStatus {
  running: boolean;
  capital_thb: number;
  peak_capital_thb: number;
  pnl_thb: number;
  pnl_pct: number;
  drawdown_pct: number;
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_fees_thb: number;
  opportunities_found: number;
  opportunities_executed: number;
  last_scan_at: number;
  usdt_thb_rate: number | null;
  min_spread_pct: number;
  scan_interval_sec: number;
  recent_trades: ArbTrade[];
  recent_opportunities: ArbOpportunity[];
}

interface ArbTrade {
  id: string;
  asset: string;
  buy_exchange: string;
  sell_exchange: string;
  buy_price_thb: number;
  sell_price_thb: number;
  quantity: number;
  capital_thb: number;
  fees_thb: number;
  pnl_thb: number;
  pnl_pct: number;
  opened_at: number;
  closed_at: number | null;
}

interface ArbOpportunity {
  asset: string;
  buy_exchange: string;
  sell_exchange: string;
  buy_price_thb: number;
  sell_price_thb: number;
  spread_pct: number;
  gross_spread_pct: number;
  timestamp: number;
  executed: boolean;
}

function formatTime(ts: number): string {
  if (!ts) return '—';
  return new Date(ts * 1000).toLocaleString();
}

function timeAgo(ts: number): string {
  if (!ts) return 'never';
  const diff = Math.floor(Date.now() / 1000 - ts);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

export default function ArbitragePage() {
  const [status, setStatus] = useState<ArbStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<'trades' | 'opportunities'>('trades');
  const [resetting, setResetting] = useState(false);

  const fetchData = useCallback(async () => {
    try {
      const data = await api.getArbPaperStatus();
      setStatus(data);
    } catch (err) {
      console.error('Failed to fetch arb status:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleReset = async () => {
    if (!confirm('Reset arbitrage paper bot state? This cannot be undone.')) return;
    setResetting(true);
    await api.resetArbPaper();
    await fetchData();
    setResetting(false);
  };

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Arbitrage Paper Trading</h1>
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

  const pnlPositive = (status?.pnl_thb ?? 0) >= 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-cyan-100 dark:bg-cyan-900/30 rounded-lg">
            <ArrowLeftRight className="w-6 h-6 text-cyan-600 dark:text-cyan-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Arbitrage Paper Trading</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Cross-exchange simulation — Binance Global · Binance TH · Bitkub
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className={`flex items-center gap-2 px-3 py-1.5 rounded-full text-sm font-medium ${
            status?.running
              ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
              : 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
          }`}>
            <span className={`w-2 h-2 rounded-full ${status?.running ? 'bg-green-500 animate-pulse' : 'bg-red-500'}`} />
            {status?.running ? 'RUNNING' : 'STOPPED'}
          </div>
          <button
            onClick={handleReset}
            disabled={resetting}
            className="flex items-center gap-1.5 px-3 py-1.5 text-sm border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-700 dark:text-gray-300 disabled:opacity-50"
          >
            <RotateCcw className={`w-4 h-4 ${resetting ? 'animate-spin' : ''}`} />
            Reset
          </button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard
          title="Paper P&L"
          value={`${pnlPositive ? '+' : ''}฿${(status?.pnl_thb ?? 0).toFixed(2)}`}
          subtitle={`${pnlPositive ? '+' : ''}${(status?.pnl_pct ?? 0).toFixed(3)}%`}
          icon={pnlPositive ? TrendingUp : TrendingDown}
          color={pnlPositive ? 'green' : 'red'}
        />
        <StatCard
          title="Total Trades"
          value={String(status?.total_trades ?? 0)}
          subtitle={`${status?.winning_trades ?? 0}W / ${status?.losing_trades ?? 0}L`}
          icon={Activity}
          color="blue"
        />
        <StatCard
          title="Win Rate"
          value={`${(status?.win_rate ?? 0).toFixed(1)}%`}
          subtitle={`Fees: ฿${(status?.total_fees_thb ?? 0).toFixed(2)}`}
          icon={BarChart3}
          color="amber"
        />
        <StatCard
          title="Capital"
          value={`฿${(status?.capital_thb ?? 10000).toLocaleString()}`}
          subtitle={`Drawdown: ${(status?.drawdown_pct ?? 0).toFixed(2)}%`}
          icon={DollarSign}
          color={pnlPositive ? 'green' : 'red'}
        />
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card>
          <div className="text-sm text-gray-500 dark:text-gray-400">Opportunities</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">
            {status?.opportunities_found ?? 0}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {status?.opportunities_executed ?? 0} executed
          </div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500 dark:text-gray-400">USDT/THB Rate</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">
            {status?.usdt_thb_rate ? `฿${status.usdt_thb_rate.toFixed(2)}` : '—'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Updated {timeAgo(status?.last_scan_at ?? 0)}
          </div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500 dark:text-gray-400">Min Spread</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">
            {(status?.min_spread_pct ?? 0.3).toFixed(1)}%
          </div>
          <div className="text-xs text-gray-500 mt-1">
            After 0.2% round-trip fees
          </div>
        </Card>
        <Card>
          <div className="text-sm text-gray-500 dark:text-gray-400">Scan Interval</div>
          <div className="text-xl font-bold text-gray-900 dark:text-white mt-1">
            {status?.scan_interval_sec ?? 30}s
          </div>
          <div className="text-xs text-gray-500 mt-1">
            Last scan: {timeAgo(status?.last_scan_at ?? 0)}
          </div>
        </Card>
      </div>

      {/* Tabs: Trades / Opportunities */}
      <Card>
        <div className="flex items-center gap-4 mb-4 border-b border-gray-200 dark:border-gray-700 pb-3">
          <button
            onClick={() => setActiveTab('trades')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'trades'
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <Activity className="w-4 h-4" />
            Recent Trades ({status?.recent_trades?.length ?? 0})
          </button>
          <button
            onClick={() => setActiveTab('opportunities')}
            className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
              activeTab === 'opportunities'
                ? 'bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-400'
                : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}
          >
            <Zap className="w-4 h-4" />
            Opportunities ({status?.recent_opportunities?.length ?? 0})
          </button>
          <button
            onClick={fetchData}
            className="ml-auto flex items-center gap-1.5 px-3 py-1.5 text-sm text-gray-500 hover:text-gray-700 dark:hover:text-gray-300"
          >
            <RefreshCw className="w-4 h-4" />
            Refresh
          </button>
        </div>

        {activeTab === 'trades' && (
          <TradesTable trades={status?.recent_trades ?? []} />
        )}
        {activeTab === 'opportunities' && (
          <OpportunitiesTable opportunities={status?.recent_opportunities ?? []} />
        )}
      </Card>

      {/* Exchange Legend */}
      <Card>
        <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300 mb-3">Monitored Exchanges</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-yellow-500" />
            <div>
              <div className="text-sm font-medium text-gray-900 dark:text-white">Binance Global</div>
              <div className="text-xs text-gray-500">USDT pairs → THB normalized</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-blue-500" />
            <div>
              <div className="text-sm font-medium text-gray-900 dark:text-white">Binance Thailand</div>
              <div className="text-xs text-gray-500">THB pairs</div>
            </div>
          </div>
          <div className="flex items-center gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
            <div className="w-2 h-2 rounded-full bg-green-500" />
            <div>
              <div className="text-sm font-medium text-gray-900 dark:text-white">Bitkub</div>
              <div className="text-xs text-gray-500">THB pairs</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function StatCard({ title, value, subtitle, icon: Icon, color }: {
  title: string;
  value: string;
  subtitle?: string;
  icon: any;
  color: 'green' | 'red' | 'blue' | 'amber';
}) {
  const colors = {
    green: 'bg-green-100 dark:bg-green-900/30 text-green-600 dark:text-green-400',
    red: 'bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400',
    blue: 'bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400',
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

function TradesTable({ trades }: { trades: ArbTrade[] }) {
  if (trades.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        <Activity className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No trades yet. The bot scans for spread opportunities every 30s.</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 font-medium">Asset</th>
            <th className="pb-2 font-medium">Route</th>
            <th className="pb-2 font-medium">Buy Price</th>
            <th className="pb-2 font-medium">Sell Price</th>
            <th className="pb-2 font-medium">Capital</th>
            <th className="pb-2 font-medium">Fees</th>
            <th className="pb-2 font-medium">P&L</th>
            <th className="pb-2 font-medium">Time</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
          {trades.slice().reverse().map((trade, i) => (
            <tr key={trade.id || i} className="text-gray-900 dark:text-gray-100">
              <td className="py-2 font-medium">{trade.asset}</td>
              <td className="py-2 text-xs">
                <span className="text-green-600 dark:text-green-400">{trade.buy_exchange}</span>
                {' → '}
                <span className="text-red-600 dark:text-red-400">{trade.sell_exchange}</span>
              </td>
              <td className="py-2 font-mono text-xs">฿{trade.buy_price_thb.toFixed(2)}</td>
              <td className="py-2 font-mono text-xs">฿{trade.sell_price_thb.toFixed(2)}</td>
              <td className="py-2 font-mono text-xs">฿{trade.capital_thb.toFixed(2)}</td>
              <td className="py-2 font-mono text-xs text-gray-500">฿{trade.fees_thb.toFixed(2)}</td>
              <td className={`py-2 font-mono text-xs font-medium ${
                trade.pnl_thb > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              }`}>
                {trade.pnl_thb > 0 ? '+' : ''}฿{trade.pnl_thb.toFixed(2)}
                <span className="text-[10px] ml-1">({trade.pnl_pct > 0 ? '+' : ''}{trade.pnl_pct.toFixed(3)}%)</span>
              </td>
              <td className="py-2 text-xs text-gray-500">{formatTime(trade.opened_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function OpportunitiesTable({ opportunities }: { opportunities: ArbOpportunity[] }) {
  if (opportunities.length === 0) {
    return (
      <div className="text-center py-12 text-gray-500 dark:text-gray-400">
        <Zap className="w-10 h-10 mx-auto mb-3 opacity-30" />
        <p className="text-sm">No recent opportunities. Scanning continuously...</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <th className="pb-2 font-medium">Asset</th>
            <th className="pb-2 font-medium">Route</th>
            <th className="pb-2 font-medium">Buy Price</th>
            <th className="pb-2 font-medium">Sell Price</th>
            <th className="pb-2 font-medium">Gross Spread</th>
            <th className="pb-2 font-medium">Net Spread</th>
            <th className="pb-2 font-medium">Executed</th>
            <th className="pb-2 font-medium">Time</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
          {opportunities.slice().reverse().map((opp, i) => (
            <tr key={i} className="text-gray-900 dark:text-gray-100">
              <td className="py-2 font-medium">{opp.asset}</td>
              <td className="py-2 text-xs">
                <span className="text-green-600 dark:text-green-400">{opp.buy_exchange}</span>
                {' → '}
                <span className="text-red-600 dark:text-red-400">{opp.sell_exchange}</span>
              </td>
              <td className="py-2 font-mono text-xs">฿{opp.buy_price_thb.toFixed(2)}</td>
              <td className="py-2 font-mono text-xs">฿{opp.sell_price_thb.toFixed(2)}</td>
              <td className="py-2 font-mono text-xs text-gray-500">{opp.gross_spread_pct.toFixed(3)}%</td>
              <td className={`py-2 font-mono text-xs font-medium ${
                opp.spread_pct > 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
              }`}>
                {opp.spread_pct.toFixed(3)}%
              </td>
              <td className="py-2">
                {opp.executed ? (
                  <CheckCircle2 className="w-4 h-4 text-green-500" />
                ) : (
                  <XCircle className="w-4 h-4 text-gray-400" />
                )}
              </td>
              <td className="py-2 text-xs text-gray-500">{formatTime(opp.timestamp)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
