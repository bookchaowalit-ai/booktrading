/**
 * DCA (Dollar Cost Averaging) Bot Page
 * Configure and manage DCA bots with automated recurring investments
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bot,
  Plus,
  Play,
  Square,
  Trash2,
  ChevronDown,
  ChevronUp,
  Clock,
  DollarSign,
  TrendingUp,
  Percent,
  Shield,
  Activity,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import { dcaApi, DCABot, DCAOrder, DCACreateRequest } from '@/services/dca';

const INTERVAL_OPTIONS = [
  { value: 15, label: '15 min' },
  { value: 30, label: '30 min' },
  { value: 60, label: '1h' },
  { value: 240, label: '4h' },
  { value: 1440, label: '1d' },
];

const SYMBOL_OPTIONS = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT'];

export default function DCABotPage() {
  const { success, error, warning } = useToast();

  const [bots, setBots] = useState<DCABot[]>([]);
  const [orders, setOrders] = useState<Record<string, DCAOrder[]>>({});
  const [expandedBotId, setExpandedBotId] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isCreating, setIsCreating] = useState(false);
  const [lastRefresh, setLastRefresh] = useState<Date | null>(null);

  // Form state
  const [form, setForm] = useState<DCACreateRequest>({
    symbol: 'BTCUSDT',
    investment_amount: 100,
    interval_minutes: 60,
    take_profit_percent: 0,
    safety_order_multiplier: 1.5,
    max_safety_orders: 3,
    price_deviation_percent: 2,
  });

  const fetchBots = useCallback(async () => {
    try {
      const data = await dcaApi.getBots();
      setBots(data);
      setLastRefresh(new Date());
    } catch (err) {
      console.error('Failed to fetch DCA bots:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchBots();
    const interval = setInterval(fetchBots, 15000);
    return () => clearInterval(interval);
  }, [fetchBots]);

  const handleCreateBot = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsCreating(true);
    try {
      await dcaApi.createBot(form);
      success('DCA bot created successfully');
      setForm({
        symbol: 'BTCUSDT',
        investment_amount: 100,
        interval_minutes: 60,
        take_profit_percent: 0,
        safety_order_multiplier: 1.5,
        max_safety_orders: 3,
        price_deviation_percent: 2,
      });
      await fetchBots();
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to create DCA bot');
    } finally {
      setIsCreating(false);
    }
  };

  const handleStartBot = async (id: string) => {
    try {
      await dcaApi.startBot(id);
      success('DCA bot started');
      await fetchBots();
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to start bot');
    }
  };

  const handleStopBot = async (id: string) => {
    try {
      await dcaApi.stopBot(id);
      warning('DCA bot stopped');
      await fetchBots();
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to stop bot');
    }
  };

  const handleDeleteBot = async (id: string) => {
    if (!confirm('Are you sure you want to delete this DCA bot? This action cannot be undone.')) {
      return;
    }
    try {
      await dcaApi.deleteBot(id);
      success('DCA bot deleted');
      if (expandedBotId === id) setExpandedBotId(null);
      await fetchBots();
    } catch (err) {
      error(err instanceof Error ? err.message : 'Failed to delete bot');
    }
  };

  const handleExpandBot = async (id: string) => {
    if (expandedBotId === id) {
      setExpandedBotId(null);
      return;
    }
    setExpandedBotId(id);
    try {
      const botOrders = await dcaApi.getBotOrders(id);
      setOrders((prev) => ({ ...prev, [id]: botOrders }));
    } catch (err) {
      error('Failed to load bot orders');
    }
  };

  const formatInterval = (minutes: number): string => {
    if (minutes < 60) return `${minutes}m`;
    if (minutes < 1440) return `${minutes / 60}h`;
    return `${minutes / 1440}d`;
  };

  const getOrderTypeBadge = (type: string) => {
    const styles: Record<string, string> = {
      BASE: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
      SAFETY: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
      TAKE_PROFIT: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    };
    return (
      <span className={`px-2 py-0.5 rounded text-xs font-medium ${styles[type] || 'bg-gray-100 text-gray-700 dark:bg-gray-700 dark:text-gray-300'}`}>
        {type}
      </span>
    );
  };

  const getStatusBadge = (status: string) => {
    const isRunning = status === 'RUNNING';
    return (
      <span className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-medium ${
        isRunning
          ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400'
          : 'bg-gray-100 text-gray-600 dark:bg-gray-700 dark:text-gray-400'
      }`}>
        <span className={`w-1.5 h-1.5 rounded-full ${isRunning ? 'bg-green-500 animate-pulse' : 'bg-gray-400'}`} />
        {status}
      </span>
    );
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white mb-2 flex items-center gap-3">
            <Bot className="w-8 h-8 text-purple-600" />
            DCA Bot
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            Automate your investments with Dollar Cost Averaging. Set up recurring buys and let the bot handle safety orders and take profits.
          </p>
        </div>
        <div className="flex items-center gap-3 text-sm text-gray-500 dark:text-gray-400">
          {lastRefresh && (
            <span>Last refresh: {lastRefresh.toLocaleTimeString()}</span>
          )}
          <button
            onClick={fetchBots}
            className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
            title="Refresh"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Create Bot Form */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
      >
        <Card variant="elevated" gradient className="p-6">
          <div className="flex items-center gap-2 mb-6">
            <Plus className="w-5 h-5 text-purple-600" />
            <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
              Create DCA Bot
            </h2>
          </div>

          <form onSubmit={handleCreateBot}>
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
              {/* Symbol */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Trading Pair
                </label>
                <select
                  value={form.symbol}
                  onChange={(e) => setForm({ ...form, symbol: e.target.value })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  {SYMBOL_OPTIONS.map((s) => (
                    <option key={s} value={s}>{s}</option>
                  ))}
                </select>
              </div>

              {/* Investment Amount */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <span className="flex items-center gap-1.5">
                    <DollarSign className="w-4 h-4" />
                    Investment Amount (USDT)
                  </span>
                </label>
                <input
                  type="number"
                  min="1"
                  step="any"
                  value={form.investment_amount}
                  onChange={(e) => setForm({ ...form, investment_amount: parseFloat(e.target.value) || 0 })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                  required
                />
              </div>

              {/* Interval */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <span className="flex items-center gap-1.5">
                    <Clock className="w-4 h-4" />
                    Buy Interval
                  </span>
                </label>
                <select
                  value={form.interval_minutes}
                  onChange={(e) => setForm({ ...form, interval_minutes: parseInt(e.target.value) })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                >
                  {INTERVAL_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>{opt.label}</option>
                  ))}
                </select>
              </div>

              {/* Take Profit % */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <span className="flex items-center gap-1.5">
                    <TrendingUp className="w-4 h-4" />
                    Take Profit % (0 = disabled)
                  </span>
                </label>
                <input
                  type="number"
                  min="0"
                  max="100"
                  step="0.1"
                  value={form.take_profit_percent}
                  onChange={(e) => setForm({ ...form, take_profit_percent: parseFloat(e.target.value) || 0 })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              {/* Safety Order Multiplier */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <span className="flex items-center gap-1.5">
                    <Shield className="w-4 h-4" />
                    Safety Order Multiplier
                  </span>
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  step="0.1"
                  value={form.safety_order_multiplier}
                  onChange={(e) => setForm({ ...form, safety_order_multiplier: parseFloat(e.target.value) || 1 })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              {/* Max Safety Orders */}
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  Max Safety Orders
                </label>
                <input
                  type="number"
                  min="0"
                  max="20"
                  value={form.max_safety_orders}
                  onChange={(e) => setForm({ ...form, max_safety_orders: parseInt(e.target.value) || 0 })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
              </div>

              {/* Price Deviation % */}
              <div className="md:col-span-2 lg:col-span-1">
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  <span className="flex items-center gap-1.5">
                    <Percent className="w-4 h-4" />
                    Price Deviation %
                  </span>
                </label>
                <input
                  type="number"
                  min="0.1"
                  max="50"
                  step="0.1"
                  value={form.price_deviation_percent}
                  onChange={(e) => setForm({ ...form, price_deviation_percent: parseFloat(e.target.value) || 1 })}
                  className="w-full px-4 py-2.5 bg-gray-50 dark:bg-gray-700 border border-gray-300 dark:border-gray-600 rounded-lg focus:outline-none focus:ring-2 focus:ring-purple-500 text-gray-900 dark:text-white"
                />
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  Triggers safety orders when price drops this much from entry
                </p>
              </div>
            </div>

            <Button
              type="submit"
              variant="primary"
              size="lg"
              isLoading={isCreating}
              gradient
              leftIcon={<Bot className="w-5 h-5" />}
            >
              {isCreating ? 'Creating...' : 'Create DCA Bot'}
            </Button>
          </form>
        </Card>
      </motion.div>

      {/* Active Bots List */}
      <div>
        <div className="flex items-center gap-2 mb-4">
          <Activity className="w-5 h-5 text-purple-600" />
          <h2 className="text-xl font-semibold text-gray-900 dark:text-white">
            Active Bots
          </h2>
          <span className="ml-auto text-sm text-gray-500 dark:text-gray-400">
            {bots.length} bot{bots.length !== 1 ? 's' : ''}
          </span>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="flex items-center gap-3 text-gray-500 dark:text-gray-400">
              <RefreshCw className="w-5 h-5 animate-spin" />
              <span>Loading bots...</span>
            </div>
          </div>
        ) : bots.length === 0 ? (
          <Card className="p-8 text-center">
            <Bot className="w-12 h-12 text-gray-400 mx-auto mb-4" />
            <p className="text-gray-600 dark:text-gray-400">
              No DCA bots yet. Create one above to get started.
            </p>
          </Card>
        ) : (
          <div className="space-y-4">
            <AnimatePresence>
              {bots.map((bot, index) => (
                <motion.div
                  key={bot.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ delay: index * 0.05 }}
                >
                  <Card variant="elevated" hover className="p-5">
                    {/* Bot Header */}
                    <div className="flex flex-wrap items-center gap-4 mb-4">
                      <div className="flex items-center gap-3">
                        <span className="px-3 py-1 bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400 rounded-lg text-sm font-semibold">
                          {bot.symbol}
                        </span>
                        {getStatusBadge(bot.status)}
                      </div>

                      <div className="flex items-center gap-4 ml-auto">
                        <div className="flex items-center gap-1.5 text-sm text-gray-600 dark:text-gray-400">
                          <DollarSign className="w-4 h-4" />
                          <span>${bot.investment_amount.toFixed(2)} / {formatInterval(bot.interval_minutes)}</span>
                        </div>
                        <div className="text-sm text-gray-600 dark:text-gray-400">
                          Invested: <span className="font-semibold text-gray-900 dark:text-white">${bot.total_invested.toFixed(2)}</span>
                        </div>

                        {/* Action Buttons */}
                        <div className="flex items-center gap-2">
                          {bot.status === 'RUNNING' ? (
                            <Button
                              variant="danger"
                              size="sm"
                              leftIcon={<Square className="w-3.5 h-3.5" />}
                              onClick={() => handleStopBot(bot.id)}
                            >
                              Stop
                            </Button>
                          ) : (
                            <Button
                              variant="success"
                              size="sm"
                              leftIcon={<Play className="w-3.5 h-3.5" />}
                              onClick={() => handleStartBot(bot.id)}
                            >
                              Start
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            leftIcon={<Trash2 className="w-3.5 h-3.5" />}
                            onClick={() => handleDeleteBot(bot.id)}
                            className="text-red-600 hover:text-red-700 hover:bg-red-50 dark:hover:bg-red-900/20"
                          >
                            Delete
                          </Button>
                        </div>

                        {/* Expand/Collapse */}
                        <button
                          onClick={() => handleExpandBot(bot.id)}
                          className="p-2 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
                        >
                          {expandedBotId === bot.id ? (
                            <ChevronUp className="w-4 h-4 text-gray-500" />
                          ) : (
                            <ChevronDown className="w-4 h-4 text-gray-500" />
                          )}
                        </button>
                      </div>
                    </div>

                    {/* Bot Stats */}
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-4 py-3 border-t border-gray-100 dark:border-gray-700">
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Total Sold</div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          ${bot.total_sold.toFixed(2)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Position Qty</div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          {bot.current_position_qty.toFixed(6)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Avg Entry Price</div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          ${bot.avg_entry_price.toFixed(2)}
                        </div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500 dark:text-gray-400 mb-1">Safety Orders</div>
                        <div className="text-sm font-semibold text-gray-900 dark:text-white">
                          Max {bot.max_safety_orders} ({bot.price_deviation_percent}% dev, {bot.safety_order_multiplier}x)
                        </div>
                      </div>
                    </div>

                    {/* Expanded Orders Table */}
                    <AnimatePresence>
                      {expandedBotId === bot.id && (
                        <motion.div
                          initial={{ height: 0, opacity: 0 }}
                          animate={{ height: 'auto', opacity: 1 }}
                          exit={{ height: 0, opacity: 0 }}
                          transition={{ duration: 0.2 }}
                          className="overflow-hidden"
                        >
                          <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                            <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3 flex items-center gap-2">
                              <Activity className="w-4 h-4" />
                              Order History
                            </h3>

                            <div className="overflow-x-auto">
                              <table className="w-full text-sm">
                                <thead>
                                  <tr className="border-b border-gray-200 dark:border-gray-700">
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">#</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Type</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Side</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Qty</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Price</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Total</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Status</th>
                                    <th className="text-left py-2 px-3 text-xs font-medium text-gray-500 dark:text-gray-400">Date</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {!orders[bot.id] ? (
                                    <tr>
                                      <td colSpan={8} className="py-6 text-center text-gray-500 dark:text-gray-400">
                                        <RefreshCw className="w-4 h-4 animate-spin inline mr-2" />
                                        Loading orders...
                                      </td>
                                    </tr>
                                  ) : orders[bot.id]!.length === 0 ? (
                                    <tr>
                                      <td colSpan={8} className="py-6 text-center text-gray-500 dark:text-gray-400">
                                        No orders yet
                                      </td>
                                    </tr>
                                  ) : (
                                    orders[bot.id]!.map((order) => (
                                      <tr
                                        key={order.id}
                                        className="border-b border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700/50"
                                      >
                                        <td className="py-2.5 px-3 text-gray-600 dark:text-gray-400">
                                          {order.order_number}
                                        </td>
                                        <td className="py-2.5 px-3">
                                          {getOrderTypeBadge(order.order_type)}
                                        </td>
                                        <td className="py-2.5 px-3">
                                          <span className={`font-medium ${
                                            order.side === 'BUY'
                                              ? 'text-green-600 dark:text-green-400'
                                              : 'text-red-600 dark:text-red-400'
                                          }`}>
                                            {order.side}
                                          </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-gray-900 dark:text-white">
                                          {order.quantity.toFixed(6)}
                                        </td>
                                        <td className="py-2.5 px-3 text-gray-900 dark:text-white">
                                          ${order.price.toFixed(2)}
                                        </td>
                                        <td className="py-2.5 px-3 text-gray-900 dark:text-white">
                                          ${order.total.toFixed(2)}
                                        </td>
                                        <td className="py-2.5 px-3">
                                          <span className={`inline-flex items-center gap-1 text-xs ${
                                            order.status === 'FILLED'
                                              ? 'text-green-600 dark:text-green-400'
                                              : order.status === 'PENDING'
                                                ? 'text-yellow-600 dark:text-yellow-400'
                                                : 'text-gray-500 dark:text-gray-400'
                                          }`}>
                                            {order.status === 'FILLED' ? (
                                              <CheckCircle className="w-3 h-3" />
                                            ) : order.status === 'PENDING' ? (
                                              <Clock className="w-3 h-3" />
                                            ) : order.status === 'FAILED' ? (
                                              <AlertTriangle className="w-3 h-3" />
                                            ) : null}
                                            {order.status}
                                          </span>
                                        </td>
                                        <td className="py-2.5 px-3 text-gray-500 dark:text-gray-400 text-xs">
                                          {order.executed_at
                                            ? new Date(order.executed_at).toLocaleString()
                                            : new Date(order.created_at).toLocaleString()
                                          }
                                        </td>
                                      </tr>
                                    ))
                                  )}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        </motion.div>
                      )}
                    </AnimatePresence>
                  </Card>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        )}
      </div>
    </div>
  );
}
