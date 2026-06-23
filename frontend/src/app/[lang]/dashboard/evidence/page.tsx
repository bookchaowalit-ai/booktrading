/**
 * Evidence & Gates Page
 * Real evidence from EVIDENCE_LOG.md, READINESS_CHECKLIST.md, paper trial JSON
 * Part of AI Command Center — observe-only view
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { Shield, CheckCircle, XCircle, AlertTriangle, Clock, FileText, RefreshCw } from 'lucide-react';
import api from '@/services/api';

// ── Types ──────────────────────────────────────────────────────────────────────

interface EvidenceEntry {
  date: string;
  title: string;
  status: 'pass' | 'fail' | 'info';
  type: 'log' | 'trial' | 'kill_switch' | 'signal';
  details: string;
}

interface Gate {
  name: string;
  status: 'ready' | 'not_ready';
  status_text: string;
  blocked_by: string;
}

interface PaperTrial {
  [key: string]: any;
}

interface EvidenceData {
  evidence_entries: EvidenceEntry[];
  gates: Gate[];
  paper_trial: PaperTrial | null;
  files_found: {
    evidence_log: boolean;
    readiness_checklist: boolean;
    paper_grid_json: boolean;
  };
}

// ── Helpers ────────────────────────────────────────────────────────────────────

const statusIcon = (status: EvidenceEntry['status']) => {
  switch (status) {
    case 'pass': return <CheckCircle className="w-4 h-4 text-green-500" />;
    case 'fail': return <XCircle className="w-4 h-4 text-red-500" />;
    default: return <Clock className="w-4 h-4 text-gray-400" />;
  }
};

const statusBadge = (status: string) => {
  const colors: Record<string, string> = {
    pass: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    fail: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    info: 'bg-gray-100 text-gray-700 dark:bg-gray-900/30 dark:text-gray-400',
    ready: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    not_ready: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${colors[status] || colors.info}`}>
      {status.replace('_', ' ')}
    </span>
  );
};

// ── Component ──────────────────────────────────────────────────────────────────

export default function EvidencePage() {
  const { t } = useTranslation();
  const [data, setData] = useState<EvidenceData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchEvidence = useCallback(async () => {
    const result = await api.getEvidence();
    if (result) {
      setData(result as EvidenceData);
    }
  }, []);

  // Initial load
  useEffect(() => {
    fetchEvidence().finally(() => setIsLoading(false));
  }, [fetchEvidence]);

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await fetchEvidence();
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

  const gates = data?.gates || [];
  const entries = data?.evidence_entries || [];
  const paperTrial = data?.paper_trial;
  const filesFound = data?.files_found || { evidence_log: false, readiness_checklist: false, paper_grid_json: false };

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
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
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* File Status */}
      {!filesFound.evidence_log && !filesFound.readiness_checklist && (
        <div className="p-4 bg-yellow-50 dark:bg-yellow-900/10 rounded-xl border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-600" />
            <span className="text-sm font-medium text-yellow-700 dark:text-yellow-400">
              No evidence files found
            </span>
          </div>
          <p className="text-xs text-yellow-600 mt-1">
            Expected files: docs/EVIDENCE_LOG.md, docs/READINESS_CHECKLIST.md
          </p>
        </div>
      )}

      {/* Readiness Gates */}
      {gates.length > 0 && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <Shield className="w-5 h-5 text-gray-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Readiness Gates</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {gates.map((gate, i) => (
              <div
                key={i}
                className={`p-4 rounded-xl border ${
                  gate.status === 'ready'
                    ? 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800'
                    : 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800'
                }`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {gate.name}
                  </span>
                  {statusBadge(gate.status)}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  {gate.blocked_by}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Paper Trial Results */}
      {paperTrial && (
        <div>
          <div className="flex items-center gap-2 mb-4">
            <CheckCircle className="w-5 h-5 text-green-500" />
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Latest Paper Trial</h2>
          </div>
          <div className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <pre className="text-xs text-gray-600 dark:text-gray-400 overflow-x-auto">
              {JSON.stringify(paperTrial, null, 2)}
            </pre>
          </div>
        </div>
      )}

      {/* Evidence Log Timeline */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <FileText className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Evidence Log</h2>
          {!filesFound.evidence_log && (
            <span className="text-xs text-gray-400 ml-2">(file not found)</span>
          )}
        </div>
        {entries.length === 0 ? (
          <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700">
            <p className="text-sm text-gray-500 dark:text-gray-400">No evidence entries yet.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {entries.map((entry, i) => (
              <div
                key={i}
                className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    {statusIcon(entry.status)}
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {entry.title}
                    </span>
                  </div>
                  {statusBadge(entry.status)}
                </div>
                {entry.details && (
                  <p className="text-xs text-gray-500 dark:text-gray-400 ml-6">{entry.details}</p>
                )}
                <div className="text-[10px] text-gray-400 mt-2 ml-6">{entry.date}</div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
