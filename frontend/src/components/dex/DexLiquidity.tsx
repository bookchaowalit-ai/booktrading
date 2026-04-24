/**
 * DEX Liquidity Component — Improved
 * % remove liquidity, better positions display, improved IL calculator
 */
'use client';

import { useState, useCallback, useEffect } from 'react';
import { Droplets, Plus, Minus, Search, AlertTriangle, TrendingDown, TrendingUp } from 'lucide-react';
import { dexApi, type LiquidityPosition, type WalletInfo } from '@/services/dexApi';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { TokenIcon } from '@/utils/tokenIcons';

const COMMON_TOKENS: Array<{ symbol: string; name: string; address: string; decimals: number }> = [
  { symbol: 'ETH', name: 'Ethereum', address: 'NATIVE', decimals: 18 },
  { symbol: 'USDC', name: 'USD Coin', address: '0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48', decimals: 6 },
  { symbol: 'USDT', name: 'Tether', address: '0xdAC17F958D2ee523a2206206994597C13D831ec7', decimals: 6 },
  { symbol: 'WBTC', name: 'Wrapped Bitcoin', address: '0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599', decimals: 8 },
  { symbol: 'DAI', name: 'Dai', address: '0x6B175474E89094C44Da98b954EedeAC495271d0F', decimals: 18 },
];

const REMOVE_PERCENTS = [25, 50, 75, 100];

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

  // Remove liquidity — now per-position with % selector
  const [removePositionIdx, setRemovePositionIdx] = useState<number | null>(null);
  const [removePct, setRemovePct] = useState(100);
  const [removing, setRemoving] = useState(false);

  // IL Calculator
  const [ilPriceRatio, setIlPriceRatio] = useState('2.0');
  const [ilInitialValue, setIlInitialValue] = useState('1000');
  const [ilFeeAPR, setIlFeeAPR] = useState('20');
  const [ilDaysHeld, setIlDaysHeld] = useState('30');
  const [ilResult, setIlResult] = useState<Awaited<ReturnType<typeof dexApi.calculateImpermanentLoss>> | null>(null);
  const [calculatingIL, setCalculatingIL] = useState(false);

  const [showTokenPicker, setShowTokenPicker] = useState<'add0' | 'add1' | null>(null);
  const [tokenSearch, setTokenSearch] = useState('');

  // Load positions
  useEffect(() => {
    if (loadedWallet) loadPositions();
    else setPositions([]);
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
    if (removePositionIdx === null || !loadedWallet) return;
    const pos = positions[removePositionIdx];
    if (!pos || !pos.id) return;
    setRemoving(true);
    try {
      // Calculate LP amount based on percentage
      const lpAmount = (pos.share * removePct / 100).toString();
      const result = await dexApi.removeLiquidity({
        walletId: loadedWallet.id,
        pool: pos.pool,
        lpAmount,
      });
      success(`Removed ${removePct}% liquidity! TX: ${result.txHash.slice(0, 10)}...`);
      setRemovePositionIdx(null);
      setRemovePct(100);
      loadPositions();
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to remove liquidity';
      showError(msg);
    } finally {
      setRemoving(false);
    }
  }, [removePositionIdx, loadedWallet, positions, removePct, success, showError, loadPositions]);

  const calculateIL = useCallback(async () => {
    setCalculatingIL(true);
    try {
      const result = await dexApi.calculateImpermanentLoss(
        parseFloat(ilPriceRatio),
        parseFloat(ilInitialValue),
        parseFloat(ilFeeAPR),
        parseFloat(ilDaysHeld)
      );
      setIlResult(result);
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to calculate IL';
      showError(msg);
    } finally {
      setCalculatingIL(false);
    }
  }, [ilPriceRatio, ilInitialValue, ilFeeAPR, ilDaysHeld, showError]);

  const handleSelectToken = (field: 'add0' | 'add1', address: string, symbol: string) => {
    if (field === 'add0') { setAddToken0(address); setAddToken0Symbol(symbol); }
    else { setAddToken1(address); setAddToken1Symbol(symbol); }
    setShowTokenPicker(null);
    setTokenSearch('');
  };

  const filteredTokens = COMMON_TOKENS.filter(
    (t) =>
      t.symbol.toLowerCase().includes(tokenSearch.toLowerCase()) ||
      t.address.toLowerCase().includes(tokenSearch.toLowerCase())
  );

  // Total value of all positions
  const totalValue = positions.reduce((sum, p) => sum + (p.valueUSD || 0), 0);
  const totalFees = positions.reduce((sum, p) => sum + (p.feesEarned || 0), 0);

  return (
    <div className="space-y-4">
      {/* Summary */}
      {positions.length > 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Card variant="elevated" className="p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Total Value</div>
            <div className="text-lg font-bold text-gray-900 dark:text-white">
              ${totalValue.toLocaleString(undefined, { maximumFractionDigits: 2 })}
            </div>
          </Card>
          <Card variant="elevated" className="p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Fees Earned</div>
            <div className="text-lg font-bold text-green-600 dark:text-green-400">
              +${totalFees.toFixed(2)}
            </div>
          </Card>
          <Card variant="elevated" className="p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Positions</div>
            <div className="text-lg font-bold text-gray-900 dark:text-white">{positions.length}</div>
          </Card>
        </div>
      )}

      {/* Add Liquidity */}
      <Card variant="elevated" className="p-4">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="w-full flex items-center justify-between"
        >
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Plus className="w-5 h-5 text-green-500" />
            Add Liquidity
          </h3>
          <svg className={`w-5 h-5 text-gray-400 transition-transform ${showAddForm ? 'rotate-180' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        {showAddForm && (
          <div className="mt-4 space-y-3">
            <div className="flex gap-2">
              <button
                onClick={() => setShowTokenPicker('add0')}
                className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-600 rounded-lg border border-gray-200 dark:border-gray-500 min-w-[120px]"
              >
                {addToken0Symbol ? (
                  <>
                    <TokenIcon symbol={addToken0Symbol} size={24} />
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
            <div className="flex gap-2">
              <button
                onClick={() => setShowTokenPicker('add1')}
                className="flex items-center gap-2 px-3 py-2 bg-white dark:bg-gray-600 rounded-lg border border-gray-200 dark:border-gray-500 min-w-[120px]"
              >
                {addToken1Symbol ? (
                  <>
                    <TokenIcon symbol={addToken1Symbol} size={24} />
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
        )}
      </Card>

      {/* Positions Table */}
      <Card variant="elevated" className="p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2">
            <Droplets className="w-5 h-5 text-blue-500" />
            Your Positions
          </h3>
          <button onClick={loadPositions} className="text-xs text-purple-600 dark:text-purple-400 hover:underline">
            Refresh
          </button>
        </div>

        {loadingPositions ? (
          <div className="py-8 text-center text-gray-500 dark:text-gray-400">Loading positions...</div>
        ) : positions.length === 0 ? (
          <div className="py-8 text-center">
            <Droplets className="w-12 h-12 text-gray-300 dark:text-gray-600 mx-auto mb-3" />
            <p className="text-sm text-gray-500 dark:text-gray-400">No liquidity positions</p>
            <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">Add liquidity to start earning fees</p>
          </div>
        ) : (
          <div className="space-y-3">
            {positions.map((p, idx) => (
              <div key={p.id || idx} className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl">
                <div className="flex items-center justify-between mb-2">
                  <div className="flex items-center gap-2">
                    <TokenIcon symbol={p.token0} size={24} />
                    <TokenIcon symbol={p.token1} size={24} />
                    <span className="font-semibold text-gray-900 dark:text-white">
                      {p.token0}/{p.token1}
                    </span>
                  </div>
                  <span className="font-bold text-gray-900 dark:text-white">
                    ${p.valueUSD?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || '0'}
                  </span>
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs mb-3">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Fees Earned</span>
                    <div className="text-green-600 dark:text-green-400 font-medium">
                      +${p.feesEarned?.toFixed(2) || '0'}
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">IL</span>
                    <div className={`font-medium flex items-center gap-1 ${(p.impermanentLoss || 0) < 0 ? 'text-red-500' : 'text-green-500'
                      }`}>
                      {(p.impermanentLoss || 0) < 0 ? <TrendingDown className="w-3 h-3" /> : <TrendingUp className="w-3 h-3" />}
                      {p.impermanentLoss?.toFixed(2) || '0'}%
                    </div>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Pool Share</span>
                    <div className="text-gray-900 dark:text-white font-medium">
                      {(p.share * 100).toFixed(4)}%
                    </div>
                  </div>
                </div>

                {/* Remove section */}
                {removePositionIdx === idx ? (
                  <div className="p-2 bg-white dark:bg-gray-600 rounded-lg space-y-2">
                    <div className="flex gap-1">
                      {REMOVE_PERCENTS.map((pct) => (
                        <button
                          key={pct}
                          onClick={() => setRemovePct(pct)}
                          className={`flex-1 py-1 text-xs font-medium rounded-md transition-colors ${removePct === pct
                            ? 'bg-purple-600 text-white'
                            : 'bg-gray-200 dark:bg-gray-500 text-gray-700 dark:text-gray-300 hover:bg-gray-300 dark:hover:bg-gray-400'
                            }`}
                        >
                          {pct}%
                        </button>
                      ))}
                    </div>
                    <div className="flex gap-2">
                      <Button
                        variant="danger"
                        size="sm"
                        onClick={handleRemoveLiquidity}
                        disabled={removing}
                        isLoading={removing}
                        className="flex-1"
                      >
                        Remove {removePct}%
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => { setRemovePositionIdx(null); setRemovePct(100); }}
                      >
                        Cancel
                      </Button>
                    </div>
                  </div>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => { setRemovePositionIdx(idx); setRemovePct(100); }}
                    leftIcon={<Minus className="w-3 h-3" />}
                    className="w-full"
                  >
                    Remove Liquidity
                  </Button>
                )}
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* IL Calculator */}
      <Card variant="elevated" className="p-4">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white flex items-center gap-2 mb-4">
          <AlertTriangle className="w-5 h-5 text-yellow-500" />
          Impermanent Loss Calculator
        </h3>

        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Initial Deposit (USD)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilInitialValue}
                onChange={(e) => setIlInitialValue(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Price Change Multiplier (×)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilPriceRatio}
                onChange={(e) => setIlPriceRatio(e.target.value)}
                placeholder="e.g., 2.0 = 2x"
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Fee APR (%)
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilFeeAPR}
                onChange={(e) => setIlFeeAPR(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-gray-500 dark:text-gray-400 mb-1">
                Days Held
              </label>
              <input
                type="text"
                inputMode="decimal"
                value={ilDaysHeld}
                onChange={(e) => setIlDaysHeld(e.target.value)}
                className="w-full px-3 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-200 dark:border-gray-600 rounded-lg text-sm text-gray-900 dark:text-white focus:outline-none focus:ring-2 focus:ring-purple-500"
              />
            </div>
          </div>

          <Button
            variant="warning"
            size="sm"
            fullWidth
            onClick={calculateIL}
            disabled={!ilPriceRatio || !ilInitialValue || !ilFeeAPR || !ilDaysHeld}
            isLoading={calculatingIL}
          >
            Calculate IL
          </Button>

          {ilResult && (
            <div className="p-3 bg-gray-50 dark:bg-gray-700/50 rounded-xl space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Impermanent Loss</span>
                <span className={`font-bold ${ilResult.il_percentage < 0 ? 'text-red-500' : 'text-green-500'}`}>
                  {ilResult.il_percentage.toFixed(2)}%
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Value if Held</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  ${ilResult.hold_value_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Value in Pool</span>
                <span className="text-gray-900 dark:text-white font-medium">
                  ${ilResult.current_value_usd.toLocaleString(undefined, { maximumFractionDigits: 2 })}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Fees Earned</span>
                <span className="text-green-600 dark:text-green-400 font-medium">
                  +${ilResult.fees_earned_usd.toFixed(2)}
                </span>
              </div>
              <div className="flex items-center justify-between text-sm">
                <span className="text-gray-500 dark:text-gray-400">Net Result</span>
                <span className={`font-bold ${ilResult.net_result_usd >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                  {ilResult.net_result_usd >= 0 ? '+' : '-'}${Math.abs(ilResult.net_result_usd).toFixed(2)}
                </span>
              </div>
            </div>
          )}
        </div>
      </Card>

      {/* Token Picker Modal */}
      {showTokenPicker && (
        <div
          className="fixed inset-0 bg-black/50 z-50 flex items-end sm:items-center justify-center p-0 sm:p-4"
          onClick={() => { setShowTokenPicker(null); setTokenSearch(''); }}
        >
          <div onClick={(e) => e.stopPropagation()}>
            <Card variant="elevated" className="w-full sm:max-w-sm p-4 rounded-t-xl sm:rounded-xl">
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
                    onClick={() => { if (showTokenPicker) handleSelectToken(showTokenPicker, t.address, t.symbol); }}
                    className="w-full flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                  >
                    <TokenIcon symbol={t.symbol} size={32} />
                    <div className="text-left">
                      <div className="text-sm font-medium text-gray-900 dark:text-white">{t.symbol}</div>
                      <div className="text-xs text-gray-500 dark:text-gray-400">{t.name}</div>
                    </div>
                  </button>
                ))}
              </div>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
