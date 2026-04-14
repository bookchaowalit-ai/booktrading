/**
 * Paper Trading Page - Simplified, Real API Only
 * Practice trading with virtual money
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  Target,
  BarChart3,
  RefreshCw,
  RotateCcw,
  DollarSign,
  Percent,
  Activity,
  PlusCircle,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';
const STRATEGY_URL = process.env.NEXT_PUBLIC_STRATEGY_URL || '/strategy-api';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function PaperTradingPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning } = useToast();

  const [portfolio, setPortfolio] = useState<any>(null);
  const [orders, setOrders] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [orderForm, setOrderForm] = useState({
    symbol: '',
    side: 'BUY' as 'BUY' | 'SELL',
    quantity: '',
    price: '',
  });

  const loadPortfolio = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${STRATEGY_URL}/api/paper/portfolio`, {
        headers: authHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setPortfolio(data);
      } else {
        setPortfolio(null);
      }
    } catch {
      setPortfolio(null);
    } finally {
      setLoading(false);
    }
  }, []);

  const loadOrders = useCallback(async () => {
    try {
      const response = await fetch(`${STRATEGY_URL}/api/paper/history`, {
        headers: authHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setOrders(Array.isArray(data) ? data : []);
      }
    } catch {
      setOrders([]);
    }
  }, []);

  useEffect(() => {
    loadPortfolio();
    loadOrders();
  }, [loadPortfolio, loadOrders]);

  const placeOrder = async () => {
    if (!orderForm.symbol || !orderForm.quantity || !orderForm.price) {
      warning('Please fill in all fields');
      return;
    }

    try {
      const response = await fetch(`${STRATEGY_URL}/api/paper/order`, {
        method: 'POST',
        headers: authHeaders(),
        body: JSON.stringify({
          symbol: orderForm.symbol.toUpperCase(),
          side: orderForm.side,
          quantity: parseFloat(orderForm.quantity),
          limit_price: parseFloat(orderForm.price),
        }),
      });

      if (!response.ok) throw new Error('Failed to place order');

      success(`${orderForm.side} order placed for ${orderForm.symbol}`);
      setOrderForm({ symbol: '', side: 'BUY', quantity: '', price: '' });
      loadPortfolio();
      loadOrders();
    } catch (err: any) {
      showError(err.message || 'Failed to place order');
    }
  };

  const resetPortfolio = async () => {
    if (!confirm('Reset paper trading portfolio?')) return;
    try {
      const response = await fetch(`${STRATEGY_URL}/api/paper/reset`, {
        method: 'POST',
        headers: authHeaders(),
      });
      if (!response.ok) throw new Error('Failed to reset portfolio');
      success('Portfolio reset complete');
      loadPortfolio();
      loadOrders();
    } catch (err: any) {
      showError(err.message || 'Failed to reset portfolio');
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading paper trading...</p>
        </div>
      </div>
    );
  }

  if (!portfolio) {
    return (
      <EmptyState
        icon={<Wallet className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
        title="Paper Trading Not Available"
        description="Paper trading requires strategy service to be running"
        action={{ label: "Go to Live Trading", onClick: () => window.location.href = '/th/dashboard/trading' }}
      />
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Paper Trading</h1>
          <p className="text-gray-500 dark:text-gray-400">Practice trading with virtual money</p>
        </div>
        <div className="flex gap-2">
          <Button variant="ghost" onClick={() => { loadPortfolio(); loadOrders(); }} leftIcon={<RefreshCw className="w-4 h-4" />}>
            Refresh
          </Button>
          <Button variant="danger" onClick={resetPortfolio} leftIcon={<RotateCcw className="w-4 h-4" />}>
            Reset
          </Button>
        </div>
      </div>

      {/* Portfolio Summary */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Initial Balance</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            ${portfolio.initial_balance?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Current Balance</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">
            ${portfolio.current_balance?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total P&L</p>
          <p className={`text-2xl font-bold ${portfolio.total_pnl >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {portfolio.total_pnl >= 0 ? '+' : ''}${portfolio.total_pnl?.toLocaleString(undefined, { minimumFractionDigits: 2 })}
          </p>
          <p className={`text-sm ${portfolio.total_pnl_percent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
            {portfolio.total_pnl_percent >= 0 ? '+' : ''}{portfolio.total_pnl_percent?.toFixed(2)}%
          </p>
        </Card>
        <Card variant="elevated" className="p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400">Total Trades</p>
          <p className="text-2xl font-bold text-gray-900 dark:text-white">{portfolio.total_trades || 0}</p>
          <p className="text-sm text-green-600">
            Win Rate: {portfolio.win_rate?.toFixed(1) || 0}%
          </p>
        </Card>
      </div>

      {/* Order Form */}
      <Card variant="elevated" className="p-6">
        <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
          <PlusCircle className="w-5 h-5 text-purple-600" />
          Place Paper Order
        </h3>
        <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Symbol</label>
            <input
              type="text"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white uppercase"
              value={orderForm.symbol}
              onChange={(e) => setOrderForm({ ...orderForm, symbol: e.target.value })}
              placeholder="BTCUSDT"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Side</label>
            <select
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={orderForm.side}
              onChange={(e) => setOrderForm({ ...orderForm, side: e.target.value as 'BUY' | 'SELL' })}
            >
              <option value="BUY">BUY</option>
              <option value="SELL">SELL</option>
            </select>
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Quantity</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={orderForm.quantity}
              onChange={(e) => setOrderForm({ ...orderForm, quantity: e.target.value })}
              placeholder="0.001"
            />
          </div>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Price</label>
            <input
              type="number"
              className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              value={orderForm.price}
              onChange={(e) => setOrderForm({ ...orderForm, price: e.target.value })}
              placeholder="50000"
            />
          </div>
          <div className="flex items-end">
            <Button fullWidth onClick={placeOrder}>
              Place Order
            </Button>
          </div>
        </div>
      </Card>

      {/* Order History */}
      {orders.length > 0 ? (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-bold text-gray-900 dark:text-white mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-blue-600" />
            Order History
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700 text-gray-500 dark:text-gray-400">
                  <th className="text-left py-3 px-4 font-medium">Time</th>
                  <th className="text-left py-3 px-4 font-medium">Symbol</th>
                  <th className="text-center py-3 px-4 font-medium">Side</th>
                  <th className="text-right py-3 px-4 font-medium">Quantity</th>
                  <th className="text-right py-3 px-4 font-medium">Price</th>
                  <th className="text-center py-3 px-4 font-medium">Status</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order, idx) => (
                  <tr key={idx} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-3 px-4 text-gray-700 dark:text-gray-300">
                      {new Date(order.created_at || order.filled_at).toLocaleString()}
                    </td>
                    <td className="py-3 px-4 font-medium text-gray-900 dark:text-white">{order.symbol}</td>
                    <td className="py-3 px-4 text-center">
                      <Badge variant={order.side === 'BUY' ? 'success' : 'error'} size="sm">
                        {order.side}
                      </Badge>
                    </td>
                    <td className="py-3 px-4 text-right text-gray-700 dark:text-gray-300">{order.quantity}</td>
                    <td className="py-3 px-4 text-right text-gray-700 dark:text-gray-300">${order.price?.toLocaleString()}</td>
                    <td className="py-3 px-4 text-center">
                      <Badge variant={order.status === 'FILLED' ? 'success' : 'warning'} size="sm">
                        {order.status}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ) : (
        <Card variant="elevated" className="p-12 text-center">
          <BarChart3 className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No Orders Yet</h3>
          <p className="text-gray-500 dark:text-gray-400">Place your first paper trade to get started</p>
        </Card>
      )}
    </div>
  );
}
