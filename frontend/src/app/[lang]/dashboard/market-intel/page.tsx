/**
 * Market Intelligence Dashboard — Unified Multi-Market Scanner
 * Covers: Crypto (TH), Stocks, Prediction Markets, Forex/Commodities,
 *         Airdrops, Degen/Meme, Binance Alpha, Cross-Exchange Arb
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Crosshair,
  RefreshCw,
  AlertTriangle,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Globe,
  Activity,
  Zap,
  Clock,
  Gift,
  Flame,
  Sparkles,
  ArrowLeftRight,
  ExternalLink,
  Rocket,
  Shield,
  BarChart3,
  Wallet,
  CheckCircle,
  Circle,
  Trash2,
  Plus,
  Target,
  ThumbsUp,
  ThumbsDown,
} from 'lucide-react';
import { marketIntelService } from '@/services/market-intel';
import { airdropTrackerService } from '@/services/airdrop-tracker';
import { signalTrackerService } from '@/services/signal-tracker';
import type { AirdropTask, AirdropTrackerStats } from '@/services/airdrop-tracker';
import type { LoggedSignal, SignalPerformanceStats } from '@/services/signal-tracker';
import type {
  ScannerResult,
  MarketQuote,
  MarketSource,
  MarketAlert,
  MarketOverview,
  MarketOpportunity,
  Severity,
} from '@/types/market-intel';
import type { PortfolioHolding } from '@/services/market-intel';
import Card from '@/components/ui/Card';

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: 'bg-red-500',
  high: 'bg-orange-500',
  medium: 'bg-yellow-500',
  low: 'bg-blue-500',
};

const SEVERITY_TEXT: Record<Severity, string> = {
  critical: 'text-red-600 dark:text-red-400',
  high: 'text-orange-600 dark:text-orange-400',
  medium: 'text-yellow-600 dark:text-yellow-400',
  low: 'text-blue-600 dark:text-blue-400',
};

const SEVERITY_BG: Record<Severity, string> = {
  critical: 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800',
  high: 'bg-orange-50 dark:bg-orange-900/10 border-orange-200 dark:border-orange-800',
  medium: 'bg-yellow-50 dark:bg-yellow-900/10 border-yellow-200 dark:border-yellow-800',
  low: 'bg-blue-50 dark:bg-blue-900/10 border-blue-200 dark:border-blue-800',
};

const MARKET_CONFIG: Record<string, { icon: any; color: string; label: string }> = {
  crypto: { icon: DollarSign, color: 'text-yellow-500', label: 'Crypto (TH)' },
  stock: { icon: TrendingUp, color: 'text-blue-500', label: 'Stocks' },
  forex: { icon: Globe, color: 'text-green-500', label: 'Forex & Commodities' },
  prediction: { icon: Zap, color: 'text-purple-500', label: 'Prediction Markets' },
  airdrop: { icon: Gift, color: 'text-pink-500', label: 'Airdrops' },
  degen: { icon: Flame, color: 'text-red-500', label: 'Degen / Meme' },
};

// Tab definitions
type TabId = 'overview' | 'portfolio' | 'performance' | 'airdrops' | 'degen' | 'alpha' | 'arb' | 'quotes' | 'alerts';

const TABS: { id: TabId; label: string; icon: any; color: string }[] = [
  { id: 'overview', label: 'Overview', icon: BarChart3, color: 'text-indigo-500' },
  { id: 'portfolio', label: 'Portfolio', icon: Wallet, color: 'text-emerald-500' },
  { id: 'performance', label: 'Performance', icon: Target, color: 'text-cyan-500' },
  { id: 'airdrops', label: 'Airdrops', icon: Gift, color: 'text-pink-500' },
  { id: 'degen', label: 'Degen', icon: Flame, color: 'text-red-500' },
  { id: 'alpha', label: 'Alpha', icon: Sparkles, color: 'text-purple-500' },
  { id: 'arb', label: 'Arbitrage', icon: ArrowLeftRight, color: 'text-green-500' },
  { id: 'quotes', label: 'Quotes', icon: DollarSign, color: 'text-yellow-500' },
  { id: 'alerts', label: 'Alerts', icon: AlertTriangle, color: 'text-orange-500' },
];

export default function MarketIntelPage() {
  const [overview, setOverview] = useState<MarketOverview | null>(null);
  const [quotes, setQuotes] = useState<MarketQuote[]>([]);
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [sources, setSources] = useState<MarketSource[]>([]);
  const [lastScan, setLastScan] = useState<ScannerResult | null>(null);
  const [portfolio, setPortfolio] = useState<{ holdings: PortfolioHolding[]; total_value_thb: number; signal_count: number } | null>(null);
  const [signalStats, setSignalStats] = useState<SignalPerformanceStats | null>(null);
  const [loggedSignals, setLoggedSignals] = useState<LoggedSignal[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isScanning, setIsScanning] = useState(false);
  const [activeTab, setActiveTab] = useState<TabId>('overview');
  const [selectedMarket, setSelectedMarket] = useState<string>('all');
  const [selectedSeverity, setSelectedSeverity] = useState<string>('all');

  const loadData = useCallback(async () => {
    try {
      const [overviewData, quotesData, alertsData, sourcesData, lastScanData, portfolioData, signalStatsData, signalsData] = await Promise.all([
        marketIntelService.getOverview(),
        marketIntelService.getQuotes(),
        marketIntelService.getAlerts(50),
        marketIntelService.getSources(),
        marketIntelService.getLastScan(),
        marketIntelService.getPortfolio().catch(() => null),
        signalTrackerService.getStats().catch(() => null),
        signalTrackerService.getSignals({ limit: 50 }).catch(() => ({ signals: [], total: 0 })),
      ]);

      setOverview(overviewData);
      setQuotes(quotesData.quotes || []);
      setAlerts(alertsData.alerts || []);
      setSources(sourcesData.sources || []);
      if ('scan_id' in lastScanData) {
        setLastScan(lastScanData as ScannerResult);
      }
      if (portfolioData) {
        setPortfolio(portfolioData);
      }
      if (signalStatsData) {
        setSignalStats(signalStatsData);
      }
      setLoggedSignals(signalsData.signals || []);
    } catch (err) {
      console.error('Failed to load market intel:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 60000);
    return () => clearInterval(interval);
  }, [loadData]);

  const handleScan = async () => {
    setIsScanning(true);
    try {
      const result = await marketIntelService.scan(0.3);
      setLastScan(result);
      const alertsData = await marketIntelService.getAlerts(50);
      setAlerts(alertsData.alerts || []);
    } catch (err) {
      console.error('Scan failed:', err);
    } finally {
      setIsScanning(false);
    }
  };

  // Filter opportunities by market type
  const getOppsByType = (type: string): MarketOpportunity[] => {
    if (!lastScan?.opportunities) return [];
    return lastScan.opportunities.filter(o => o.opportunity_type === type || o.market_type === type);
  };

  const filteredQuotes = selectedMarket === 'all'
    ? quotes
    : quotes.filter(q => q.market_type === selectedMarket);

  const filteredAlerts = selectedSeverity === 'all'
    ? alerts
    : alerts.filter(a => a.severity === selectedSeverity);

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
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[1, 2, 3, 4].map(i => (
            <div key={i} className="h-24 bg-gray-200 dark:bg-gray-700 rounded-xl animate-pulse" />
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
          <div className="p-2 bg-indigo-100 dark:bg-indigo-900/30 rounded-lg">
            <Crosshair className="w-8 h-8 text-indigo-600" />
          </div>
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
              Market Intelligence
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              Multi-market scanner &bull; {sources.length} sources &bull; {lastScan?.total_opportunities || 0} opportunities
            </p>
          </div>
        </div>
        <button
          onClick={handleScan}
          disabled={isScanning}
          className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isScanning ? 'animate-spin' : ''}`} />
          {isScanning ? 'Scanning...' : 'Scan Now'}
        </button>
      </div>

      {/* Source Status Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {sources.map((source, idx) => {
          const config = MARKET_CONFIG[source.market_type] || { icon: Activity, color: 'text-gray-500', label: source.name };
          const Icon = config.icon;
          const marketData = overview?.[source.name];
          return (
            <motion.div
              key={source.name}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: idx * 0.05 }}
            >
              <Card className="p-3 cursor-pointer hover:ring-2 hover:ring-indigo-300 transition-all" >
                <div className="flex items-center justify-between mb-1">
                  <Icon className={`w-4 h-4 ${config.color}`} />
                  <span className="text-xs px-1.5 py-0.5 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full">
                    ON
                  </span>
                </div>
                <h3 className="text-xs font-medium text-gray-500 dark:text-gray-400">{config.label}</h3>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {marketData?.instruments || 0}
                </p>
                <p className="text-xs text-gray-500">
                  {marketData?.opportunities || 0} opps
                </p>
              </Card>
            </motion.div>
          );
        })}
      </div>

      {/* Tab Navigation */}
      <div className="flex gap-1 overflow-x-auto pb-1 border-b border-gray-200 dark:border-gray-700">
        {TABS.map(tab => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          const oppCount = tab.id === 'airdrops' ? getOppsByType('airdrop').length
            : tab.id === 'degen' ? getOppsByType('degen').length
            : tab.id === 'alpha' ? getOppsByType('early_alpha').length
            : tab.id === 'arb' ? getOppsByType('cross_exchange_arb').length
            : tab.id === 'alerts' ? filteredAlerts.length
            : 0;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-1.5 px-3 py-2 text-sm font-medium rounded-t-lg transition-colors whitespace-nowrap
                ${isActive ? 'bg-indigo-50 dark:bg-indigo-900/20 text-indigo-600 dark:text-indigo-400 border-b-2 border-indigo-500'
                  : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}
            >
              <Icon className={`w-4 h-4 ${isActive ? tab.color : ''}`} />
              {tab.label}
              {oppCount > 0 && (
                <span className="ml-1 px-1.5 py-0.5 text-xs bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 dark:text-indigo-400 rounded-full">
                  {oppCount}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content */}
      <AnimatePresence mode="wait">
        <motion.div
          key={activeTab}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -10 }}
          transition={{ duration: 0.15 }}
        >
          {activeTab === 'overview' && <OverviewTab overview={overview} lastScan={lastScan} sources={sources} />}
          {activeTab === 'portfolio' && <PortfolioTab portfolio={portfolio} />}
          {activeTab === 'performance' && <PerformanceTab stats={signalStats} signals={loggedSignals} />}
          {activeTab === 'airdrops' && <AirdropTab opportunities={getOppsByType('airdrop')} />}
          {activeTab === 'degen' && <DegenTab opportunities={getOppsByType('degen')} />}
          {activeTab === 'alpha' && <AlphaTab opportunities={getOppsByType('early_alpha')} />}
          {activeTab === 'arb' && <ArbTab opportunities={getOppsByType('cross_exchange_arb')} />}
          {activeTab === 'quotes' && <QuotesTab quotes={filteredQuotes} selectedMarket={selectedMarket} setSelectedMarket={setSelectedMarket} />}
          {activeTab === 'alerts' && <AlertsTab alerts={filteredAlerts} selectedSeverity={selectedSeverity} setSelectedSeverity={setSelectedSeverity} />}
        </motion.div>
      </AnimatePresence>
    </div>
  );
}

// === OVERVIEW TAB ===
function OverviewTab({ overview, lastScan, sources }: { overview: MarketOverview | null; lastScan: ScannerResult | null; sources: MarketSource[] }) {
  return (
    <div className="space-y-6">
      {/* Scan Summary */}
      {lastScan && (
        <Card className="p-5">
          <div className="flex items-center gap-2 mb-4">
            <Clock className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Latest Scan</h2>
            <span className="text-xs text-gray-500">{new Date(lastScan.timestamp).toLocaleString()}</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4 text-center">
            <div>
              <p className="text-3xl font-bold text-indigo-600">{lastScan.total_opportunities}</p>
              <p className="text-xs text-gray-500">Total Opportunities</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-red-600">{lastScan.by_severity?.critical || 0}</p>
              <p className="text-xs text-gray-500">Critical</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-orange-600">{lastScan.by_severity?.high || 0}</p>
              <p className="text-xs text-gray-500">High</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-yellow-600">{lastScan.by_severity?.medium || 0}</p>
              <p className="text-xs text-gray-500">Medium</p>
            </div>
            <div>
              <p className="text-3xl font-bold text-blue-600">{lastScan.by_severity?.low || 0}</p>
              <p className="text-xs text-gray-500">Low</p>
            </div>
          </div>
        </Card>
      )}

      {/* Market Breakdown */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {lastScan?.by_market && Object.entries(lastScan.by_market).map(([market, count]) => {
          const config = MARKET_CONFIG[market] || { icon: Activity, color: 'text-gray-500', label: market };
          const Icon = config.icon;
          return (
            <Card key={market} className="p-4">
              <div className="flex items-center gap-2 mb-3">
                <Icon className={`w-5 h-5 ${config.color}`} />
                <h3 className="font-semibold text-gray-900 dark:text-white capitalize">{config.label}</h3>
                <span className="ml-auto px-2 py-0.5 bg-indigo-100 dark:bg-indigo-900/30 text-indigo-600 text-xs rounded-full">
                  {count as number} opps
                </span>
              </div>
              <div className="space-y-2">
                {lastScan.opportunities
                  .filter(o => o.market_type === market)
                  .slice(0, 3)
                  .map(opp => (
                    <div key={opp.opportunity_id} className="flex items-start gap-2 p-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
                      <div className={`w-2 h-2 rounded-full mt-1.5 ${SEVERITY_COLORS[opp.severity]}`} />
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{opp.title}</p>
                        <p className="text-xs text-gray-500 truncate">{opp.description}</p>
                      </div>
                      <span className={`text-xs font-medium ${SEVERITY_TEXT[opp.severity]}`}>
                        {(opp.confidence * 100).toFixed(0)}%
                      </span>
                    </div>
                  ))}
              </div>
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// === AIRDROP TAB ===
function AirdropTab({ opportunities }: { opportunities: MarketOpportunity[] }) {
  const [trackedTasks, setTrackedTasks] = useState<AirdropTask[]>([]);
  const [trackerStats, setTrackerStats] = useState<AirdropTrackerStats | null>(null);
  const [showAddForm, setShowAddForm] = useState(false);
  const [newTask, setNewTask] = useState({ name: '', chain: '', estimated_value: '', url: '', deadline: '' });

  const fetchTrackedTasks = useCallback(async () => {
    try {
      const data = await airdropTrackerService.getTasks();
      setTrackedTasks(data.tasks);
      setTrackerStats(data.stats);
    } catch (e) {
      console.error('Failed to fetch tracked tasks:', e);
    }
  }, []);

  useEffect(() => {
    fetchTrackedTasks();
  }, [fetchTrackedTasks]);

  const handleAddTask = async () => {
    if (!newTask.name) return;
    try {
      await airdropTrackerService.addTask(newTask);
      setNewTask({ name: '', chain: '', estimated_value: '', url: '', deadline: '' });
      setShowAddForm(false);
      fetchTrackedTasks();
    } catch (e) {
      console.error('Failed to add task:', e);
    }
  };

  const handleToggleSubtask = async (taskId: string, idx: number, completed: boolean) => {
    try {
      await airdropTrackerService.toggleSubtask(taskId, idx, completed);
      fetchTrackedTasks();
    } catch (e) {
      console.error('Failed to toggle subtask:', e);
    }
  };

  const handleDeleteTask = async (taskId: string) => {
    try {
      await airdropTrackerService.deleteTask(taskId);
      fetchTrackedTasks();
    } catch (e) {
      console.error('Failed to delete task:', e);
    }
  };

  const handleUpdateStatus = async (taskId: string, status: AirdropTask['status']) => {
    try {
      await airdropTrackerService.updateTask(taskId, { status });
      fetchTrackedTasks();
    } catch (e) {
      console.error('Failed to update status:', e);
    }
  };

  const STATUS_STYLES: Record<string, string> = {
    not_started: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
    in_progress: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    completed: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    expired: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };

  return (
    <div className="space-y-6">
      {/* Tracker Section */}
      <div className="p-4 bg-gradient-to-r from-pink-50 to-purple-50 dark:from-pink-900/10 dark:to-purple-900/10 rounded-xl border border-pink-200 dark:border-pink-800">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-3">
            <Gift className="w-8 h-8 text-pink-500" />
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">Airdrop Task Tracker</h3>
              <p className="text-sm text-gray-600 dark:text-gray-400">Track your progress on free airdrop opportunities</p>
            </div>
          </div>
          <button
            onClick={() => setShowAddForm(!showAddForm)}
            className="flex items-center gap-1 px-3 py-1.5 bg-pink-500 hover:bg-pink-600 text-white rounded-lg text-sm font-medium transition-colors"
          >
            <Plus className="w-4 h-4" /> Add Task
          </button>
        </div>

        {/* Stats */}
        {trackerStats && trackerStats.total > 0 && (
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
            <div className="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">Total Tasks</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">{trackerStats.total}</p>
            </div>
            <div className="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">In Progress</p>
              <p className="text-xl font-bold text-blue-600">{trackerStats.by_status.in_progress || 0}</p>
            </div>
            <div className="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">Completed</p>
              <p className="text-xl font-bold text-green-600">{trackerStats.by_status.completed || 0}</p>
            </div>
            <div className="p-3 bg-white/60 dark:bg-gray-800/60 rounded-lg">
              <p className="text-xs text-gray-500 dark:text-gray-400">Est. Value</p>
              <p className="text-xl font-bold text-pink-600">${trackerStats.total_estimated_low}</p>
            </div>
          </div>
        )}

        {/* Add Task Form */}
        {showAddForm && (
          <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-pink-200 dark:border-pink-700 mb-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <input
                type="text"
                placeholder="Airdrop name *"
                value={newTask.name}
                onChange={(e) => setNewTask({ ...newTask, name: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
              <input
                type="text"
                placeholder="Chain (e.g., Ethereum, Solana)"
                value={newTask.chain}
                onChange={(e) => setNewTask({ ...newTask, chain: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
              <input
                type="text"
                placeholder="Estimated value (e.g., $100-500)"
                value={newTask.estimated_value}
                onChange={(e) => setNewTask({ ...newTask, estimated_value: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
              <input
                type="text"
                placeholder="Deadline (e.g., June 30, 2026)"
                value={newTask.deadline}
                onChange={(e) => setNewTask({ ...newTask, deadline: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm"
              />
              <input
                type="text"
                placeholder="URL"
                value={newTask.url}
                onChange={(e) => setNewTask({ ...newTask, url: e.target.value })}
                className="px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm md:col-span-2"
              />
            </div>
            <div className="flex gap-2 mt-3">
              <button
                onClick={handleAddTask}
                className="px-4 py-2 bg-pink-500 hover:bg-pink-600 text-white rounded-lg text-sm font-medium"
              >
                Save Task
              </button>
              <button
                onClick={() => setShowAddForm(false)}
                className="px-4 py-2 bg-gray-200 dark:bg-gray-700 hover:bg-gray-300 dark:hover:bg-gray-600 text-gray-700 dark:text-gray-300 rounded-lg text-sm"
              >
                Cancel
              </button>
            </div>
          </div>
        )}

        {/* Tracked Tasks List */}
        {trackedTasks.length > 0 && (
          <div className="space-y-3">
            {trackedTasks.map((task) => (
              <div
                key={task.task_id}
                className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-2">
                    <h4 className="font-bold text-gray-900 dark:text-white">{task.name}</h4>
                    {task.chain && <span className="text-xs px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">{task.chain}</span>}
                  </div>
                  <div className="flex items-center gap-2">
                    <select
                      value={task.status}
                      onChange={(e) => handleUpdateStatus(task.task_id, e.target.value as AirdropTask['status'])}
                      className={`text-xs px-2 py-1 rounded-full border-0 font-medium ${STATUS_STYLES[task.status]}`}
                    >
                      <option value="not_started">Not Started</option>
                      <option value="in_progress">In Progress</option>
                      <option value="completed">Completed</option>
                      <option value="expired">Expired</option>
                    </select>
                    <button
                      onClick={() => handleDeleteTask(task.task_id)}
                      className="p-1 text-gray-400 hover:text-red-500 transition-colors"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
                <div className="mt-2 flex flex-wrap gap-3 text-sm">
                  {task.estimated_value && <span className="text-green-600 font-medium">{task.estimated_value}</span>}
                  {task.deadline && <span className="text-orange-600 flex items-center gap-1"><Clock className="w-3 h-3" />{task.deadline}</span>}
                  {task.url && (
                    <a href={task.url} target="_blank" rel="noopener noreferrer" className="text-indigo-600 flex items-center gap-1 hover:underline">
                      <ExternalLink className="w-3 h-3" /> Visit
                    </a>
                  )}
                </div>
                {task.subtasks && task.subtasks.length > 0 && (
                  <div className="mt-3 space-y-1">
                    {task.subtasks.map((st, idx) => (
                      <label key={idx} className="flex items-center gap-2 cursor-pointer">
                        <button
                          onClick={() => handleToggleSubtask(task.task_id, idx, !st.completed)}
                          className="flex-shrink-0"
                        >
                          {st.completed ? (
                            <CheckCircle className="w-4 h-4 text-green-500" />
                          ) : (
                            <Circle className="w-4 h-4 text-gray-400" />
                          )}
                        </button>
                        <span className={`text-sm ${st.completed ? 'line-through text-gray-400' : 'text-gray-700 dark:text-gray-300'}`}>
                          {st.title}
                        </span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {trackedTasks.length === 0 && !showAddForm && (
          <p className="text-center text-gray-500 dark:text-gray-400 py-4">
            No tracked tasks yet. Click &quot;Add Task&quot; to start tracking an airdrop.
          </p>
        )}
      </div>

      {/* Scanner Results */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Rocket className="w-5 h-5 text-pink-500" />
          <h3 className="font-semibold text-gray-900 dark:text-white">Scanner Results</h3>
          <span className="text-xs px-2 py-0.5 bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-400 rounded-full">
            {opportunities.length} opportunities
          </span>
        </div>

        {opportunities.length === 0 ? (
          <Card className="p-6 text-center text-gray-500">
            <p>No airdrop opportunities found. Scanning DeFi Llama...</p>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {opportunities.map(opp => (
              <Card key={opp.opportunity_id} className={`p-4 border ${SEVERITY_BG[opp.severity]}`}>
                <div className="flex items-start justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <Rocket className="w-5 h-5 text-pink-500" />
                    <h3 className="font-bold text-gray-900 dark:text-white">{opp.metadata?.name || opp.symbol}</h3>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${SEVERITY_TEXT[opp.severity]}`}>
                    {opp.severity}
                  </span>
                </div>
                <div className="space-y-1 text-sm">
                  {opp.metadata?.chain && <p className="text-gray-600 dark:text-gray-400">Chain: <span className="font-medium">{opp.metadata.chain}</span></p>}
                  {opp.metadata?.task && <p className="text-gray-600 dark:text-gray-400">Task: <span className="font-medium">{opp.metadata.task}</span></p>}
                  {opp.metadata?.estimated_value && <p className="text-gray-600 dark:text-gray-400">Est. Value: <span className="font-bold text-green-600">{opp.metadata.estimated_value}</span></p>}
                  {opp.metadata?.cost && <p className="text-gray-600 dark:text-gray-400">Cost: <span className="font-medium">{opp.metadata.cost}</span></p>}
                </div>
                {opp.metadata?.url && (
                  <a
                    href={opp.metadata.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="mt-3 flex items-center gap-1 text-sm text-indigo-600 hover:text-indigo-700"
                  >
                    <ExternalLink className="w-3 h-3" /> Visit Project
                  </a>
                )}
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

// === DEGEN TAB ===
function DegenTab({ opportunities }: { opportunities: MarketOpportunity[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-red-50 to-orange-50 dark:from-red-900/10 dark:to-orange-900/10 rounded-xl border border-red-200 dark:border-red-800">
        <Flame className="w-8 h-8 text-red-500" />
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">Trending Degen / Meme Tokens</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">High-momentum tokens from DexScreener — Solana & BSC chains</p>
        </div>
        <span className="ml-auto px-3 py-1 bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-400 rounded-full font-bold">
          {opportunities.length}
        </span>
      </div>

      {opportunities.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          <Flame className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No trending degen tokens right now.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {opportunities.sort((a, b) => (b.confidence || 0) - (a.confidence || 0)).map(opp => (
            <Card key={opp.opportunity_id} className="p-4">
              <div className="flex items-center gap-3">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-gray-900 dark:text-white">{opp.metadata?.name || opp.symbol}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded capitalize">{opp.metadata?.chain}</span>
                    <span className="text-xs px-1.5 py-0.5 bg-gray-100 dark:bg-gray-800 rounded">{opp.metadata?.dex}</span>
                  </div>
                  <div className="flex items-center gap-4 text-xs text-gray-500">
                    {opp.metadata?.liquidity_usd && <span>Liq: ${(opp.metadata.liquidity_usd as number).toLocaleString()}</span>}
                    {opp.metadata?.fdv && <span>FDV: ${(opp.metadata.fdv as number).toLocaleString()}</span>}
                    {opp.metadata?.buys_24h && <span className="text-green-600">Buys: {opp.metadata.buys_24h}</span>}
                    {opp.metadata?.sells_24h && <span className="text-red-600">Sells: {opp.metadata.sells_24h}</span>}
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono font-bold text-gray-900 dark:text-white">
                    ${opp.current_price?.toLocaleString(undefined, { maximumFractionDigits: 8 })}
                  </p>
                  <p className={`text-xs font-medium ${SEVERITY_TEXT[opp.severity]}`}>
                    {opp.title.match(/\(([^)]+)\)/)?.[1] || opp.severity}
                  </p>
                </div>
                {opp.metadata?.pair_url && (
                  <a href={opp.metadata.pair_url as string} target="_blank" rel="noopener noreferrer" className="p-2 hover:bg-gray-100 dark:hover:bg-gray-800 rounded-lg">
                    <ExternalLink className="w-4 h-4 text-gray-400" />
                  </a>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// === ALPHA TAB ===
function AlphaTab({ opportunities }: { opportunities: MarketOpportunity[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-purple-50 to-indigo-50 dark:from-purple-900/10 dark:to-indigo-900/10 rounded-xl border border-purple-200 dark:border-purple-800">
        <Sparkles className="w-8 h-8 text-purple-500" />
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">Binance Alpha Spotlight</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">Early-stage tokens on Binance Alpha — potential main listing upside</p>
        </div>
        <span className="ml-auto px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded-full font-bold">
          {opportunities.length}
        </span>
      </div>

      {opportunities.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          <Sparkles className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No early alpha tokens found. Scanning CoinGecko...</p>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {opportunities.map(opp => (
            <Card key={opp.opportunity_id} className="p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="w-4 h-4 text-purple-500" />
                <h3 className="font-bold text-gray-900 dark:text-white">{opp.symbol}</h3>
                <span className={`text-xs px-2 py-0.5 rounded-full ${SEVERITY_TEXT[opp.severity]}`}>{opp.severity}</span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mb-2">{opp.title}</p>
              <p className="text-xs text-gray-500 mb-3">{opp.description}</p>
              <div className="flex items-center justify-between">
                <p className="text-sm font-mono font-bold">${opp.current_price?.toLocaleString(undefined, { maximumFractionDigits: 6 })}</p>
                {opp.target_price && (
                  <p className="text-xs text-green-600">Target: ${opp.target_price.toLocaleString()}</p>
                )}
                <p className="text-xs text-gray-500">{(opp.confidence * 100).toFixed(0)}% conf</p>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// === ARBITRAGE TAB ===
function ArbTab({ opportunities }: { opportunities: MarketOpportunity[] }) {
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 p-4 bg-gradient-to-r from-green-50 to-emerald-50 dark:from-green-900/10 dark:to-emerald-900/10 rounded-xl border border-green-200 dark:border-green-800">
        <ArrowLeftRight className="w-8 h-8 text-green-500" />
        <div>
          <h3 className="font-semibold text-gray-900 dark:text-white">Cross-Exchange Arbitrage</h3>
          <p className="text-sm text-gray-600 dark:text-gray-400">Price differences across Binance TH, Binance Global, Gate.io & KuCoin</p>
        </div>
        <span className="ml-auto px-3 py-1 bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 rounded-full font-bold">
          {opportunities.length}
        </span>
      </div>

      {opportunities.length === 0 ? (
        <Card className="p-8 text-center text-gray-500">
          <ArrowLeftRight className="w-12 h-12 mx-auto mb-3 opacity-30" />
          <p>No arbitrage opportunities detected. Markets are well-aligned.</p>
        </Card>
      ) : (
        <div className="space-y-3">
          {opportunities.map(opp => (
            <Card key={opp.opportunity_id} className={`p-4 border ${SEVERITY_BG[opp.severity]}`}>
              <div className="flex items-center gap-3">
                <div className="flex-1">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-bold text-gray-900 dark:text-white">{opp.symbol}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${SEVERITY_TEXT[opp.severity]}`}>{opp.severity}</span>
                  </div>
                  <p className="text-sm text-gray-600 dark:text-gray-400">{opp.title}</p>
                  <p className="text-xs text-gray-500 mt-1">{opp.description}</p>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono">${opp.current_price?.toLocaleString()}</p>
                  {opp.target_price && <p className="text-xs text-green-600">→ ${opp.target_price.toLocaleString()}</p>}
                  <p className="text-xs text-gray-500">{(opp.confidence * 100).toFixed(0)}% conf</p>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// === QUOTES TAB ===
function QuotesTab({ quotes, selectedMarket, setSelectedMarket }: { quotes: MarketQuote[]; selectedMarket: string; setSelectedMarket: (v: string) => void }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <DollarSign className="w-5 h-5 text-green-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Live Quotes</h2>
          <span className="text-xs text-gray-500">{quotes.length} instruments</span>
        </div>
        <select
          value={selectedMarket}
          onChange={e => setSelectedMarket(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800"
        >
          <option value="all">All Markets</option>
          <option value="crypto">Crypto</option>
          <option value="stock">Stocks</option>
          <option value="forex">Forex</option>
          <option value="commodity">Commodities</option>
          <option value="prediction">Prediction</option>
        </select>
      </div>
      {quotes.length > 0 ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
          {quotes.slice(0, 40).map(quote => (
            <div key={quote.symbol} className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-medium text-gray-900 dark:text-white truncate">{quote.symbol}</span>
                <span className="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 rounded capitalize">{quote.market_type}</span>
              </div>
              <p className="text-lg font-mono font-bold text-gray-900 dark:text-white">
                ${quote.price?.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
              </p>
              {quote.change_pct_24h !== null && (
                <div className={`flex items-center gap-1 text-xs ${quote.change_pct_24h >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {quote.change_pct_24h >= 0 ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {quote.change_pct_24h >= 0 ? '+' : ''}{quote.change_pct_24h?.toFixed(2)}%
                </div>
              )}
            </div>
          ))}
        </div>
      ) : (
        <p className="text-center text-gray-500 py-8">No quotes available</p>
      )}
    </Card>
  );
}

// === ALERTS TAB ===
function AlertsTab({ alerts, selectedSeverity, setSelectedSeverity }: { alerts: MarketAlert[]; selectedSeverity: string; setSelectedSeverity: (v: string) => void }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5 text-orange-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Alerts</h2>
          <span className="px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400 text-xs rounded-full">
            {alerts.length}
          </span>
        </div>
        <select
          value={selectedSeverity}
          onChange={e => setSelectedSeverity(e.target.value)}
          className="text-sm border border-gray-200 dark:border-gray-700 rounded-lg px-2 py-1 bg-white dark:bg-gray-800"
        >
          <option value="all">All Severities</option>
          <option value="critical">Critical</option>
          <option value="high">High</option>
          <option value="medium">Medium</option>
          <option value="low">Low</option>
        </select>
      </div>
      {alerts.length > 0 ? (
        <div className="space-y-2 max-h-[600px] overflow-y-auto">
          <AnimatePresence>
            {alerts.map(alert => (
              <motion.div
                key={alert.id}
                initial={{ opacity: 0, x: -20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: 20 }}
                className="flex items-start gap-3 p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
              >
                <div className={`w-2 h-2 rounded-full mt-2 ${SEVERITY_COLORS[alert.severity]}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-medium uppercase ${SEVERITY_TEXT[alert.severity]}`}>{alert.severity}</span>
                    <span className="text-xs text-gray-500 capitalize">{alert.market}</span>
                    <span className="text-xs text-gray-400">&bull;</span>
                    <span className="text-xs text-gray-500">{alert.source}</span>
                  </div>
                  <p className="text-sm font-medium text-gray-900 dark:text-white truncate">{alert.title}</p>
                  <p className="text-xs text-gray-500 truncate">{alert.description}</p>
                </div>
                <div className="text-right">
                  {alert.price > 0 && <p className="text-sm font-mono text-gray-900 dark:text-white">${alert.price?.toLocaleString()}</p>}
                  <p className="text-xs text-gray-500">{(alert.confidence * 100).toFixed(0)}% conf</p>
                </div>
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      ) : (
        <p className="text-center text-gray-500 py-8">No alerts at this time</p>
      )}
    </Card>
  );
}

// === PORTFOLIO TAB ===
function PortfolioTab({ portfolio }: { portfolio: { holdings: PortfolioHolding[]; total_value_thb: number; signal_count: number } | null }) {
  if (!portfolio || !portfolio.holdings?.length) {
    return (
      <Card className="p-8 text-center">
        <Wallet className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
        <p className="text-gray-500 dark:text-gray-400 font-medium">No holdings found</p>
        <p className="text-sm text-gray-400 dark:text-gray-500 mt-1">Connect your Binance TH account to see portfolio signals</p>
      </Card>
    );
  }

  const { holdings, total_value_thb, signal_count } = portfolio;

  return (
    <div className="space-y-4">
      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card className="p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Value</p>
          <p className="text-2xl font-bold text-emerald-600 dark:text-emerald-400">
            \u0e3f{total_value_thb.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Assets Held</p>
          <p className="text-2xl font-bold text-indigo-600 dark:text-indigo-400">{holdings.length}</p>
        </Card>
        <Card className="p-4 text-center">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Active Signals</p>
          <p className="text-2xl font-bold text-orange-600 dark:text-orange-400">{signal_count}</p>
        </Card>
      </div>

      {/* Holdings Table */}
      <Card className="p-4">
        <div className="flex items-center gap-2 mb-4">
          <Wallet className="w-5 h-5 text-emerald-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Binance TH Holdings</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 dark:border-gray-700">
                <th className="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase">Asset</th>
                <th className="text-right py-2 px-2 text-xs font-medium text-gray-500 uppercase">Amount</th>
                <th className="text-right py-2 px-2 text-xs font-medium text-gray-500 uppercase">Price</th>
                <th className="text-right py-2 px-2 text-xs font-medium text-gray-500 uppercase">Value (THB)</th>
                <th className="text-left py-2 px-2 text-xs font-medium text-gray-500 uppercase">Signals</th>
              </tr>
            </thead>
            <tbody>
              {holdings.map((h) => (
                <tr key={h.currency} className="border-b border-gray-100 dark:border-gray-800 hover:bg-gray-50 dark:hover:bg-gray-800/50">
                  <td className="py-3 px-2">
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-gray-900 dark:text-white">{h.currency}</span>
                      {h.symbol !== '\u2014' && (
                        <span className="text-xs text-gray-400">{h.symbol}</span>
                      )}
                    </div>
                  </td>
                  <td className="py-3 px-2 text-right font-mono text-gray-900 dark:text-white">
                    {h.amount.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 6 })}
                    {h.locked > 0 && (
                      <span className="text-xs text-gray-400 ml-1" title={`Locked: ${h.locked}`}>
                        ({h.locked.toLocaleString(undefined, { maximumFractionDigits: 4 })} locked)
                      </span>
                    )}
                  </td>
                  <td className="py-3 px-2 text-right font-mono text-gray-700 dark:text-gray-300">
                    {h.price_thb > 0
                      ? `\u0e3f${h.price_thb.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: h.price_thb > 100 ? 2 : 6 })}`
                      : '\u2014'}
                  </td>
                  <td className="py-3 px-2 text-right font-mono font-semibold text-gray-900 dark:text-white">
                    {h.value_thb > 0
                      ? `\u0e3f${h.value_thb.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
                      : '\u2014'}
                  </td>
                  <td className="py-3 px-2">
                    {h.signals.length > 0 ? (
                      <div className="flex flex-wrap gap-1">
                        {h.signals.map((sig, i) => (
                          <span
                            key={i}
                            className={`text-xs px-1.5 py-0.5 rounded-full font-medium ${
                              sig.severity === 'high' || sig.severity === 'critical'
                                ? 'bg-orange-100 dark:bg-orange-900/30 text-orange-700 dark:text-orange-400'
                                : sig.severity === 'medium'
                                ? 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400'
                                : 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400'
                            }`}
                            title={sig.title}
                          >
                            {sig.type || 'signal'}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="text-xs text-gray-400">No signals</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// === PERFORMANCE TAB ===
function PerformanceTab({ stats, signals }: { stats: SignalPerformanceStats | null; signals: LoggedSignal[] }) {
  const handleEvaluate = async () => {
    try {
      await signalTrackerService.evaluate();
      window.location.reload();
    } catch (e) {
      console.error('Failed to evaluate signals:', e);
    }
  };

  if (!stats) {
    return (
      <Card className="p-8 text-center text-gray-500">
        <Target className="w-12 h-12 mx-auto mb-3 opacity-30" />
        <p>Loading signal performance data...</p>
      </Card>
    );
  }

  const accuracyColor = (rate: number) => {
    if (rate >= 70) return 'text-green-600';
    if (rate >= 50) return 'text-yellow-600';
    return 'text-red-600';
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between p-4 bg-gradient-to-r from-cyan-50 to-blue-50 dark:from-cyan-900/10 dark:to-blue-900/10 rounded-xl border border-cyan-200 dark:border-cyan-800">
        <div className="flex items-center gap-3">
          <Target className="w-8 h-8 text-cyan-500" />
          <div>
            <h3 className="font-semibold text-gray-900 dark:text-white">Signal Performance Tracker</h3>
            <p className="text-sm text-gray-600 dark:text-gray-400">Track if signals were profitable over time</p>
          </div>
        </div>
        <button
          onClick={handleEvaluate}
          className="flex items-center gap-2 px-4 py-2 bg-cyan-500 hover:bg-cyan-600 text-white rounded-lg text-sm font-medium transition-colors"
        >
          <RefreshCw className="w-4 h-4" /> Evaluate Now
        </button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Signals</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.total_signals}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Evaluated (24h)</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{stats.evaluated_24h}</p>
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Accuracy (24h)</p>
          <p className={`text-2xl font-bold ${accuracyColor(stats.accuracy_24h.rate)}`}>
            {stats.accuracy_24h.rate > 0 ? `${stats.accuracy_24h.rate}%` : '—'}
          </p>
          {stats.evaluated_24h > 0 && (
            <p className="text-xs text-gray-500 mt-1">
              <ThumbsUp className="w-3 h-3 inline text-green-500" /> {stats.accuracy_24h.correct}
              {' '}
              <ThumbsDown className="w-3 h-3 inline text-red-500" /> {stats.accuracy_24h.incorrect}
            </p>
          )}
        </Card>
        <Card className="p-4">
          <p className="text-xs text-gray-500 dark:text-gray-400 mb-1">Accuracy (7d)</p>
          <p className={`text-2xl font-bold ${accuracyColor(stats.accuracy_7d.rate)}`}>
            {stats.accuracy_7d.rate > 0 ? `${stats.accuracy_7d.rate}%` : '—'}
          </p>
          {stats.evaluated_7d > 0 && (
            <p className="text-xs text-gray-500 mt-1">
              <ThumbsUp className="w-3 h-3 inline text-green-500" /> {stats.accuracy_7d.correct}
              {' '}
              <ThumbsDown className="w-3 h-3 inline text-red-500" /> {stats.accuracy_7d.incorrect}
            </p>
          )}
        </Card>
      </div>

      {/* Visual Charts */}
      {Object.keys(stats.by_source).length > 0 && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Signal Distribution Chart */}
          <Card className="p-4">
            <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Signal Distribution by Source</h4>
            <div className="space-y-2">
              {Object.entries(stats.by_source)
                .sort((a, b) => b[1].total - a[1].total)
                .map(([source, data]) => {
                  const maxTotal = Math.max(...Object.values(stats.by_source).map(d => d.total));
                  const widthPct = maxTotal > 0 ? (data.total / maxTotal) * 100 : 0;
                  const colors: Record<string, string> = {
                    polymarket: 'bg-purple-500',
                    dexscreener: 'bg-green-500',
                    crypto: 'bg-blue-500',
                    binance_th: 'bg-yellow-500',
                    yahoo_finance: 'bg-red-500',
                    macro: 'bg-indigo-500',
                    airdrops: 'bg-pink-500',
                    degen: 'bg-orange-500',
                    curated: 'bg-cyan-500',
                  };
                  const color = colors[source] || 'bg-gray-500';
                  return (
                    <div key={source} className="flex items-center gap-2">
                      <span className="w-20 text-xs text-gray-600 dark:text-gray-400 capitalize truncate">{source}</span>
                      <div className="flex-1 h-6 bg-gray-100 dark:bg-gray-800 rounded-lg overflow-hidden">
                        <div
                          className={`h-full ${color} rounded-lg transition-all duration-500 flex items-center justify-end pr-2`}
                          style={{ width: `${widthPct}%` }}
                        >
                          <span className="text-xs text-white font-medium">{data.total}</span>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </div>
          </Card>

          {/* Accuracy Gauge */}
          <Card className="p-4">
            <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Accuracy Overview</h4>
            <div className="flex items-center justify-around py-4">
              {/* 24h Gauge */}
              <div className="text-center">
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 transform -rotate-90">
                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="none" className="text-gray-200 dark:text-gray-700" />
                    <circle
                      cx="48" cy="48" r="40"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="none"
                      strokeDasharray={`${(stats.accuracy_24h.rate / 100) * 251.2} 251.2`}
                      strokeLinecap="round"
                      className={stats.accuracy_24h.rate >= 70 ? 'text-green-500' : stats.accuracy_24h.rate >= 50 ? 'text-yellow-500' : 'text-red-500'}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-xl font-bold ${accuracyColor(stats.accuracy_24h.rate)}`}>
                      {stats.accuracy_24h.rate > 0 ? `${stats.accuracy_24h.rate}%` : '—'}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">24h Accuracy</p>
                <p className="text-xs text-gray-400">{stats.evaluated_24h} evaluated</p>
              </div>

              {/* 7d Gauge */}
              <div className="text-center">
                <div className="relative w-24 h-24">
                  <svg className="w-24 h-24 transform -rotate-90">
                    <circle cx="48" cy="48" r="40" stroke="currentColor" strokeWidth="8" fill="none" className="text-gray-200 dark:text-gray-700" />
                    <circle
                      cx="48" cy="48" r="40"
                      stroke="currentColor"
                      strokeWidth="8"
                      fill="none"
                      strokeDasharray={`${(stats.accuracy_7d.rate / 100) * 251.2} 251.2`}
                      strokeLinecap="round"
                      className={stats.accuracy_7d.rate >= 70 ? 'text-green-500' : stats.accuracy_7d.rate >= 50 ? 'text-yellow-500' : 'text-red-500'}
                    />
                  </svg>
                  <div className="absolute inset-0 flex items-center justify-center">
                    <span className={`text-xl font-bold ${accuracyColor(stats.accuracy_7d.rate)}`}>
                      {stats.accuracy_7d.rate > 0 ? `${stats.accuracy_7d.rate}%` : '—'}
                    </span>
                  </div>
                </div>
                <p className="text-xs text-gray-500 mt-2">7d Accuracy</p>
                <p className="text-xs text-gray-400">{stats.evaluated_7d} evaluated</p>
              </div>
            </div>
          </Card>
        </div>
      )}

      {/* Performance by Source */}
      {Object.keys(stats.by_source).length > 0 && (
        <Card className="p-4">
          <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Performance by Source</h4>
          <div className="space-y-2">
            {Object.entries(stats.by_source).map(([source, data]) => {
              const total = data.correct_24h + data.incorrect_24h;
              const rate = total > 0 ? Math.round((data.correct_24h / total) * 100) : 0;
              return (
                <div key={source} className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-800 last:border-0">
                  <span className="font-medium text-gray-900 dark:text-white capitalize">{source}</span>
                  <div className="flex items-center gap-4 text-sm">
                    <span className="text-gray-500">{data.total} signals</span>
                    {total > 0 && (
                      <span className={accuracyColor(rate)}>
                        {rate}% ({data.correct_24h}/{total})
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      )}

      {/* Recent Signals */}
      <Card className="p-4">
        <h4 className="font-semibold text-gray-900 dark:text-white mb-3">Recent Signals</h4>
        {signals.length === 0 ? (
          <p className="text-center text-gray-500 py-6">No signals logged yet. Signals will appear after the next scan.</p>
        ) : (
          <div className="space-y-2">
            {signals.slice(0, 20).map((sig) => (
              <div
                key={sig.signal_id}
                className="flex items-center justify-between py-2 px-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <span className={`w-2 h-2 rounded-full ${
                    sig.severity === 'high' || sig.severity === 'critical' ? 'bg-red-500' :
                    sig.severity === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                  }`} />
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white text-sm">{sig.symbol}</p>
                    <p className="text-xs text-gray-500">{sig.source} · {sig.signal_type}</p>
                  </div>
                </div>
                <div className="text-right">
                  <p className="text-sm font-mono text-gray-900 dark:text-white">
                    ${sig.price_at_signal.toLocaleString(undefined, { maximumFractionDigits: 4 })}
                  </p>
                  <div className="flex items-center gap-2 text-xs">
                    {sig.eval_24h && (
                      <span className={sig.eval_24h.correct ? 'text-green-600' : 'text-red-600'}>
                        24h: {sig.eval_24h.pct_change > 0 ? '+' : ''}{sig.eval_24h.pct_change}%
                      </span>
                    )}
                    {sig.eval_7d && (
                      <span className={sig.eval_7d.correct ? 'text-green-600' : 'text-red-600'}>
                        7d: {sig.eval_7d.pct_change > 0 ? '+' : ''}{sig.eval_7d.pct_change}%
                      </span>
                    )}
                    {!sig.eval_24h && !sig.eval_7d && (
                      <span className="text-gray-400">Pending</span>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
