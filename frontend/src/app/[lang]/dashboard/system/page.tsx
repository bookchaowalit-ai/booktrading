/**
 * System & Health Page
 * Real-time component health from backend APIs
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { Cpu, Activity, CheckCircle, XCircle, Clock, Server, Shield, RefreshCw, Target, AlertTriangle, DollarSign, Layers, TrendingUp, Bell, BellOff, Plus, Trash2, Container, Database, HardDrive } from 'lucide-react';
import { monitoringService } from '@/services/monitoring';
import { api } from '@/services/api';
import { AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ComponentHealth {
  component: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  lastCheck: string;
  details?: string;
}

interface RiskSources {
  paper_bot: {
    drawdown_pct: number;
    bankroll: number;
    peak_bankroll: number;
    kill_switch_active: boolean;
    kill_reason: string;
    active_positions: number;
  };
  grid_bot: {
    drawdown_pct: number;
    halted: boolean;
    running: boolean;
    daily_pnl: number;
  };
}

interface SymbolPnL {
  symbol: string;
  realized_pnl: number;
  unrealized_pnl: number;
  total_pnl: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  total_volume: number;
  total_hold_time_seconds: number;
  avg_hold_time_seconds: number;
  updated_at: string;
}

interface PaperPosition {
  symbol: string;
  quantity: number;
  avg_entry_price: number;
  current_price: number;
  unrealized_pnl: number;
  realized_pnl: number;
  updated_at: string;
}

interface PaperPortfolio {
  initial_balance: number;
  current_balance: number;
  total_value: number;
  total_pnl: number;
  total_pnl_percent: number;
  total_trades: number;
  win_trades: number;
  loss_trades: number;
  max_drawdown: number;
  positions?: PaperPosition[];
  symbol_pnl?: Record<string, SymbolPnL>;
  updated_at: string;
}

interface TradeActivity {
  todayCount: number;
  todayBuys: number;
  todaySells: number;
  totalCount: number;
  totalBuys: number;
  totalSells: number;
  mostActivePair: string;
  pairCounts: Record<string, number>;
}

interface PaperOpenOrder {
  id: string;
  symbol: string;
  side: string;
  type: string;
  quantity: number;
  price: number;
  limit_price: number;
  status: string;
  fee: number;
  created_at: string;
}

interface PaperTrade {
  id: string;
  symbol: string;
  side: string;
  type: string;
  quantity: number;
  price: number;
  limit_price: number;
  status: string;
  fee: number;
  created_at: string;
  filled_at: string;
}

interface PortfolioSnapshot {
  total_value: number;
  current_balance: number;
  positions_value: number;
  total_pnl: number;
  total_trades: number;
  created_at: string;
}

interface PriceAlert {
  id: string;
  symbol: string;
  target_price: number;
  direction: string;
  triggered: boolean;
  triggered_at: string | null;
  created_at: string;
}

interface CommandCenterData {
  risk_sources?: RiskSources;
  kill_switch?: {
    active: boolean;
    reason: string;
    drawdown_pct: number;
    max_drawdown_pct: number;
    source: string;
  };
  capital?: {
    bankroll_usdc: number;
    drawdown_pct: number;
    risk_source: string;
  };
  current_decision?: string;
  next_trigger?: string;
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const statusIcon = (status: ComponentHealth['status']) => {
  switch (status) {
    case 'healthy': return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'degraded': return <Clock className="w-4 h-4 text-yellow-500" />;
    case 'down': return <XCircle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const statusBadge = (status: ComponentHealth['status']) => {
  const colors = {
    healthy: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    degraded: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    down: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    unknown: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium uppercase ${colors[status]}`}>
      {status}
    </span>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function SystemPage() {
  const { t } = useTranslation();
  const [components, setComponents] = useState<ComponentHealth[]>([]);
  const [ccData, setCcData] = useState<CommandCenterData | null>(null);
  const [paperPortfolio, setPaperPortfolio] = useState<PaperPortfolio | null>(null);
  const [paperOrders, setPaperOrders] = useState<PaperOpenOrder[]>([]);
  const [paperTrades, setPaperTrades] = useState<PaperTrade[]>([]);
  const [tradeActivity, setTradeActivity] = useState<TradeActivity>({ todayCount: 0, todayBuys: 0, todaySells: 0, totalCount: 0, totalBuys: 0, totalSells: 0, mostActivePair: '', pairCounts: {} });
  const [snapshots, setSnapshots] = useState<PortfolioSnapshot[]>([]);
  const [priceAlerts, setPriceAlerts] = useState<PriceAlert[]>([]);
  const [alertForm, setAlertForm] = useState({ symbol: 'BTCUSDT', target_price: '', direction: 'ABOVE' });
  const [paperGridPnl, setPaperGridPnl] = useState<Record<string, any> | null>(null);
  const [containerHealth, setContainerHealth] = useState<{ name: string; status: string; uptime?: string; image?: string }[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchHealth = useCallback(async () => {
    const now = new Date().toISOString();
    const results: ComponentHealth[] = [];

    // Fire all checks in parallel
    const [healthRes, botStatusRes, gridHealthRes, riskRes, paperGridRes, polyPaperRes, paperPortfolioRes, paperOrdersRes, paperHistoryRes, snapshotsRes, alertsRes] = await Promise.allSettled([
      monitoringService.getHealth(),
      api.getBotStatus(),
      api.getRealGridHealth(),
      api.getRiskStatus(),
      api.getPaperGridStatus(),
      api.getPolyPaperStatus(),
      api.getPaperPortfolio(),
      api.getPaperOpenOrders(),
      api.getPaperHistory(),
      api.getPaperSnapshots(200),
      api.getPriceAlerts(),
    ]);

    // 1. Strategy API (from /api/health — redis + overall)
    if (healthRes.status === 'fulfilled' && healthRes.value) {
      const h = healthRes.value as { status: string; redis_connected: boolean };
      results.push({
        component: 'Strategy API',
        status: h.status === 'healthy' ? 'healthy' : 'degraded',
        lastCheck: now,
        details: `Redis: ${h.redis_connected ? 'connected' : 'disconnected'}`,
      });
    } else {
      results.push({
        component: 'Strategy API',
        status: 'down',
        lastCheck: now,
        details: 'No response from strategy service',
      });
    }

    // 2. Trading Bot Engine (from /api/bot/status)
    if (botStatusRes.status === 'fulfilled' && botStatusRes.value) {
      const bot = botStatusRes.value as { running?: boolean; enabled?: boolean };
      const isRunning = bot.running ?? false;
      const isEnabled = bot.enabled ?? false;
      results.push({
        component: 'Trading Bot Engine',
        status: isRunning ? 'healthy' : isEnabled ? 'degraded' : 'down',
        lastCheck: now,
        details: isRunning
          ? 'Running'
          : isEnabled
            ? 'Enabled but not running'
            : 'Halted — capital protection mode',
      });
    } else {
      results.push({
        component: 'Trading Bot Engine',
        status: 'down',
        lastCheck: now,
        details: 'Backend API unreachable',
      });
    }

    // 3. Real Grid Health (from /api/real-grid/health — stuck detection)
    if (gridHealthRes.status === 'fulfilled' && gridHealthRes.value) {
      const gh = gridHealthRes.value as Record<string, any>;
      const isStuck = gh.is_stuck ?? false;
      results.push({
        component: 'Grid Bot Health',
        status: isStuck ? 'degraded' : 'healthy',
        lastCheck: now,
        details: isStuck
          ? `Stuck detected — ${gh.stuck_duration_sec ?? '?'}s`
          : `No stuck orders, last fill: ${gh.last_fill_age_sec != null ? `${Math.round(gh.last_fill_age_sec)}s ago` : 'N/A'}`,
      });
    } else {
      results.push({
        component: 'Grid Bot Health',
        status: 'unknown',
        lastCheck: now,
        details: 'Health endpoint unreachable',
      });
    }

    // 4. Risk Manager (from /api/risk/status)
    if (riskRes.status === 'fulfilled' && riskRes.value) {
      const risk = riskRes.value as Record<string, any>;
      const halted = risk.halted ?? false;
      const drawdown = risk.current_drawdown_pct ?? 0;
      results.push({
        component: 'Risk Manager',
        status: halted ? 'down' : drawdown > 10 ? 'degraded' : 'healthy',
        lastCheck: now,
        details: halted
          ? `Kill switch ACTIVE — ${drawdown.toFixed(1)}% drawdown`
          : `Drawdown: ${drawdown.toFixed(1)}%, Trades today: ${risk.daily_trades ?? 0}`,
      });
    } else {
      results.push({
        component: 'Risk Manager',
        status: 'unknown',
        lastCheck: now,
        details: 'Risk endpoint unreachable',
      });
    }

    // 5. Paper Grid Bot (from /api/grid/status — geometric + DGT + confluence)
    if (paperGridRes.status === 'fulfilled' && paperGridRes.value) {
      const pg = paperGridRes.value as Record<string, any>;
      const running = pg.running ?? false;
      const symbolCount = Object.keys(pg.symbols || {}).length;
      const totalTrades = Object.values(pg.symbols || {}).reduce((sum: number, s: any) => sum + (s.trades_executed || 0), 0);
      const totalDgtResets = Object.values(pg.symbols || {}).reduce((sum: number, s: any) => sum + (s.dgt_resets || 0), 0);
      results.push({
        component: 'Paper Grid Bot',
        status: running ? 'healthy' : 'degraded',
        lastCheck: now,
        details: running
          ? `Geometric+DGT+Confluence — ${symbolCount} pairs, ${totalTrades} trades, ${totalDgtResets} DGT resets`
          : 'Not running',
      });
      // Extract per-pair PnL from paper grid symbols
      if (pg.symbols && typeof pg.symbols === 'object') {
        setPaperGridPnl(pg.symbols);
      }
    } else {
      results.push({
        component: 'Paper Grid Bot',
        status: 'unknown',
        lastCheck: now,
        details: 'Paper grid endpoint unreachable',
      });
    }

    // 6. Frontend (always healthy if page loads)
    results.push({
      component: 'Frontend (Next.js)',
      status: 'healthy',
      lastCheck: now,
      details: 'Docker container on port 3000',
    });

    // 7. Infrastructure — derive container health from available signals
    const containers: { name: string; status: string; uptime?: string; image?: string }[] = [];
    // Redis (from health check)
    if (healthRes.status === 'fulfilled' && healthRes.value) {
      const h = healthRes.value as { redis_connected: boolean };
      containers.push({
        name: 'Redis',
        status: h.redis_connected ? 'running' : 'stopped',
        image: 'redis:7-alpine',
      });
    } else {
      containers.push({ name: 'Redis', status: 'unknown', image: 'redis:7-alpine' });
    }
    // Strategy API (from health check)
    if (healthRes.status === 'fulfilled' && healthRes.value) {
      const h = healthRes.value as { status: string };
      containers.push({
        name: 'Strategy API',
        status: h.status === 'healthy' ? 'running' : 'degraded',
        image: 'booktrading/strategy',
      });
    }
    // Go Paper Engine (from portfolio fetch)
    if (paperPortfolioRes.status === 'fulfilled') {
      containers.push({
        name: 'Go Paper Engine',
        status: 'running',
        image: 'booktrading/paper-engine',
      });
    } else {
      containers.push({ name: 'Go Paper Engine', status: 'stopped', image: 'booktrading/paper-engine' });
    }
    // Polymarket Paper Bot (from poly paper status)
    if (polyPaperRes.status === 'fulfilled' && polyPaperRes.value) {
      const pp = polyPaperRes.value as { running?: boolean };
      containers.push({
        name: 'Polymarket Bot',
        status: pp.running ? 'running' : 'stopped',
        image: 'booktrading/poly-bot',
      });
    }
    // Frontend
    containers.push({ name: 'Frontend', status: 'running', image: 'booktrading/frontend' });
    setContainerHealth(containers);

    // Fetch command-center for risk_sources data
    try {
      const ccRes = await api.getCommandCenter();
      if (ccRes) setCcData(ccRes as CommandCenterData);
    } catch {
      // Optional — component health still works without it
    }

    // Paper Trading Engine (Go — BTCTHB)
    if (paperPortfolioRes.status === 'fulfilled' && paperPortfolioRes.value) {
      setPaperPortfolio(paperPortfolioRes.value as PaperPortfolio);
    }
    if (paperOrdersRes.status === 'fulfilled' && paperOrdersRes.value) {
      setPaperOrders(paperOrdersRes.value as PaperOpenOrder[]);
    }
    if (paperHistoryRes.status === 'fulfilled' && paperHistoryRes.value) {
      const trades = paperHistoryRes.value as PaperTrade[];
      const sorted = trades.sort((a, b) => new Date(b.filled_at).getTime() - new Date(a.filled_at).getTime());
      setPaperTrades(sorted.slice(0, 15));

      // Compute activity summary from all trades
      const now = new Date();
      const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
      const todayTrades = trades.filter(t => new Date(t.filled_at) >= todayStart);
      const todayBuys = todayTrades.filter(t => t.side === 'BUY').length;
      const todaySells = todayTrades.filter(t => t.side === 'SELL').length;
      const totalBuys = trades.filter(t => t.side === 'BUY').length;
      const totalSells = trades.filter(t => t.side === 'SELL').length;
      const pairCounts: Record<string, number> = {};
      trades.forEach(t => { pairCounts[t.symbol] = (pairCounts[t.symbol] || 0) + 1; });
      const mostActivePair = Object.entries(pairCounts).sort((a, b) => b[1] - a[1])[0]?.[0] || '';
      setTradeActivity({ todayCount: todayTrades.length, todayBuys, todaySells, totalCount: trades.length, totalBuys, totalSells, mostActivePair, pairCounts });
    }

    // Portfolio snapshots for sparkline
    if (snapshotsRes.status === 'fulfilled' && snapshotsRes.value) {
      setSnapshots(snapshotsRes.value as PortfolioSnapshot[]);
    }

    // Price alerts
    if (alertsRes.status === 'fulfilled' && alertsRes.value) {
      setPriceAlerts(alertsRes.value as PriceAlert[]);
    }

    setComponents(results);
    setLastRefresh(now);
  }, []);

  // Initial load
  useEffect(() => {
    fetchHealth().finally(() => setIsLoading(false));
  }, [fetchHealth]);

  // Auto-refresh every 30s
  useEffect(() => {
    const interval = setInterval(async () => {
      setIsRefreshing(true);
      await fetchHealth();
      setIsRefreshing(false);
    }, 30000);
    return () => clearInterval(interval);
  }, [fetchHealth]);

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchHealth();
    setIsRefreshing(false);
  };

  // Price alert handlers
  const handleAddAlert = async () => {
    if (!alertForm.target_price || parseFloat(alertForm.target_price) <= 0) return;
    try {
      await api.createPriceAlert(alertForm.symbol, parseFloat(alertForm.target_price), alertForm.direction as 'ABOVE' | 'BELOW');
      setAlertForm({ ...alertForm, target_price: '' });
      const alerts = await api.getPriceAlerts();
      if (alerts) setPriceAlerts(alerts as PriceAlert[]);
    } catch { /* ignore */ }
  };

  const handleDeleteAlert = async (id: string) => {
    try {
      await api.deletePriceAlert(id);
      setPriceAlerts(prev => prev.filter(a => a.id !== id));
    } catch { /* ignore */ }
  };

  const handleResetAlerts = async () => {
    try {
      await api.resetPriceAlerts();
      const alerts = await api.getPriceAlerts();
      if (alerts) setPriceAlerts(alerts as PriceAlert[]);
    } catch { /* ignore */ }
  };

  if (isLoading) {
    return (
      <div className="mx-auto max-w-7xl p-6 space-y-4">
        <div className="space-y-2">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
            <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-3 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  const healthyCount = components.filter(s => s.status === 'healthy').length;
  const totalCount = components.length;

  return (
    <div className="mx-auto max-w-7xl p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <Cpu className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('nav.system')}
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Live system health — auto-refresh every 30s
          </p>
        </div>
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          aria-label="Refresh system health"
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Activity className="w-5 h-5 text-gray-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Overall Health</span>
          </div>
          <div className={`text-lg font-bold ${healthyCount === totalCount ? 'text-green-600' : 'text-yellow-600'}`}>
            {healthyCount}/{totalCount} Components
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {healthyCount === totalCount ? 'All systems operational' : 'Some components need attention'}
          </div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Shield className="w-5 h-5 text-red-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Protection Mode</span>
          </div>
          {(() => {
            const risk = components.find(c => c.component === 'Risk Manager');
            const isHalted = risk?.status === 'down';
            return (
              <>
                <div className={`text-lg font-bold ${isHalted ? 'text-red-600' : 'text-green-600'}`}>
                  {isHalted ? 'ACTIVE' : 'INACTIVE'}
                </div>
                <div className="text-xs text-gray-500 mt-1">{risk?.details ?? 'Checking...'}</div>
              </>
            );
          })()}
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <Server className="w-5 h-5 text-gray-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Last Check</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">
            {lastRefresh ? new Date(lastRefresh).toLocaleTimeString() : '—'}
          </div>
          <div className="text-xs text-gray-500 mt-1">
            {isRefreshing ? 'Refreshing...' : 'Next refresh in 30s'}
          </div>
        </div>
      </div>

      {/* Component Status */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Server className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Component Status</h2>
        </div>
        <div className="space-y-3">
          {components.map((item, i) => (
            <div
              key={i}
              className="p-4 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-2">
                  {statusIcon(item.status)}
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {item.component}
                  </span>
                </div>
                {statusBadge(item.status)}
              </div>
              {item.details && (
                <p className="text-xs text-gray-500 dark:text-gray-400 ml-6">{item.details}</p>
              )}
              <div className="text-xs text-gray-400 mt-1 ml-6">
                Last check: {new Date(item.lastCheck).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Infrastructure */}
      {containerHealth.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <HardDrive className="w-5 h-5 text-cyan-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Infrastructure</h2>
            <span className="text-xs text-gray-400">({containerHealth.filter(c => c.status === 'running').length}/{containerHealth.length} running)</span>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            {containerHealth.map((c) => (
              <div key={c.name} className="p-3 bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700">
                <div className="flex items-center gap-2 mb-1">
                  <div className={`w-2 h-2 rounded-full ${c.status === 'running' ? 'bg-green-500' : c.status === 'degraded' ? 'bg-yellow-500' : 'bg-red-500'}`} />
                  <span className="text-xs font-medium text-gray-900 dark:text-white truncate">{c.name}</span>
                </div>
                <span className={`text-[10px] px-1.5 py-0.5 rounded font-medium ${
                  c.status === 'running' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400' :
                  c.status === 'degraded' ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400' :
                  'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                }`}>
                  {c.status.toUpperCase()}
                </span>
                {c.image && (
                  <p className="text-[10px] text-gray-400 mt-1 truncate font-mono">{c.image}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Trading Metrics (3 separate panels — never combine PnL) ── */}
      <div>
        <div className="flex items-center gap-2 mb-3">
          <Layers className="w-5 h-5 text-indigo-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Trading Metrics</h2>
          <span className="text-xs text-gray-400 ml-2">PnL is separated per engine — never combined</span>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">

          {/* ── 1. Paper Grid Bot (BTCTHB) — Go Paper Engine ── */}
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-purple-200 dark:border-purple-800/50">
            <div className="flex items-center gap-2 mb-3">
              <Layers className="w-4 h-4 text-purple-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">Paper Grid (BTCTHB)</span>
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400">SIMULATED</span>
            </div>
            {paperPortfolio ? (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Balance</span>
                  <span className="font-medium text-gray-900 dark:text-white">${paperPortfolio.current_balance.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Total Value</span>
                  <span className="font-medium text-gray-900 dark:text-white">${paperPortfolio.total_value.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Total P&L</span>
                  <span className={`font-medium ${paperPortfolio.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {paperPortfolio.total_pnl >= 0 ? '+' : ''}${paperPortfolio.total_pnl.toFixed(2)} ({paperPortfolio.total_pnl_percent.toFixed(2)}%)
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Open Orders</span>
                  <span className="font-medium text-gray-900 dark:text-white">{paperOrders.filter(o => o.status === 'PENDING').length}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Trades</span>
                  <span className="font-medium text-gray-900 dark:text-white">{paperPortfolio.total_trades} ({paperPortfolio.win_trades}W/{paperPortfolio.loss_trades}L)</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Max Drawdown</span>
                  <span className="font-medium text-gray-900 dark:text-white">{paperPortfolio.max_drawdown.toFixed(2)}%</span>
                </div>
                {/* Per-symbol PnL breakdown */}
                {paperPortfolio.symbol_pnl && Object.keys(paperPortfolio.symbol_pnl).length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-xs text-gray-400 mb-1">Per-Symbol P&L:</p>
                    <div className="space-y-1">
                      {Object.entries(paperPortfolio.symbol_pnl)
                        .sort(([, a], [, b]) => b.total_pnl - a.total_pnl)
                        .map(([sym, spnl]) => {
                          const winRate = spnl.total_trades > 0 ? (spnl.win_trades / spnl.total_trades) * 100 : 0;
                          const avgHold = spnl.avg_hold_time_seconds || 0;
                          const avgHoldStr = avgHold >= 3600 ? `${(avgHold / 3600).toFixed(1)}h` : avgHold >= 60 ? `${(avgHold / 60).toFixed(0)}m` : `${avgHold.toFixed(0)}s`;
                          return (
                            <div key={sym} className="text-xs py-1 border-b border-gray-50 dark:border-gray-700/50 last:border-0">
                              <div className="flex items-center justify-between">
                                <span className="font-mono text-gray-600 dark:text-gray-300 w-16 truncate">{sym}</span>
                                <span className={`font-medium ${spnl.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                                  {spnl.total_pnl >= 0 ? '+' : ''}${spnl.total_pnl.toFixed(2)}
                                </span>
                              </div>
                              {spnl.total_trades > 0 && (
                                <div className="flex items-center justify-between text-[10px] text-gray-400 mt-0.5">
                                  <span>{spnl.total_trades}t • {winRate.toFixed(0)}% WR</span>
                                  <span>{avgHold > 0 ? avgHoldStr : '—'}</span>
                                </div>
                              )}
                            </div>
                          );
                        })}
                    </div>
                  </div>
                )}
                {/* Open Positions */}
                {paperPortfolio.positions && paperPortfolio.positions.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-xs text-gray-400 mb-1">Open Positions ({paperPortfolio.positions.length}):</p>
                    <div className="space-y-1">
                      {paperPortfolio.positions.map(pos => {
                        const pnlPct = pos.avg_entry_price > 0 ? ((pos.current_price - pos.avg_entry_price) / pos.avg_entry_price) * 100 : 0;
                        return (
                          <div key={pos.symbol} className="flex items-center justify-between text-xs">
                            <span className="font-mono text-gray-600 dark:text-gray-300 w-14 truncate">{pos.symbol}</span>
                            <span className="text-gray-500">{pos.quantity.toFixed(4)}</span>
                            <span className={`font-medium ${pos.unrealized_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                              {pos.unrealized_pnl >= 0 ? '+' : ''}${pos.unrealized_pnl.toFixed(2)}
                            </span>
                            <span className={`text-[10px] ${pnlPct >= 0 ? 'text-green-500' : 'text-red-500'}`}>
                              {pnlPct >= 0 ? '+' : ''}{pnlPct.toFixed(2)}%
                            </span>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}
                {/* Pending orders detail */}
                {paperOrders.filter(o => o.status === 'PENDING').length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-xs text-gray-400 mb-1">Pending Limits:</p>
                    {paperOrders.filter(o => o.status === 'PENDING').slice(0, 4).map(o => (
                      <div key={o.id} className="flex justify-between text-xs py-0.5">
                        <span className={`${o.side === 'BUY' ? 'text-green-600' : 'text-red-600'}`}>{o.side}</span>
                        <span className="text-gray-500 font-mono">฿{Math.round(o.limit_price).toLocaleString()}</span>
                      </div>
                    ))}
                    {paperOrders.filter(o => o.status === 'PENDING').length > 4 && (
                      <p className="text-xs text-gray-400">+{paperOrders.filter(o => o.status === 'PENDING').length - 4} more</p>
                    )}
                  </div>
                )}
                {/* Trade Activity Summary */}
                {tradeActivity.totalCount > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-xs text-gray-400 mb-1">
                      {tradeActivity.todayCount > 0 ? "Today's Activity:" : "All-time Activity:"}
                    </p>
                    <div className="flex items-center gap-3 text-xs">
                      {tradeActivity.todayCount > 0 ? (
                        <>
                          <span className="font-medium text-gray-700 dark:text-gray-200">{tradeActivity.todayCount} trades</span>
                          <span className="text-green-600">{tradeActivity.todayBuys}B</span>
                          <span className="text-red-600">{tradeActivity.todaySells}S</span>
                        </>
                      ) : (
                        <>
                          <span className="font-medium text-gray-700 dark:text-gray-200">{tradeActivity.totalCount} trades</span>
                          <span className="text-green-600">{tradeActivity.totalBuys}B</span>
                          <span className="text-red-600">{tradeActivity.totalSells}S</span>
                        </>
                      )}
                      {tradeActivity.mostActivePair && (
                        <span className="text-gray-500">top: <span className="font-mono">{tradeActivity.mostActivePair}</span></span>
                      )}
                    </div>
                  </div>
                )}
                {/* Recent Trade History */}
                {paperTrades.length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <p className="text-xs text-gray-400 mb-1">Recent Trades ({paperTrades.length}):</p>
                    <div className="space-y-0.5 max-h-32 overflow-y-auto">
                      {paperTrades.slice(0, 8).map(trade => {
                        const time = new Date(trade.filled_at);
                        const timeStr = time.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
                        return (
                          <div key={trade.id} className="flex items-center justify-between text-[10px] py-0.5">
                            <span className="text-gray-400 w-10">{timeStr}</span>
                            <span className="font-mono text-gray-600 dark:text-gray-300 w-14 truncate">{trade.symbol}</span>
                            <span className={trade.side === 'BUY' ? 'text-green-600' : 'text-red-600'}>{trade.side}</span>
                            <span className="text-gray-500 font-mono">{trade.quantity.toFixed(4)}</span>
                            <span className="text-gray-500 font-mono">฿{trade.price < 100 ? trade.price.toFixed(2) : Math.round(trade.price).toLocaleString()}</span>
                          </div>
                        );
                      })}
                      {paperTrades.length > 8 && (
                        <p className="text-[10px] text-gray-400 text-center">+{paperTrades.length - 8} more</p>
                      )}
                    </div>
                  </div>
                )}
                {/* Portfolio Value Sparkline */}
                {snapshots.length > 1 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <div className="flex items-center gap-1 mb-1">
                      <TrendingUp className="w-3 h-3 text-purple-500" />
                      <p className="text-xs text-gray-400">Portfolio Value ({snapshots.length} snapshots)</p>
                    </div>
                    <ResponsiveContainer width="100%" height={80}>
                      <AreaChart data={snapshots.map(s => ({ time: new Date(s.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }), value: s.total_value }))}>
                        <XAxis dataKey="time" hide />
                        <YAxis domain={['dataMin - 5', 'dataMax + 5']} hide />
                        <Tooltip
                          contentStyle={{ fontSize: 10, background: 'rgba(0,0,0,0.8)', border: 'none', borderRadius: 4 }}
                          labelStyle={{ color: '#9ca3af' }}
                          formatter={(value: number) => [`$${value.toFixed(2)}`, 'Value']}
                        />
                        <Area type="monotone" dataKey="value" stroke="#a855f7" fill="rgba(168,85,247,0.15)" strokeWidth={1.5} dot={false} />
                      </AreaChart>
                    </ResponsiveContainer>
                  </div>
                )}
                {/* Paper Grid Per-Pair Status */}
                {paperGridPnl && Object.keys(paperGridPnl).length > 0 && (
                  <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                    <div className="flex items-center gap-1 mb-1">
                      <Layers className="w-3 h-3 text-purple-500" />
                      <p className="text-xs text-gray-400">Grid Bot Per-Pair</p>
                    </div>
                    <div className="space-y-1">
                      {Object.entries(paperGridPnl).map(([pair, data]: [string, any]) => (
                        <div key={pair} className="flex items-center justify-between text-xs py-0.5">
                          <span className="font-mono text-gray-600 dark:text-gray-300 w-16 truncate">{pair}</span>
                          <span className="text-gray-500">{data.trades_executed || 0} trades</span>
                          <span className="text-gray-500">{data.dgt_resets || 0} DGT</span>
                          <span className={`font-medium ${(data.trades_executed || 0) > 0 ? 'text-green-600 dark:text-green-400' : 'text-gray-400'}`}>
                            {(data.trades_executed || 0) > 0 ? 'ACTIVE' : 'IDLE'}
                          </span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No data</p>
            )}
          </div>

          {/* ── 2. Real Grid Bot (BTCTHB) — Testnet/Safety Mode ── */}
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-blue-200 dark:border-blue-800/50">
            <div className="flex items-center gap-2 mb-3">
              <Activity className="w-4 h-4 text-blue-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">Real Grid (BTCTHB)</span>
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">TESTNET</span>
            </div>
            {ccData?.risk_sources?.grid_bot ? (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Running</span>
                  <span className={`font-medium ${ccData.risk_sources.grid_bot.running ? 'text-green-600 dark:text-green-400' : 'text-gray-500'}`}>
                    {ccData.risk_sources.grid_bot.running ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Halted</span>
                  <span className={`font-medium ${ccData.risk_sources.grid_bot.halted ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                    {ccData.risk_sources.grid_bot.halted ? 'Yes' : 'No'}
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Drawdown</span>
                  <span className="font-medium text-gray-900 dark:text-white">
                    {ccData.risk_sources.grid_bot.drawdown_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Daily P&L</span>
                  <span className={`font-medium ${ccData.risk_sources.grid_bot.daily_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                    {ccData.risk_sources.grid_bot.daily_pnl >= 0 ? '+' : ''}${ccData.risk_sources.grid_bot.daily_pnl.toFixed(2)}
                  </span>
                </div>
                <div className="mt-2 pt-2 border-t border-gray-100 dark:border-gray-700">
                  <p className="text-xs text-gray-400">Real orders DISABLED — safety/testnet mode. No real capital at risk.</p>
                </div>
              </div>
            ) : (
              <p className="text-sm text-gray-400">No data</p>
            )}
          </div>

          {/* ── 3. Paper Bot (Polymarket) — Prediction Market Paper ── */}
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-emerald-200 dark:border-emerald-800/50">
            <div className="flex items-center gap-2 mb-3">
              <Target className="w-4 h-4 text-emerald-500" />
              <span className="text-sm font-semibold text-gray-900 dark:text-white">Paper Bot (Polymarket)</span>
              <span className="ml-auto text-xs px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400">PAPER</span>
            </div>
            {ccData?.risk_sources?.paper_bot ? (
              <div className="space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Bankroll</span>
                  <span className="font-medium text-gray-900 dark:text-white">${ccData.risk_sources.paper_bot.bankroll.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Peak</span>
                  <span className="font-medium text-gray-900 dark:text-white">${ccData.risk_sources.paper_bot.peak_bankroll.toFixed(2)}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Drawdown</span>
                  <span className={`font-medium ${ccData.risk_sources.paper_bot.drawdown_pct > 10 ? 'text-red-600 dark:text-red-400' : 'text-gray-900 dark:text-white'}`}>
                    {ccData.risk_sources.paper_bot.drawdown_pct.toFixed(1)}%
                  </span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Active Positions</span>
                  <span className="font-medium text-gray-900 dark:text-white">{ccData.risk_sources.paper_bot.active_positions}</span>
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">Kill Switch</span>
                  <span className={`font-medium ${ccData.risk_sources.paper_bot.kill_switch_active ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                    {ccData.risk_sources.paper_bot.kill_switch_active ? 'ACTIVE' : 'Inactive'}
                  </span>
                </div>
                {ccData.risk_sources.paper_bot.kill_reason && (
                  <p className="text-xs text-red-500 dark:text-red-400 bg-red-50 dark:bg-red-900/10 p-2 rounded">
                    {ccData.risk_sources.paper_bot.kill_reason}
                  </p>
                )}
              </div>
            ) : (
              <p className="text-sm text-gray-400">No data</p>
            )}
          </div>
        </div>

        {/* Decision context */}
        {ccData?.current_decision && (
          <div className="mt-3 p-3 bg-gray-50 dark:bg-gray-700/30 rounded-lg">
            <div className="flex items-center gap-2">
              <span className="text-xs font-medium text-gray-500 dark:text-gray-400">Current Decision:</span>
              <span className="text-sm font-bold text-gray-900 dark:text-white">{ccData.current_decision}</span>
            </div>
            {ccData.next_trigger && (
              <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">Next: {ccData.next_trigger}</p>
            )}
          </div>
        )}
      </div>

      {/* ── Price Alerts ── */}
      <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-amber-200 dark:border-amber-800/50">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Bell className="w-4 h-4 text-amber-500" />
            <span className="text-sm font-semibold text-gray-900 dark:text-white">Price Alerts</span>
            <span className="text-xs text-gray-400">({priceAlerts.length})</span>
          </div>
          {priceAlerts.some(a => a.triggered) && (
            <button onClick={handleResetAlerts} className="flex items-center gap-1 text-xs px-2 py-1 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400 hover:bg-amber-200 dark:hover:bg-amber-900/50 transition-colors">
              <BellOff className="w-3 h-3" /> Reset Triggered
            </button>
          )}
        </div>
        {/* Add Alert Form */}
        <div className="flex flex-wrap items-end gap-2 mb-3">
          <div>
            <label className="text-[10px] text-gray-400 block mb-0.5">Symbol</label>
            <select
              value={alertForm.symbol}
              onChange={e => setAlertForm({ ...alertForm, symbol: e.target.value })}
              className="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
            >
              {['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'XRPUSDT', 'BNBUSDT', 'BTCTHB', 'ETHTHB', 'SOLTHB', 'XRPTHB', 'BNBTHB'].map(s => (
                <option key={s} value={s}>{s}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="text-[10px] text-gray-400 block mb-0.5">Target Price</label>
            <input
              type="number"
              step="any"
              value={alertForm.target_price}
              onChange={e => setAlertForm({ ...alertForm, target_price: e.target.value })}
              placeholder="0.00"
              className="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white w-28"
            />
          </div>
          <div>
            <label className="text-[10px] text-gray-400 block mb-0.5">Direction</label>
            <select
              value={alertForm.direction}
              onChange={e => setAlertForm({ ...alertForm, direction: e.target.value })}
              className="text-xs px-2 py-1 rounded border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 text-gray-900 dark:text-white"
            >
              <option value="ABOVE">ABOVE</option>
              <option value="BELOW">BELOW</option>
            </select>
          </div>
          <button
            onClick={handleAddAlert}
            disabled={!alertForm.target_price}
            className="flex items-center gap-1 text-xs px-3 py-1 rounded bg-purple-600 text-white hover:bg-purple-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            <Plus className="w-3 h-3" /> Add
          </button>
        </div>
        {/* Alert List */}
        {priceAlerts.length > 0 ? (
          <div className="space-y-1 max-h-40 overflow-y-auto">
            {priceAlerts.map(alert => (
              <div key={alert.id} className={`flex items-center justify-between text-xs px-2 py-1.5 rounded ${alert.triggered ? 'bg-green-50 dark:bg-green-900/10' : 'bg-gray-50 dark:bg-gray-900/30'}`}>
                <div className="flex items-center gap-2">
                  <span className={`w-1.5 h-1.5 rounded-full ${alert.triggered ? 'bg-green-500' : 'bg-gray-400'}`} />
                  <span className="font-mono text-gray-700 dark:text-gray-300">{alert.symbol}</span>
                  <span className={alert.direction === 'ABOVE' ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}>
                    {alert.direction === 'ABOVE' ? '↑' : '↓'}
                  </span>
                  <span className="text-gray-600 dark:text-gray-400 font-mono">{alert.target_price.toLocaleString()}</span>
                  {alert.triggered && (
                    <span className="text-[10px] text-green-600 dark:text-green-400">TRIGGERED</span>
                  )}
                </div>
                <button onClick={() => handleDeleteAlert(alert.id)} className="text-gray-400 hover:text-red-500 transition-colors">
                  <Trash2 className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        ) : (
          <p className="text-xs text-gray-400">No alerts configured. Add one above to get notified on price movements.</p>
        )}
      </div>
    </div>
  );
}
