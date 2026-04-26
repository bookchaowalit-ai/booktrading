/**
 * Trading Management Page - Redesigned
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import { useKeyboardShortcuts } from '@/hooks/useKeyboardShortcuts';
import { useFormValidation } from '@/hooks/useFormValidation';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import { Tabs } from '@/components/ui';
import ExchangeSelector from '@/components/ExchangeSelector';
import TradingViewChart from '@/components/TradingViewChart';
import StopLossTakeProfit from '@/components/StopLossTakeProfit';
import PositionSizingCalculator from '@/components/PositionSizingCalculator';
import OrderTracking from '@/components/OrderTracking';
import ActivityFeed from '@/components/ActivityFeed';
import { api } from '@/services/api';
import {
  Zap, LayoutDashboard, Settings, Shield, Activity,
  PlayCircle, StopCircle, RefreshCw, ChevronDown,
  DollarSign, BarChart2, Target, Layers,
  ArrowUpRight, ArrowDownRight, Wallet, AlertTriangle,
  CheckCircle2, Zap as ZapIcon, HelpCircle,
} from 'lucide-react';
import HelpTooltip, { TradingTooltips } from '@/components/ui/HelpTooltip';

const SYMBOLS = [
  { value: 'BINANCE:BTCUSDT', label: 'BTC/USDT' },
  { value: 'BINANCE:ETHUSDT', label: 'ETH/USDT' },
  { value: 'BINANCE:BNBUSDT', label: 'BNB/USDT' },
  { value: 'BINANCE:SOLUSDT', label: 'SOL/USDT' },
  // Binance TH (Thailand) THB pairs
  { value: 'BINANCE:BTCTHB', label: 'BTC/THB' },
  { value: 'BINANCE:ETHTHB', label: 'ETH/THB' },
  { value: 'BINANCE:BNBTHB', label: 'BNB/THB' },
  { value: 'BINANCE:XRPTHB', label: 'XRP/THB' },
  { value: 'BINANCE:DOTTHB', label: 'DOT/THB' },
  { value: 'BINANCE:ADAHTHB', label: 'ADA/THB' },
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
  const { validateGridConfig, positiveNumber, priceRange, gridLevelsRange, sufficientBalance } = useFormValidation();

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

  const authHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
    return token ? { Authorization: `Bearer ${token}` } : {};
  };

  const [activeTab, setActiveTab] = useState<'overview' | 'config' | 'signal' | 'risk' | 'orders'>('overview');
  const [isRunning, setIsRunning] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [chartSymbol, setChartSymbol] = useState('BINANCE:BTCUSDT');
  const [chartInterval, setChartInterval] = useState('60');
  const [showSymbolDropdown, setShowSymbolDropdown] = useState(false);
  const [uptime, setUptime] = useState(0);
  const [startedAt, setStartedAt] = useState<string | null>(null);
  const [balances, setBalances] = useState<Array<{ currency: string; free: number; locked: number; total: number }>>([]);
  const [balancesLoading, setBalancesLoading] = useState(false);
  const [gridConfig, setGridConfig] = useState({
    symbol: 'BTCTHB',
    lowerPrice: 1000000,
    upperPrice: 3000000,
    gridLevels: 5,
    investmentAmount: 500,
    gridType: 'arithmetic',
  });
  const [formErrors, setFormErrors] = useState<Record<string, string>>({});
  const [touchedFields, setTouchedFields] = useState<Record<string, boolean>>({});
  const [stats, setStats] = useState({
    totalProfit: 0,
    totalTrades: 0,
    activeOrders: 0,
    profitRate: 0,
  });
  const [botMode, setBotMode] = useState<'GRID' | 'SIGNAL' | 'AUTO'>('GRID');
  const [currentActivity, setCurrentActivity] = useState<string>('Waiting for bot to start...');
  const [signalConfig, setSignalConfig] = useState({
    symbol: 'BTCTHB',
    riskLevel: 'moderate' as 'conservative' | 'moderate' | 'aggressive',
    maxPositionPct: 0.25,
    stopLossPct: 0.05,
    takeProfitPct: 0.10,
    minStrength: 0.5,
    quantity: 0.001,
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

  // Validate form fields on change
  useEffect(() => {
    const newErrors: Record<string, string> = {};

    // Validate symbol
    if (!gridConfig.symbol) {
      newErrors.symbol = t('validation.required');
    }

    // Validate lower price
    if (gridConfig.lowerPrice <= 0) {
      newErrors.lowerPrice = t('validation.positive-number');
    }

    // Validate upper price
    if (gridConfig.upperPrice <= 0) {
      newErrors.upperPrice = t('validation.positive-number');
    } else if (gridConfig.upperPrice <= gridConfig.lowerPrice) {
      newErrors.upperPrice = t('validation.price-range');
    }

    // Validate grid levels
    if (gridConfig.gridLevels < 2 || gridConfig.gridLevels > 50) {
      newErrors.gridLevels = t('validation.grid-levels');
    }

    // Validate investment amount
    if (gridConfig.investmentAmount <= 0) {
      newErrors.investmentAmount = t('validation.negative-not-allowed');
    } else if (freeQuoteBalance > 0 && gridConfig.investmentAmount > freeQuoteBalance) {
      newErrors.investmentAmount = t('validation.insufficient-balance', {
        balance: freeQuoteBalance.toLocaleString(undefined, { maximumFractionDigits: 2 }),
        currency: quoteCurrency,
      });
    }

    setFormErrors(newErrors);
  }, [gridConfig, freeQuoteBalance, quoteCurrency, t]);

  const loadBalances = useCallback(async () => {
    setBalancesLoading(true);
    try {
      const data = await api.getExchangeBalances();
      setBalances(data);
    } catch (_) { }
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
        setBotMode(data.bot_mode || 'AUTO');
        setStartedAt(data.started_at || null);
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

    // Listen to bot activity updates from WebSocket
    import('@/services/websocket').then(({ wsService }) => {
      wsService.onBotActivity((activity) => {
        setCurrentActivity(activity.message);
      });
    });

    return () => { clearInterval(botInterval); clearInterval(balanceInterval); };
  }, [loadBotStatus, loadBalances]);

  // Update activity message when bot status changes
  useEffect(() => {
    if (isRunning) {
      // Always update to running state when bot is active
      setCurrentActivity((prev) => {
        // Only override if it's a stale/initializing message
        if (prev === 'Waiting for bot to start...' || prev === 'Bot stopped' || prev.includes('Bot started') || prev.includes('Initializing')) {
          return `Bot running — Mode: ${botMode}`;
        }
        // Keep real-time activity messages from WebSocket (SCANNING, WAITING, etc.)
        return prev;
      });
    } else {
      setCurrentActivity('Bot stopped');
    }
  }, [isRunning, botMode]);

  // Uptime counter — calculate from startedAt so it survives page refresh
  useEffect(() => {
    if (!isRunning || !startedAt) { setUptime(0); return; }
    const calcUptime = () => {
      const diff = Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000);
      setUptime(Math.max(0, diff));
    };
    calcUptime(); // initial calculation
    const timer = setInterval(calcUptime, 1000);
    return () => clearInterval(timer);
  }, [isRunning, startedAt]);

  const formatUptime = (s: number) => {
    const h = Math.floor(s / 3600);
    const m = Math.floor((s % 3600) / 60);
    const sec = s % 60;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  };

  const handleStartBot = async () => {
    // Validate based on bot mode
    if (botMode === 'GRID') {
      setTouchedFields({
        symbol: true,
        lowerPrice: true,
        upperPrice: true,
        gridLevels: true,
        investmentAmount: true,
      });

      const validation = validateGridConfig(
        {
          symbol: gridConfig.symbol,
          lowerPrice: gridConfig.lowerPrice,
          upperPrice: gridConfig.upperPrice,
          gridLevels: gridConfig.gridLevels,
          investmentAmount: gridConfig.investmentAmount,
        },
        freeQuoteBalance,
        quoteCurrency
      );

      if (!validation.isValid) {
        error(validation.errors[0].message);
        setActiveTab('config');
        return;
      }
    }

    setIsLoading(true);
    try {
      const requestBody: Record<string, unknown> = {
        botMode,
      };

      if (botMode === 'GRID') {
        requestBody.symbol = gridConfig.symbol;
        requestBody.lowerPrice = gridConfig.lowerPrice;
        requestBody.upperPrice = gridConfig.upperPrice;
        requestBody.gridLevels = gridConfig.gridLevels;
        requestBody.investment = gridConfig.investmentAmount;
      }

      // Signal/AUTO modes also need signal config
      if (botMode === 'SIGNAL' || botMode === 'AUTO') {
        requestBody.signalConfig = {
          symbol: signalConfig.symbol,
          riskLevel: signalConfig.riskLevel,
          maxPositionPct: signalConfig.maxPositionPct,
          stopLossPct: signalConfig.stopLossPct,
          takeProfitPct: signalConfig.takeProfitPct,
          minStrength: signalConfig.minStrength,
          quantity: signalConfig.quantity,
        };
      }

      const response = await fetch(`${API_BASE_URL}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...authHeaders() },
        body: JSON.stringify(requestBody),
      });
      if (response.ok) {
        success('✅ เปิดใช้งานบอทเทรดสำเร็จ! บอทกำลังเริ่มต้นระบบ...');
        setIsRunning(true);
        setCurrentActivity(`Bot started — Mode: ${botMode}`);
        loadBotStatus();
      } else {
        try {
          const data = await response.json();
          error(data.error || data.message || '❌ ไม่สามารถเปิดใช้งานบอทได้');
        } catch {
          error('❌ ไม่สามารถเปิดใช้งานบอทได้');
        }
      }
    } catch (err) {
      error(err instanceof Error ? err.message : '❌ เกิดข้อผิดพลาดในการเชื่อมต่อกับเซิร์ฟเวอร์');
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

  // Keyboard shortcuts for bot control
  useKeyboardShortcuts([
    { key: 's', ctrl: true, shift: true, action: () => isRunning ? handleStopBot() : handleStartBot() },
    { key: 'r', ctrl: true, action: () => loadBotStatus() },
  ]);

  // Grid level preview calculation
  const gridLevels = Array.from({ length: gridConfig.gridLevels }, (_, i) => {
    const step = (gridConfig.upperPrice - gridConfig.lowerPrice) / (gridConfig.gridLevels - 1 || 1);
    return gridConfig.lowerPrice + step * i;
  });

  const perGridInvestment = gridConfig.investmentAmount / (gridConfig.gridLevels || 1);

  return (
    <div className="h-full flex flex-col gap-0 overflow-hidden">
      {/* ── Header Bar ─────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 sm:px-4 py-2.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 shrink-0">
        {/* Left: title + symbol picker */}
        <div className="flex items-center gap-2 sm:gap-3">
          <div className="flex items-center gap-1.5 sm:gap-2">
            <div className="p-1.5 bg-purple-100 dark:bg-purple-900/40 rounded-md">
              <ZapIcon className="w-4 h-4 text-purple-600 dark:text-purple-400" />
            </div>
            <div className="hidden sm:block">
              <h1 className="text-sm font-bold leading-none">Trading</h1>
              <p className="text-[10px] text-gray-400 mt-0.5">
                {botMode === 'GRID' && 'Grid Bot'}
                {botMode === 'SIGNAL' && 'Signal Bot'}
                {botMode === 'AUTO' && 'Auto Bot'}
              </p>
            </div>
          </div>

          <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 hidden sm:block" />

          {/* Mode Selector */}
          <div className="flex items-center gap-1">
            {(['GRID', 'SIGNAL', 'AUTO'] as const).map((mode) => {
              const icons = { GRID: '⚡', SIGNAL: '📡', AUTO: '🤖' };
              const labels = { GRID: 'Grid', SIGNAL: 'Signal', AUTO: 'Auto' };
              const isActive = botMode === mode;
              return (
                <button
                  key={mode}
                  disabled={isRunning}
                  onClick={() => setBotMode(mode)}
                  className={`px-2.5 py-1 text-xs font-medium rounded-md transition-all ${
                    isRunning && !isActive
                      ? 'opacity-40 cursor-not-allowed'
                      : 'cursor-pointer'
                  } ${
                    isActive
                      ? 'bg-purple-600 text-white shadow-sm'
                      : 'bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-400 hover:bg-gray-200 dark:hover:bg-gray-700'
                  }`}
                  title={
                    mode === 'GRID'
                      ? 'Grid bot: Buys at lower price levels, sells at higher levels'
                      : mode === 'SIGNAL'
                      ? 'Signal bot: Trades based on RSI/EMA signals from strategy service'
                      : 'Auto bot: Signal-based entry with auto stop-loss/take-profit'
                  }
                >
                  {icons[mode]} {labels[mode]}
                </button>
              );
            })}
          </div>

          <div className="w-px h-6 bg-gray-200 dark:bg-gray-700 hidden sm:block" />

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

          {isRunning && (
            <Badge variant="purple" className="hidden sm:flex">
              {botMode}
            </Badge>
          )}

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
            { id: 'signal', label: 'Signal', icon: <Zap className="w-3.5 h-3.5" /> },
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
          <div className="h-full flex flex-col md:flex-row gap-0">
            {/* Chart area */}
            <div className="flex-1 flex flex-col min-w-0 border-b md:border-r border-gray-200 dark:border-gray-800">
              {/* Interval selector - horizontal scroll on mobile */}
              <div className="flex items-center gap-1 px-3 py-1.5 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 overflow-x-auto">
                {INTERVALS.map((iv) => (
                  <button
                    key={iv.value}
                    onClick={() => setChartInterval(iv.value)}
                    className={`px-2.5 py-1 text-xs font-medium rounded transition-colors whitespace-nowrap ${chartInterval === iv.value
                      ? 'bg-purple-600 text-white'
                      : 'text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800'
                      }`}
                  >
                    {iv.label}
                  </button>
                ))}
              </div>
              {/* Chart */}
              <div className="flex-1 min-h-[300px] md:min-h-[400px]">
                <TradingViewChart
                  symbol={chartSymbol}
                  interval={chartInterval}
                  theme="dark"
                  height={600}
                />
              </div>
            </div>

            {/* Right sidebar - becomes bottom panel on mobile */}
            <div className="w-full md:w-72 shrink-0 flex flex-col gap-0 overflow-y-auto bg-white dark:bg-gray-900 border-t md:border-l border-gray-200 dark:border-gray-800">

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

              {/* Live Activity Feed */}
              <div className="border-t border-gray-100 dark:border-gray-800">
                <ActivityFeed compact maxItems={10} showToasts={false} />
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
                <div className={`flex items-center gap-2 p-2 rounded-lg mb-2 text-xs ${hasEnoughBalance
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
                            className={`flex items-center justify-between py-1.5 px-2 rounded-md ${isQuote
                              ? isInsufficient
                                ? 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                                : 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                              : 'bg-gray-50 dark:bg-gray-800'
                              }`}
                          >
                            <div className="flex items-center gap-2">
                              <div className={`w-5 h-5 rounded-full flex items-center justify-center text-[9px] font-bold ${isQuote ? (isInsufficient ? 'bg-red-100 text-red-700' : 'bg-green-100 text-green-700') : 'bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-300'
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

        {/* ── SIGNAL CONFIG ────────────────────────────────────────── */}
        {activeTab === 'signal' && (
          <div className="h-full flex flex-col md:flex-row overflow-hidden">
            {/* Signal Bot Config Form */}
            <div className="w-full md:w-80 shrink-0 overflow-y-auto border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
              <div className="flex items-center gap-2 mb-5">
                <div className="p-1.5 bg-blue-100 dark:bg-blue-900/40 rounded-md">
                  <Zap className="w-4 h-4 text-blue-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="text-sm font-bold truncate">Signal Bot Config</h2>
                  <p className="text-[10px] text-gray-400 truncate">Configure signal-driven trading</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Signal Symbol */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Symbol</label>
                  <select
                    value={signalConfig.symbol}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, symbol: e.target.value }))}
                    className="w-full mt-1 px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 focus:ring-purple-500 focus:ring-2 focus:outline-none"
                  >
                    {SYMBOLS.map((s) => (
                      <option key={s.value} value={s.value.replace('BINANCE:', '')}>{s.label}</option>
                    ))}
                  </select>
                </div>

                {/* Risk Level */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Risk Level</label>
                  <div className="grid grid-cols-3 gap-1.5 mt-1.5">
                    {(['conservative', 'moderate', 'aggressive'] as const).map((level) => (
                      <button
                        key={level}
                        onClick={() => {
                          const presets = {
                            conservative: { stopLossPct: 0.03, takeProfitPct: 0.08, maxPositionPct: 0.15, minStrength: 0.7, quantity: 0.0005 },
                            moderate: { stopLossPct: 0.05, takeProfitPct: 0.10, maxPositionPct: 0.25, minStrength: 0.5, quantity: 0.001 },
                            aggressive: { stopLossPct: 0.08, takeProfitPct: 0.15, maxPositionPct: 0.4, minStrength: 0.3, quantity: 0.002 },
                          };
                          setSignalConfig((p) => ({ ...p, riskLevel: level, ...presets[level] }));
                        }}
                        className={`py-2 text-xs font-medium rounded-lg border transition-all ${
                          signalConfig.riskLevel === level
                            ? level === 'conservative'
                              ? 'border-green-500 bg-green-50 dark:bg-green-900/30 text-green-700 dark:text-green-300'
                              : level === 'moderate'
                              ? 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-300'
                              : 'border-red-500 bg-red-50 dark:bg-red-900/30 text-red-700 dark:text-red-300'
                            : 'border-gray-200 dark:border-gray-700 text-gray-500 hover:border-gray-300'
                        }`}
                      >
                        {level.charAt(0).toUpperCase() + level.slice(1)}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Quantity */}
                <div>
                  <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Quantity per Trade</label>
                  <input
                    type="number"
                    step="0.001"
                    min="0.001"
                    value={signalConfig.quantity}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, quantity: Number(e.target.value) }))}
                    className="w-full mt-1 px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 focus:ring-purple-500 focus:ring-2 focus:outline-none"
                  />
                </div>

                {/* Min Strength */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Min Signal Strength</label>
                    <span className="text-sm font-bold text-purple-600">{signalConfig.minStrength}</span>
                  </div>
                  <input
                    type="range"
                    min="0.1"
                    max="1.0"
                    step="0.1"
                    value={signalConfig.minStrength}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, minStrength: Number(e.target.value) }))}
                    className="w-full mt-1 accent-purple-600"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>Low (more trades)</span><span>High (fewer trades)</span>
                  </div>
                </div>

                {/* Stop Loss */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Stop Loss</label>
                    <span className="text-sm font-bold text-red-600">{(signalConfig.stopLossPct * 100).toFixed(1)}%</span>
                  </div>
                  <input
                    type="range"
                    min="1"
                    max="15"
                    step="0.5"
                    value={signalConfig.stopLossPct * 100}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, stopLossPct: Number(e.target.value) / 100 }))}
                    className="w-full mt-1 accent-red-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>1%</span><span>15%</span>
                  </div>
                </div>

                {/* Take Profit */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Take Profit</label>
                    <span className="text-sm font-bold text-green-600">{(signalConfig.takeProfitPct * 100).toFixed(1)}%</span>
                  </div>
                  <input
                    type="range"
                    min="2"
                    max="30"
                    step="1"
                    value={signalConfig.takeProfitPct * 100}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, takeProfitPct: Number(e.target.value) / 100 }))}
                    className="w-full mt-1 accent-green-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>2%</span><span>30%</span>
                  </div>
                </div>

                {/* Max Position */}
                <div>
                  <div className="flex items-center justify-between">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Max Position</label>
                    <span className="text-sm font-bold text-blue-600">{(signalConfig.maxPositionPct * 100).toFixed(0)}%</span>
                  </div>
                  <input
                    type="range"
                    min="5"
                    max="50"
                    step="5"
                    value={signalConfig.maxPositionPct * 100}
                    onChange={(e) => setSignalConfig((p) => ({ ...p, maxPositionPct: Number(e.target.value) / 100 }))}
                    className="w-full mt-1 accent-blue-500"
                  />
                  <div className="flex justify-between text-[10px] text-gray-400 mt-0.5">
                    <span>5%</span><span>50%</span>
                  </div>
                </div>
              </div>

              <div className="mt-6 flex gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  fullWidth
                  onClick={() => setSignalConfig({
                    symbol: 'BTCUSDT',
                    riskLevel: 'moderate',
                    maxPositionPct: 0.25,
                    stopLossPct: 0.05,
                    takeProfitPct: 0.10,
                    minStrength: 0.5,
                    quantity: 0.001,
                  })}
                >
                  Reset
                </Button>
              </div>
            </div>

            {/* Signal Bot Info / Preview */}
            <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-gray-50 dark:bg-gray-950">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1 bg-blue-100 dark:bg-blue-900/40 rounded">
                  <Zap className="w-3.5 h-3.5 text-blue-600" />
                </div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">How It Works</p>
              </div>

              <div className="max-w-2xl space-y-4">
                {/* Mode Cards */}
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                  <Card className="p-4 border-l-4 border-l-blue-500">
                    <h4 className="text-sm font-bold text-blue-600 mb-1">Signal Bot</h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Listens to strategy service (RSI/EMA) signals from Redis and automatically buys/sells.
                      Simple, direct signal-to-trade mapping.
                    </p>
                  </Card>
                  <Card className="p-4 border-l-4 border-l-purple-500">
                    <h4 className="text-sm font-bold text-purple-600 mb-1">Auto Bot</h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Same as signal bot but with automatic stop-loss and take-profit monitoring.
                      Closes positions when thresholds are hit.
                    </p>
                  </Card>
                  <Card className="p-4 border-l-4 border-l-gray-500">
                    <h4 className="text-sm font-bold text-gray-600 mb-1">Grid Bot</h4>
                    <p className="text-xs text-gray-500 dark:text-gray-400">
                      Buys at lower price levels and sells at higher levels.
                      No signal-based entry, just price-range trading.
                    </p>
                  </Card>
                </div>

                {/* Signal Flow */}
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                  <h4 className="text-sm font-bold mb-3">Signal Flow</h4>
                  <div className="flex items-center gap-2 text-xs">
                    <div className="px-3 py-2 bg-blue-100 dark:bg-blue-900/30 rounded-lg text-center">
                      <p className="font-semibold">Strategy Service</p>
                      <p className="text-gray-500">RSI + EMA Analysis</p>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-gray-400" />
                    <div className="px-3 py-2 bg-red-100 dark:bg-red-900/30 rounded-lg text-center">
                      <p className="font-semibold">Redis Pub/Sub</p>
                      <p className="text-gray-500">order_signals</p>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-gray-400" />
                    <div className="px-3 py-2 bg-green-100 dark:bg-green-900/30 rounded-lg text-center">
                      <p className="font-semibold">Backend Bot</p>
                      <p className="text-gray-500">Signal Filter + Execute</p>
                    </div>
                    <ArrowUpRight className="w-4 h-4 text-gray-400" />
                    <div className="px-3 py-2 bg-purple-100 dark:bg-purple-900/30 rounded-lg text-center">
                      <p className="font-semibold">Exchange</p>
                      <p className="text-gray-500">Market Order</p>
                    </div>
                  </div>
                </div>

                {/* Config Summary */}
                <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-xl p-4">
                  <h4 className="text-sm font-bold mb-3">Current Config</h4>
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                    <div>
                      <p className="text-[10px] text-gray-400">Symbol</p>
                      <p className="text-sm font-bold">{signalConfig.symbol}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400">Risk Level</p>
                      <p className="text-sm font-bold capitalize">{signalConfig.riskLevel}</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400">Stop Loss</p>
                      <p className="text-sm font-bold text-red-600">{(signalConfig.stopLossPct * 100).toFixed(1)}%</p>
                    </div>
                    <div>
                      <p className="text-[10px] text-gray-400">Take Profit</p>
                      <p className="text-sm font-bold text-green-600">{(signalConfig.takeProfitPct * 100).toFixed(1)}%</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* ── GRID CONFIG ──────────────────────────────────────────── */}
        {activeTab === 'config' && (
          <div className="h-full flex flex-col md:flex-row overflow-hidden">
            {/* Form */}
            <div className="w-full md:w-80 shrink-0 overflow-y-auto border-r border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 p-4">
              <div className="flex items-center gap-2 mb-5">
                <div className="p-1.5 bg-purple-100 dark:bg-purple-900/40 rounded-md">
                  <Settings className="w-4 h-4 text-purple-600" />
                </div>
                <div className="flex-1 min-w-0">
                  <h2 className="text-sm font-bold truncate">Grid Configuration</h2>
                  <p className="text-[10px] text-gray-400 truncate">Set parameters for grid trading</p>
                </div>
              </div>

              <div className="space-y-4">
                {/* Symbol */}
                <div>
                  <div className="flex items-center gap-1 mb-1.5">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Symbol</label>
                    <HelpTooltip content={TradingTooltips.gridLevels.content} title={TradingTooltips.gridLevels.title} />
                  </div>
                  <input
                    type="text"
                    value={gridConfig.symbol}
                    onChange={(e) => setGridConfig((p) => ({ ...p, symbol: e.target.value }))}
                    onBlur={() => setTouchedFields((p) => ({ ...p, symbol: true }))}
                    className={`w-full px-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:border-transparent ${
                      formErrors.symbol && touchedFields.symbol
                        ? 'border-red-500 focus:ring-red-500'
                        : 'border-gray-200 dark:border-gray-700 focus:ring-purple-500'
                    }`}
                    placeholder="e.g. BTCUSDT"
                  />
                  {formErrors.symbol && touchedFields.symbol && (
                    <p className="text-[10px] text-red-500 mt-1 flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      {formErrors.symbol}
                    </p>
                  )}
                </div>

                {/* Grid Type */}
                <div>
                  <div className="flex items-center gap-1 mb-1.5">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Grid Type</label>
                    <HelpTooltip
                      content={gridConfig.gridType === 'arithmetic'
                        ? TradingTooltips.arithmeticGrid.content
                        : TradingTooltips.geometricGrid.content}
                      title={gridConfig.gridType === 'arithmetic'
                        ? TradingTooltips.arithmeticGrid.title
                        : TradingTooltips.geometricGrid.title}
                    />
                  </div>
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
                  <div className="flex items-center gap-1 mb-1.5">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Price Range</label>
                    <HelpTooltip content={TradingTooltips.lowerPrice.content} title={TradingTooltips.lowerPrice.title} />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <div className="flex items-center gap-1 mb-1">
                        <p className="text-[10px] text-gray-400">Lower</p>
                        <HelpTooltip content="The bottom price of your grid range where buy orders are placed" position="right" />
                      </div>
                      <input
                        type="number"
                        value={gridConfig.lowerPrice}
                        onChange={(e) => setGridConfig((p) => ({ ...p, lowerPrice: Number(e.target.value) }))}
                        onBlur={() => setTouchedFields((p) => ({ ...p, lowerPrice: true }))}
                        className={`w-full px-2.5 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:border-transparent ${
                          formErrors.lowerPrice && touchedFields.lowerPrice
                            ? 'border-red-500 focus:ring-red-500'
                            : 'border-gray-200 dark:border-gray-700 focus:ring-purple-500'
                        }`}
                      />
                      {formErrors.lowerPrice && touchedFields.lowerPrice && (
                        <p className="text-[10px] text-red-500 mt-1">{formErrors.lowerPrice}</p>
                      )}
                    </div>
                    <div>
                      <div className="flex items-center gap-1 mb-1">
                        <p className="text-[10px] text-gray-400">Upper</p>
                        <HelpTooltip content="The top price of your grid range where sell orders are placed" position="right" />
                      </div>
                      <input
                        type="number"
                        value={gridConfig.upperPrice}
                        onChange={(e) => setGridConfig((p) => ({ ...p, upperPrice: Number(e.target.value) }))}
                        onBlur={() => setTouchedFields((p) => ({ ...p, upperPrice: true }))}
                        className={`w-full px-2.5 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:border-transparent ${
                          formErrors.upperPrice && touchedFields.upperPrice
                            ? 'border-red-500 focus:ring-red-500'
                            : 'border-gray-200 dark:border-gray-700 focus:ring-purple-500'
                        }`}
                      />
                      {formErrors.upperPrice && touchedFields.upperPrice && (
                        <p className="text-[10px] text-red-500 mt-1">{formErrors.upperPrice}</p>
                      )}
                    </div>
                  </div>
                </div>

                {/* Grid Levels */}
                <div>
                  <div className="flex justify-between items-center mb-1.5">
                    <div className="flex items-center gap-1">
                      <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Grid Levels</label>
                      <HelpTooltip content={TradingTooltips.gridLevels.content} title={TradingTooltips.gridLevels.title} />
                    </div>
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
                  {formErrors.gridLevels && touchedFields.gridLevels && (
                    <p className="text-[10px] text-red-500 mt-1">{formErrors.gridLevels}</p>
                  )}
                </div>

                {/* Investment */}
                <div>
                  <div className="flex items-center gap-1 mb-1.5">
                    <label className="text-xs font-medium text-gray-600 dark:text-gray-400">Investment Amount</label>
                    <HelpTooltip content={TradingTooltips.investmentAmount.content} title={TradingTooltips.investmentAmount.title} />
                  </div>
                  <div className="relative">
                    <span className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400 text-sm">$</span>
                    <input
                      type="number"
                      min={1}
                      value={gridConfig.investmentAmount}
                      onChange={(e) => setGridConfig((p) => ({ ...p, investmentAmount: Number(e.target.value) }))}
                      onBlur={() => setTouchedFields((p) => ({ ...p, investmentAmount: true }))}
                      className={`w-full pl-7 pr-3 py-2 text-sm border rounded-lg bg-white dark:bg-gray-800 focus:outline-none focus:ring-2 focus:border-transparent ${
                        formErrors.investmentAmount && touchedFields.investmentAmount
                          ? 'border-red-500 focus:ring-red-500'
                          : 'border-gray-200 dark:border-gray-700 focus:ring-purple-500'
                      }`}
                    />
                  </div>
                  <div className="flex justify-between items-center mt-1">
                    <p className="text-[10px] text-gray-400">${perGridInvestment.toFixed(2)} per grid level</p>
                    {freeQuoteBalance > 0 && (
                      <p className={`text-[10px] ${hasEnoughBalance ? 'text-green-500' : 'text-red-500'}`}>
                        Balance: {freeQuoteBalance.toLocaleString(undefined, { maximumFractionDigits: 2 })} {quoteCurrency}
                      </p>
                    )}
                  </div>
                  {formErrors.investmentAmount && touchedFields.investmentAmount && (
                    <p className="text-[10px] text-red-500 mt-1">{formErrors.investmentAmount}</p>
                  )}
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
            <div className="flex-1 overflow-y-auto p-4 md:p-6 bg-gray-50 dark:bg-gray-950">
              <div className="flex items-center gap-2 mb-4">
                <div className="p-1 bg-purple-100 dark:bg-purple-900/40 rounded">
                  <BarChart2 className="w-3.5 h-3.5 text-purple-600" />
                </div>
                <p className="text-xs font-semibold text-gray-500 uppercase tracking-wider">Grid Preview</p>
              </div>
              <div className="max-w-full md:max-w-md">
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
