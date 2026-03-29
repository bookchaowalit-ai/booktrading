/**
 * Grid Trading Page
 * Configure and monitor grid trading strategy with multi-asset support
 */
'use client';

import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import {
  Grid3X3,
  Settings,
  TrendingUp,
  DollarSign,
  Percent,
  Activity,
  ArrowRight,
} from 'lucide-react';
import { useTranslation } from '@/i18n/translations';
import { AssetCategory } from '@/types';
import { useToast } from '@/components/ui/Toast';
import AssetCategoryFilter from '@/components/AssetCategoryFilter';
import CategoryIcon from '@/components/CategoryIcon';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import {
  TRADING_PAIRS,
  EXCHANGE_PROVIDERS,
  getTradingPairsByCategory,
  getThaiPopularTradingPairs,
  searchTradingPairs
} from '@/config/trading-pairs';

export default function GridTradingPage() {
  const { t } = useTranslation();
  const { error, success } = useToast();
  const [isRunning, setIsRunning] = useState(false);
  const [selectedCategories, setSelectedCategories] = useState<AssetCategory[]>(
    ['crypto', 'stock', 'forex', 'commodity', 'index']
  );
  const [config, setConfig] = useState({
    symbol: 'BTCUSDT',
    category: 'crypto' as AssetCategory,
    exchange: 'bitkub' as import('@/config/trading-pairs').ExchangeProvider,
    lowerPrice: 40000,
    upperPrice: 50000,
    gridLevels: 10,
    investmentAmount: 1000,
    gridType: 'arithmetic'
  });
  const [searchQuery, setSearchQuery] = useState('');
  const [showThaiPairs, setShowThaiPairs] = useState(true);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [gridOrders, setGridOrders] = useState<any[]>([]);
  const [isLoadingOrders, setIsLoadingOrders] = useState(false);
  const [gridStats, setGridStats] = useState({
    totalProfit: 0,
    totalTrades: 0,
    profitRate: 0,
    activeOrders: 0,
  });

  // Validate configuration
  const validateConfig = () => {
    const newErrors: Record<string, string> = {};

    if (config.lowerPrice >= config.upperPrice) {
      newErrors.priceRange = '❌ Lower price must be less than upper price';
    }

    if (config.gridLevels < 2 || config.gridLevels > 100) {
      newErrors.gridLevels = '❌ Grid levels must be between 2 and 100';
    }

    if (config.investmentAmount <= 0) {
      newErrors.investment = '❌ Investment must be greater than 0';
    }

    if (config.gridLevels > 0 && config.investmentAmount / config.gridLevels < 10) {
      newErrors.investment = '❌ Investment per grid level must be at least $10';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Get available pairs based on filters
  const availablePairs = TRADING_PAIRS.filter(pair => {
    const matchesCategory = selectedCategories.includes(pair.category);
    const matchesSearch = searchQuery === '' ||
      pair.symbol.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pair.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      pair.nameTH.includes(searchQuery);
    const matchesThai = showThaiPairs ? pair.thaiPopular : true;

    return matchesCategory && matchesSearch && matchesThai;
  });

  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

  // Fetch real grid orders from backend
  useEffect(() => {
    const fetchGridOrders = async () => {
      setIsLoadingOrders(true);
      try {
        const [ordersResponse, statsResponse] = await Promise.all([
          fetch(`${API_BASE_URL}/api/orders/open`),
          fetch(`${API_BASE_URL}/api/bot/status`),
        ]);

        const ordersData = await ordersResponse.json().catch(() => ({ orders: [] }));
        const statsData = await statsResponse.json().catch(() => null);

        setGridOrders(ordersData.orders || []);

        // Update stats from real data
        if (statsData) {
          setGridStats({
            totalProfit: statsData.total_profit || 0,
            totalTrades: statsData.total_trades || 0,
            profitRate: statsData.total_trades > 0 ? ((statsData.total_profit / statsData.total_trades) * 100) : 0,
            activeOrders: ordersData.orders?.length || 0,
          });
        }
      } catch (error) {
        console.error('Failed to fetch grid orders:', error);
        setGridOrders([]);
        setGridStats({
          totalProfit: 0,
          totalTrades: 0,
          profitRate: 0,
          activeOrders: 0,
        });
      } finally {
        setIsLoadingOrders(false);
      }
    };

    if (isRunning) {
      fetchGridOrders();
      // Poll for updates every 5 seconds
      const interval = setInterval(fetchGridOrders, 5000);
      return () => clearInterval(interval);
    } else {
      setGridOrders([]);
      setGridStats({
        totalProfit: 0,
        totalTrades: 0,
        profitRate: 0,
        activeOrders: 0,
      });
    }
  }, [isRunning, config.symbol]);

  const handleCategoryToggle = (category: AssetCategory) => {
    setSelectedCategories((prev) => {
      if (prev.includes(category)) {
        return prev.filter((c) => c !== category);
      }
      return [...prev, category];
    });
  };

  const handleSelectAll = () => {
    setSelectedCategories(['crypto', 'stock', 'forex', 'commodity', 'index']);
  };

  const handleSymbolChange = (symbol: string) => {
    const category = config.category;
    setConfig({ ...config, symbol, category });

    // Auto-adjust price range based on symbol
    const symbolPrices: Record<string, number> = {
      'BTCUSDT': 45000,
      'ETHUSDT': 2500,
      'XAUUSD': 1950,
      'EURUSD': 1.08,
      'AAPL': 175,
      'SPX': 4500,
    };
    const basePrice = symbolPrices[symbol] || 100;
    setConfig(prev => ({
      ...prev,
      symbol,
      lowerPrice: basePrice * 0.8,
      upperPrice: basePrice * 1.2,
    }));
  };

  const handleStartGrid = async () => {
    // Validate configuration first
    if (!validateConfig()) {
      error('Please fix configuration errors before starting');
      return;
    }

    setIsRunning(true);
    try {
      // Call backend API to start grid trading
      const response = await fetch(`${API_BASE_URL}/api/bot/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          symbol: config.symbol,
          quantity: config.investmentAmount / config.gridLevels,
          gridLevels: config.gridLevels,
          lowerPrice: config.lowerPrice,
          upperPrice: config.upperPrice,
          investment: config.investmentAmount,
        }),
      });

      if (response.ok) {
        success('Grid trading started successfully');
      } else {
        const data = await response.json();
        error(data.error || 'Failed to start grid trading');
        setIsRunning(false);
      }
    } catch (err) {
      error('Failed to start grid trading - backend unavailable');
      setIsRunning(false);
    }
  };

  const handleStopGrid = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/bot/stop`, {
        method: 'POST',
      });

      if (response.ok) {
        success('Grid trading stopped successfully');
        setIsRunning(false);
      } else {
        error('Failed to stop grid trading');
      }
    } catch (err) {
      error('Failed to stop grid trading - backend unavailable');
      setIsRunning(false);
    }
  };

  return (
    <div>
      {/* Trading Control Banner */}
      <Card variant="elevated" className="p-6 mb-8 bg-gradient-to-r from-purple-50 to-blue-50 dark:from-purple-900/20 dark:to-blue-900/20">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Settings className="w-8 h-8 text-purple-600" />
            </div>
            <div>
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">
                Grid Trading Controls
              </h2>
              <p className="text-sm text-gray-600 dark:text-gray-400">
                Configure and start grid trading from the centralized trading page
              </p>
            </div>
          </div>
          <Button
            variant="primary"
            size="lg"
            onClick={() => window.location.href = '/dashboard/trading'}
            rightIcon={<ArrowRight className="w-5 h-5" />}
            gradient
          >
            Go to Trading Page
          </Button>
        </div>
      </Card>

      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-3">
              <Grid3X3 className="w-8 h-8 text-purple-600" />
              {t('grid.title')}
            </h1>
            <p className="text-gray-600 dark:text-gray-400">
              {t('grid.subtitle')} - View Only
            </p>
          </div>
          {/* Removed Start/Stop buttons - moved to /dashboard/trading */}
        </div>
      </div>

      {/* Status Cards */}
      <div className="grid md:grid-cols-4 gap-6 mb-8">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center gap-3 mb-2">
            <DollarSign className="w-5 h-5 text-green-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('analytics.total-profit')}</span>
          </div>
          <div className={`text-2xl font-bold ${gridStats.totalProfit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {gridStats.totalProfit >= 0 ? '+' : ''}${gridStats.totalProfit.toFixed(2)}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center gap-3 mb-2">
            <Activity className="w-5 h-5 text-blue-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('grid.grid-trades')}</span>
          </div>
          <div className="text-2xl font-bold text-blue-600">
            {gridStats.totalTrades}
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center gap-3 mb-2">
            <Percent className="w-5 h-5 text-purple-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('grid.profit-rate')}</span>
          </div>
          <div className="text-2xl font-bold text-purple-600">
            {gridStats.profitRate.toFixed(1)}%
          </div>
        </motion.div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
        >
          <div className="flex items-center gap-3 mb-2">
            <TrendingUp className="w-5 h-5 text-orange-600" />
            <span className="text-sm text-gray-600 dark:text-gray-400">{t('grid.active-orders')}</span>
          </div>
          <div className="text-2xl font-bold text-orange-600">
            {gridStats.activeOrders}
          </div>
        </motion.div>
      </div>

      {/* Category Filter */}
      <div className="mb-6">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
          Filter by Asset Category
        </h3>
        <AssetCategoryFilter
          selectedCategories={selectedCategories}
          onCategoryToggle={handleCategoryToggle}
          onSelectAll={handleSelectAll}
        />
      </div>

      <div className="grid lg:grid-cols-3 gap-6">
        {/* Configuration */}
        <div className="lg:col-span-1 space-y-6">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
          >
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              <Settings className="w-5 h-5 text-purple-600" />
              {t('grid.configuration')}
            </h2>

            <div className="space-y-4">
              {/* Search Box */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Search Trading Pair
                </label>
                <input
                  type="text"
                  placeholder="Search by symbol, name (e.g., BTC, Bitcoin, บิต)"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              {/* Thai Pairs Toggle */}
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Show Popular in Thailand
                </label>
                <button
                  onClick={() => setShowThaiPairs(!showThaiPairs)}
                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${showThaiPairs ? 'bg-purple-600' : 'bg-gray-300 dark:bg-gray-600'
                    }`}
                >
                  <span
                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${showThaiPairs ? 'translate-x-6' : 'translate-x-1'
                      }`}
                  />
                </button>
              </div>

              {/* Trading Pair Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.trading-pair')}
                </label>
                <select
                  value={config.symbol}
                  onChange={(e) => handleSymbolChange(e.target.value)}
                  className="w-full px-4 py-3 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white max-h-60 overflow-y-auto"
                >
                  {availablePairs.map((pair) => (
                    <option key={pair.symbol} value={pair.symbol}>
                      {pair.symbol} - {pair.name} {pair.nameTH && `(${pair.nameTH})`}
                    </option>
                  ))}
                </select>
                {availablePairs.length === 0 && (
                  <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                    No pairs found. Try adjusting your filters.
                  </p>
                )}
                <div className="mt-2 flex items-center gap-2">
                  <CategoryIcon category={config.category} size="sm" />
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {t(`category.${config.category}.desc`)}
                  </span>
                </div>
              </div>

              {/* Exchange Selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Exchange Provider
                </label>
                <select
                  value={config.exchange}
                  onChange={(e) => setConfig({ ...config, exchange: e.target.value as any })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  {Object.entries(EXCHANGE_PROVIDERS).map(([key, provider]) => (
                    <option key={key} value={key}>
                      {provider.name} {provider.nameTH && `- ${provider.nameTH}`}
                      {provider.thaiExchange && ' 🇹🇭'}
                    </option>
                  ))}
                </select>
                <div className="mt-2 flex items-center gap-2">
                  <a
                    href={EXCHANGE_PROVIDERS[config.exchange]?.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-purple-600 hover:text-purple-700 flex items-center gap-1"
                  >
                    Visit Exchange
                    <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                    </svg>
                  </a>
                  {EXCHANGE_PROVIDERS[config.exchange]?.thaiExchange && (
                    <span className="text-xs bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400 px-2 py-0.5 rounded">
                      Thai Exchange
                    </span>
                  )}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.lower-price')}
                </label>
                <input
                  type="number"
                  value={config.lowerPrice}
                  onChange={(e) => setConfig({ ...config, lowerPrice: parseFloat(e.target.value) })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
                {errors.priceRange && (
                  <p className="text-red-600 text-sm mt-1">{errors.priceRange}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.upper-price')}
                </label>
                <input
                  type="number"
                  value={config.upperPrice}
                  onChange={(e) => setConfig({ ...config, upperPrice: parseFloat(e.target.value) })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.levels')}
                </label>
                <input
                  type="number"
                  value={config.gridLevels}
                  onChange={(e) => setConfig({ ...config, gridLevels: parseInt(e.target.value) })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
                {errors.gridLevels && (
                  <p className="text-red-600 text-sm mt-1">{errors.gridLevels}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.investment')}
                </label>
                <input
                  type="number"
                  value={config.investmentAmount}
                  onChange={(e) => setConfig({ ...config, investmentAmount: parseFloat(e.target.value) })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
                {errors.investment && (
                  <p className="text-red-600 text-sm mt-1">{errors.investment}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  {t('grid.type')}
                </label>
                <select
                  value={config.gridType}
                  onChange={(e) => setConfig({ ...config, gridType: e.target.value })}
                  className="w-full px-4 py-2 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  <option value="arithmetic">{t('grid.arithmetic')}</option>
                  <option value="geometric">{t('grid.geometric')}</option>
                </select>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Grid Visualization */}
        <div className="lg:col-span-2">
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            className="bg-white dark:bg-gray-800 rounded-xl p-6 border border-gray-200 dark:border-gray-700"
          >
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
              {t('grid.grid-levels-table')}
              <CategoryIcon category={config.category} size="sm" />
            </h2>

            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700">
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                      {t('grid.level')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                      {t('grid.price-usdt')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                      {t('grid.buy-amount-usdt')}
                    </th>
                    <th className="text-left py-3 px-4 text-sm font-medium text-gray-500 dark:text-gray-400">
                      {t('grid.status')}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {isLoadingOrders ? (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-gray-500 dark:text-gray-400">
                        Loading real orders...
                      </td>
                    </tr>
                  ) : gridOrders.length > 0 ? (
                    gridOrders.map((order, index) => (
                      <tr
                        key={order.id || index}
                        className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
                      >
                        <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                          #{index + 1}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                          ${order.price?.toFixed(2) || '0.00'}
                        </td>
                        <td className="py-3 px-4 text-sm text-gray-900 dark:text-white">
                          ${order.quantity?.toFixed(2) || '0.00'}
                        </td>
                        <td className="py-3 px-4">
                          <span
                            className={`px-2 py-1 rounded text-xs font-medium ${order.status === 'FILLED'
                              ? 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200'
                              : order.status === 'OPEN'
                                ? 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200'
                                : 'bg-gray-100 text-gray-800 dark:bg-gray-700 dark:text-gray-200'
                              }`}
                          >
                            {order.status || 'PENDING'}
                          </span>
                        </td>
                      </tr>
                    ))
                  ) : (
                    <tr>
                      <td colSpan={4} className="py-8 text-center text-gray-500 dark:text-gray-400">
                        {isRunning
                          ? 'No active grid orders yet'
                          : 'Start grid trading to see orders'}
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  );
}
