/**
 * Order Tracking Component
 * Real-time grid order monitoring and management
 */
'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import Badge from '@/components/ui/Badge';
import Button from '@/components/ui/Button';
import DataTable from '@/components/ui/DataTable';
import { RefreshCw, XCircle, CheckCircle, Clock } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';

interface GridOrder {
  id: string;
  level: number;
  type: 'BUY' | 'SELL';
  price: number;
  quantity: number;
  filled: number;
  status: 'PENDING' | 'ACTIVE' | 'FILLED' | 'CANCELLED';
  pnl?: number;
  timestamp: Date;
}

interface OrderTrackingProps {
  symbol?: string;
  gridLevels?: number;
}

export default function OrderTracking({
  symbol = 'BTCUSDT',
  gridLevels = 10,
}: OrderTrackingProps) {
  const { success, error } = useToast();
  const [isRefreshing, setIsRefreshing] = useState(false);

  // Mock orders (replace with real data from backend)
  const [orders, setOrders] = useState<GridOrder[]>([
    {
      id: '1',
      level: 1,
      type: 'BUY',
      price: 49000,
      quantity: 0.1,
      filled: 0.1,
      status: 'FILLED',
      pnl: 125.50,
      timestamp: new Date(),
    },
    {
      id: '2',
      level: 2,
      type: 'BUY',
      price: 48500,
      quantity: 0.1,
      filled: 0.1,
      status: 'FILLED',
      pnl: 87.30,
      timestamp: new Date(),
    },
    {
      id: '3',
      level: 3,
      type: 'BUY',
      price: 48000,
      quantity: 0.1,
      filled: 0,
      status: 'ACTIVE',
      timestamp: new Date(),
    },
    {
      id: '4',
      level: 4,
      type: 'SELL',
      price: 49500,
      quantity: 0.1,
      filled: 0,
      status: 'PENDING',
      timestamp: new Date(),
    },
    {
      id: '5',
      level: 5,
      type: 'SELL',
      price: 50000,
      quantity: 0.1,
      filled: 0,
      status: 'PENDING',
      timestamp: new Date(),
    },
  ]);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    // TODO: Fetch real orders from backend
    setTimeout(() => {
      setIsRefreshing(false);
      success('Orders refreshed');
    }, 1000);
  };

  const handleCancelOrder = async (orderId: string) => {
    // TODO: Call backend API to cancel order
    setOrders((prev) =>
      prev.map((order) =>
        order.id === orderId
          ? { ...order, status: 'CANCELLED' as const }
          : order
      )
    );
    success('Order cancelled');
  };

  const getStatusBadge = (status: GridOrder['status']) => {
    switch (status) {
      case 'FILLED':
        return <Badge variant="success" size="sm">Filled</Badge>;
      case 'ACTIVE':
        return <Badge variant="info" size="sm">Active</Badge>;
      case 'PENDING':
        return <Badge variant="warning" size="sm">Pending</Badge>;
      case 'CANCELLED':
        return <Badge variant="default" size="sm">Cancelled</Badge>;
    }
  };

  const columns = [
    {
      key: 'level',
      header: 'Level',
      render: (order: GridOrder) => (
        <span className="font-medium">#{order.level}</span>
      ),
    },
    {
      key: 'type',
      header: 'Type',
      render: (order: GridOrder) => (
        <Badge
          variant={order.type === 'BUY' ? 'success' : 'error'}
          size="sm"
        >
          {order.type}
        </Badge>
      ),
    },
    {
      key: 'price',
      header: 'Price',
      render: (order: GridOrder) => (
        <span className="font-mono">${order.price.toFixed(2)}</span>
      ),
    },
    {
      key: 'quantity',
      header: 'Quantity',
      render: (order: GridOrder) => (
        <span className="font-mono">{order.quantity.toFixed(4)}</span>
      ),
    },
    {
      key: 'filled',
      header: 'Filled',
      render: (order: GridOrder) => (
        <div className="flex items-center gap-2">
          <span className="font-mono text-xs">
            {order.filled.toFixed(4)} / {order.quantity.toFixed(4)}
          </span>
          <div className="w-16 bg-gray-200 dark:bg-gray-700 rounded-full h-1.5">
            <div
              className="bg-purple-600 h-1.5 rounded-full"
              style={{
                width: `${(order.filled / order.quantity) * 100}%`,
              }}
            />
          </div>
        </div>
      ),
    },
    {
      key: 'pnl',
      header: 'P&L',
      render: (order: GridOrder) =>
        order.pnl !== undefined ? (
          <span
            className={`font-mono font-bold ${
              order.pnl >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {order.pnl >= 0 ? '+' : ''}${order.pnl.toFixed(2)}
          </span>
        ) : (
          <span className="text-gray-400">-</span>
        ),
    },
    {
      key: 'status',
      header: 'Status',
      render: (order: GridOrder) => getStatusBadge(order.status),
    },
    {
      key: 'actions',
      header: 'Actions',
      render: (order: GridOrder) =>
        order.status === 'ACTIVE' || order.status === 'PENDING' ? (
          <button
            onClick={() => handleCancelOrder(order.id)}
            className="text-red-600 hover:text-red-700"
            title="Cancel order"
          >
            <XCircle className="w-4 h-4" />
          </button>
        ) : order.status === 'FILLED' ? (
          <CheckCircle className="w-4 h-4 text-green-600" />
        ) : (
          <Clock className="w-4 h-4 text-gray-400" />
        ),
    },
  ];

  const activeOrders = orders.filter(
    (o) => o.status === 'ACTIVE' || o.status === 'PENDING'
  ).length;
  const filledOrders = orders.filter((o) => o.status === 'FILLED').length;
  const totalPnL = orders.reduce((sum, o) => sum + (o.pnl || 0), 0);

  return (
    <Card variant="elevated" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <RefreshCw
            className={`w-4 h-4 text-purple-600 ${
              isRefreshing ? 'animate-spin' : ''
            }`}
          />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            Grid Orders ({symbol})
          </h3>
        </div>
        <div className="flex items-center gap-3">
          <Badge variant="info" size="sm">
            {activeOrders} Active
          </Badge>
          <Badge variant="success" size="sm">
            {filledOrders} Filled
          </Badge>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            isLoading={isRefreshing}
          >
            Refresh
          </Button>
        </div>
      </div>

      {/* Order Summary */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Total Orders
          </span>
          <div className="text-lg font-bold text-gray-900 dark:text-white mt-1">
            {orders.length}
          </div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Fill Rate
          </span>
          <div className="text-lg font-bold text-purple-600 mt-1">
            {((filledOrders / orders.length) * 100).toFixed(1)}%
          </div>
        </div>
        <div className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <span className="text-xs text-gray-600 dark:text-gray-400">
            Total P&L
          </span>
          <div
            className={`text-lg font-bold mt-1 ${
              totalPnL >= 0 ? 'text-green-600' : 'text-red-600'
            }`}
          >
            {totalPnL >= 0 ? '+' : ''}${totalPnL.toFixed(2)}
          </div>
        </div>
      </div>

      {/* Orders Table */}
      <DataTable
        data={orders}
        columns={columns}
        size="sm"
        emptyMessage="No orders yet"
      />
    </Card>
  );
}
