/**
 * Trading Management Page - Redesigned
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Tabs } from '@/components/ui';
import ExchangeSelector from '@/components/ExchangeSelector';
import TradingViewChart from '@/components/TradingViewChart';
import StopLossTakeProfit from '@/components/StopLossTakeProfit';
import PositionSizingCalculator from '@/components/PositionSizingCalculator';
import OrderTracking from '@/components/OrderTracking';
import { api } from '@/services/api';
import {
  Zap, LayoutDashboard, Settings, Shield, Activity,
  PlayCircle, StopCircle, RefreshCw, ChevronDown,
  DollarSign, BarChart2, Target, Layers,
  ArrowUpRight, ArrowDownRight, Wallet, AlertTriangle,
  CheckCircle2,
} from 'lucide-react';

const SYMBOLS = [
  { value: 'BINANCE:BTCUSDT', label: 'BTC/USDT' },
  { value: 'BINANCE:ETHUSDT', label: 'ETH/USDT' },
  { value: 'BINANCE:BNBUSDT', label: 'BNB/USDT' },
  { value: 'BINANCE:SOLUSDT', label: 'SOL/USDT' },
];

const INTERVALS: { value: string; label: string }[] = [
  { value: '1', label: '1m' },
  { value: '5', label: '5m' },
  { value: '15', label: '15m' },
  { value: '60', label: '1h' },
  { value: '240', label: '4h' },
  { value: 'D', label: '1D' },
];

export default function TradingPage() {
  const { t } = useTranslation();
  const { success, error } = useToast();

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const authHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const [activeTab, setActiveTab] = useState<'overview' | 'config' | 'risk' | 'orders'>('overview');
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [chartSymbol, setChartSymbol] = useState('BINANCE:BTCUSDT');
  const [chartInterval, setChartInterval] = useState('60');
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [balances, setBalances] = useState<Array<{ currency: string; free: number; locked: number; total: number }>>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [gridConfig, setGridConfig] = useState({
    symbol: 'BTCUSDT',
    lowerPrice: 40000,
    upperPrice: 50000,
    gridLevels: 10,
    investmentAmount: 1000,
    gridType: 'arithmetic',
  });
  const [stats, setStats] = useState({
    totalProfit: 0,
    totalTrades: 0,
    activeOrders: 0,
    profitRate: 0,
  });

  /** Derive the quote currency from a trading symbol, e.g. BTCTHB → THB, BTCUSDT → USDT */
  const getQuoteCurrency = (symbol: string): string => {
    if (symbol.endsWith('THB')) return 'THB';
    if (symbol.endsWith('USDT')) return 'USDT';
    if (symbol.endsWith('BUSD')) return 'BUSD';
    if (symbol.endsWith('BTC')) return 'BTC';
    if (symbol.endsWith('ETH')) return 'ETH';
    return 'USDT';
  };

  const quoteCurrency = getQuoteCurrency(gridConfig.symbol);
  const quoteBalance = balances.find((b) => b.currency === quoteCurrency);
  const freeQuoteBalance = quoteBalance?.free ?? 0;
  const hasEnoughBalance = freeQuoteBalance >= gridConfig.investmentAmount;

  const loadBalances = useCallback(async () => {
    setBalancesLoading(true);
    try {
      const data = await api.getExchangeBalances();
      setBalances(data);
    } catch (_) {}
    finally { setBalancesLoading(false); }
  }, []);

  const loadBotStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/status`, {
        headers: authHeaders(),
      });
      const data = await response.json().catch(() => null);
      if (data) {
        setIsRunning(data.is_active);
        setStats({
          totalProfit: data.total_profit || 0,
          totalTrades: data.total_trades || 0,
          activeOrders: data.active_orders || 0,
          profitRate: data.total_trades > 0 ? ((data.profit_trades / data.total_trades) * 100) : 0,
        });
      }
    } catch (_) { }
  }, [API_BASE_URL]);

  useEffect(() => {
    loadBotStatus();
    loadBalances();
    const botInterval = setInterval(loadBotStatus, 5000);
    const balanceInterval = setInterval(loadBalances, 30000);
    return () => { clearInterval(botInterval); clearInterval(balanceInterval); };
  }, [loadBotStatus, loadBalances]);

  // Uptime counter
  useEffect(() => {
    if (!isRunning) { setUptime(0); return; }
    const timer = setInterval(() => setUptime((p) => p + 1), 1000);
    return () => clearInterval(timer);
  }, [isRunning]);

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

  const handleStartBot = async () => {
    // ── Balance pre-flight check ──────────────────────────────────
    const freshBalances = await api.getExchangeBalances();
    setBalances(freshBalances);
    const fresh = freshBalances.find((b) => b.currency === quoteCurrency);
    const available = fresh?.free ?? 0;

    if (available < gridConfig.investmentAmount) {
      error(
        `ยอดเงินไม่เพียงพอ: มี ${available.toLocaleString(undefined, { maximumFractionDigits: 8 })} ${quoteCurrency} ` +
        `แต่ต้องการ ${gridConfig.investmentAmount.toLocaleString()} ${quoteCurrency}`
      );
      return;
    }
    // ─────────────────────────────────────────────────────────────

    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify({
          symbol: gridConfig.symbol,
          lowerPrice: gridConfig.lowerPrice,
          upperPrice: gridConfig.upperPrice,
          gridLevels: gridConfig.gridLevels,
          investmentAmount: gridConfig.investmentAmount,
          gridType: gridConfig.gridType,
        }),
      });
      if (response.ok) {
        success('Trading bot started');
        setIsRunning(true);
        loadBotStatus();
      } else {
        error('Failed to start bot');
      }
    } catch (_) {
      error('Failed to start bot');
    } finally {
      setIsLoading(false);
    }
  };

  const handleStopBot = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/stop`, { method: 'POST', headers: authHeaders() });
      if (response.ok) {
        success('Trading bot stopped');
        setIsRunning(false);
        loadBotStatus();
      } else {
        error('Failed to stop bot');
      }
    } catch (_) {
      error('Failed to stop bot');
    } finally {
      setIsLoading(false);
    }
  };

  // Grid level preview calculation
  const gridLevels = Array.from({ length: gridConfig.gridLevels }, (_, i) => {
    const step = (gridConfig.upperPrice - gridConfig.lowerPrice) / (gridConfig.gridLevels - 1 || 1);
    return gridConfig.lowerPrice + step * i;
  });

  const perGridInvestment = gridConfig.investmentAmount / (gridConfig.gridLevels || 1);

  return (
    <div className="h-full flex flex-col gap-0 overflow-hidden">
      {/* ── Header Bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
        {/* Left: title + symbol picker */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2">
            <div className="p-1.5 bg-purple-100 dark:bg-purple-900/40 rounded-md">
              <Zap className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            </div>
            <div>
              <h1 className="text-sm font-bold leading-none">Trading</h1>
              <p className="text-[10px] text-gray-400 mt-0.5">Grid Bot</p>
            </div>
          </div>

          <div className="w-px h-6 bg-gray-200 dark:bg-gray-700" />

          {/* Symbol Dropdown */}
          <div className="relative">
            <button
              onClick={() => setShowSymbolDropdown((p) => !p)}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-md bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors text-sm font-semibold"
            >
              {SYMBOLS.find((s) => s.value === chartSymbol)?.label ?? 'BTC/USDT'}
              <ChevronDown className="w-3.5 h-3.5 text-gray-500" />
            </button>
            {showSymbolDropdown && (
              <div className="absolute top-full left-0 mt-1 z-50 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg shadow-lg py-1 min-w-[140px]">
                {SYMBOLS.map((s) => (
                  <button
                    key={s.value}
                    onClick={() => { setChartSymbol(s.value); setShowSymbolDropdown(false); }}
                    className={`w-full text-left px-3 py-1.5 text-sm hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors ${chartSymbol === s.value ? 'text-purple-600 font-semibold' : ''}`}
                  >
                    {s.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* Right: bot status + control */}
        <div className="flex items-center gap-3">
          {isRunning && (
            <div className="hidden sm:flex items-center gap-1.5 text-xs text-gray-500">
              <RefreshCw className="w-3 h-3 animate-spin text-green-500" />
              <span className="font-mono">{formatUptime(uptime)}</span>
            </div>
          )}

          <Badge variant={isRunning ? 'success' : 'default'}>
            <div className={`w-1.5 h-1.5 rounded-full mr-1 ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
            {isRunning ? 'Running' : 'Stopped'}
          </Badge>

          <Button
            variant={isRunning ? 'danger' : 'success'}
            size="sm"
            onClick={isRunning ? handleStopBot : handleStartBot}
            isLoading={isLoading}
            leftIcon={isRunning ? <StopCircle className="w-3.5 h-3.5" /> : <PlayCircle className="w-3.5 h-3.5" />}
          >
            {isRunning ? 'Stop Bot' : 'Start Bot'}
          </Button>
        </div>
      </div>

      {/* ── Tabs ───────────────────────────────────────────────────── */}
      <div className="px-4 pt-2 shrink-0 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800">
        <Tabs
          tabs={[
            { id: 'overview', label: 'Overview', icon: <LayoutDashboard className="w-3.5 h-3.5" /> },
            { id: 'config', label: 'Grid Config', icon: <Settings className="w-3.5 h-3.5" /> },
            { id: 'risk', label: 'Risk', icon: <Shield className="w-3.5 h-3.5" /> },
            { id: 'orders', label: 'Orders', icon: <Activity className="w-3.5 h-3.5" /> },
          ]}
          activeTab={activeTab}
          onChange={(tab) => setActiveTab(tab as typeof activeTab)}
          size="sm"
        />
      </div>

      {/* ── Tab Content ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden bg-gray-50 dark:bg-gray-950">

        {/* ── OVERVIEW ─────────────────────────────────────────────── */}
        {activeTab === 'overview' && (
          <div className="h-full flex gap-0">
            {/* Chart area */}
            <div className="flex-1 flex flex-col min-w-0 border-r border-gray-200 dark:border-gray-800">
              {/* Interval selector */}
              <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900">
                {INTERVALS.map((iv) => (
                  <button
                    key={iv.value}
                    onClick={() => setChartInterval(iv.value)}
                    className={`px-2.5 py-1 text-xs font-medium rounded transition-colors ${chartInterval === iv.value
                        ? 'bg-purple-600 text-white'
                        : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                      }`}
                  >
                    {iv.label}
                  </button>
                ))}
              </div>
              {/* Chart */}
              <div className="flex-1">
                <TradingViewChart
                  symbol={chartSymbol}
                  interval={chartInterval}
                  theme="dark"
                  height={600}
                />
              </div>
            </div>

            {/* Right sidebar */}
            <div className="w-72 shrink-0 flex flex-col gap-0 overflow-y-auto bg-white dark:bg-gray-900">

              {/* Stats Grid */}
              <div className="p-3 border-b border-gray-100 dark:border-gray-800">
                <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Performance</p>
                <div className="grid grid-cols-2 gap-2">
                  {/* Total P&L */}
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                    <div className="flex items-center gap-1 mb-1">
                      <DollarSign className="w-3 h-3 text-gray-400" />
                      <span className="text-[10px] text-gray-400">Total P&L</span>
                    </div>
                    <div className={`text-base font-bold ${stats.totalProfit >= 0 ? 'text-green-600' : 'text-red-500'}`}>
                      {stats.totalProfit >= 0 ? '+' : ''}{stats.totalProfit.toFixed(2)}
                    </div>
                    <div className={`flex items-center gap-0.5 text-[10px] mt-0.5 ${stats.totalProfit >= 0 ? 'text-green-500' : 'text-red-400'}`}>
                      {stats.totalProfit >= 0 ? <ArrowUpRight className="w-3 h-3" /> : <ArrowDownRight className="w-3 h-3" />}
                      USDT
                    </div>
                  </div>

                  {/* Win Rate */}
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                    <div className="flex items-center gap-1 mb-1">
                      <Target className="w-3 h-3 text-gray-400" />
                      <span className="text-[10px] text-gray-400">Win Rate</span>
                    </div>
                    <div className={`text-base font-bold ${stats.profitRate >= 50 ? 'text-green-600' : 'text-orange-500'}`}>
                      {stats.profitRate.toFixed(1)}%
                    </div>
                    <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-1 mt-1.5">
                      <div
                        className={`h-1 rounded-full ${stats.profitRate >= 50 ? 'bg-green-500' : 'bg-orange-500'}`}
                        style={{ width: `${Math.min(stats.profitRate, 100)}%` }}
                      />
                    </div>
                  </div>

                  {/* Total Trades */}
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                    <div className="flex items-center gap-1 mb-1">
                      <BarChart2 className="w-3 h-3 text-gray-400" />
                      <span className="text-[10px] text-gray-400">Trades</span>
                    </div>
                    <div className="text-base font-bold text-blue-600">{stats.totalTrades}</div>
                    <div className="text-[10px] text-gray-400 mt-0.5">executed</div>
                  </div>

                  {/* Active Orders */}
                  <div className="bg-gray-50 dark:bg-gray-800 rounded-lg p-2.5">
                    <div className="flex items-center gap-1 mb-1">
                      <Layers className="w-3 h-3 text-gray-400" />
                      <span className="text-[10px] text-gray-400">Orders</span>
                    </div>
                    <div className="text-base font-bold text-purple-600">{stats.activeOrders}</div>
                    <div className="text-[10px] text-gray-400 mt-0.5">active</div>
                  </div>
                </div>
              </div>

              {/* Grid Summary */}
              <div className="p-3 border-b border-gray-100 dark:border-gray-800">
                <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Grid Config</p>
                <div className="space-y-1.5">
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Symbol</span>
                    <span className="font-semibold">{gridConfig.symbol}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Range</span>
                    <span className="font-semibold">${gridConfig.lowerPrice.toLocaleString()} – ${gridConfig.upperPrice.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Levels</span>
                    <span className="font-semibold">{gridConfig.gridLevels}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Investment</span>
                    <span className="font-semibold">${gridConfig.investmentAmount.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between text-xs">
                    <span className="text-gray-500">Per Grid</span>
                    <span className="font-semibold text-purple-600">${perGridInvestment.toFixed(2)}</span>
                  </div>
                </div>
                <button
                  onClick={() => setActiveTab('config')}
                  className="mt-3 w-full text-xs text-purple-600 hover:text-purple-700 font-medium flex items-center justify-center gap-1 py-1.5 border border-purple-200 dark:border-purple-800 rounded-md hover:bg-purple-50 dark:hover:bg-purple-900/20 transition-colors"
                >
                  <Settings className="w-3 h-3" />
                  Edit Config
                </button>
              </div>

              {/* Exchange */}
              <div className="p-3">
                <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold mb-2">Exchange</p>
                <ExchangeSelector compact onExchangeChange={() => { loadBalances(); }} />
              </div>

              {/* Wallet Balances */}
              <div className="p-3 border-t border-gray-100 dark:border-gray-800">
                <div className="flex items-center justify-between mb-2">
                  <p className="text-[10px] uppercase tracking-wider text-gray-400 font-semibold">Wallet</p>
                  <button
                    onClick={loadBalances}
                    disabled={balancesLoading}
                    className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                    title="Refresh balances"
                  >
                    <RefreshCw className={`w-3 h-3 ${balancesLoading ? 'animate-spin' : ''}`} />
                  </button>
                </div>

                {/* Investment sufficiency indicator */}
                <div className={`flex items-center gap-2 p-2 rounded-lg mb-2 text-xs ${
                  hasEnoughBalance
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400'
                    : 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400'
                }`}>
                  {hasEnoughBalance
                    ? <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
                    : <AlertTriangle className="w-3.5 h-3.5 shrink-0" />}
                  <span>
                    {hasEnoughBalance
                      ? `Ready to invest ${gridConfig.investmentAmount.toLocaleString()} ${quoteCurrency}`
                      : `Need ${gridConfig.investmentAmount.toLocaleString()} ${quoteCurrency} to start`}
                  </span>
                </div>

                {balancesLoading && balances.length === 0 ? (
                  <div className="space-y-2">
                    {[1, 2, 3].map((i) => (
                      <div key={i} className="h-8 bg-gray-100 dark:bg-gray-800 rounded animate-pulse" />
                    ))}
                  </div>
                ) : balances.length === 0 ? (
                  <div className="text-center py-3">
                    <Wallet className="w-6 h-6 text-gray-300 mx-auto mb-1" />
                    <p className="text-xs text-gray-400">No balances found</p>
                    <p className="text-[10px] text-gray-400 mt-0.5">Configure API keys in Settings</p>
                  </div>
                ) : (
                  <div className="space-y-1">
                    {balances
                      .sort((a, b) => b.total - a.total)
                      .map((b) => {
                        const isQuote = b.currency === quoteCurrency;
                        const isInsufficient = isQuote && b.free < gridConfig.investmentAmount;
                        return (
                          <div
                            key={b.currency}
                            className={`flex items-center justify-between py-1.5 px-2 rounded-md ${
                              isQuote
                                ? isInsufficient
                                  ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                                  : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                                : 'bg-gray-50 dark:bg-gray-800'
                            }`}
                          >
                            <div className="flex items-center gap-2">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold ${
                                isQuote ? (isInsufficient ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700') : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
                              }`}>
                                {b.currency.slice(0, 1)}
                              </div>
                              <div>
                                <p className={`text-xs font-semibold ${isQuote ? (isInsufficient ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400') : 'text-gray-700 dark:text-gray-300'}`}>
                                  {b.currency}
                                </p>
                                {b.locked > 0 && (
                                  <p className="text-[9px] text-gray-400">+{b.locked.toLocaleString(undefined, { maximumFractionDigits: 6 })} locked</p>
                                )}
                              </div>
                            </div>
                            <div className="text-right">
                              <p className={`text-xs font-mono font-semibold ${isQuote ? (isInsufficient ? 'text-red-700 dark:text-red-400' : 'text-green-700 dark:text-green-400') : 'text-gray-700 dark:text-gray-300'}`}>
                                {b.free.toLocaleString(undefined, { maximumFractionDigits: b.free < 1 ? 8 : 2 })}
                              </p>
                              <p className="text-[9px] text-gray-400">free</p>
                            </div>
                          </div>
                        );
                      })}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* ── GRID CONFIG ──────────────────────────────────────────── */}
        {activeTab === 'config' && (
          <div className="h-full flex overflow-hidden">
            {/* Form */}
            <div className="w-80 shrink-0 overflow-y-auto border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
              <div className="flex items-center gap-2 mb-5">
                <div className="p-1.5 bg-purple-100 dark:bg-purple-900/40 rounded-md">
                  <Settings className="w-4 h-4 text-purple-600" />
                </div>
                <div>
                  <h2 className="text-sm font-bold">Grid Configuration</h2>
                  <p className="text-[10px] text-gray-400">Set parameters for grid trading</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Symbol */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5 block">Symbol</label>
                  <input
                    type="text"
                    value={gridConfig.symbol}
                    onChange={(e) => setGridConfig((p) => ({ ...p, symbol: e.target.value }))}
                    className="w-full px-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    placeholder="e.g. BTCUSDT"
                  />
                </div>

                {/* Grid Type */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5 block">Grid Type</label>
                  <div className="grid grid-cols-2 gap-2">
                    {['arithmetic', 'geometric'].map((type) => (
                      <button
                        key={type}
                        onClick={() => setGridConfig((p) => ({ ...p, gridType: type }))}
                        className={`py-2 text-xs font-medium rounded-lg border transition-all ${gridConfig.gridType === type
                            ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                            : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'
                          }`}
                      >
                        {type.charAt(0).toUpperCase() + type.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Price Range */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5 block">Price Range</label>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-[10px] text-gray-400 mb-1">Lower</p>
                      <input
                        type="number"
                        value={gridConfig.lowerPrice}
                        onChange={(e) => setGridConfig((p) => ({ ...p, lowerPrice: Number(e.target.value) }))}
                        className="w-full px-2.5 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      />
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400 mb-1">Upper</p>
                      <input
                        type="number"
                        value={gridConfig.upperPrice}
                        onChange={(e) => setGridConfig((p) => ({ ...p, upperPrice: Number(e.target.value) }))}
                        className="w-full px-2.5 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                {/* Grid Levels */}
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Grid Levels</label>
                    <span className="text-sm font-bold text-purple-600">{gridConfig.gridLevels}</span>
                  </div>
                  <input
                    type="range"
                    min={2}
                    max={50}
                    value={gridConfig.gridLevels}
                    onChange={(e) => setGridConfig((p) => ({ ...p, gridLevels: Number(e.target.value) }))}
                    className="w-full accent-purple-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>2</span><span>50</span>
                  </div>
                </div>

                {/* Investment */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400 mb-1.5 block">Investment Amount</label>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                    <input
                      type="number"
                      min={1}
                      value={gridConfig.investmentAmount}
                      onChange={(e) => setGridConfig((p) => ({ ...p, investmentAmount: Number(e.target.value) }))}
                      className="w-full pl-7 pr-3 py-2 text-sm border border-gray-200 dark:border-gray-700 rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:ring-purple-500 focus:border-transparent"
                    />
                  </div>
                  <p className="text-[10px] text-gray-400 mt-1">${perGridInvestment.toFixed(2)} per grid level</p>
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  fullWidth
                  onClick={() => setGridConfig({ symbol: 'BTCUSDT', lowerPrice: 40000, upperPrice: 50000, gridLevels: 10, investmentAmount: 1000, gridType: 'arithmetic' })}
                >
                  Reset
                </Button>
                <Button variant="primary" size="sm" fullWidth>
                  Apply
                </Button>
              </div>
            </div>

            {/* Grid Visual Preview */}
            <div className="flex-1 overflow-y-auto p-6 bg-gray-50 dark:bg-gray-950">
              <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-4">Grid Preview</p>
              <div className="max-w-md">
                {/* Grid bars */}
                <div className="relative bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4 overflow-hidden">
                  <div className="absolute inset-0 bg-gradient-to-b from-green-500/5 to-red-500/5 pointer-events-none" />
                  {gridLevels.slice().reverse().map((price, i) => {
                    const originalIdx = gridConfig.gridLevels - 1 - i;
                    const pct = ((price - gridConfig.lowerPrice) / ((gridConfig.upperPrice - gridConfig.lowerPrice) || 1)) * 100;
                    const isTop = i === 0;
                    const isBottom = i === gridLevels.length - 1;
                    return (
                      <div key={i} className="flex items-center gap-3 py-1 border-b border-dashed border-gray-100 dark:border-gray-800 last:border-0">
                        <div className="w-16 text-right">
                          <span className={`text-[10px] font-mono font-semibold ${isTop ? 'text-green-600' : isBottom ? 'text-red-500' : 'text-gray-500'}`}>
                            ${price.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                          </span>
                        </div>
                        <div className="flex-1 h-1.5 bg-gray-100 dark:bg-gray-800 rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${isTop ? 'bg-green-500' : isBottom ? 'bg-red-500' : 'bg-purple-400'}`}
                            style={{ width: `${pct}%`, minWidth: '4px' }}
                          />
                        </div>
                        <div className="w-16 text-left">
                          <span className="text-[10px] text-gray-400">
                            {originalIdx < Math.floor(gridConfig.gridLevels / 2) ? '↑ BUY' : '↓ SELL'}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>

                {/* Summary stats */}
                <div className="mt-4 grid grid-cols-3 gap-3">
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-gray-400">Grid Spread</p>
                    <p className="text-sm font-bold text-purple-600 mt-0.5">
                      {(((gridConfig.upperPrice - gridConfig.lowerPrice) / gridConfig.lowerPrice) * 100).toFixed(1)}%
                    </p>
                  </div>
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-gray-400">Step Size</p>
                    <p className="text-sm font-bold text-blue-600 mt-0.5">
                      ${((gridConfig.upperPrice - gridConfig.lowerPrice) / ((gridConfig.gridLevels - 1) || 1)).toFixed(0)}
                    </p>
                  </div>
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-lg p-3 text-center">
                    <p className="text-[10px] text-gray-400">Per Grid</p>
                    <p className="text-sm font-bold text-green-600 mt-0.5">
                      ${perGridInvestment.toFixed(2)}
                    </p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── RISK ─────────────────────────────────────────────────── */}
        {activeTab === 'risk' && (
          <div className="h-full overflow-y-auto p-4">
            <div className="max-w-4xl mx-auto grid grid-cols-1 lg:grid-cols-2 gap-4">
              <StopLossTakeProfit symbol={gridConfig.symbol} entryPrice={gridConfig.lowerPrice} />
              <PositionSizingCalculator
                accountBalance={gridConfig.investmentAmount}
                entryPrice={gridConfig.lowerPrice}
                stopLossPercent={5}
              />
            </div>
          </div>
        )}

        {/* ── ORDERS ───────────────────────────────────────────────── */}
        {activeTab === 'orders' && (
          <div className="h-full overflow-y-auto p-4">
            <OrderTracking symbol={gridConfig.symbol} gridLevels={gridConfig.gridLevels} />
          </div>
        )}
      </div>
    </div>
  );
}
