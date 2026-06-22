/**
 * Monitoring & Alerting Dashboard
 * Real-time bot health, risk metrics, and alerts
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Activity,
  Shield,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  Power,
  PowerOff,
  RefreshCw,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  Clock,
  Zap,
  Eye,
  Wifi,
  WifiOff,
} from 'lucide-react';
import Card from '@/components/ui/Card';
import { monitoringService } from '@/services/monitoring';
import type { BotStatus, HealthStatus, MarketAlert, RiskEvent } from '@/types/monitoring';

const REFRESH_INTERVAL = 30_000; // 30 seconds

export default function MonitoringPage() {
  const [health, setHealth] = useState<HealthStatus | null>(null);
  const [bot, setBot] = useState<BotStatus | null>(null);
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastRefresh, setLastRefresh] = useState<number>(0);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchData = useCallback(async (showLoader = false) => {
    try {
      if (showLoader) setLoading(true);
      setError(null);
      const data = await monitoringService.getAll();
      setHealth(data.health);
      setBot(data.bot);
      setAlerts(data.alerts);
      setLastRefresh(Date.now());
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load monitoring data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(true);
    const interval = setInterval(() => fetchData(false), REFRESH_INTERVAL);
    return () => clearInterval(interval);
  }, [fetchData]);

  const handleKill = async () => {
    if (!confirm('Are you sure? This will halt ALL real trading immediately.')) return;
    setActionLoading('kill');
    try {
      await monitoringService.killBot();
      await fetchData();
    } catch { /* ignore */ }
    setActionLoading(null);
  };

  const handleEnable = async () => {
    setActionLoading('enable');
    try {
      await monitoringService.enableBot();
      await fetchData();
    } catch { /* ignore */ }
    setActionLoading(null);
  };

  const isBotRunning = bot?.running && bot?.enabled;
  const isHalted = bot?.risk?.halted || !bot?.enabled;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-emerald-100 dark:bg-emerald-900/30 rounded-lg">
            <Eye className="w-6 h-6 text-emerald-600 dark:text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Monitoring</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Real-time bot health, risk metrics & alerts
              {lastRefresh > 0 && (
                <span className="ml-2 text-xs">
                  Updated {formatTimeAgo(lastRefresh)}
                </span>
              )}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() => fetchData(true)}
            className="p-2 rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 text-gray-600 dark:text-gray-400 ${loading ? 'animate-spin' : ''}`} />
          </button>
          {isHalted ? (
            <button
              onClick={handleEnable}
              disabled={actionLoading !== null}
              className="flex items-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <Power className="w-4 h-4" />
              Enable Bot
            </button>
          ) : (
            <button
              onClick={handleKill}
              disabled={actionLoading !== null}
              className="flex items-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:opacity-50 text-white text-sm font-medium rounded-lg transition-colors"
            >
              <PowerOff className="w-4 h-4" />
              Kill Switch
            </button>
          )}
        </div>
      </div>

      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-300 text-sm">
          {error}
        </div>
      )}

      {loading && !bot ? (
        <Card className="flex flex-col items-center justify-center py-16">
          <div className="w-12 h-12 border-4 border-emerald-600 border-t-transparent rounded-full animate-spin mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading monitoring data...</p>
        </Card>
      ) : bot ? (
        <>
          {/* System Health Banner */}
          <HealthBanner health={health} botRunning={!!isBotRunning} halted={!!isHalted} />

          {/* Symbol Status Cards */}
          {bot.symbols && Object.keys(bot.symbols).length > 0 && (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {Object.entries(bot.symbols).map(([symbol, status]) => (
                <SymbolCard key={symbol} symbol={symbol} status={status} />
              ))}
            </div>
          )}

          {/* Risk + Performance Grid */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Risk Metrics */}
            <RiskPanel risk={bot.risk} />

            {/* Performance Stats */}
            <PerformancePanel bot={bot} />
          </div>

          {/* Alerts + Risk Events */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Market Alerts */}
            <AlertsPanel alerts={alerts} />

            {/* Risk Events */}
            <RiskEventsPanel events={bot.risk?.recent_events || []} />
          </div>
        </>
      ) : null}
    </div>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function HealthBanner({ health, botRunning, halted }: {
  health: HealthStatus | null;
  botRunning: boolean;
  halted: boolean;
}) {
  const isHealthy = health?.status === 'healthy' && botRunning && !halted;
  const isDegraded = health?.status === 'degraded' || (botRunning && halted);

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`rounded-lg p-4 flex items-center gap-3 ${
        isHealthy
          ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
          : isDegraded
            ? 'bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800'
            : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
      }`}
    >
      {isHealthy ? (
        <CheckCircle2 className="w-6 h-6 text-green-600 dark:text-green-400 flex-shrink-0" />
      ) : isDegraded ? (
        <AlertTriangle className="w-6 h-6 text-amber-600 dark:text-amber-400 flex-shrink-0" />
      ) : (
        <XCircle className="w-6 h-6 text-red-600 dark:text-red-400 flex-shrink-0" />
      )}
      <div className="flex-1">
        <span className={`font-semibold ${
          isHealthy ? 'text-green-800 dark:text-green-300'
            : isDegraded ? 'text-amber-800 dark:text-amber-300'
              : 'text-red-800 dark:text-red-300'
        }`}>
          {isHealthy ? 'All Systems Operational' : isDegraded ? 'Degraded Performance' : 'System Down'}
        </span>
        <div className={`text-sm mt-0.5 ${
          isHealthy ? 'text-green-600 dark:text-green-400'
            : isDegraded ? 'text-amber-600 dark:text-amber-400'
              : 'text-red-600 dark:text-red-400'
        }`}>
          {!botRunning && 'Bot not running. '}
          {halted && 'Trading halted. '}
          {health && (
            <span className="inline-flex items-center gap-1">
              {health.redis_connected
                ? <><Wifi className="w-3 h-3" /> Redis connected</>
                : <><WifiOff className="w-3 h-3" /> Redis disconnected</>}
            </span>
          )}
        </div>
      </div>
    </motion.div>
  );
}

function SymbolCard({ symbol, status }: { symbol: string; status: any }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <Card>
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <div className={`w-2 h-2 rounded-full ${status.halted ? 'bg-red-500' : 'bg-green-500'}`} />
            <span className="font-bold text-gray-900 dark:text-white">{symbol}</span>
          </div>
          {status.halted && (
            <span className="text-xs px-2 py-0.5 bg-red-100 dark:bg-red-900/30 text-red-600 dark:text-red-400 rounded-full">
              HALTED
            </span>
          )}
        </div>

        <div className="text-2xl font-bold text-gray-900 dark:text-white mb-3">
          ฿{status.last_price?.toLocaleString(undefined, { maximumFractionDigits: 2 })}
        </div>

        <div className="grid grid-cols-2 gap-3 text-sm">
          <div className="flex items-center gap-1.5">
            <TrendingUp className="w-3.5 h-3.5 text-green-500" />
            <span className="text-gray-500 dark:text-gray-400">Buys:</span>
            <span className="font-medium text-gray-900 dark:text-white">{status.active_buys}</span>
          </div>
          <div className="flex items-center gap-1.5">
            <TrendingDown className="w-3.5 h-3.5 text-red-500" />
            <span className="text-gray-500 dark:text-gray-400">Sells:</span>
            <span className="font-medium text-gray-900 dark:text-white">{status.active_sells}</span>
          </div>
          <div>
            <span className="text-gray-500 dark:text-gray-400">Trades: </span>
            <span className="font-medium text-gray-900 dark:text-white">{status.trades_executed}</span>
          </div>
          <div>
            <span className="text-gray-500 dark:text-gray-400">Today: </span>
            <span className={`font-medium ${status.daily_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {status.daily_pnl >= 0 ? '+' : ''}฿{status.daily_pnl?.toFixed(2)}
            </span>
          </div>
        </div>
      </Card>
    </motion.div>
  );
}

function RiskPanel({ risk }: { risk: any }) {
  if (!risk) return null;

  const drawdownPct = risk.current_drawdown_pct || 0;
  const maxDdPct = risk.max_drawdown_pct || 5;
  const ddRatio = Math.min((drawdownPct / maxDdPct) * 100, 100);
  const dailyLossPct = Math.min(
    (Math.abs(Math.min(risk.daily_pnl, 0)) / risk.config?.max_daily_loss_thb) * 100,
    100
  );
  const consecRatio = (risk.consecutive_losses / risk.max_consecutive_losses) * 100;

  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Shield className="w-5 h-5 text-amber-500" />
        Risk Metrics
      </h3>
      <div className="space-y-4">
        {/* Drawdown gauge */}
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-gray-500 dark:text-gray-400">Drawdown</span>
            <span className={`font-medium ${drawdownPct > maxDdPct * 0.7 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
              {drawdownPct.toFixed(2)}% / {maxDdPct}%
            </span>
          </div>
          <div className="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${ddRatio > 70 ? 'bg-red-500' : ddRatio > 40 ? 'bg-amber-500' : 'bg-green-500'}`}
              style={{ width: `${ddRatio}%` }}
            />
          </div>
        </div>

        {/* Daily loss gauge */}
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-gray-500 dark:text-gray-400">Daily Loss</span>
            <span className={`font-medium ${risk.daily_pnl < 0 ? 'text-red-600' : 'text-green-600'}`}>
              {risk.daily_pnl >= 0 ? '+' : ''}฿{risk.daily_pnl?.toFixed(2)} / ฿{risk.config?.max_daily_loss_thb}
            </span>
          </div>
          <div className="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${dailyLossPct > 70 ? 'bg-red-500' : dailyLossPct > 40 ? 'bg-amber-500' : 'bg-green-500'}`}
              style={{ width: `${dailyLossPct}%` }}
            />
          </div>
        </div>

        {/* Consecutive losses */}
        <div>
          <div className="flex items-center justify-between text-sm mb-1">
            <span className="text-gray-500 dark:text-gray-400">Consecutive Losses</span>
            <span className={`font-medium ${consecRatio > 60 ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
              {risk.consecutive_losses} / {risk.max_consecutive_losses}
            </span>
          </div>
          <div className="w-full h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${consecRatio > 60 ? 'bg-red-500' : consecRatio > 30 ? 'bg-amber-500' : 'bg-green-500'}`}
              style={{ width: `${consecRatio}%` }}
            />
          </div>
        </div>

        {/* Config summary */}
        <div className="pt-3 border-t border-gray-200 dark:border-gray-700 grid grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
          <span>Max order: ฿{risk.config?.max_order_size_thb}</span>
          <span>Risk/trade: {risk.config?.risk_per_trade_pct}%</span>
          <span>Max open: {risk.config?.max_open_orders}</span>
          <span>Min interval: {risk.config?.max_daily_loss_thb > 0 ? '10s' : '-'}</span>
        </div>
      </div>
    </Card>
  );
}

function PerformancePanel({ bot }: { bot: BotStatus }) {
  const risk = bot.risk;
  const stats = [
    {
      label: 'Win Rate',
      value: `${risk?.win_rate_pct?.toFixed(1) || 0}%`,
      icon: BarChart3,
      color: (risk?.win_rate_pct || 0) >= 50 ? 'text-green-600 dark:text-green-400' : 'text-amber-600',
    },
    {
      label: 'Daily P&L',
      value: `${risk?.daily_pnl >= 0 ? '+' : ''}฿${risk?.daily_pnl?.toFixed(2) || '0.00'}`,
      icon: DollarSign,
      color: (risk?.daily_pnl || 0) >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400',
    },
    {
      label: 'Daily Trades',
      value: `${risk?.daily_wins || 0}W / ${risk?.daily_losses || 0}L`,
      icon: Activity,
      color: 'text-blue-600 dark:text-blue-400',
    },
    {
      label: 'Total Trades',
      value: String(risk?.total_trades || 0),
      icon: Zap,
      color: 'text-gray-900 dark:text-white',
    },
  ];

  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <BarChart3 className="w-5 h-5 text-blue-500" />
        Performance
      </h3>
      <div className="grid grid-cols-2 gap-4">
        {stats.map((s) => (
          <div key={s.label} className="p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
            <div className="flex items-center gap-1.5 mb-1">
              <s.icon className="w-3.5 h-3.5 text-gray-400" />
              <span className="text-xs text-gray-500 dark:text-gray-400">{s.label}</span>
            </div>
            <div className={`text-lg font-bold ${s.color}`}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Journal stats */}
      {bot.journal_stats && Object.keys(bot.journal_stats).length > 0 && (
        <div className="mt-4 pt-3 border-t border-gray-200 dark:border-gray-700">
          <span className="text-xs text-gray-500 dark:text-gray-400 uppercase font-medium">Journal</span>
          <div className="grid grid-cols-3 gap-2 mt-2 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">Entries: </span>
              <span className="font-medium text-gray-900 dark:text-white">{bot.journal_stats.total_entries || 0}</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Exits: </span>
              <span className="font-medium text-gray-900 dark:text-white">{bot.journal_stats.total_exits || 0}</span>
            </div>
            <div>
              <span className="text-gray-500 dark:text-gray-400">Open: </span>
              <span className="font-medium text-gray-900 dark:text-white">{bot.journal_stats.open_positions || 0}</span>
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}

function AlertsPanel({ alerts }: { alerts: MarketAlert[] }) {
  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <AlertTriangle className="w-5 h-5 text-orange-500" />
        Market Alerts
        {alerts.length > 0 && (
          <span className="ml-auto text-xs px-2 py-0.5 bg-orange-100 dark:bg-orange-900/30 text-orange-600 dark:text-orange-400 rounded-full">
            {alerts.length}
          </span>
        )}
      </h3>
      {alerts.length === 0 ? (
        <div className="text-center py-8 text-gray-400 dark:text-gray-600">
          <CheckCircle2 className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No high-severity alerts</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {alerts.slice(0, 10).map((alert, i) => (
            <div
              key={alert.id || i}
              className="flex items-start gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50"
            >
              <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                alert.severity === 'CRITICAL' ? 'bg-red-500' : 'bg-orange-500'
              }`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white truncate">
                    {alert.title}
                  </span>
                  <span className="text-xs px-1.5 py-0.5 bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded">
                    {alert.symbol}
                  </span>
                </div>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{alert.description}</p>
              </div>
              {alert.timestamp && (
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {formatAlertTime(alert.timestamp)}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function RiskEventsPanel({ events }: { events: RiskEvent[] }) {
  return (
    <Card>
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
        <Clock className="w-5 h-5 text-purple-500" />
        Recent Risk Events
        {events.length > 0 && (
          <span className="ml-auto text-xs px-2 py-0.5 bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded-full">
            {events.length}
          </span>
        )}
      </h3>
      {events.length === 0 ? (
        <div className="text-center py-8 text-gray-400 dark:text-gray-600">
          <Shield className="w-8 h-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No risk events recorded</p>
        </div>
      ) : (
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {events.slice(-10).reverse().map((event, i) => (
            <div
              key={i}
              className="flex items-start gap-2 p-2 rounded-lg bg-gray-50 dark:bg-gray-800/50"
            >
              <div className={`mt-0.5 w-2 h-2 rounded-full flex-shrink-0 ${
                event.severity === 'critical' ? 'bg-red-500'
                  : event.severity === 'warning' ? 'bg-amber-500'
                    : 'bg-blue-500'
              }`} />
              <div className="flex-1 min-w-0">
                <span className="text-sm font-medium text-gray-900 dark:text-white">
                  {event.event_type}
                </span>
                <p className="text-xs text-gray-500 dark:text-gray-400 truncate">{event.message}</p>
              </div>
              {event.timestamp && (
                <span className="text-xs text-gray-400 flex-shrink-0">
                  {new Date(event.timestamp * 1000).toLocaleTimeString()}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function formatTimeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  if (diff < 5000) return 'just now';
  if (diff < 60000) return `${Math.floor(diff / 1000)}s ago`;
  return `${Math.floor(diff / 60000)}m ago`;
}

function formatAlertTime(ts: string): string {
  try {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  } catch {
    return '';
  }
}
