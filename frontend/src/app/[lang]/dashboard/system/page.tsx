/**
 * System & Health Page
 * Bot health, CI/deploy status, technical settings
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import { Cpu, Activity, CheckCircle, XCircle, Clock, Server, GitBranch, Shield } from 'lucide-react';

interface SystemHealth {
  component: string;
  status: 'healthy' | 'degraded' | 'down' | 'unknown';
  lastCheck: string;
  details?: string;
}

const SYSTEM_STATUS: SystemHealth[] = [
  {
    component: 'Trading Bot Engine',
    status: 'down',
    lastCheck: '2026-06-23T01:00:00Z',
    details: 'Halted — capital protection mode (kill switch active)',
  },
  {
    component: 'Backend API',
    status: 'healthy',
    lastCheck: '2026-06-23T01:00:00Z',
    details: 'Responding on port 4000',
  },
  {
    component: 'Strategy API',
    status: 'healthy',
    lastCheck: '2026-06-23T01:00:00Z',
    details: 'Grid strategy engine running',
  },
  {
    component: 'WebSocket Server',
    status: 'healthy',
    lastCheck: '2026-06-23T01:00:00Z',
    details: 'Connected clients: 1',
  },
  {
    component: 'Frontend (Next.js)',
    status: 'healthy',
    lastCheck: '2026-06-23T01:00:00Z',
    details: 'Docker container on port 3000',
  },
  {
    component: 'Paper Grid Observer',
    status: 'healthy',
    lastCheck: '2026-06-23T01:00:00Z',
    details: '1-day BTCTHB observation running (started 2026-06-23T00:50Z)',
  },
];

const statusIcon = (status: SystemHealth['status']) => {
  switch (status) {
    case 'healthy': return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'degraded': return <Clock className="w-4 h-4 text-yellow-500" />;
    case 'down': return <XCircle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const statusBadge = (status: SystemHealth['status']) => {
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

export default function SystemPage() {
  const { t } = useTranslation();
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const timer = setTimeout(() => setIsLoading(false), 800);
    return () => clearTimeout(timer);
  }, []);

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

  const healthyCount = SYSTEM_STATUS.filter(s => s.status === 'healthy').length;
  const totalCount = SYSTEM_STATUS.length;

  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <Cpu className="w-6 h-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('nav.system')}
          </h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          System health, deployment status, and technical overview
        </p>
      </div>

      {/* Overall Health */}
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
          <div className="text-lg font-bold text-red-600">ACTIVE</div>
          <div className="text-xs text-gray-500 mt-1">Kill switch engaged — 15.8% drawdown</div>
        </div>

        <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <GitBranch className="w-5 h-5 text-gray-500" />
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">Last Deploy</span>
          </div>
          <div className="text-lg font-bold text-gray-900 dark:text-white">Docker</div>
          <div className="text-xs text-gray-500 mt-1">Frontend rebuilt with --no-cache</div>
        </div>
      </div>

      {/* Component Health */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Server className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Component Status</h2>
        </div>
        <div className="space-y-3">
          {SYSTEM_STATUS.map((item, i) => (
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
                Last check: {new Date(item.lastCheck).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
