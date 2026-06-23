/**
 * Market Research Page
 * Polymarket scanner + crypto watchlist + candidate review
 * Part of AI Command Center — AI-selected focus, read-only
 */
'use client';

import { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/translations';
import { FlaskConical, Target, TrendingUp, Eye } from 'lucide-react';

interface MarketCandidate {
  id: string;
  name: string;
  type: 'polymarket' | 'crypto';
  status: 'watching' | 'reviewing' | 'rejected' | 'approved';
  signal?: string;
  price?: string;
  volume?: string;
  lastUpdated: string;
}

// Static candidates — will be replaced by API/scanner
const CANDIDATES: MarketCandidate[] = [
  {
    id: 'btcthb-grid',
    name: 'BTC/THB Grid Paper Trial',
    type: 'crypto',
    status: 'watching',
    signal: 'Grid levels active — BUY ฿2,023,578 / SELL ฿2,150,052',
    price: '฿2,097,000',
    lastUpdated: '2026-06-23T00:50:00Z',
  },
  {
    id: 'polymarket-us-election',
    name: 'US Presidential Election 2028',
    type: 'polymarket',
    status: 'reviewing',
    signal: 'Market volume spike — monitoring for entry signal',
    volume: '$2.4M',
    lastUpdated: '2026-06-22T18:00:00Z',
  },
  {
    id: 'polymarket-btc-100k',
    name: 'BTC > $100K by End of 2026',
    type: 'polymarket',
    status: 'watching',
    signal: 'Current odds: 34% — below threshold',
    volume: '$890K',
    lastUpdated: '2026-06-22T12:00:00Z',
  },
];

const statusColors: Record<string, string> = {
  watching: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
  reviewing: 'bg-purple-100 text-purple-700 dark:bg-purple-900/30 dark:text-purple-400',
  rejected: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
  approved: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
};

export default function ResearchPage() {
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
        {[1, 2, 3].map((i) => (
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
          <FlaskConical className="w-6 h-6 text-purple-600" />
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('nav.research')}
          </h1>
        </div>
        <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
          AI-selected market focus — Polymarket scanner & crypto watchlist
        </p>
      </div>

      {/* Scanner Status */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div className="p-4 bg-blue-50 dark:bg-blue-900/10 rounded-xl border border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-2 mb-2">
            <Target className="w-5 h-5 text-blue-500" />
            <span className="text-sm font-medium text-blue-700 dark:text-blue-400">Polymarket Scanner</span>
          </div>
          <div className="text-lg font-bold text-blue-600 dark:text-blue-400">Scanning</div>
          <div className="text-xs text-blue-500 mt-1">Monitoring {CANDIDATES.filter(c => c.type === 'polymarket').length} markets</div>
        </div>

        <div className="p-4 bg-purple-50 dark:bg-purple-900/10 rounded-xl border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2 mb-2">
            <TrendingUp className="w-5 h-5 text-purple-500" />
            <span className="text-sm font-medium text-purple-700 dark:text-purple-400">Crypto Watchlist</span>
          </div>
          <div className="text-lg font-bold text-purple-600 dark:text-purple-400">Active</div>
          <div className="text-xs text-purple-500 mt-1">{CANDIDATES.filter(c => c.type === 'crypto').length} pairs tracked</div>
        </div>
      </div>

      {/* Candidates */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Eye className="w-5 h-5 text-gray-500" />
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">Candidates</h2>
        </div>
        <div className="space-y-3">
          {CANDIDATES.map((candidate) => (
            <div
              key={candidate.id}
              className="p-4 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-gray-900 dark:text-white">
                    {candidate.name}
                  </span>
                  <span className={`px-2 py-0.5 rounded-full text-[10px] font-medium uppercase ${statusColors[candidate.status]}`}>
                    {candidate.status}
                  </span>
                </div>
                <span className="text-[10px] px-2 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-500 dark:text-gray-400 uppercase">
                  {candidate.type}
                </span>
              </div>
              {candidate.signal && (
                <p className="text-xs text-gray-500 dark:text-gray-400">{candidate.signal}</p>
              )}
              <div className="flex items-center gap-4 mt-2 text-[10px] text-gray-400">
                {candidate.price && <span>Price: {candidate.price}</span>}
                {candidate.volume && <span>Vol: {candidate.volume}</span>}
                <span>Updated: {new Date(candidate.lastUpdated).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
