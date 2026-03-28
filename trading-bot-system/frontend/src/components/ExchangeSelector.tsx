/**
 * Compact Exchange Selector Component
 * Dropdown-style exchange selection with balance display
 */
'use client';

import { useState, useEffect } from 'react';
import { useToast } from '@/components/ui/Toast';
import { Dropdown, Badge, Button, Tooltip } from '@/components/ui';
import { Building2, CheckCircle, AlertCircle, RefreshCw, Wallet } from 'lucide-react';

export interface ExchangeInfo {
  provider: string;
  name: string;
  name_th: string;
  connected: boolean;
  testnet: boolean;
  balances?: ExchangeBalance[];
}

export interface ExchangeBalance {
  currency: string;
  free: number;
  locked: number;
  total: number;
}

interface ExchangeSelectorProps {
  onExchangeChange?: (provider: string) => void;
  compact?: boolean;
}

export default function ExchangeSelector({ onExchangeChange, compact = false }: ExchangeSelectorProps) {
  const { success, error, info } = useToast();

  const [exchanges, setExchanges] = useState<ExchangeInfo[]>([]);
  const [currentProvider, setCurrentProvider] = useState<string>('');
  const [balances, setBalances] = useState<ExchangeBalance[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Load exchanges on mount
  useEffect(() => {
    loadExchanges();
  }, []);

  // Auto-load balances when exchange is connected
  useEffect(() => {
    if (currentProvider) {
      const exchange = exchanges.find(e => e.provider === currentProvider);
      if (exchange?.connected) {
        loadBalances(currentProvider);
      }
    }
  }, [currentProvider, exchanges]);

  const loadExchanges = async () => {
    try {
      const response = await fetch('http://localhost:8080/api/exchange');
      if (response.ok) {
        const data = await response.json();
        setExchanges(data.exchanges || []);
        setCurrentProvider(data.current_provider || '');
      }
    } catch (err) {
      console.error('Failed to load exchanges:', err);
    }
  };

  const loadBalances = async (provider: string) => {
    try {
      const response = await fetch('http://localhost:8080/api/exchange/balances');
      if (response.ok) {
        const data = await response.json();
        setBalances(data.balances || []);
      }
    } catch (err) {
      console.error('Failed to load balances:', err);
    }
  };

  const handleSwitchExchange = async (provider: string) => {
    if (provider === currentProvider) return;

    setIsLoading(true);
    try {
      const response = await fetch('http://localhost:8080/api/exchange/set', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ provider }),
      });

      const data = await response.json();

      if (response.ok) {
        setCurrentProvider(provider);
        success(`Switched to ${provider}`);
        onExchangeChange?.(provider);
        loadBalances(provider);
        loadExchanges();
      } else {
        // Only show error toast, don't show success
        if (data.error?.includes('no API credentials')) {
          error(
            `No API credentials for ${provider}. Add keys in Settings → API Keys`
          );
        } else {
          error(data.error || `Failed to switch to ${provider}`);
        }
      }
    } catch (err) {
      error(`Failed to switch exchange`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRefreshBalances = async () => {
    setIsRefreshing(true);
    await loadBalances(currentProvider);
    setIsRefreshing(false);
    info('Balances refreshed');
  };

  const currentExchange = exchanges.find(e => e.provider === currentProvider);

  // Get exchange options for dropdown
  const exchangeOptions = exchanges.map(ex => ({
    value: ex.provider,
    label: `${ex.name} ${ex.connected ? '✓' : ''}`,
  }));

  if (compact) {
    // Ultra-compact version for tight spaces
    return (
      <div className="flex items-center gap-2">
        <Dropdown
          options={exchangeOptions}
          value={currentProvider}
          onChange={handleSwitchExchange}
          size="sm"
        />
        {currentExchange && (
          <Badge variant={currentExchange.connected ? 'success' : 'default'} size="sm">
            {currentExchange.connected ? 'Connected' : 'Offline'}
          </Badge>
        )}
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Exchange Selection Row */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Building2 className="w-4 h-4 text-gray-500" />
          <span className="text-sm font-medium text-gray-700 dark:text-gray-300">Exchange</span>
        </div>
        <div className="flex items-center gap-2">
          <Dropdown
            options={exchangeOptions}
            value={currentProvider}
            onChange={handleSwitchExchange}
            size="sm"
          />
          {currentExchange && (
            <Tooltip content={currentExchange.testnet ? 'Testnet mode' : 'Live trading'}>
              <Badge
                variant={currentExchange.connected ? 'success' : 'default'}
                size="sm"
              >
                {currentExchange.connected ? 'Connected' : 'Setup Required'}
              </Badge>
            </Tooltip>
          )}
        </div>
      </div>

      {/* Current Exchange Info */}
      {currentExchange && (
        <div className="space-y-2">
          <div className="flex items-center justify-between px-3 py-2 bg-gray-50 dark:bg-gray-800/50 rounded-md">
            <div className="flex items-center gap-2">
              <Wallet className="w-3.5 h-3.5 text-gray-500" />
              <span className="text-xs text-gray-600 dark:text-gray-400">
                {balances.length > 0 ? `${balances.length} asset${balances.length > 1 ? 's' : ''}` : 'No balances'}
              </span>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefreshBalances}
              isLoading={isRefreshing}
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />
            </Button>
          </div>

          {/* Balance List */}
          {balances.length > 0 && (
            <div className="space-y-1 max-h-32 overflow-auto">
              {balances.map((balance) => (
                <div
                  key={balance.currency}
                  className="flex items-center justify-between px-3 py-1.5 bg-white dark:bg-gray-800/50 rounded text-xs"
                >
                  <span className="font-medium text-gray-700 dark:text-gray-300">
                    {balance.currency}
                  </span>
                  <span className="text-gray-900 dark:text-white font-mono">
                    {balance.total.toFixed(6)}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
