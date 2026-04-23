/**
 * DEX Swap Component
 * Token swap interface with quote fetching and slippage control
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { ArrowDown, Settings, Search, X, Info, Zap } from 'lucide-react';
import { dexApi, type QuoteResponse, type TokenBalance, type WalletInfo, type ChainInfo } from '@/services/dexApi';
import { useToast } from '@/components/ui/Toast';
import Button from '@/components/ui/Button';
import Card from '@/components/ui/Card';

// Common tokens for quick selection
const COMMON_TOKENS: Array<{ symbol: string; name: string; address: string; decimals: number; icon: string }> = [
  { symbol: 'ETH', name: 'Ethereum', address: 'NATIVE', decimals: 18, icon: '\u25CA' },
  { symbol: 'USDC', name: 'USD Coin', address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', decimals: 6, icon: '$' },
  { symbol: 'USDT', name: 'Tether', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', decimals: 6, icon: '\u20AE' },
  { symbol: 'WBTC', name: 'Wrapped Bitcoin', address: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', decimals: 8, icon: '\u20BF' },
  { symbol: 'DAI', name: 'Dai', address: '0x6B175474E89094C44Da98b954EedeAC495271d0F', decimals: 18, icon: '\u25C6' },
];

const SLIPPAGE_PRESETS = [0.1, 0.5, 1.0];

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

  // Settings
  const [slippage, setSlippage] = useState(0.5);
  const [customSlippage, setCustomSlippage] = useState('');
  const [bestRoute, setBestRoute] = useState(true);
  const [showSettings, setShowSettings] = useState(false);

  // State
  const [quote, setQuote] = useState<QuoteResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [swapping, setSwapping] = useState(false);
  const [balances, setBalances] = useState<TokenBalance[]>([]);

  // Fetch balances when wallet is loaded
  useEffect(() => {
    if (loadedWallet) {
      dexApi.getBalance(loadedWallet.address)
        .then((b) => setBalances(b.tokens))
        .catch(() => setBalances([]));
    } else {
      setBalances([]);
    }
  }, [loadedWallet]);

  // Fetch quote when amount changes
  useEffect(() => {
    if (!tokenIn || !tokenOut || !amountIn || parseFloat(amountIn) <= 0) {
      setQuote(null);
      return;
    }

    const timer = setTimeout(() => {
      fetchQuote();
    }, 500);

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
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to get quote';
      showError(msg);
      setQuote(null);
    } finally {
      setLoading(false);
    }
  }, [tokenIn, tokenOut, amountIn, slippage, bestRoute, showError]);

  const handleSwap = useCallback(async () => {
    if (!loadedWallet || !tokenIn || !tokenOut || !amountIn || !quote) return;
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
      success(`Swap successful! TX: ${result.txHash.slice(0, 10)}...`);
      setAmountIn('');
      setQuote(null);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Swap failed';
      showError(msg);
    } finally {
      setSwapping(false);
    }
  }, [loadedWallet, tokenIn, tokenOut, amountIn, quote, slippage, bestRoute, success, showError]);

  const handleSwitchTokens = () => {
    setTokenIn(tokenOut);
    setTokenOut(tokenIn);
    if (quote) {
      setAmountIn(quote.amountOut);
    }
    setQuote(null);
  };

  const handleSelectToken = (token: (typeof COMMON_TOKENS)[0]) => {
    const tb: TokenBalance = {
      symbol: token.symbol,
      address: token.address,
      balance: '0',
      decimals: token.decimals,
    };
    if (showTokenSelector === 'in') {
      if (tokenOut?.address === token.address) setTokenOut(null);
      setTokenIn(tb);
    } else {
      if (tokenIn?.address === token.address) setTokenIn(null);
      setTokenOut(tb);
    }
    setShowTokenSelector(null);
    setTokenSearch('');
  };

  const handleSetSlippage = (val: number) => {
    setSlippage(val);
    setCustomSlippage('');
  };

  const handleCustomSlippage = (val: string) => {
    setCustomSlippage(val);
    const num = parseFloat(val);
    if (!isNaN(num) && num > 0 && num < 50) {
      setSlippage(num);
    }
  };

  const filteredTokens = COMMON_TOKENS.filter(
    (t) =>
      t.symbol.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.name.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.address.toLowerCase().includes(tokenSearch.toLowerCase())
  );

  const isSwapDisabled = !loadedWallet || !tokenIn || !tokenOut || !amountIn || parseFloat(amountIn) <= 0 || !quote;

  const chain = chains.find((c) => c.id === selectedChain);

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
              <span className="text-xs text-gray-500 dark:text-gray-400 font-mono">
                {loadedWallet.address.slice(0, 6)}...{loadedWallet.address.slice(-4)}
              </span>
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
          <button
            onClick={() => setShowSettings(!showSettings)}
            className="p-1.5 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 text-gray-500"
          >
            <Settings className="w-4 h-4" />
          </button>
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
                    className={`px-3 py-1 text-xs font-medium rounded-md transition-colors ${
                      slippage === s && !customSlippage
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
                className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                  bestRoute ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'
                }`}
              >
                <span
                  className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                    bestRoute ? 'translate-x-5' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
          </div>
        )}

        {/* Token In */}
        <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs text-gray-500 dark:text-gray-400">From</span>
            {tokenIn && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Balance: {balances.find((b) => b.address === tokenIn.address)?.balance || '0'}
              </span>
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
                if (val === '' || /^\d*\.?\d*$/.test(val)) {
                  setAmountIn(val);
                }
              }}
              className="flex-1 bg-transparent text-2xl font-semibold text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none"
            />
            <button
              onClick={() => setShowTokenSelector('in')}
              className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-600 rounded-full border border-gray-200 dark:border-gray-500 hover:border-purple-400 dark:hover:border-purple-500 transition-colors"
            >
              {tokenIn ? (
                <>
                  <span className="w-6 h-6 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center text-xs font-bold">
                    {tokenIn.symbol.slice(0, 2)}
                  </span>
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
            <span className="text-xs text-gray-500 dark:text-gray-400">To</span>
          </div>
          <div className="flex gap-2">
            <input
              type="text"
              placeholder="0.0"
              value={quote?.amountOut ?? (loading ? '...' : '')}
              readOnly
              className="flex-1 bg-transparent text-2xl font-semibold text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none"
            />
            <button
              onClick={() => setShowTokenSelector('out')}
              className="flex items-center gap-2 px-3 py-1.5 bg-white dark:bg-gray-600 rounded-full border border-gray-200 dark:border-gray-500 hover:border-purple-400 dark:hover:border-purple-500 transition-colors"
            >
              {tokenOut ? (
                <>
                  <span className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-xs font-bold">
                    {tokenOut.symbol.slice(0, 2)}
                  </span>
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
                1 {tokenIn?.symbol} = {quote.exchangeRate} {tokenOut?.symbol}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Minimum Received</span>
              <span className="text-gray-900 dark:text-white font-medium">
                {quote.minimumReceived} {tokenOut?.symbol}
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400 flex items-center gap-1">
                Price Impact
                <Info className="w-3 h-3" />
              </span>
              <span className={`font-medium ${quote.priceImpact > 3 ? 'text-red-500' : quote.priceImpact > 1 ? 'text-yellow-500' : 'text-green-500'}`}>
                {quote.priceImpact.toFixed(2)}%
              </span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Route</span>
              <span className="text-gray-900 dark:text-white font-medium">{quote.dexProvider}</span>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-500 dark:text-gray-400">Gas Estimate</span>
              <span className="text-gray-900 dark:text-white font-medium">{quote.gasEstimate}</span>
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

        {/* Swap Button */}
        <Button
          variant="primary"
          size="lg"
          fullWidth
          gradient
          onClick={handleSwap}
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
      </Card>

      {/* Token Selector Modal */}
      {showTokenSelector && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => { setShowTokenSelector(null); setTokenSearch(''); }}
        >
          <Card
            variant="elevated"
            className="w-full max-w-sm p-4"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                Select Token
              </h3>
              <button
                onClick={() => { setShowTokenSelector(null); setTokenSearch(''); }}
                className="p-1 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700"
              >
                <X className="w-5 h-5 text-gray-500" />
              </button>
            </div>

            {/* Search */}
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

            {/* Token List */}
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {filteredTokens.map((token) => (
                <button
                  key={token.address}
                  onClick={() => handleSelectToken(token)}
                  className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/50 dark:to-blue-900/50 flex items-center justify-center text-sm font-bold text-purple-600 dark:text-purple-400">
                    {token.icon}
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{token.symbol}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{token.name}</div>
                  </div>
                </button>
              ))}
              {filteredTokens.length === 0 && (
                <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                  No tokens found
                </div>
              )}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
