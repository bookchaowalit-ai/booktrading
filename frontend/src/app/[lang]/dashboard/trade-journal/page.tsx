/**
 * Trade Journal Dashboard Page
 * Track and analyze all trading decisions with detailed stats
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion } from 'framer-motion';
import {
  BookOpen,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Target,
  Activity,
  Clock,
  Filter,
  BarChart3,
  Award,
  AlertCircle,
} from 'lucide-react';
import { tradeJournalService } from '@/services/trade-journal';
import type {
  JournalEntry,
  JournalStats,
  JournalResponse,
} from '@/types/trade-journal';
import Card from '@/components/ui/Card';

const STATUS_COLORS: Record<string, string> = {
  OPEN: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  CLOSED: 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-400',
  CANCELLED: 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400',
};

export default function TradeJournalPage() {
  const [data, setData] = useState<JournalResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [selectedStatus, setSelectedStatus] = useState<string>('all');
  const [activeTab, setActiveTab] = useState<'db' | 'memory'>('db');

  const loadData = useCallback(async () => {
    try {
      const result = await tradeJournalService.getEntries(100);
      setData(result);
    } catch (err) {
      console.error('Failed to load journal:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 30000);
    return () => clearInterval(interval);
  }, [loadData]);

  const allEntries = data
    ? activeTab === 'db'
      ? data.db_entries
      : data.in_memory
    : [];

  const filteredEntries = selectedStatus === 'all'
    ? allEntries
    : allEntries.filter((e: JournalEntry) => e.status === selectedStatus);

  const stats = data?.db_stats || data?.in_memory_stats;

  if (isLoading) {
    return (
      <div className="p-6 space-y-6">
        <div className="flex items-center gap-3">
          <div className="w-12 h-12 bg-gray-200 dark:bg-gray-700 rounded-lg animate-pulse" />
          <div className="space-y-2">
            <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-4 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-28 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg">
            <BookOpen className="w-8 h-8 text-emerald-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Trade Journal
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Track every trading decision and outcome
            </p>
          </div>
        </div>
        <button
          onClick={loadData}
          className="flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-lg transition-colors"
        >
          <RefreshCw className="w-4 h-4" />
          Refresh
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0 }}>
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <BarChart3 className="w-5 h-5 text-gray-500" />
              <span className="text-xs px-2 py-0.5 bg-emerald-100 dark:bg-emerald-900/30 text-emerald-700 dark:text-emerald-400 rounded-full">
                Total
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total Trades</h3>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats?.total_entries || 0}
            </p>
            <p className="text-xs text-gray-500">
              {stats?.open_entries || 0} open / {stats?.closed_entries || 0} closed
            </p>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <Award className="w-5 h-5 text-gray-500" />
              <span className={`text-xs px-2 py-0.5 rounded-full ${(stats?.win_rate || 0) >= 50 ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
                {(stats?.win_rate || 0).toFixed(1)}%
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Win Rate</h3>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {stats?.winning_trades || 0}W / {stats?.losing_trades || 0}L
            </p>
            <p className="text-xs text-gray-500">
              Avg win: ฿{(stats?.avg_win || 0).toFixed(2)} | Avg loss: ฿{(stats?.avg_loss || 0).toFixed(2)}
            </p>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.2 }}>
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <DollarSign className="w-5 h-5 text-gray-500" />
              <span className={`text-xs px-2 py-0.5 rounded-full ${(stats?.total_pnl || 0) >= 0 ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400'}`}>
                {(stats?.total_pnl || 0) >= 0 ? 'Profit' : 'Loss'}
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Total P&L</h3>
            <p className={`text-2xl font-bold ${(stats?.total_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ฿{(stats?.total_pnl || 0).toFixed(2)}
            </p>
            <p className="text-xs text-gray-500">
              Fees: ฿{(stats?.total_fees || 0).toFixed(2)}
            </p>
          </Card>
        </motion.div>

        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.3 }}>
          <Card className="p-4">
            <div className="flex items-center justify-between mb-2">
              <Target className="w-5 h-5 text-gray-500" />
              <span className={`text-xs px-2 py-0.5 rounded-full ${(stats?.profit_factor || 0) >= 1 ? 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400' : 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'}`}>
                {(stats?.profit_factor || 0).toFixed(2)}x
              </span>
            </div>
            <h3 className="text-sm font-medium text-gray-500 dark:text-gray-400">Profit Factor</h3>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">
              {(stats?.profit_factor || 0).toFixed(2)}
            </p>
            <p className="text-xs text-gray-500">
              Gross profit / Gross loss
            </p>
          </Card>
        </motion.div>
      </div>

      {/* Entries Table */}
      <Card className="p-4">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <Activity className="w-5 h-5 text-emerald-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">
              Journal Entries
            </h2>
            <span className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 text-xs rounded-full">
              {filteredEntries.length}
            </span>
          </div>
          <div className="flex items-center gap-2">
            {/* Source toggle */}
            <div className="flex border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
              <button
                onClick={() => setActiveTab('db')}
                className={`px-3 py-1 text-xs font-medium transition-colors ${activeTab === 'db' ? 'bg-emerald-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
              >
                Database
              </button>
              <button
                onClick={() => setActiveTab('memory')}
                className={`px-3 py-1 text-xs font-medium transition-colors ${activeTab === 'memory' ? 'bg-emerald-600 text-white' : 'bg-white dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-50 dark:hover:bg-gray-700'}`}
              >
                In-Memory
              </button>
            </div>
            {/* Status filter */}
            <select
              value={selectedStatus}
              onChange={e => setSelectedStatus(e.target.value)}
              className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800"
            >
              <option value="all">All Status</option>
              <option value="OPEN">Open</option>
              <option value="CLOSED">Closed</option>
              <option value="CANCELLED">Cancelled</option>
            </select>
          </div>
        </div>

        {filteredEntries.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Symbol</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Side</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Strategy</th>
                  <th className="text-right py-3 px-2 text-gray-500 font-medium">Entry Price</th>
                  <th className="text-right py-3 px-2 text-gray-500 font-medium">Exit Price</th>
                  <th className="text-right py-3 px-2 text-gray-500 font-medium">Qty</th>
                  <th className="text-right py-3 px-2 text-gray-500 font-medium">P&L</th>
                  <th className="text-center py-3 px-2 text-gray-500 font-medium">Status</th>
                  <th className="text-left py-3 px-2 text-gray-500 font-medium">Date</th>
                </tr>
              </thead>
              <tbody>
                {filteredEntries.map((entry: JournalEntry, idx: number) => (
                  <tr
                    key={entry.id || idx}
                    className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors"
                  >
                    <td className="py-3 px-2 font-medium text-gray-900 dark:text-white">
                      {entry.symbol}
                    </td>
                    <td className="py-3 px-2">
                      <span className={`inline-flex items-center gap-1 text-xs font-medium ${entry.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>
                        {entry.side === 'BUY' ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                        {entry.side}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-gray-600 dark:text-gray-400">
                      {entry.strategy}
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-gray-900 dark:text-white">
                      {entry.entry_price?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-gray-900 dark:text-white">
                      {entry.exit_price ? entry.exit_price.toLocaleString(undefined, { minimumFractionDigits: 2 }) : '-'}
                    </td>
                    <td className="py-3 px-2 text-right font-mono text-gray-600 dark:text-gray-400">
                      {entry.quantity}
                    </td>
                    <td className={`py-3 px-2 text-right font-mono font-medium ${(entry.actual_pnl || 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {entry.actual_pnl ? `฿${entry.actual_pnl.toFixed(2)}` : '-'}
                    </td>
                    <td className="py-3 px-2 text-center">
                      <span className={`text-xs px-2 py-0.5 rounded-full ${STATUS_COLORS[entry.status] || 'bg-gray-100 text-gray-600'}`}>
                        {entry.status}
                      </span>
                    </td>
                    <td className="py-3 px-2 text-gray-500 text-xs">
                      {entry.created_at
                        ? new Date(typeof entry.created_at === 'number' ? entry.created_at * 1000 : entry.created_at).toLocaleDateString()
                        : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-center py-12">
            <AlertCircle className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-gray-500 dark:text-gray-400 font-medium">No journal entries yet</p>
            <p className="text-gray-400 dark:text-gray-500 text-sm mt-1">
              Entries will appear here when trades are executed with journal tracking
            </p>
          </div>
        )}
      </Card>
    </div>
  );
}
