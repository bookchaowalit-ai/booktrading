/**
 * Market Research Page
 * Crypto watchlist + Polymarket scanner — read-only research data
 * Part of AI Command Center — AI-selected focus, read-only
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import api from '@/services/api';
import { FlaskConical, Target, TrendingUp, RefreshCw, AlertTriangle } from 'lucide-react';

interface CryptoPair {
  rank: number;
  score: number;
  exchange: string;
  symbol: string;
  price: string;
  volume: string;
  vol_pct: string;
  spread: string;
  depth: string;
}

interface ReviewedMarket {
  rank: number;
  market: string;
  resolution: string;
  category_leak: string;
  data_source: string;
  signal: string;
  decision: string;
}

interface ResearchData {
  crypto: {
    pairs: CryptoPair[];
    meta: {
      last_scan?: string;
      pairs_scanned?: number;
      min_volume?: string;
    };
    files_found: boolean;
  };
  polymarket: {
    reviewed: ReviewedMarket[];
    meta: {
      last_scan?: string;
      candidates_summary?: string;
      filters?: { key: string; value: string }[];
    };
    files_found: boolean;
  };
}

const scoreColor = (score: number): string => {
  if (score >= 8) return 'text-green-600 dark:text-green-400';
  if (score >= 6) return 'text-yellow-600 dark:text-yellow-400';
  return 'text-red-600 dark:text-red-400';
};

export default function ResearchPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<ResearchData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const fetchData = useCallback(async (isRefresh = false) => {
    if (isRefresh) setIsRefreshing(true);
    const result = await api.getResearch();
    if (result) setData(result);
    setIsLoading(false);
    setIsRefreshing(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(() => fetchData(true), 60000); // refresh every 60s
    return () => clearInterval(interval);
  }, [fetchData]);

  if (isLoading) {
    return (
      <div className="p-6 space-y-4">
        <div className="space-y-2">
          <div className="h-7 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          <div className="h-4 w-72 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
        </div>
        {[1, 2, 3].map((i) => (
          <div key={i} className="p-4 space-y-3 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
            <div className="h-4 w-48 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
            <div className="h-3 w-64 bg-gray-200 dark:bg-gray-700 rounded animate-pulse" />
          </div>
        ))}
      </div>
    );
  }

  const noFiles = data && !data.crypto.files_found && !data.polymarket.files_found;

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-3">
            <FlaskConical className="w-6 h-6 text-purple-600" />
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {t('nav.research')}
            </h1>
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
            Read-only market scanner — crypto watchlist & Polymarket candidates
          </p>
        </div>
        <button
          onClick={() => fetchData(true)}
          disabled={isRefreshing}
          className="flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800 disabled:opacity-50"
        >
          <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          {isRefreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* No files warning */}
      {noFiles && (
        <div className="flex items-center gap-3 p-4 bg-yellow-50 dark:bg-yellow-900/10 rounded-xl border border-yellow-200 dark:border-yellow-800">
          <AlertTriangle className="w-5 h-5 text-yellow-600" />
          <span className="text-sm text-yellow-700 dark:text-yellow-400">
            No watchlist files found. Run the scanner scripts to generate data.
          </span>
        </div>
      )}

      {/* Scanner Status Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-purple-50 dark:bg-purple-900/10 rounded-xl border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-medium text-purple-700 dark:text-purple-400">Crypto Watchlist</span>
          </div>
          <div className="text-lg font-bold text-purple-600 dark:text-purple-400">
            {data?.crypto.meta.pairs_scanned ?? 0} pairs scanned
          </div>
          <div className="text-xs text-purple-500 mt-1">
            {data?.crypto.meta.last_scan ? `Last scan: ${data.crypto.meta.last_scan}` : 'No scan data'}
          </div>
          {data?.crypto.meta.min_volume && (
            <div className="text-xs text-purple-500 mt-0.5">
              Min volume: {data.crypto.meta.min_volume}
            </div>
          )}
        </div>

        <div className="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-medium text-blue-700 dark:text-blue-400">Polymarket Scanner</span>
          </div>
          <div className="text-lg font-bold text-blue-600 dark:text-blue-400">
            {data?.polymarket.meta.candidates_summary ?? 'No data'}
          </div>
          <div className="text-xs text-blue-500 mt-1">
            {data?.polymarket.meta.last_scan ? `Last scan: ${data.polymarket.meta.last_scan}` : 'No scan data'}
          </div>
        </div>
      </div>

      {/* Crypto Watchlist Table */}
      {data?.crypto.files_found && data.crypto.pairs.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-purple-500" />
            Ranked Crypto Pairs
          </h2>
          <div className="overflow-x-auto rounded-xl border border-gray-200 dark:border-gray-700">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-800">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Score</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Exchange</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Symbol</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Price</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Volume</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Spread</th>
                  <th className="px-3 py-2 text-left text-xs font-medium text-gray-500 dark:text-gray-400">Depth</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {data.crypto.pairs.map((pair) => (
                  <tr key={pair.rank} className="bg-white dark:bg-gray-800 hover:bg-gray-50 dark:hover:bg-gray-750">
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{pair.rank}</td>
                    <td className={`px-3 py-2 font-bold ${scoreColor(pair.score)}`}>{pair.score}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{pair.exchange}</td>
                    <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{pair.symbol}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{pair.price}</td>
                    <td className="px-3 py-2 text-gray-700 dark:text-gray-300">{pair.volume}</td>
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{pair.spread}</td>
                    <td className="px-3 py-2 text-gray-500 dark:text-gray-400">{pair.depth}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Polymarket Reviewed Markets */}
      {data?.polymarket.files_found && data.polymarket.reviewed.length > 0 && (
        <div>
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <Target className="w-5 h-5 text-blue-500" />
            Reviewed Polymarket Candidates
          </h2>
          <div className="space-y-3">
            {data.polymarket.reviewed.map((market) => (
              <div
                key={market.rank}
                className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {market.market}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${
                    market.decision === 'REJECT'
                      ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400'
                      : market.decision === 'WATCH'
                      ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400'
                      : 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
                  }`}>
                    {market.decision}
                  </span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-xs text-gray-500 dark:text-gray-400">
                  <div><span className="font-medium">Resolution:</span> {market.resolution}</div>
                  <div><span className="font-medium">Category leak:</span> {market.category_leak}</div>
                  <div><span className="font-medium">Data source:</span> {market.data_source}</div>
                  <div><span className="font-medium">Signal:</span> {market.signal}</div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Polymarket Filters */}
      {data?.polymarket.meta.filters && data.polymarket.meta.filters.length > 0 && (
        <div className="p-4 bg-gray-50 dark:bg-gray-800/50 rounded-xl border border-gray-200 dark:border-gray-700">
          <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">Scanner Filters</h3>
          <div className="flex flex-wrap gap-2">
            {data.polymarket.meta.filters.map((f, i) => (
              <span key={i} className="px-2 py-1 text-xs rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                {f.key}: {f.value}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
