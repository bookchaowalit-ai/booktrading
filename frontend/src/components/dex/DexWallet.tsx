/**
 * DEX Wallet Component
 * Wallet management: create, import, list, load wallets with balance display
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { Wallet, Plus, Download, Key, RefreshCw, Copy, ExternalLink, Trash2, Loader2, Eye, EyeOff, AlertTriangle, X } from 'lucide-react';
import { dexApi, type WalletInfo, type BalanceInfo, type ChainInfo, type TokenBalance } from '@/services/dexApi';
import { fetchTokenPrices, getTokenPrice, formatUSD } from '@/services/tokenPrices';
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

  // Export wallet
  const [exportingWallet, setExportingWallet] = useState<string | null>(null);
  const [exportedKey, setExportedKey] = useState<string | null>(null);
  const [showExportedKey, setShowExportedKey] = useState(false);

  // Import warning acknowledgment
  const [importWarningAcknowledged, setImportWarningAcknowledged] = useState(false);

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
      fetchTokenPrices();
    } else {
      setBalance(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedWallet]);

  // Refresh prices every 30 seconds
  useEffect(() => {
    const timer = setInterval(() => fetchTokenPrices(), 30_000);
    return () => clearInterval(timer);
  }, []);

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

  const handleExportWallet = useCallback(async (wallet: WalletInfo) => {
    setExportingWallet(wallet.id);
    try {
      const result = await dexApi.exportWallet(wallet.id);
      setExportedKey(result.privateKey);
      setShowExportedKey(false);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to export wallet';
      showError(msg);
    } finally {
      setExportingWallet(null);
    }
  }, [success, showError]);

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

          {/* Security Warning */}
          {!importWarningAcknowledged ? (
            <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg space-y-3">
              <div className="flex items-start gap-2">
                <AlertTriangle className="w-5 h-5 text-red-500 flex-shrink-0 mt-0.5" />
                <div className="space-y-2">
                  <p className="text-sm font-semibold text-red-700 dark:text-red-400">
                    Security Warning
                  </p>
                  <ul className="text-xs text-red-600 dark:text-red-400 space-y-1 list-disc list-inside">
                    <li>Never share your private key with anyone</li>
                    <li>Anyone with your private key can steal your funds</li>
                    <li>Make sure you are on the correct website URL</li>
                    <li>Bookmark this page to avoid phishing sites</li>
                  </ul>
                </div>
              </div>
              <Button
                variant="danger"
                size="sm"
                fullWidth
                onClick={() => setImportWarningAcknowledged(true)}
              >
                I Understand the Risks
              </Button>
            </div>
          ) : (
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
          )}
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
                <div className="text-right">
                  <span className="text-sm font-mono font-bold text-gray-900 dark:text-white">
                    {formatBalance(balance.native_balance)}
                  </span>
                  {(() => {
                    const price = getTokenPrice('NATIVE');
                    const usd = formatUSD(parseFloat(balance.native_balance), price);
                    return usd ? (
                      <div className="text-xs text-gray-400 dark:text-gray-500">{usd}</div>
                    ) : null;
                  })()}
                </div>
              </div>

              {/* Token Balances */}
              {Object.keys(balance.token_balances).length > 0 && (
                <div>
                  <div className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Tokens</div>
                  <div className="space-y-1">
                    {Object.entries(balance.token_balances)
                      .filter(([, bal]) => parseFloat(bal) > 0)
                      .map(([addr, bal]) => (
                        <div
                          key={addr}
                          className="flex items-center justify-between p-2 bg-gray-50 dark:bg-gray-700/50 rounded-lg"
                        >
                          <div className="flex items-center gap-2">
                            <span className="w-6 h-6 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/50 dark:to-blue-900/50 flex items-center justify-center text-xs font-bold text-purple-600 dark:text-purple-400">
                              {addr.slice(0, 2)}
                            </span>
                            <span className="text-sm text-gray-700 dark:text-gray-300">{addr}</span>
                          </div>
                          <div className="text-right">
                            <span className="text-sm font-mono text-gray-900 dark:text-white">
                              {formatBalance(bal)}
                            </span>
                          </div>
                        </div>
                      ))}
                  </div>
                </div>
              )}

              {Object.keys(balance.token_balances).filter((k) => parseFloat(balance.token_balances[k]) > 0).length === 0 && (
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
                  className={`flex items-center justify-between p-3 rounded-lg border transition-colors ${isLoaded
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

                  <div className="flex items-center gap-1 flex-shrink-0">
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
                      title="Copy Address"
                    >
                      <Copy className="w-3 h-3" />
                    </button>
                    <button
                      onClick={() => handleExportWallet(w)}
                      className="p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400"
                      title="Export Private Key"
                    >
                      {exportingWallet === w.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Eye className="w-3 h-3" />}
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </Card>

      {/* Export Key Modal */}
      {exportedKey && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
          onClick={() => { setExportedKey(null); setShowExportedKey(false); }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Card variant="elevated" className="w-full sm:max-w-sm p-5 rounded-t-xl sm:rounded-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                  <Key className="w-5 h-5 text-yellow-500" />
                  Private Key
                </h3>
                <button
                  onClick={() => { setExportedKey(null); setShowExportedKey(false); }}
                  className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              <div className="p-3 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg mb-4">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                  <p className="text-xs text-red-600 dark:text-red-400">
                    Never share your private key. Anyone with this key has full control of your funds.
                  </p>
                </div>
              </div>

              <div className="relative mb-4">
                <div className="w-full p-3 bg-gray-50 dark:bg-gray-700 rounded-lg font-mono text-xs text-gray-900 dark:text-white break-all">
                  {showExportedKey ? exportedKey : '••••••••••••••••••••••••••••••••••••••••••••••••••••'}
                </div>
                <button
                  onClick={() => setShowExportedKey(!showExportedKey)}
                  className="absolute right-2 top-2 p-1 rounded hover:bg-gray-200 dark:hover:bg-gray-600 text-gray-400"
                >
                  {showExportedKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>

              <div className="flex gap-2">
                <Button
                  variant="primary"
                  size="sm"
                  className="flex-1"
                  onClick={() => {
                    navigator.clipboard.writeText(exportedKey);
                    success('Private key copied to clipboard');
                  }}
                >
                  Copy Key
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => { setExportedKey(null); setShowExportedKey(false); }}
                >
                  Close
                </Button>
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
