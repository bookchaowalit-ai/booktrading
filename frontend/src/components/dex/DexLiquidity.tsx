/**
 * DEX Liquidity Component
 * Add/remove liquidity and view positions with impermanent loss tracking
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { Droplets, Plus, Minus, Search, AlertTriangle, TrendingDown } from 'lucide-react';
import { dexApi, type LiquidityPosition, type WalletInfo, type TokenBalance } from '@/services/dexApi';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';

const COMMON_TOKENS: Array<{ symbol: string; name: string; address: string; decimals: number }> = [
  { symbol: 'ETH', name: 'Ethereum', address: 'NATIVE', decimals: 18 },
  { symbol: 'USDC', name: 'USD Coin', address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', decimals: 6 },
  { symbol: 'USDT', name: 'Tether', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', decimals: 6 },
  { symbol: 'WBTC', name: 'Wrapped Bitcoin', address: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', decimals: 8 },
  { symbol: 'DAI', name: 'Dai', address: '0x6B175474E89094C44Da98b954EedeAC495271d0F', decimals: 18 },
];

interface DexLiquidityProps {
  wallets: WalletInfo[];
  loadedWallet: WalletInfo | null;
}

export default function DexLiquidity({ loadedWallet }: DexLiquidityProps) {
  const { success, error: showError } = useToast();

  // Positions
  const [positions, setPositions] = useState<LiquidityPosition[]>([]);
  const [loadingPositions, setLoadingPositions] = useState(false);

  // Add liquidity form
  const [showAddForm, setShowAddForm] = useState(false);
  const [addToken0, setAddToken0] = useState('');
  const [addToken1, setAddToken1] = useState('');
  const [addToken0Symbol, setAddToken0Symbol] = useState('');
  const [addToken1Symbol, setAddToken1Symbol] = useState('');
  const [addAmount0, setAddAmount0] = useState('');
  const [addAmount1, setAddAmount1] = useState('');
  const [adding, setAdding] = useState(false);

  // Remove liquidity form
  const [removePool, setRemovePool] = useState('');
  const [removeAmount, setRemoveAmount] = useState('');
  const [removing, setRemoving] = useState(false);

  // IL Calculator
  const [ilToken0, setIlToken0] = useState('ETH');
  const [ilToken1, setIlToken1] = useState('USDC');
  const [ilInitialRatio, setIlInitialRatio] = useState('2000');
  const [ilCurrentRatio, setIlCurrentRatio] = useState('2500');
  const [ilResult, setIlResult] = useState<Awaited<ReturnType<typeof dexApi.calculateImpermanentLoss>> | null>(null);
  const [calculatingIL, setCalculatingIL] = useState(false);

  const [showTokenPicker, setShowTokenPicker] = useState<'add0' | 'add1' | null>(null);
  const [tokenSearch, setTokenSearch] = useState('');

  // Load positions
  useEffect(() => {
    if (loadedWallet) {
      loadPositions();
    } else {
      setPositions([]);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadedWallet]);

  const loadPositions = useCallback(async () => {
    if (!loadedWallet) return;
    setLoadingPositions(true);
    try {
      const pos = await dexApi.getLiquidity(loadedWallet.address);
      setPositions(pos);
    } catch {
      setPositions([]);
    } finally {
      setLoadingPositions(false);
    }
  }, [loadedWallet]);

  const handleAddLiquidity = useCallback(async () => {
    if (!loadedWallet || !addToken0 || !addToken1 || !addAmount0 || !addAmount1) return;
    setAdding(true);
    try {
      const result = await dexApi.addLiquidity({
        walletId: loadedWallet.id,
        token0: addToken0,
        token1: addToken1,
        amount0: addAmount0,
        amount1: addAmount1,
      });
      success(`Liquidity added! TX: ${result.txHash.slice(0, 10)}...`);
      setAddAmount0('');
      setAddAmount1('');
      setShowAddForm(false);
      loadPositions();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add liquidity';
      showError(msg);
    } finally {
      setAdding(false);
    }
  }, [loadedWallet, addToken0, addToken1, addAmount0, addAmount1, success, showError, loadPositions]);

  const handleRemoveLiquidity = useCallback(async () => {
    if (!loadedWallet || !removePool || !removeAmount) return;
    setRemoving(true);
    try {
      const result = await dexApi.removeLiquidity({
        walletId: loadedWallet.id,
        pool: removePool,
        lpAmount: removeAmount,
      });
      success(`Liquidity removed! TX: ${result.txHash.slice(0, 10)}...`);
      setRemoveAmount('');
      loadPositions();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to remove liquidity';
      showError(msg);
    } finally {
      setRemoving(false);
    }
  }, [loadedWallet, removePool, removeAmount, success, showError, loadPositions]);

  const calculateIL = useCallback(async () => {
    setCalculatingIL(true);
    try {
      const result = await dexApi.calculateImpermanentLoss(
        ilToken0,
        ilToken1,
        parseFloat(ilInitialRatio),
        parseFloat(ilCurrentRatio)
      );
      setIlResult(result);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to calculate IL';
      showError(msg);
    } finally {
      setCalculatingIL(false);
    }
  }, [ilToken0, ilToken1, ilInitialRatio, ilCurrentRatio, showError]);

  const handleSelectToken = (field: 'add0' | 'add1', address: string, symbol: string) => {
    if (field === 'add0') {
      setAddToken0(address);
      setAddToken0Symbol(symbol);
    } else {
      setAddToken1(address);
      setAddToken1Symbol(symbol);
    }
    setShowTokenPicker(null);
    setTokenSearch('');
  };

  const filteredTokens = COMMON_TOKENS.filter(
    (t) =>
      t.symbol.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.address.toLowerCase().includes(tokenSearch.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Add Liquidity Section */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Plus className="w-5 h-5 text-green-500" />
            Add Liquidity
          </h3>
        </div>

        <div className="space-y-3">
          {/* Token 0 */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowTokenPicker('add0')}
              className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-600 rounded-lg border border-gray-200 dark:border-gray-500 min-w-[120px]"
            >
              {addToken0Symbol ? (
                <>
                  <span className="w-6 h-6 rounded-full bg-purple-100 dark:bg-purple-900/50 flex items-center justify-center text-xs font-bold">
                    {addToken0Symbol.slice(0, 2)}
                  </span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{addToken0Symbol}</span>
                </>
              ) : (
                <span className="text-sm text-gray-500 dark:text-gray-400">Token 0</span>
              )}
            </button>
            <input
              type="text"
              inputMode="decimal"
              placeholder="Amount"
              value={addAmount0}
              onChange={(e) => {
                const val = e.target.value;
                if (val === '' || /^\d*\.?\d*$/.test(val)) setAddAmount0(val);
              }}
              className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          {/* Token 1 */}
          <div className="flex gap-2">
            <button
              onClick={() => setShowTokenPicker('add1')}
              className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-600 rounded-lg border border-gray-200 dark:border-gray-500 min-w-[120px]"
            >
              {addToken1Symbol ? (
                <>
                  <span className="w-6 h-6 rounded-full bg-blue-100 dark:bg-blue-900/50 flex items-center justify-center text-xs font-bold">
                    {addToken1Symbol.slice(0, 2)}
                  </span>
                  <span className="text-sm font-medium text-gray-900 dark:text-white">{addToken1Symbol}</span>
                </>
              ) : (
                <span className="text-sm text-gray-500 dark:text-gray-400">Token 1</span>
              )}
            </button>
            <input
              type="text"
              inputMode="decimal"
              placeholder="Amount"
              value={addAmount1}
              onChange={(e) => {
                const val = e.target.value;
                if (val === '' || /^\d*\.?\d*$/.test(val)) setAddAmount1(val);
              }}
              className="flex-1 px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
            />
          </div>

          <Button
            variant="success"
            size="md"
            fullWidth
            onClick={handleAddLiquidity}
            disabled={!loadedWallet || !addToken0 || !addToken1 || !addAmount0 || !addAmount1}
            isLoading={adding}
          >
            Add Liquidity
          </Button>
        </div>
      </Card>

      {/* Remove Liquidity Section */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Minus className="w-5 h-5 text-red-500" />
            Remove Liquidity
          </h3>
        </div>

        <div className="space-y-3">
          <select
            value={removePool}
            onChange={(e) => setRemovePool(e.target.value)}
            className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
          >
            <option value="">Select Pool</option>
            {positions.map((p) => (
              <option key={p.id} value={p.pool}>
                {p.token0}/{p.token1}
              </option>
            ))}
          </select>

          <input
            type="text"
            inputMode="decimal"
            placeholder="LP Token Amount (% or absolute)"
            value={removeAmount}
            onChange={(e) => setRemoveAmount(e.target.value)}
            className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
          />

          <Button
            variant="danger"
            size="md"
            fullWidth
            onClick={handleRemoveLiquidity}
            disabled={!loadedWallet || !removePool || !removeAmount}
            isLoading={removing}
          >
            Remove Liquidity
          </Button>
        </div>
      </Card>

      {/* Positions Table */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Droplets className="w-5 h-5 text-blue-500" />
            Liquidity Positions
          </h3>
          <button
            onClick={loadPositions}
            className="text-xs text-purple-600 dark:text-purple-400 hover:underline"
          >
            Refresh
          </button>
        </div>

        {loadingPositions ? (
          <div className="py-8 text-center text-gray-500 dark:text-gray-400">Loading positions...</div>
        ) : positions.length === 0 ? (
          <div className="py-8 text-center">
            <Droplets className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">No liquidity positions found</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Add liquidity to a pool to get started</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Pool</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Value</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Fees</th>
                  <th className="text-right py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">IL</th>
                </tr>
              </thead>
              <tbody>
                {positions.map((p) => (
                  <tr key={p.id} className="border-b border-gray-100 dark:border-gray-700/50">
                    <td className="py-3 px-3">
                      <div className="font-medium text-gray-900 dark:text-white">
                        {p.token0}/{p.token1}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {p.amount0} / {p.amount1}
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <div className="font-medium text-gray-900 dark:text-white">
                        ${p.valueUSD.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                      </div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">
                        {(p.share * 100).toFixed(4)}% of pool
                      </div>
                    </td>
                    <td className="py-3 px-3 text-right">
                      <span className="text-green-600 dark:text-green-400 font-medium">
                        +${p.feesEarned.toFixed(2)}
                      </span>
                    </td>
                    <td className="py-3 px-3 text-right">
                      {p.impermanentLoss !== 0 ? (
                        <span className={`font-medium flex items-center justify-end gap-1 ${p.impermanentLoss < 0 ? 'text-red-500' : 'text-green-500'}`}>
                          <TrendingDown className="w-3 h-3" />
                          {p.impermanentLoss.toFixed(2)}%
                        </span>
                      ) : (
                        <span className="text-gray-400">-</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {/* Impermanent Loss Calculator */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-yellow-500" />
            Impermanent Loss Calculator
          </h3>
        </div>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Token 0</label>
              <input
                type="text"
                value={ilToken0}
                onChange={(e) => setIlToken0(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">Token 1</label>
              <input
                type="text"
                value={ilToken1}
                onChange={(e) => setIlToken1(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Initial Price Ratio (T0/T1)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilInitialRatio}
                onChange={(e) => setIlInitialRatio(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Current Price Ratio (T0/T1)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilCurrentRatio}
                onChange={(e) => setIlCurrentRatio(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>

          <Button
            variant="warning"
            size="sm"
            fullWidth
            onClick={calculateIL}
            disabled={!ilInitialRatio || !ilCurrentRatio}
            isLoading={calculatingIL}
          >
            Calculate IL
          </Button>

          {ilResult && (
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Impermanent Loss</span>
                <span className={`font-bold ${ilResult.impermanentLoss < 0 ? 'text-red-500' : 'text-green-500'}`}>
                  {ilResult.impermanentLoss.toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Value if Held</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  ${ilResult.valueIfHeld.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Value in Pool</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  ${ilResult.valueInPool.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Loss</span>
                <span className="text-red-500 font-medium">
                  -${ilResult.loss.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Token Picker Modal */}
      {showTokenPicker && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4"
          onClick={() => { setShowTokenPicker(null); setTokenSearch(''); }}
        >
          <Card variant="elevated" className="w-full max-w-sm p-4" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">Select Token</h3>
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
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {filteredTokens.map((t) => (
                <button
                  key={t.address}
                  onClick={() => {
                    if (showTokenPicker) handleSelectToken(showTokenPicker, t.address, t.symbol);
                  }}
                  className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                >
                  <div className="w-8 h-8 rounded-full bg-gradient-to-br from-purple-100 to-blue-100 dark:from-purple-900/50 dark:to-blue-900/50 flex items-center justify-center text-sm font-bold text-purple-600 dark:text-purple-400">
                    {t.symbol.slice(0, 2)}
                  </div>
                  <div className="text-left">
                    <div className="text-sm font-medium text-gray-900 dark:text-white">{t.symbol}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{t.name}</div>
                  </div>
                </button>
              ))}
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
