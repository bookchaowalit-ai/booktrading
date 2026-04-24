/**
 * DEX Swap Component — Improved
 * Max button, approval flow, swap confirmation modal, swap history, token icons
 */
'use client';

import { useState, useCallback, useEffect, useRef } from 'react';
import {
  ArrowDown, Settings, Search, X, Info, Zap, Copy, Check,
  ExternalLink, Clock, Shield, AlertTriangle, Loader2,
} from 'lucide-react';
import { dexApi, type QuoteResponse, type TokenBalance, type WalletInfo, type ChainInfo } from '@/services/dexApi';
import { fetchTokenPrices, getTokenPrice, formatUSD } from '@/services/tokenPrices';
import { useToast } from '@/components/ui/Toast';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';
import { TokenIcon } from '@/utils/tokenIcons';

// ── Common tokens ──────────────────────────────────────────────────────────────
interface TokenDef {
  symbol: string;
  name: string;
  address: string;
  decimals: number;
}

const COMMON_TOKENS: TokenDef[] = [
  { symbol: 'ETH', name: 'Ethereum', address: 'NATIVE', decimals: 18 },
  { symbol: 'USDC', name: 'USD Coin', address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', decimals: 6 },
  { symbol: 'USDT', name: 'Tether', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', decimals: 6 },
  { symbol: 'WBTC', name: 'Wrapped Bitcoin', address: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', decimals: 8 },
  { symbol: 'DAI', name: 'Dai', address: '0x6B175474E89094C44Da98b954EedeAC495271d0F', decimals: 18 },
];

const SLIPPAGE_PRESETS = [0.1, 0.5, 1.0];

// ── Swap history stored in localStorage ────────────────────────────────────────
interface SwapRecord {
  txHash: string;
  tokenIn: string;
  tokenOut: string;
  amountIn: string;
  amountOut: string;
  dexProvider: string;
  timestamp: string;
  status: 'pending' | 'confirmed' | 'failed';
}

const SWAP_HISTORY_KEY = 'dex_swap_history';

function loadSwapHistory(): SwapRecord[] {
  try {
    const raw = localStorage.getItem(SWAP_HISTORY_KEY);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveSwapHistory(record: SwapRecord) {
  try {
    const history = loadSwapHistory();
    // Update existing record with same txHash, or prepend new one
    const existingIdx = history.findIndex((h) => h.txHash === record.txHash);
    if (existingIdx >= 0) {
      history[existingIdx] = record;
    } else {
      history.unshift(record);
    }
    localStorage.setItem(SWAP_HISTORY_KEY, JSON.stringify(history.slice(0, 20)));
  } catch { /* ignore */ }
}

function updateSwapStatus(txHash: string, status: 'pending' | 'confirmed' | 'failed') {
  try {
    const history = loadSwapHistory();
    const idx = history.findIndex((h) => h.txHash === txHash);
    if (idx >= 0) {
      history[idx].status = status;
      localStorage.setItem(SWAP_HISTORY_KEY, JSON.stringify(history));
    }
  } catch { /* ignore */ }
}

// ── Helpers ────────────────────────────────────────────────────────────────────
function formatNumber(val: string | number, decimals = 6): string {
  const num = typeof val === 'string' ? parseFloat(val) : val;
  if (isNaN(num)) return '0';
  if (num < 0.000001) return num.toExponential(4);
  if (num < 1) return num.toFixed(6);
  if (num < 1000) return num.toFixed(4);
  return num.toLocaleString(undefined, { maximumFractionDigits: decimals });
}

// ── Component ──────────────────────────────────────────────────────────────────
interface DexSwapProps {
  chains: ChainInfo[];
  selectedChain: string;
  wallets: WalletInfo[];
  loadedWallet: WalletInfo | null;
}

export default function DexSwap({ chains, selectedChain, wallets, loadedWallet }: DexSwapProps) {
  const { success, error: showError } = useToast();

  // Token selection
  const [tokenIn, setTokenIn] = useState<TokenBalance | null>(null);
  const [tokenOut, setTokenOut] = useState<TokenBalance | null>(null);
  const [amountIn, setAmountIn] = useState('');
  const [showTokenSelector, setShowTokenSelector] = useState<'in' | 'out' | null>(null);
  const [tokenSearch, setTokenSearch] = useState('');

  // Custom token import
  const [customTokenAddress, setCustomTokenAddress] = useState('');
  const [importingToken, setImportingToken] = useState(false);
  const [customTokens, setCustomTokens] = useState<TokenDef[]>([]);

  // Settings
  const [slippage, setSlippage] = useState(0.5);
  const [customSlippage, setCustomSlippage] = useState('');
  const [bestRoute, setBestRoute] = useState(true);
  const [showSettings, setShowSettings] = useState(false);

  // State
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const [approving, setApproving] = useState(false);
  const [balances, setBalances] = useState<TokenBalance[]>([]);
  const [approved, setApproved] = useState(true); // native tokens don't need approval
  const [showConfirmModal, setShowConfirmModal] = useState(false);
  const [copiedAddress, setCopiedAddress] = useState<string | null>(null);

  // Swap history
  const [swapHistory, setSwapHistory] = useState<SwapRecord[]>([]);
  const [showHistory, setShowHistory] = useState(false);

  // Polling refs for pending transactions
  const pollingTimersRef = useRef<Map<string, NodeJS.Timeout>>(new Map());

  // Fetch balances when wallet is loaded
  useEffect(() => {
    if (loadedWallet) {
      dexApi.getBalance(loadedWallet.address)
        .then((b) => {
          const tokens: TokenBalance[] = [{
            symbol: b.native_symbol || 'ETH',
            address: 'NATIVE',
            balance: b.native_balance || '0',
            decimals: 18,
          }];
          if (b.token_balances) {
            for (const [addr, bal] of Object.entries(b.token_balances)) {
              tokens.push({
                symbol: addr,
                address: addr,
                balance: typeof bal === 'string' ? bal : String(bal),
                decimals: 18,
              });
            }
          }
          setBalances(tokens);
          fetchTokenPrices();
        })
        .catch(() => setBalances([]));
    } else {
      setBalances([]);
    }
  }, [loadedWallet]);

  // Refresh prices every 30 seconds
  useEffect(() => {
    const timer = setInterval(() => fetchTokenPrices(), 30_000);
    return () => clearInterval(timer);
  }, []);

  // Load swap history
  useEffect(() => {
    setSwapHistory(loadSwapHistory());
  }, []);

  // Cleanup polling timers on unmount
  useEffect(() => {
    return () => {
      pollingTimersRef.current.forEach((timer) => clearInterval(timer));
      pollingTimersRef.current.clear();
    };
  }, []);

  // Poll transaction status
  const pollTxStatus = useCallback((txHash: string) => {
    const startTime = Date.now();
    const POLL_INTERVAL = 3000; // 3 seconds
    const POLL_TIMEOUT = 60000; // 60 seconds

    const timer = setInterval(async () => {
      // Stop polling after timeout
      if (Date.now() - startTime > POLL_TIMEOUT) {
        clearInterval(timer);
        pollingTimersRef.current.delete(txHash);
        return;
      }

      try {
        const result = await dexApi.getTransactionStatus(txHash);
        if (result.status === 'pending') {
          updateSwapStatus(txHash, 'pending');
          setSwapHistory([...loadSwapHistory()]);
          return; // continue polling
        }

        // Confirmed or failed — stop polling
        clearInterval(timer);
        pollingTimersRef.current.delete(txHash);
        updateSwapStatus(txHash, result.status);
        setSwapHistory([...loadSwapHistory()]);

        if (result.status === 'confirmed') {
          success(`Transaction confirmed on-chain`);
        } else {
          showError(`Transaction failed on-chain`);
        }
      } catch {
        // RPC error — keep polling
      }
    }, POLL_INTERVAL);

    pollingTimersRef.current.set(txHash, timer);
  }, [success, showError]);

  // Fetch quote when amount changes
  useEffect(() => {
    if (!tokenIn || !tokenOut || !amountIn || parseFloat(amountIn) <= 0) {
      setQuote(null);
      return;
    }
    const timer = setTimeout(() => fetchQuote(), 500);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tokenIn, tokenOut, amountIn, slippage, bestRoute]);

  const fetchQuote = useCallback(async () => {
    if (!tokenIn || !tokenOut || !amountIn) return;
    setLoading(true);
    try {
      const q = await dexApi.getQuote({
        tokenIn: tokenIn.address,
        tokenOut: tokenOut.address,
        amountIn,
        slippage,
        bestRoute,
      });
      setQuote(q);
      setApproved(tokenIn.address === 'NATIVE'); // native doesn't need approval
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to get quote';
      showError(msg);
      setQuote(null);
    } finally {
      setLoading(false);
    }
  }, [tokenIn, tokenOut, amountIn, slippage, bestRoute, showError]);

  const handleApprove = useCallback(async () => {
    if (!loadedWallet || !tokenIn || !amountIn) return;
    setApproving(true);
    try {
      // Call approve endpoint — in production this sends an approve tx to the token contract
      await dexApi.approveToken({
        walletId: loadedWallet.id,
        tokenAddress: tokenIn.address,
        amount: amountIn,
      });
      setApproved(true);
      success(`Approved ${tokenIn.symbol} for trading`);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Approval failed';
      showError(msg);
    } finally {
      setApproving(false);
    }
  }, [loadedWallet, tokenIn, amountIn, success, showError]);

  const handleSwap = useCallback(async () => {
    if (!loadedWallet || !tokenIn || !tokenOut || !amountIn || !quote) return;
    setShowConfirmModal(false);
    setSwapping(true);
    try {
      const result = await dexApi.swap({
        walletId: loadedWallet.id,
        tokenIn: tokenIn.address,
        tokenOut: tokenOut.address,
        amountIn,
        slippage,
        bestRoute,
      });
      // Save to history with pending status — polling will update it
      const record: SwapRecord = {
        txHash: result.tx_hash,
        tokenIn: tokenIn.symbol,
        tokenOut: tokenOut.symbol,
        amountIn,
        amountOut: result.amount_out || quote.amount_out,
        dexProvider: result.dex_provider || quote.dex_provider,
        timestamp: new Date().toISOString(),
        status: 'pending',
      };
      saveSwapHistory(record);
      setSwapHistory(loadSwapHistory());
      success(`Swap submitted! TX: ${result.tx_hash.slice(0, 10)}...`);
      // Start polling for on-chain status
      pollTxStatus(result.tx_hash);
      setAmountIn('');
      setQuote(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Swap failed';
      showError(msg);
    } finally {
      setSwapping(false);
    }
  }, [loadedWallet, tokenIn, tokenOut, amountIn, quote, slippage, bestRoute, success, showError, pollTxStatus]);

  const handleSwitchTokens = () => {
    setTokenIn(tokenOut);
    setTokenOut(tokenIn);
    if (quote) setAmountIn(quote.amount_out);
    setQuote(null);
  };

  const handleSelectToken = (token: TokenDef) => {
    const tb: TokenBalance = {
      symbol: token.symbol,
      address: token.address,
      balance: '0',
      decimals: token.decimals,
    };
    if (showTokenSelector === 'in') {
      if (tokenOut?.address === token.address) setTokenOut(null);
      setTokenIn(tb);
      setApproved(token.address === 'NATIVE');
    } else {
      if (tokenIn?.address === token.address) setTokenIn(null);
      setTokenOut(tb);
    }
    setShowTokenSelector(null);
    setTokenSearch('');
  };

  const isValidAddress = (addr: string): boolean => {
    return /^0x[a-fA-F0-9]{40}$/.test(addr);
  };

  const handleImportCustomToken = async () => {
    const addr = customTokenAddress.trim();
    if (!isValidAddress(addr)) return;
    setImportingToken(true);
    try {
      const info = await dexApi.getTokenInfo(addr);
      const token: TokenDef = {
        symbol: info.symbol,
        name: info.name,
        address: info.address,
        decimals: info.decimals,
      };
      setCustomTokens((prev) => {
        if (prev.some((t) => t.address.toLowerCase() === addr.toLowerCase())) return prev;
        return [token, ...prev];
      });
      setCustomTokenAddress('');
      success(`Imported ${info.symbol}`);
    } catch {
      // Fallback: add as Unknown token
      const token: TokenDef = {
        symbol: 'Unknown',
        name: 'Unknown Token',
        address: addr,
        decimals: 18,
      };
      setCustomTokens((prev) => {
        if (prev.some((t) => t.address.toLowerCase() === addr.toLowerCase())) return prev;
        return [token, ...prev];
      });
      setCustomTokenAddress('');
      showError('Could not fetch token info — added as Unknown');
    } finally {
      setImportingToken(false);
    }
  };

  const handleSetMax = () => {
    if (!tokenIn) return;
    const bal = balances.find((b) => b.address === tokenIn.address);
    if (bal && parseFloat(bal.balance) > 0) {
      setAmountIn(bal.balance);
    }
  };

  const handleSetSlippage = (val: number) => {
    setSlippage(val);
    setCustomSlippage('');
  };

  const handleCustomSlippage = (val: string) => {
    setCustomSlippage(val);
    const num = parseFloat(val);
    if (!isNaN(num) && num > 0 && num < 50) setSlippage(num);
  };

  const handleCopyAddress = (address: string) => {
    navigator.clipboard.writeText(address);
    setCopiedAddress(address);
    setTimeout(() => setCopiedAddress(null), 2000);
    success('Address copied');
  };

  const allTokens = [...COMMON_TOKENS, ...customTokens];
  const filteredTokens = allTokens.filter(
    (t) =>
      t.symbol.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.name.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.address.toLowerCase().includes(tokenSearch.toLowerCase())
  );

  const tokenInBalance = balances.find((b) => b.address === tokenIn?.address);
  const chain = chains.find((c) => c.id === selectedChain);
  const isSwapDisabled = !loadedWallet || !tokenIn || !tokenOut || !amountIn || parseFloat(amountIn) <= 0 || !quote;
  const needsApproval = !approved && tokenIn?.address !== 'NATIVE';

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Chain & Wallet Status */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <span className="text-sm text-gray-500 dark:text-gray-400">Chain:</span>
          <span className="px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded">
            {chain?.name || selectedChain}
          </span>
        </div>
        <div className="flex items-center gap-2">
          {loadedWallet ? (
            <>
              <span className="w-2 h-2 bg-green-500 rounded-full" />
              <span
                className="text-xs text-gray-500 dark:text-gray-400 font-mono cursor-pointer hover:text-purple-500"
                onClick={() => handleCopyAddress(loadedWallet.address)}
              >
                {loadedWallet.address.slice(0, 6)}...{loadedWallet.address.slice(-4)}
              </span>
              {chain?.blockExplorer && (
                <a
                  href={`${chain.blockExplorer}/address/${loadedWallet.address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-gray-400 hover:text-purple-500 transition-colors"
                >
                  <ExternalLink className="w-3 h-3" />
                </a>
              )}
            </>
          ) : (
            <>
              <span className="w-2 h-2 bg-red-500 rounded-full" />
              <span className="text-xs text-gray-500 dark:text-gray-400">No wallet loaded</span>
            </>
          )}
        </div>
      </div>

      {/* Swap Card */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Swap</h3>
          <div className="flex items-center gap-1">
            <button
              onClick={() => setShowHistory(!showHistory)}
              className={`p-1.5 rounded-lg transition-colors ${showHistory ? 'bg-purple-100 dark:bg-purple-900/30 text-purple-600' : 'hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500'}`}
              title="Swap History"
            >
              <Clock className="w-4 h-4" />
            </button>
            <button
              onClick={() => setShowSettings(!showSettings)}
              className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
            >
              <Settings className="w-4 h-4" />
            </button>
          </div>
        </div>

        {/* Settings Panel */}
        {showSettings && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg space-y-3">
            <div>
              <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2 block">
                Slippage Tolerance
              </label>
              <div className="flex gap-2">
                {SLIPPAGE_PRESETS.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleSetSlippage(s)}
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${slippage === s && !customSlippage
                      ? 'bg-purple-600 text-white'
                      : 'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-500'
                      }`}
                  >
                    {s}%
                  </button>
                ))}
                <input
                  type="text"
                  placeholder="Custom"
                  value={customSlippage}
                  onChange={(e) => handleCustomSlippage(e.target.value)}
                  className="w-20 px-2 py-1 text-xs bg-white dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-md text-gray-900 dark:text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                />
              </div>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-xs text-gray-500 dark:text-gray-400">
                <Zap className="w-3 h-3" />
                Best Route
              </div>
              <button
                onClick={() => setBestRoute(!bestRoute)}
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${bestRoute ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'
                  }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${bestRoute ? 'translate-x-5' : 'translate-x-1'
                    }`}
                />
              </button>
            </div>
          </div>
        )}

        {/* Swap History Panel */}
        {showHistory && (
          <div className="mb-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
            <h4 className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-2">Recent Swaps</h4>
            {swapHistory.length === 0 ? (
              <p className="text-xs text-gray-400 dark:text-gray-500">No recent swaps</p>
            ) : (
              <div className="space-y-2 max-h-40 overflow-y-auto">
                {swapHistory.slice(0, 5).map((s, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <div className="flex items-center gap-2">
                      {/* Status indicator */}
                      {s.status === 'pending' && (
                        <span className="flex items-center gap-1">
                          <span className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse" />
                          <Loader2 className="w-3 h-3 text-yellow-400 animate-spin" />
                        </span>
                      )}
                      {s.status === 'confirmed' && (
                        <Check className="w-3.5 h-3.5 text-green-500" />
                      )}
                      {s.status === 'failed' && (
                        <X className="w-3.5 h-3.5 text-red-500" />
                      )}
                      <div>
                        <span className="text-gray-900 dark:text-white font-medium">
                          {s.tokenIn} → {s.tokenOut}
                        </span>
                        <span className="text-gray-500 dark:text-gray-400 ml-2">
                          {s.amountIn}
                        </span>
                      </div>
                    </div>
                    <span className="text-gray-400">{s.dexProvider}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Token In */}
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 dark:text-gray-400">You pay</span>
            {tokenIn && tokenInBalance && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  Balance: {formatNumber(tokenInBalance.balance, 4)}
                </span>
                {(() => {
                  const price = getTokenPrice(tokenInBalance.address);
                  const usd = formatUSD(parseFloat(tokenInBalance.balance), price);
                  return usd ? (
                    <span className="text-xs text-gray-400 dark:text-gray-500">({usd})</span>
                  ) : null;
                })()}
                <button
                  onClick={handleSetMax}
                  className="px-2 py-0.5 text-xs font-medium bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 rounded hover:bg-purple-200 dark:hover:bg-purple-900/50 transition-colors"
                >
                  Max
                </button>
              </div>
            )}
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              inputMode="decimal"
              placeholder="0.0"
              value={amountIn}
              onChange={(e) => {
                const val = e.target.value;
                if (val === '' || /^\d*\.?\d*$/.test(val)) setAmountIn(val);
              }}
              className="flex-1 bg-transparent text-2xl font-semibold text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none"
            />
            <button
              onClick={() => setShowTokenSelector('in')}
              className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-600 rounded-full border border-gray-200 dark:border-gray-500 hover:border-purple-400 dark:hover:border-purple-500 transition-colors"
            >
              {tokenIn ? (
                <>
                  <TokenIcon symbol={tokenIn.symbol} size={24} />
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{tokenIn.symbol}</span>
                </>
              ) : (
                <span className="text-sm text-gray-500 dark:text-gray-400">Select</span>
              )}
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Switch Button */}
        <div className="flex justify-center -my-2 relative z-10">
          <button
            onClick={handleSwitchTokens}
            className="p-2 bg-white dark:bg-gray-600 rounded-xl border-4 border-gray-50 dark:border-gray-800 hover:border-purple-200 dark:hover:border-purple-800 transition-colors"
          >
            <ArrowDown className="w-4 h-4 text-gray-500 dark:text-gray-400" />
          </button>
        </div>

        {/* Token Out */}
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 dark:text-gray-400">You receive</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="0.0"
              value={quote?.amount_out ?? (loading ? '...' : '')}
              readOnly
              className="flex-1 bg-transparent text-2xl font-semibold text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none"
            />
            <button
              onClick={() => setShowTokenSelector('out')}
              className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-600 rounded-full border border-gray-200 dark:border-gray-500 hover:border-purple-400 dark:hover:border-purple-500 transition-colors"
            >
              {tokenOut ? (
                <>
                  <TokenIcon symbol={tokenOut.symbol} size={24} />
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{tokenOut.symbol}</span>
                </>
              ) : (
                <span className="text-sm text-gray-500 dark:text-gray-400">Select</span>
              )}
              <svg className="w-4 h-4 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
            </button>
          </div>
        </div>

        {/* Quote Details */}
        {quote && (
          <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Rate</span>
              <span className="text-gray-900 dark:text-white font-medium">
                1 {tokenIn?.symbol} = {formatNumber(parseFloat(quote.amount_out) / parseFloat(quote.amount_in || '1'), 6)} {tokenOut?.symbol}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Minimum Received</span>
              <span className="text-gray-900 dark:text-white font-medium">
                {formatNumber(quote.minimum_received, 6)} {tokenOut?.symbol}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                Price Impact
                <Info className="w-3 h-3" />
              </span>
              <span className={`font-medium ${quote.price_impact > 3 ? 'text-red-500' :
                quote.price_impact > 1 ? 'text-yellow-500' : 'text-green-500'
                }`}>
                {quote.price_impact.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Route</span>
              <span className="text-gray-900 dark:text-white font-medium">{quote.dex_provider}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Gas Estimate</span>
              <span className="text-gray-900 dark:text-white font-medium">{quote.gas_estimate}</span>
            </div>
          </div>
        )}

        {/* Loading State */}
        {loading && !quote && (
          <div className="mt-4 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl text-center">
            <div className="inline-block w-4 h-4 border-2 border-purple-200 border-t-purple-600 rounded-full animate-spin mr-2" />
            <span className="text-sm text-gray-500 dark:text-gray-400">Fetching best quote...</span>
          </div>
        )}

        {/* Approval Button */}
        {needsApproval && (
          <Button
            variant="warning"
            size="lg"
            fullWidth
            onClick={handleApprove}
            disabled={approving || !tokenIn || !amountIn}
            isLoading={approving}
            leftIcon={<Shield className="w-4 h-4" />}
            className="mt-4"
          >
            Approve {tokenIn?.symbol}
          </Button>
        )}

        {/* Swap Button */}
        {!needsApproval && (
          <Button
            variant="primary"
            size="lg"
            fullWidth
            gradient
            onClick={() => setShowConfirmModal(true)}
            disabled={isSwapDisabled}
            isLoading={swapping}
            className="mt-4"
          >
            {!loadedWallet
              ? 'Load a wallet first'
              : !tokenIn || !tokenOut
                ? 'Select tokens'
                : !amountIn || parseFloat(amountIn) <= 0
                  ? 'Enter an amount'
                  : !quote
                    ? 'Getting quote...'
                    : 'Swap'}
          </Button>
        )}
      </Card>

      {/* ── Swap Confirmation Modal ──────────────────────────────────────── */}
      {showConfirmModal && quote && (
        <div
          className="fixed inset-0 bg-black/60 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
          onClick={() => setShowConfirmModal(false)}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Card variant="elevated" className="w-full sm:max-w-sm p-5 rounded-t-xl sm:rounded-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-bold text-gray-900 dark:text-white">Confirm Swap</h3>
                <button
                  onClick={() => setShowConfirmModal(false)}
                  className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              {/* Swap Summary */}
              <div className="space-y-3 mb-4">
                <div className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                  <div className="flex items-center gap-2">
                    <TokenIcon symbol={tokenIn!.symbol} size={28} />
                    <div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">{amountIn}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{tokenIn!.symbol}</div>
                    </div>
                  </div>
                  <ArrowDown className="w-4 h-4 text-gray-400" />
                  <div className="flex items-center gap-2">
                    <TokenIcon symbol={tokenOut!.symbol} size={28} />
                    <div>
                      <div className="text-sm font-semibold text-gray-900 dark:text-white">
                        {formatNumber(quote.amount_out, 6)}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{tokenOut!.symbol}</div>
                    </div>
                  </div>
                </div>

                {/* Details */}
                <div className="space-y-1.5 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Minimum received</span>
                    <span className="text-gray-900 dark:text-white font-medium">
                      {formatNumber(quote.minimum_received, 6)} {tokenOut!.symbol}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                      Price impact <Info className="w-3 h-3" />
                    </span>
                    <span className={`font-medium ${quote.price_impact > 3 ? 'text-red-500' :
                      quote.price_impact > 1 ? 'text-yellow-500' : 'text-green-500'
                      }`}>
                      {quote.price_impact.toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Slippage</span>
                    <span className="text-gray-900 dark:text-white">{slippage}%</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-500 dark:text-gray-400">Route</span>
                    <span className="text-gray-900 dark:text-white">{quote.dex_provider}</span>
                  </div>
                </div>

                {/* Warning for high price impact */}
                {quote.price_impact > 3 && (
                  <div className="flex items-start gap-2 p-2 bg-red-50 dark:bg-red-900/20 rounded-lg">
                    <AlertTriangle className="w-4 h-4 text-red-500 flex-shrink-0 mt-0.5" />
                    <p className="text-xs text-red-600 dark:text-red-400">
                      High price impact. You may receive significantly less than expected.
                    </p>
                  </div>
                )}
              </div>

              <Button
                variant="primary"
                size="lg"
                fullWidth
                gradient
                onClick={handleSwap}
                isLoading={swapping}
              >
                Confirm Swap
              </Button>
            </Card>
          </div>
        </div>
      )}

      {/* ── Token Selector Modal ─────────────────────────────────────────── */}
      {showTokenSelector && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
          onClick={() => { setShowTokenSelector(null); setTokenSearch(''); }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Card variant="elevated" className="w-full sm:max-w-sm p-4 rounded-t-xl sm:rounded-xl">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">Select Token</h3>
                <button
                  onClick={() => { setShowTokenSelector(null); setTokenSearch(''); }}
                  className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
                >
                  <X className="w-5 h-5 text-gray-500" />
                </button>
              </div>

              <div className="relative mb-4">
                <Search className="w-4 h-4 absolute left-3 top-1/2 -translate-y-1/2 text-gray-400" />
                <input
                  type="text"
                  placeholder="Search by symbol or address"
                  value={tokenSearch}
                  onChange={(e) => setTokenSearch(e.target.value)}
                  className="w-full pl-9 pr-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
                  autoFocus
                />
              </div>

              {/* Custom Token Import */}
              <div className="mb-3 p-3 bg-gray-50 dark:bg-gray-700/50 rounded-lg">
                <label className="text-xs font-medium text-gray-500 dark:text-gray-400 mb-1.5 block">
                  Import custom token
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    placeholder="0x... contract address"
                    value={customTokenAddress}
                    onChange={(e) => setCustomTokenAddress(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') handleImportCustomToken();
                    }}
                    className="flex-1 px-2.5 py-1.5 text-xs font-mono bg-white dark:bg-gray-600 border border-gray-300 dark:border-gray-500 rounded-md text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-1 focus:ring-purple-500"
                  />
                  <button
                    onClick={handleImportCustomToken}
                    disabled={importingToken || !isValidAddress(customTokenAddress.trim())}
                    className="px-3 py-1.5 text-xs font-medium bg-purple-600 text-white rounded-md hover:bg-purple-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                  >
                    {importingToken ? (
                      <span className="flex items-center gap-1">
                        <span className="w-3 h-3 border border-purple-300 border-t-white rounded-full animate-spin" />
                        ...
                      </span>
                    ) : (
                      'Import'
                    )}
                  </button>
                </div>
              </div>

              <div className="space-y-1 max-h-64 overflow-y-auto">
                {filteredTokens.map((token) => {
                  const bal = balances.find((b) => b.address === token.address);
                  return (
                    <button
                      key={token.address}
                      onClick={() => handleSelectToken(token)}
                      className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                    >
                      <TokenIcon symbol={token.symbol} size={32} />
                      <div className="text-left flex-1">
                        <div className="text-sm font-medium text-gray-900 dark:text-white">{token.symbol}</div>
                        <div className="text-xs text-gray-500 dark:text-gray-400">{token.name}</div>
                      </div>
                      {bal && parseFloat(bal.balance) > 0 && (
                        <div className="text-right">
                          <div className="text-sm font-medium text-gray-900 dark:text-white">
                            {formatNumber(bal.balance, 4)}
                          </div>
                          {(() => {
                            const price = getTokenPrice(bal.address);
                            const usd = formatUSD(parseFloat(bal.balance), price);
                            return usd ? (
                              <div className="text-xs text-gray-400 dark:text-gray-500">{usd}</div>
                            ) : null;
                          })()}
                        </div>
                      )}
                    </button>
                  );
                })}
                {filteredTokens.length === 0 && (
                  <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                    No tokens found
                  </div>
                )}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
