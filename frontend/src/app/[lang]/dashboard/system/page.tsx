/**
 * System & Health Page
 * Real-time component health from backend APIs
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { Cpu, Activity, CheckCircle, XCircle, Clock, Server, Shield, RefreshCw } from 'lucide-react';
import { monitoringService } from '@/services/monitoring';
import api from '@/services/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface ComponentHealth {
  component: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  lastCheck: string;
  details?: string;
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
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${colors[status]}`}>
      {status}
    </span>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function SystemPage() {
  const { t } = useTranslation();
  const [components, setComponents] = useState<ComponentHealth[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastRefresh, setLastRefresh] = useState<string>('');
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchHealth = useCallback(async () => {
    const now = new Date().toISOString();
    const results: ComponentHealth[] = [];

    // Fire all checks in parallel
    const [healthRes, botStatusRes, gridHealthRes, riskRes, polyPaperRes] = await Promise.allSettled([
      monitoringService.getHealth(),
      api.getBotStatus(),
      api.getRealGridHealth(),
      api.getRiskStatus(),
      api.getPolyPaperStatus(),
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

    // 5. Paper Grid Observer (from /api/poly-paper/status)
    if (polyPaperRes.status === 'fulfilled' && polyPaperRes.value) {
      const pp = polyPaperRes.value as Record<string, any>;
      const running = pp.running ?? false;
      results.push({
        component: 'Paper Grid Observer',
        status: running ? 'healthy' : 'degraded',
        lastCheck: now,
        details: running
          ? `Active — ${Object.keys(pp.markets || {}).length} markets tracked`
          : 'Not running',
      });
    } else {
      results.push({
        component: 'Paper Grid Observer',
        status: 'unknown',
        lastCheck: now,
        details: 'Paper trading endpoint unreachable',
      });
    }

    // 6. Frontend (always healthy if page loads)
    results.push({
      component: 'Frontend (Next.js)',
      status: 'healthy',
      lastCheck: now,
      details: 'Docker container on port 3000',
    });

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

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="space-y-2">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        {[1, 2, 3, 4].map((i) => (
          <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
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
    <div className="p-6 space-y-6">
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
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
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

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
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

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
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
              className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
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
              <div className="text-[10px] text-gray-400 mt-1 ml-6">
                Last check: {new Date(item.lastCheck).toLocaleTimeString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
