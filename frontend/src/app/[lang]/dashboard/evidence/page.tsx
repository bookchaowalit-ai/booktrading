/**
 * Evidence & Gates Page
 * Shows EVIDENCE_LOG, readiness gates, and trial results
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import { Shield, CheckCircle, XCircle, AlertTriangle, Clock, FileText } from 'lucide-react';

interface EvidenceEntry {
  timestamp: string;
  type: 'gate' | 'trial' | 'signal' | 'kill_switch';
  status: 'pass' | 'fail' | 'pending' | 'active';
  message: string;
  details?: string;
}

// Static evidence data — will be replaced by API fetch
const EVIDENCE_LOG: EvidenceEntry[] = [
  {
    timestamp: '2026-06-23T00:50:23Z',
    type: 'kill_switch',
    status: 'active',
    message: 'Capital Protection Mode ACTIVE',
    details: 'Kill switch triggered at 15.8% drawdown. Bot halted.',
  },
  {
    timestamp: '2026-06-23T00:50:00Z',
    type: 'trial',
    status: 'pass',
    message: 'BTCTHB Paper Grid 30-min Trial — PASSED',
    details: '0 errors, safety guards held. 1-day observation running.',
  },
  {
    timestamp: '2026-06-22T23:00:00Z',
    type: 'gate',
    status: 'pending',
    message: 'Drawdown Recovery Gate',
    details: 'Waiting for drawdown to recover below 10% threshold before resuming live trading.',
  },
  {
    timestamp: '2026-06-22T20:00:00Z',
    type: 'signal',
    status: 'pass',
    message: 'Grid Level Calculation — Valid',
    details: 'BUY @ ฿2,023,578 / ฿2,065,736 | SELL @ ฿2,150,052 / ฿2,192,210',
  },
];

const statusIcon = (status: EvidenceEntry['status']) => {
  switch (status) {
    case 'pass': return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'fail': return <XCircle className="w-4 h-4 text-red-500" />;
    case 'pending': return <Clock className="w-4 h-4 text-yellow-500" />;
    case 'active': return <AlertTriangle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const statusBadge = (status: EvidenceEntry['status']) => {
  const colors = {
    pass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    fail: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    pending: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    active: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${colors[status]}`}>
      {status}
    </span>
  );
};

export default function EvidencePage() {
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

  return (
    <div className="p-6 space-y-6">
      <div>
        <div className="flex items-center gap-3">
          <Shield className="w-6 h-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('nav.evidence')}
          </h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          Evidence log, readiness gates, and trial results — observe-only
        </p>
      </div>

      {/* Readiness Gates Summary */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="p-4 bg-red-50 dark:bg-red-900/10 rounded-xl border border-red-200 dark:border-red-800">
          <div className="flex items-center gap-2 mb-2">
            <AlertTriangle className="w-5 h-5 text-red-500" />
            <span className="text-sm font-medium text-red-700 dark:text-red-400">Kill Switch</span>
          </div>
          <div className="text-lg font-bold text-red-600 dark:text-red-400">ACTIVE</div>
          <div className="text-xs text-red-500 mt-1">15.8% drawdown — bot halted</div>
        </div>

        <div className="p-4 bg-green-50 dark:bg-green-900/10 rounded-xl border border-green-200 dark:border-green-800">
          <div className="flex items-center gap-2 mb-2">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <span className="text-sm font-medium text-green-700 dark:text-green-400">Paper Trial</span>
          </div>
          <div className="text-lg font-bold text-green-600 dark:text-green-400">PASSED</div>
          <div className="text-xs text-green-500 mt-1">30-min BTCTHB grid — 0 errors</div>
        </div>

        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/10 rounded-xl border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-center gap-2 mb-2">
            <Clock className="w-5 h-5 text-yellow-500" />
            <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">Recovery Gate</span>
          </div>
          <div className="text-lg font-bold text-yellow-600 dark:text-yellow-400">PENDING</div>
          <div className="text-xs text-yellow-500 mt-1">Waiting for drawdown &lt; 10%</div>
        </div>
      </div>

      {/* Evidence Log */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Evidence Log</h2>
        </div>
        <div className="space-y-3">
          {EVIDENCE_LOG.map((entry, i) => (
            <div
              key={i}
              className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  {statusIcon(entry.status)}
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {entry.message}
                  </span>
                </div>
                {statusBadge(entry.status)}
              </div>
              {entry.details && (
                <p className="text-xs text-gray-500 dark:text-gray-400 ml-6">{entry.details}</p>
              )}
              <div className="text-[10px] text-gray-400 mt-2 ml-6">
                {new Date(entry.timestamp).toLocaleString()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
