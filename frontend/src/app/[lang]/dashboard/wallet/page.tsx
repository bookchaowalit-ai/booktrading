/**
 * Wallet Summary Page - Aggregate balances from all exchanges
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { api } from '@/services/api';
import { useToast } from '@/components/ui/Toast';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Wallet, RefreshCw, TrendingUp, DollarSign, Bitcoin, Landmark, ExternalLink } from 'lucide-react';

interface ExchangeBalanceData {
  connected: boolean;
  balances: Array<{ currency: string; free: number; locked: number; total: number }>;
  totalTHB: number;
  totalUSDT: number;
  balanceCount: number;
  error?: string;
}

interface AllBalancesResponse {
  exchanges: Record<string, ExchangeBalanceData>;
  totalTHB: number;
  totalUSDT: number;
  exchangeCount: number;
  cached: boolean;
  timestamp: string;
}

const exchangeNames: Record<string, { name: string; icon: string; color: string }> = {
  binance: { name: 'Binance', icon: '🟡', color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400' },
  binance_th: { name: 'Binance TH', icon: '🇹🇭', color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400' },
  bitkub: { name: 'Bitkub', icon: '🟢', color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400' },
};

export default function WalletPage() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const { success, error: showError } = useToast();
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [data, setData] = useState<AllBalancesResponse | null>(null);

  const loadBalances = useCallback(async (forceRefresh = false) => {
    try {
      let result: AllBalancesResponse;
      if (forceRefresh) {
        setRefreshing(true);
        await api.refreshAllBalances();
      }
      result = await api.getAllBalances();
      setData(result);
    } catch (e) {
      showError('Failed to load balances');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showError]);

  useEffect(() => {
    loadBalances();
  }, [loadBalances]);

  const handleRefresh = async () => {
    await loadBalances(true);
    success('Balances refreshed');
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading wallet balances...</p>
        </div>
      </div>
    );
  }

  if (!data || data.exchangeCount === 0) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Wallet className="w-6 h-6 text-purple-600" />
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">Wallet</h1>
          </div>
        </div>

        <div className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 p-12 text-center">
          <Landmark className="w-16 h-16 text-gray-300 dark:text-gray-600 mx-auto mb-4" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Exchanges Configured</h3>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            Add API keys for your exchanges to see your balances here
          </p>
          <Button
            variant="primary"
            size="md"
            onClick={() => router.push(`/${locale}/dashboard/settings`)}
            leftIcon={<ExternalLink className="w-4 h-4" />}
          >
            Go to Settings
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
            <Wallet className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">Wallet Summary</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Balances from {data.exchangeCount} exchange{data.exchangeCount > 1 ? 's' : ''}
              {data.cached && (
                <span className="ml-2 text-xs text-gray-400">(cached)</span>
              )}
            </p>
          </div>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          isLoading={refreshing}
          leftIcon={<RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />}
        >
          Refresh
        </Button>
      </div>

      {/* Total Balance Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total THB */}
        <div className="bg-gradient-to-br from-green-50 to-green-100 dark:from-green-900/20 dark:to-green-800/20 rounded-xl p-5 border border-green-200 dark:border-green-800">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">🇹🇭</span>
            <span className="text-sm font-medium text-green-700 dark:text-green-400">Total THB</span>
          </div>
          <div className="text-3xl font-bold text-green-800 dark:text-green-300">
            {data.totalTHB.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        {/* Total USDT */}
        <div className="bg-gradient-to-br from-blue-50 to-blue-100 dark:from-blue-900/20 dark:to-blue-800/20 rounded-xl p-5 border border-blue-200 dark:border-blue-800">
          <div className="flex items-center gap-2 mb-2">
            <span className="text-2xl">💵</span>
            <span className="text-sm font-medium text-blue-700 dark:text-blue-400">Total USDT</span>
          </div>
          <div className="text-3xl font-bold text-blue-800 dark:text-blue-300">
            {data.totalUSDT.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
          </div>
        </div>

        {/* Exchanges Count */}
        <div className="bg-gradient-to-br from-purple-50 to-purple-100 dark:from-purple-900/20 dark:to-purple-800/20 rounded-xl p-5 border border-purple-200 dark:border-purple-800">
          <div className="flex items-center gap-2 mb-2">
            <Landmark className="w-5 h-5 text-purple-600 dark:text-purple-400" />
            <span className="text-sm font-medium text-purple-700 dark:text-purple-400">Exchanges</span>
          </div>
          <div className="text-3xl font-bold text-purple-800 dark:text-purple-300">
            {data.exchangeCount}
          </div>
        </div>

        {/* Last Updated */}
        <div className="bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-800/50 dark:to-gray-700/50 rounded-xl p-5 border border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-2 mb-2">
            <RefreshCw className="w-5 h-5 text-gray-500 dark:text-gray-400" />
            <span className="text-sm font-medium text-gray-700 dark:text-gray-400">Last Updated</span>
          </div>
          <div className="text-lg font-bold text-gray-800 dark:text-gray-300">
            {data.timestamp ? new Date(data.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }) : '-'}
          </div>
        </div>
      </div>

      {/* Exchange Balances */}
      <div className="space-y-4">
        {Object.entries(data.exchanges).map(([key, exchange]) => {
          const info = exchangeNames[key] || { name: key, icon: '🔗', color: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-400' };

          return (
            <div key={key} className="bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700 overflow-hidden">
              {/* Exchange Header */}
              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="text-2xl">{info.icon}</span>
                  <div>
                    <h3 className="text-sm font-bold text-gray-900 dark:text-white">{info.name}</h3>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      {exchange.balanceCount} asset{exchange.balanceCount !== 1 ? 's' : ''}
                    </p>
                  </div>
                </div>

                <div className="flex items-center gap-3">
                  {exchange.totalTHB > 0 && (
                    <Badge variant="success">
                      ฿{exchange.totalTHB.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </Badge>
                  )}
                  {exchange.totalUSDT > 0 && (
                    <Badge variant="info">
                      ${exchange.totalUSDT.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                    </Badge>
                  )}
                  <Badge variant={exchange.connected ? 'success' : 'error'}>
                    {exchange.connected ? 'Connected' : 'Error'}
                  </Badge>
                </div>
              </div>

              {/* Balances List */}
              {!exchange.connected ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                  Failed to fetch balances: {exchange.error}
                </div>
              ) : exchange.balances.length === 0 ? (
                <div className="px-4 py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                  No balances found
                </div>
              ) : (
                <div className="divide-y divide-gray-100 dark:divide-gray-700">
                  {exchange.balances
                    .sort((a, b) => b.total - a.total)
                    .map((balance) => (
                      <div key={balance.currency} className="px-4 py-3 flex items-center justify-between hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                        <div className="flex items-center gap-3">
                          <div className="w-10 h-10 rounded-full bg-gray-100 dark:bg-gray-700 flex items-center justify-center text-sm font-bold text-gray-600 dark:text-gray-300">
                            {balance.currency.slice(0, 2)}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-gray-900 dark:text-white">{balance.currency}</p>
                            {balance.locked > 0 && (
                              <p className="text-xs text-gray-500 dark:text-gray-400">
                                +{balance.locked.toLocaleString(undefined, { maximumFractionDigits: 8 })} locked
                              </p>
                            )}
                          </div>
                        </div>

                        <div className="text-right">
                          <p className="text-sm font-mono font-semibold text-gray-900 dark:text-white">
                            {balance.free.toLocaleString(undefined, { maximumFractionDigits: balance.free < 1 ? 8 : 2 })}
                          </p>
                          <p className="text-xs text-gray-500 dark:text-gray-400">free</p>
                        </div>
                      </div>
                    ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
