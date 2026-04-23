/**
 * DEX Wallet Component
 * Wallet management: create, import, list, load wallets with balance display
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { Wallet, Plus, Download, Key, RefreshCw, Copy, ExternalLink, Trash2, Loader2 } from 'lucide-react';
import { dexApi, type WalletInfo, type BalanceInfo, type ChainInfo, type TokenBalance } from '@/services/dexApi';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';

interface DexWalletProps {
  chains: ChainInfo[];
  selectedChain: string;
  onChainChange: (chain: string) => void;
  loadedWallet: WalletInfo | null;
  onWalletLoaded: (wallet: WalletInfo) => void;
  onWalletsChange: () => void;
}

export default function DexWallet({
  chains,
  selectedChain,
  onChainChange,
  loadedWallet,
  onWalletLoaded,
  onWalletsChange,
}: DexWalletProps) {
  const { success, error: showError } = useToast();

  // Wallets
  const [wallets, setWallets] = useState<WalletInfo[]>([]);
  const [loadingWallets, setLoadingWallets] = useState(false);

  // Create wallet
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [createLabel, setCreateLabel] = useState('');
  const [creating, setCreating] = useState(false);

  // Import wallet
  const [showImportForm, setShowImportForm] = useState(false);
  const [importPrivateKey, setImportPrivateKey] = useState('');
  const [importLabel, setImportLabel] = useState('');
  const [importing, setImporting] = useState(false);

  // Load wallet (decrypt for signing)
  const [loadingWallet, setLoadingWallet] = useState<string | null>(null);

  // Balance
  const [balance, setBalance] = useState<BalanceInfo | null>(null);
  const [loadingBalance, setLoadingBalance] = useState(false);

  // Load wallets list
  useEffect(() => {
    loadWallets();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Load balance when wallet is loaded
  useEffect(() => {
    if (loadedWallet) {
      loadBalance(loadedWallet.address);
    } else {
      setBalance(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedWallet]);

  const loadWallets = useCallback(async () => {
    setLoadingWallets(true);
    try {
      const list = await dexApi.getWallets();
      setWallets(list);
    } catch {
      setWallets([]);
    } finally {
      setLoadingWallets(false);
    }
  }, []);

  const loadBalance = useCallback(async (address: string) => {
    setLoadingBalance(true);
    try {
      const b = await dexApi.getBalance(address);
      setBalance(b);
    } catch {
      setBalance(null);
    } finally {
      setLoadingBalance(false);
    }
  }, []);

  const handleCreateWallet = useCallback(async () => {
    setCreating(true);
    try {
      const wallet = await dexApi.createWallet({
        chain: selectedChain,
        label: createLabel || undefined,
      });
      success(`Wallet created: ${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`);
      setCreateLabel('');
      setShowCreateForm(false);
      loadWallets();
      onWalletsChange();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to create wallet';
      showError(msg);
    } finally {
      setCreating(false);
    }
  }, [selectedChain, createLabel, success, showError, loadWallets, onWalletsChange]);

  const handleImportWallet = useCallback(async () => {
    if (!importPrivateKey) return;
    setImporting(true);
    try {
      const wallet = await dexApi.importWallet({
        chain: selectedChain,
        privateKey: importPrivateKey,
        label: importLabel || undefined,
      });
      success(`Wallet imported: ${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`);
      setImportPrivateKey('');
      setImportLabel('');
      setShowImportForm(false);
      loadWallets();
      onWalletsChange();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to import wallet';
      showError(msg);
    } finally {
      setImporting(false);
    }
  }, [selectedChain, importPrivateKey, importLabel, success, showError, loadWallets, onWalletsChange]);

  const handleLoadWallet = useCallback(async (wallet: WalletInfo) => {
    setLoadingWallet(wallet.id);
    try {
      await dexApi.loadWallet(wallet.id);
      success(`Wallet loaded: ${wallet.address.slice(0, 6)}...${wallet.address.slice(-4)}`);
      onWalletLoaded(wallet);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load wallet';
      showError(msg);
    } finally {
      setLoadingWallet(null);
    }
  }, [onWalletLoaded, success, showError]);

  const handleCopyAddress = (address: string) => {
    navigator.clipboard.writeText(address).then(() => {
      success('Address copied to clipboard');
    });
  };

  const chain = chains.find((c) => c.id === selectedChain);

  const formatBalance = (val: string, decimals: number = 18): string => {
    const num = parseFloat(val);
    if (isNaN(num)) return '0';
    if (num < 0.000001) return num.toExponential(4);
    if (num < 1) return num.toFixed(6);
    if (num < 1000) return num.toFixed(4);
    return num.toLocaleString(undefined, { maximumFractionDigits: 2 });
  };

  return (
    <div className="space-y-4">
      {/* Chain Selector */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Wallet className="w-5 h-5 text-purple-600" />
            DEX Wallet
          </h3>
          <select
            value={selectedChain}
            onChange={(e) => onChainChange(e.target.value)}
            className="px-3 py-1.5 text-sm bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            {chains.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
      </Card>

      {/* Create / Import Wallet */}
      <div className="flex gap-2">
        <Button
          variant="primary"
          size="sm"
          onClick={() => { setShowCreateForm(!showCreateForm); setShowImportForm(false); }}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Create Wallet
        </Button>
        <Button
          variant="secondary"
          size="sm"
          onClick={() => { setShowImportForm(!showImportForm); setShowCreateForm(false); }}
          leftIcon={<Download className="w-4 h-4" />}
        >
          Import Wallet
        </Button>
      </div>

      {/* Create Form */}
      {showCreateForm && (
        <Card variant="elevated" className="p-4">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <Plus className="w-4 h-4" />
            Create New Wallet
          </h4>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Label (optional)
              </label>
              <input
                type="text"
                placeholder="My Wallet"
                value={createLabel}
                onChange={(e) => setCreateLabel(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Chain: {chain?.name} ({chain?.nativeSymbol})
            </div>
            <Button
              variant="success"
              size="sm"
              fullWidth
              onClick={handleCreateWallet}
              isLoading={creating}
            >
              Generate Keypair
            </Button>
          </div>
        </Card>
      )}

      {/* Import Form */}
      {showImportForm && (
        <Card variant="elevated" className="p-4">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
            <Key className="w-4 h-4" />
            Import Wallet by Private Key
          </h4>
          <div className="space-y-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Private Key (hex)
              </label>
              <input
                type="password"
                placeholder="0x..."
                value={importPrivateKey}
                onChange={(e) => setImportPrivateKey(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500 font-mono"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Label (optional)
              </label>
              <input
                type="text"
                placeholder="Imported Wallet"
                value={importLabel}
                onChange={(e) => setImportLabel(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <Button
              variant="warning"
              size="sm"
              fullWidth
              onClick={handleImportWallet}
              isLoading={importing}
            >
              Import
            </Button>
          </div>
        </Card>
      )}

      {/* Loaded Wallet Balance */}
      {loadedWallet && balance && (
        <Card variant="elevated" className="p-4">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
              Loaded Wallet
            </h4>
            <Badge variant="success">Active</Badge>
          </div>

          <div className="flex items-center gap-2 mb-4">
            <span className="text-xs font-mono text-gray-500 dark:text-gray-400 break-all">
              {loadedWallet.address}
            </span>
            <button
              onClick={() => handleCopyAddress(loadedWallet.address)}
              className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400"
            >
              <Copy className="w-3 h-3" />
            </button>
            {chain?.blockExplorer && (
              <a
                href={`${chain.blockExplorer}/address/${loadedWallet.address}`}
                target="_blank"
                rel="noopener noreferrer"
                className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400"
              >
                <ExternalLink className="w-3 h-3" />
              </a>
            )}
          </div>

          {loadingBalance ? (
            <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
              <Loader2 className="w-4 h-4 animate-spin" />
              Loading balances...
            </div>
          ) : (
            <div className="space-y-2">
              {/* Native Balance */}
              <div className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <span className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  {chain?.nativeSymbol || 'Native'}
                </span>
                <span className="text-sm font-mono font-bold text-gray-900 dark:text-white">
                  {formatBalance(balance.nativeBalance)}
                </span>
              </div>

              {/* Token Balances */}
              {balance.tokens.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Tokens</div>
                  <div className="space-y-1">
                    {balance.tokens
                      .filter((t) => parseFloat(t.balance) > 0)
                      .map((t) => (
                        <div
                          key={t.address}
                          className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            <span className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/50 dark:to-blue-900/50 flex items-center justify-center text-xs font-bold text-purple-600 dark:text-purple-400">
                              {t.symbol.slice(0, 2)}
                            </span>
                            <span className="text-sm text-gray-700 dark:text-gray-300">{t.symbol}</span>
                          </div>
                          <span className="text-sm font-mono text-gray-900 dark:text-white">
                            {formatBalance(t.balance, t.decimals)}
                          </span>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {balance.tokens.filter((t) => parseFloat(t.balance) > 0).length === 0 && (
                <div className="text-xs text-gray-400 dark:text-gray-500 text-center py-2">
                  No token balances
                </div>
              )}
            </div>
          )}
        </Card>
      )}

      {/* Wallet List */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-3">
          <h4 className="text-sm font-semibold text-gray-900 dark:text-white">
            Wallets ({wallets.length})
          </h4>
          <button
            onClick={loadWallets}
            className="p-1 rounded hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-400"
          >
            <RefreshCw className="w-3 h-3" />
          </button>
        </div>

        {loadingWallets ? (
          <div className="py-4 text-center text-sm text-gray-500 dark:text-gray-400">
            Loading wallets...
          </div>
        ) : wallets.length === 0 ? (
          <div className="py-8 text-center">
            <Wallet className="w-10 h-10 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">No wallets yet</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Create or import a wallet to get started</p>
          </div>
        ) : (
          <div className="space-y-2">
            {wallets.map((w) => {
              const isLoaded = loadedWallet?.id === w.id;
              const isLoading = loadingWallet === w.id;

              return (
                <div
                  key={w.id}
                  className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${
                    isLoaded
                      ? 'border-green-300 dark:border-green-700 bg-green-50 dark:bg-green-900/10'
                      : 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30'
                  }`}
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/50 dark:to-blue-900/50 flex items-center justify-center text-xs font-bold text-purple-600 dark:text-purple-400 flex-shrink-0">
                      {w.label ? w.label.slice(0, 2).toUpperCase() : w.address.slice(0, 2).toUpperCase()}
                    </div>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-900 dark:text-white truncate">
                        {w.label || 'Wallet'}
                      </div>
                      <div className="text-xs font-mono text-gray-500 dark:text-gray-400">
                        {w.address.slice(0, 6)}...{w.address.slice(-4)}
                      </div>
                    </div>
                  </div>

                  <div className="flex items-center gap-2 flex-shrink-0">
                    {w.chain && (
                      <Badge variant="info" className="text-[10px]">{w.chain}</Badge>
                    )}
                    {isLoaded ? (
                      <Badge variant="success" className="text-[10px]">Loaded</Badge>
                    ) : (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleLoadWallet(w)}
                        isLoading={isLoading}
                        disabled={isLoading}
                      >
                        Load
                      </Button>
                    )}
                    <button
                      onClick={() => handleCopyAddress(w.address)}
                      className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>
    </div>
  );
}
