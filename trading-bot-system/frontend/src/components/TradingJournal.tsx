/**
 * Trading Journal Component
 * Track and review your trades
 */
'use client';

import { useState } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import { BookOpen, Plus, Edit2, Trash2, Star } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';

interface TradeJournal {
  id: string;
  date: Date;
  symbol: string;
  side: 'LONG' | 'SHORT';
  entryPrice: number;
  exitPrice?: number;
  quantity: number;
  pnl: number;
  pnlPercent: number;
  notes?: string;
  screenshot?: string;
  rating?: number; // 1-5 stars
  strategy?: string;
  emotions?: string;
  lessons?: string;
}

export default function TradingJournal() {
  const { success, error } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<TradeJournal | null>(null);

  // Mock trades (replace with real data)
  const [trades, setTrades] = useState<TradeJournal[]>([
    {
      id: '1',
      date: new Date('2024-01-15'),
      symbol: 'BTCUSDT',
      side: 'LONG',
      entryPrice: 48500,
      exitPrice: 49200,
      quantity: 0.1,
      pnl: 70,
      pnlPercent: 1.44,
      notes: 'Good entry at support level',
      rating: 4,
      strategy: 'Support/Resistance',
      emotions: 'Confident',
      lessons: 'Wait for confirmation',
    },
    {
      id: '2',
      date: new Date('2024-01-14'),
      symbol: 'ETHUSDT',
      side: 'SHORT',
      entryPrice: 2650,
      exitPrice: 2680,
      quantity: 1,
      pnl: -30,
      pnlPercent: -1.13,
      notes: 'Entered too early',
      rating: 2,
      strategy: 'Breakout',
      emotions: 'Impatient',
      lessons: 'Wait for breakout confirmation',
    },
  ]);

  const handleDeleteTrade = (id: string) => {
    if (confirm('Are you sure you want to delete this trade?')) {
      setTrades((prev) => prev.filter((t) => t.id !== id));
      success('Trade deleted');
    }
  };

  const getRatingStars = (rating?: number) => {
    if (!rating) return null;
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-3 h-3 ${
              star <= rating
                ? 'fill-yellow-400 text-yellow-400'
                : 'text-gray-300'
            }`}
          />
        ))}
      </div>
    );
  };

  return (
    <Card variant="elevated" className="p-4">
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <BookOpen className="w-4 h-4 text-blue-600" />
          <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
            Trading Journal
          </h3>
        </div>
        <Button
          variant="primary"
          size="sm"
          onClick={() => setIsModalOpen(true)}
          leftIcon={<Plus className="w-4 h-4" />}
        >
          Add Trade
        </Button>
      </div>

      {/* Trades List */}
      <div className="space-y-3">
        {trades.map((trade) => (
          <div
            key={trade.id}
            className="p-3 bg-gray-50 dark:bg-gray-800/50 rounded-lg"
          >
            <div className="flex items-start justify-between mb-2">
              <div>
                <div className="flex items-center gap-2 mb-1">
                  <span className="font-bold text-gray-900 dark:text-white">
                    {trade.symbol}
                  </span>
                  <Badge
                    variant={trade.side === 'LONG' ? 'success' : 'error'}
                    size="sm"
                  >
                    {trade.side}
                  </Badge>
                  {getRatingStars(trade.rating)}
                </div>
                <div className="text-xs text-gray-600 dark:text-gray-400">
                  {trade.date.toLocaleDateString()} • Entry: $
                  {trade.entryPrice.toFixed(2)} • Exit: $
                  {trade.exitPrice?.toFixed(2)}
                </div>
              </div>
              <div className="text-right">
                <div
                  className={`text-lg font-bold ${
                    trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
                  }`}
                >
                  {trade.pnl >= 0 ? '+' : ''}${trade.pnl.toFixed(2)} (
                  {trade.pnlPercent.toFixed(2)}%)
                </div>
                <div className="text-xs text-gray-500">
                  {trade.quantity} units
                </div>
              </div>
            </div>

            {trade.notes && (
              <p className="text-xs text-gray-600 dark:text-gray-400 mb-2">
                {trade.notes}
              </p>
            )}

            <div className="flex items-center justify-between">
              <div className="flex gap-2 text-xs">
                {trade.strategy && (
                  <Badge variant="info" size="sm">
                    {trade.strategy}
                  </Badge>
                )}
                {trade.emotions && (
                  <Badge variant="warning" size="sm">
                    {trade.emotions}
                  </Badge>
                )}
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setSelectedTrade(trade)}
                  className="text-blue-600 hover:text-blue-700"
                  title="Edit"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
                <button
                  onClick={() => handleDeleteTrade(trade.id)}
                  className="text-red-600 hover:text-red-700"
                  title="Delete"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {trade.lessons && (
              <div className="mt-2 p-2 bg-blue-50 dark:bg-blue-900/10 rounded text-xs text-blue-600 dark:text-blue-400">
                <strong>Lesson:</strong> {trade.lessons}
              </div>
            )}
          </div>
        ))}

        {trades.length === 0 && (
          <div className="text-center py-8 text-sm text-gray-500 dark:text-gray-400">
            <BookOpen className="w-8 h-8 mx-auto mb-2 opacity-50" />
            <p>No trades in journal yet</p>
            <p className="text-xs mt-1">
              Add your first trade to start tracking
            </p>
          </div>
        )}
      </div>

      {/* Add/Edit Trade Modal */}
      <Modal
        isOpen={isModalOpen}
        onClose={() => {
          setIsModalOpen(false);
          setSelectedTrade(null);
        }}
        title={selectedTrade ? 'Edit Trade' : 'Add Trade'}
        size="lg"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-600 dark:text-gray-400">
            Trade journal form would go here...
          </p>
          <div className="flex justify-end gap-2">
            <Button
              variant="secondary"
              onClick={() => setIsModalOpen(false)}
              size="sm"
            >
              Cancel
            </Button>
            <Button variant="primary" size="sm">
              Save Trade
            </Button>
          </div>
        </div>
      </Modal>
    </Card>
  );
}
