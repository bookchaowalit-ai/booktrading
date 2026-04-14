/**
 * Copy Trading Page - Real API Only
 * Discover and copy top-performing strategies
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  Users,
  TrendingUp,
  Plus,
  X,
  Trophy,
  Target,
  Percent,
  BarChart3,
  Check,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function CopyTradingPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning, info } = useToast();

  const [activeTab, setActiveTab] = useState<'leaderboard' | 'my-strategies' | 'copying'>('leaderboard');
  const [leaderboard, setLeaderboard] = useState<any[]>([]);
  const [myStrategies, setMyStrategies] = useState<any[]>([]);
  const [copying, setCopying] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [newStrategy, setNewStrategy] = useState({
    name: '',
    strategy_type: 'grid',
    is_public: false,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [lbRes, myRes, copyingRes] = await Promise.allSettled([
        fetch(`${API_BASE_URL}/api/copy/leaderboard?limit=20`, { headers: authHeaders() }),
        fetch(`${API_BASE_URL}/api/copy/strategies/my`, { headers: authHeaders() }),
        fetch(`${API_BASE_URL}/api/copy/copied`, { headers: authHeaders() }),
      ]);

      if (lbRes.status === 'fulfilled' && lbRes.value.ok) {
        const data = await lbRes.value.json();
        setLeaderboard(Array.isArray(data) ? data : []);
      } else {
        setLeaderboard([]);
      }

      if (myRes.status === 'fulfilled' && myRes.value.ok) {
        const data = await myRes.value.json();
        setMyStrategies(Array.isArray(data) ? data : []);
      } else {
        setMyStrategies([]);
      }

      if (copyingRes.status === 'fulfilled' && copyingRes.value.ok) {
        const data = await copyingRes.value.json();
        setCopying(Array.isArray(data) ? data : []);
      } else {
        setCopying([]);
      }
    } catch {
      setLeaderboard([]);
      setMyStrategies([]);
      setCopying([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const createStrategy = async () => {
    if (!newStrategy.name) {
      warning('Strategy name is required');
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/copy/strategies`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify(newStrategy),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Failed to create strategy' }));
        throw new Error(err.error || 'Failed to create strategy');
      }

      success('Strategy created successfully');
      setShowCreateModal(false);
      setNewStrategy({ name: '', strategy_type: 'grid', is_public: false });
      loadData();
    } catch (err: any) {
      showError(err.message);
    }
  };

  const startCopying = async (strategyId: string, allocationPct: number = 100) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/copy/copy`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({ strategy_id: strategyId, allocation_percent: allocationPct }),
      });

      if (!response.ok) {
        const err = await response.json().catch(() => ({ error: 'Failed to start copying' }));
        throw new Error(err.error || 'Failed to start copying');
      }

      success('Started copying strategy');
      loadData();
    } catch (err: any) {
      showError(err.message);
    }
  };

  const stopCopying = async (relationshipId: string) => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/copy/copy/${relationshipId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });

      if (!response.ok) throw new Error('Failed to stop copying');

      success('Stopped copying strategy');
      loadData();
    } catch (err: any) {
      showError(err.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading copy trading...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Copy Trading</h1>
          <p className="text-gray-500 dark:text-gray-400">Discover and copy top-performing strategies</p>
        </div>
        <Button onClick={() => setShowCreateModal(true)} leftIcon={<Plus className="w-4 h-4" />}>
          Create Strategy
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 border-b border-gray-200 dark:border-gray-700">
        {[
          { id: 'leaderboard', label: 'Leaderboard', icon: <Trophy className="w-4 h-4" /> },
          { id: 'my-strategies', label: 'My Strategies', icon: <BarChart3 className="w-4 h-4" /> },
          { id: 'copying', label: 'Currently Copying', icon: <Users className="w-4 h-4" /> },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors ${activeTab === tab.id
              ? 'border-purple-600 text-purple-600 dark:text-purple-400'
              : 'border-transparent text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
              }`}
          >
            {tab.icon}
            {tab.label}
          </button>
        ))}
      </div>

      {/* Leaderboard */}
      {activeTab === 'leaderboard' && (
        leaderboard.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {leaderboard.map((strategy, idx) => (
              <Card key={strategy.strategy_id || idx} variant="elevated" className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 dark:text-white">{strategy.name}</h3>
                    <p className="text-sm text-gray-500 capitalize">{strategy.strategy_type}</p>
                  </div>
                  <Badge variant="success">#{idx + 1}</Badge>
                </div>
                <div className="grid grid-cols-2 gap-3 mb-4">
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Total Return</p>
                    <p className={`text-lg font-bold ${strategy.total_return >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {strategy.total_return >= 0 ? '+' : ''}{strategy.total_return?.toFixed(2)}%
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Win Rate</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{strategy.win_rate?.toFixed(1)}%</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Copiers</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{strategy.total_copiers}</p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-500 dark:text-gray-400">Sharpe</p>
                    <p className="text-lg font-bold text-gray-900 dark:text-white">{strategy.sharpe_ratio?.toFixed(2)}</p>
                  </div>
                </div>
                <Button fullWidth onClick={() => startCopying(strategy.strategy_id)}>
                  Copy Strategy
                </Button>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Trophy className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
            title="No Strategies on Leaderboard"
            description="Strategies will appear here when they have performance data"
          />
        )
      )}

      {/* My Strategies */}
      {activeTab === 'my-strategies' && (
        myStrategies.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {myStrategies.map((strategy) => (
              <Card key={strategy.id} variant="elevated" className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 dark:text-white">{strategy.name}</h3>
                    <p className="text-sm text-gray-500 capitalize">{strategy.strategy_type}</p>
                  </div>
                  <Badge variant={strategy.is_public ? 'success' : 'default'}>
                    {strategy.is_public ? 'Public' : 'Private'}
                  </Badge>
                </div>
                <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">
                  Copiers: {strategy.total_copiers || 0}
                </p>
                {strategy.description && (
                  <p className="text-sm text-gray-600 dark:text-gray-300 mb-4">{strategy.description}</p>
                )}
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<BarChart3 className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
            title="You have no strategies yet"
            description="Create one to share with the community"
            action={{ label: "Create Strategy", onClick: () => setShowCreateModal(true) }}
          />
        )
      )}

      {/* Currently Copying */}
      {activeTab === 'copying' && (
        copying.length > 0 ? (
          <div className="space-y-4">
            {copying.map((rel) => (
              <Card key={rel.id} variant="elevated" className="p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="font-bold text-gray-900 dark:text-white">{rel.strategy_name || 'Strategy'}</h3>
                    <p className="text-sm text-gray-500">Allocation: {rel.allocation_percent}%</p>
                  </div>
                  <Badge variant={rel.is_active ? 'success' : 'default'}>
                    {rel.is_active ? 'Active' : 'Inactive'}
                  </Badge>
                  <Button
                    variant="danger"
                    size="sm"
                    onClick={() => rel.id && stopCopying(rel.id)}
                  >
                    Stop Copying
                  </Button>
                </div>
              </Card>
            ))}
          </div>
        ) : (
          <EmptyState
            icon={<Users className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
            title="You are not copying any strategies yet"
            description="Browse the leaderboard to find strategies to copy"
            action={{ label: "Browse Leaderboard", onClick: () => setActiveTab('leaderboard') }}
          />
        )
      )}

      {/* Create Strategy Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">Create Strategy</h2>
              <button onClick={() => setShowCreateModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Strategy Name</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={newStrategy.name}
                  onChange={(e) => setNewStrategy({ ...newStrategy, name: e.target.value })}
                  placeholder="e.g. My RSI Strategy"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Strategy Type</label>
                <select
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={newStrategy.strategy_type}
                  onChange={(e) => setNewStrategy({ ...newStrategy, strategy_type: e.target.value })}
                >
                  <option value="grid">Grid Trading</option>
                  <option value="rsi">RSI</option>
                  <option value="ema_cross">EMA Cross</option>
                </select>
              </div>
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_public"
                  checked={newStrategy.is_public}
                  onChange={(e) => setNewStrategy({ ...newStrategy, is_public: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <label htmlFor="is_public" className="text-sm text-gray-700 dark:text-gray-300">
                  Make this strategy public (others can copy it)
                </label>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <Button variant="ghost" onClick={() => setShowCreateModal(false)}>Cancel</Button>
              <Button onClick={createStrategy} leftIcon={<Check className="w-4 h-4" />}>Create Strategy</Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
