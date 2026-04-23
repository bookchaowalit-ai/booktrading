/**
 * DEX Trading Page
 * Swap, Liquidity, and Wallet management tabs
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { ArrowLeftRight, Droplets, Wallet, AlertTriangle, RefreshCw } from 'lucide-react';
import { dexApi, type WalletInfo, type ChainInfo } from '@/services/dexApi';
import { useToast } from '@/components/ui/Toast';
import { Tabs } from '@/components/ui';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import DexSwap from '@/components/dex/DexSwap';
import DexLiquidity from '@/components/dex/DexLiquidity';
import DexWallet from '@/components/dex/DexWallet';

const DEFAULT_CHAINS: ChainInfo[] = [
  { id: 'ethereum', name: 'Ethereum', nativeSymbol: 'ETH', blockExplorer: 'https://etherscan.io' },
  { id: 'arbitrum', name: 'Arbitrum', nativeSymbol: 'ETH', blockExplorer: 'https://arbiscan.io' },
  { id: 'base', name: 'Base', nativeSymbol: 'ETH', blockExplorer: 'https://basescan.org' },
  { id: 'bsc', name: 'BSC', nativeSymbol: 'BNB', blockExplorer: 'https://bscscan.com' },
];

export default function DexPage() {
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const { success, error: showError } = useToast();

  // Tabs
  const [activeTab, setActiveTab] = useState<'swap' | 'liquidity' | 'wallet'>('swap');

  // DEX config
  const [dexEnabled, setDexEnabled] = useState<boolean | null>(null);
  const [chains, setChains] = useState<ChainInfo[]>(DEFAULT_CHAINS);
  const [selectedChain, setSelectedChain] = useState('ethereum');
  const [loadingConfig, setLoadingConfig] = useState(true);

  // Wallets
  const [wallets, setWallets] = useState<WalletInfo[]>([]);
  const [loadedWallet, setLoadedWallet] = useState<WalletInfo | null>(null);

  // Fetch DEX config
  useEffect(() => {
    dexApi.getConfig()
      .then((cfg) => {
        setDexEnabled(cfg.enabled);
        if (cfg.supportedChains.length > 0) {
          setChains(cfg.supportedChains);
        }
        if (cfg.defaultChain) {
          setSelectedChain(cfg.defaultChain);
        }
      })
      .catch(() => {
        // If config endpoint doesn't exist, assume DEX is enabled with defaults
        setDexEnabled(true);
      })
      .finally(() => setLoadingConfig(false));
  }, []);

  // Fetch wallets
  const loadWallets = useCallback(async () => {
    try {
      const list = await dexApi.getWallets();
      setWallets(list);
      // Auto-load the first wallet if none loaded
      if (list.length > 0 && !loadedWallet) {
        // Don't auto-load, let user choose
      }
    } catch {
      setWallets([]);
    }
  }, [loadedWallet]);

  useEffect(() => {
    loadWallets();
  }, [loadWallets]);

  const handleWalletLoaded = (wallet: WalletInfo) => {
    setLoadedWallet(wallet);
    loadWallets();
  };

  const tabItems = [
    { id: 'swap', label: 'Swap', icon: <ArrowLeftRight className="w-4 h-4" /> },
    { id: 'liquidity', label: 'Liquidity', icon: <Droplets className="w-4 h-4" /> },
    { id: 'wallet', label: 'Wallet', icon: <Wallet className="w-4 h-4" /> },
  ];

  // Loading state
  if (loadingConfig) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading DEX...</p>
        </div>
      </div>
    );
  }

  // DEX disabled
  if (dexEnabled === false) {
    return (
      <div className="space-y-4">
        <Card variant="elevated" className="p-12 text-center">
          <AlertTriangle className="w-16 h-16 text-yellow-500 mx-auto mb-4" />
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
            DEX Trading is Disabled
          </h2>
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-6">
            DEX trading features are currently disabled. This may be due to configuration (DEX_ENABLED=false) or the feature is not yet deployed.
          </p>
          <Button
            variant="primary"
            size="md"
            onClick={() => router.push(`/${locale}/dashboard`)}
            leftIcon={<ArrowLeftRight className="w-4 h-4" />}
          >
            Back to Dashboard
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="p-2 bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/30 dark:to-blue-900/30 rounded-lg">
            <ArrowLeftRight className="w-5 h-5 text-purple-600" />
          </div>
          <div>
            <h1 className="text-xl font-bold text-gray-900 dark:text-white">DEX Trading</h1>
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Swap tokens, provide liquidity, manage wallets
            </p>
          </div>
        </div>

        <button
          onClick={loadWallets}
          className="p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400"
          title="Refresh"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs */}
      <Tabs tabs={tabItems} activeTab={activeTab} onChange={(id) => setActiveTab(id as typeof activeTab)} />

      {/* Tab Content */}
      <div className="max-w-xl mx-auto">
        {activeTab === 'swap' && (
          <DexSwap
            chains={chains}
            selectedChain={selectedChain}
            wallets={wallets}
            loadedWallet={loadedWallet}
          />
        )}

        {activeTab === 'liquidity' && (
          <DexLiquidity
            wallets={wallets}
            loadedWallet={loadedWallet}
          />
        )}

        {activeTab === 'wallet' && (
          <DexWallet
            chains={chains}
            selectedChain={selectedChain}
            onChainChange={setSelectedChain}
            loadedWallet={loadedWallet}
            onWalletLoaded={handleWalletLoaded}
            onWalletsChange={loadWallets}
          />
        )}
      </div>
    </div>
  );
}
