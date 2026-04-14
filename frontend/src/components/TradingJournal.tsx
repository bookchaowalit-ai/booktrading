/**
 * Trading Journal Component
 * Track and review your trades
 */
'use client';

import { useState, useEffect, useCallback } from 'react';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import Modal from '@/components/ui/Modal';
import { BookOpen, Plus, Edit2, Trash2, Star } from 'lucide-react';
import { useToast } from '@/components/ui/Toast';
import { api } from '@/services/api';

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
  rating?: number;
  strategy?: string;
  emotions?: string;
  lessons?: string;
}

export default function TradingJournal() {
  const { success, error } = useToast();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [selectedTrade, setSelectedTrade] = useState<TradeJournal | null>(null);
  const [trades, setTrades] = useState<TradeJournal[]>([]);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);

  const fetchTrades = useCallback(async () => {
    try {
      const raw = await api.getJournalEntries();
      const mapped: TradeJournal[] = raw.map((t) => ({
        id: t.id,
        date: new Date(t.date),
        symbol: t.symbol,
        side: t.side as 'LONG' | 'SHORT',
        entryPrice: t.entryPrice,
        exitPrice: t.exitPrice,
        quantity: t.quantity,
        pnl: t.pnl,
        pnlPercent: t.pnlPercent,
        notes: t.notes,
        rating: t.rating,
        strategy: t.strategy,
        emotions: t.emotions,
        lessons: t.lessons,
      }));
      setTrades(mapped);
    } catch {
      // ignore
    }
  }, []);

  useEffect(() => {
    fetchTrades();
  }, [fetchTrades]);

  const handleDeleteTrade = async (id: string) => {
    try {
      await api.deleteJournalEntry(id);
      setTrades((prev) => prev.filter((t) => t.id !== id));
      setDeleteConfirmId(null);
      success('Trade deleted');
    } catch {
      error('Failed to delete trade');
    }
  };

  const handleSaveTrade = async (trade: Omit<TradeJournal, 'id'>) => {
    try {
      if (selectedTrade) {
        await api.updateJournalEntry(selectedTrade.id, {
          ...trade,
          date: trade.date.toISOString(),
        });
        setTrades((prev) =>
          prev.map((t) => (t.id === selectedTrade.id ? { ...trade, id: selectedTrade.id } : t))
        );
        success('Trade updated');
      } else {
        const result = await api.createJournalEntry({
          ...trade,
          date: trade.date.toISOString(),
        });
        setTrades((prev) => [{ ...trade, id: result.id }, ...prev]);
        success('Trade added');
      }
      setIsModalOpen(false);
      setSelectedTrade(null);
    } catch {
      error('Failed to save trade');
    }
  };

  const getRatingStars = (rating?: number) => {
    if (!rating) return null;
    return (
      <div className="flex gap-0.5">
        {[1, 2, 3, 4, 5].map((star) => (
          <Star
            key={star}
            className={`w-3 h-3 ${star <= rating
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
                  className={`text-lg font-bold ${trade.pnl >= 0 ? 'text-green-600' : 'text-red-600'
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
                  onClick={() => { setSelectedTrade(trade); setIsModalOpen(true); }}
                  className="text-blue-600 hover:text-blue-700"
                  title="Edit"
                  aria-label="Edit trade"
                >
                  <Edit2 className="w-3.5 h-3.5" />
                </button>
                {deleteConfirmId === trade.id ? (
                  <span className="flex items-center gap-1">
                    <span className="text-xs text-gray-500">Delete?</span>
                    <button
                      onClick={() => handleDeleteTrade(trade.id)}
                      className="text-xs text-red-600 font-semibold hover:text-red-700"
                      aria-label="Confirm delete"
                    >Yes</button>
                    <button
                      onClick={() => setDeleteConfirmId(null)}
                      className="text-xs text-gray-500 hover:text-gray-700"
                      aria-label="Cancel delete"
                    >No</button>
                  </span>
                ) : (
                  <button
                    onClick={() => setDeleteConfirmId(trade.id)}
                    className="text-red-600 hover:text-red-700"
                    title="Delete"
                    aria-label="Delete trade"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
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
        <JournalForm
          trade={selectedTrade}
          onSave={handleSaveTrade}
          onCancel={() => {
            setIsModalOpen(false);
            setSelectedTrade(null);
          }}
        />
      </Modal>
    </Card>
  );
}

interface JournalFormProps {
  trade: TradeJournal | null;
  onSave: (trade: Omit<TradeJournal, 'id'>) => void;
  onCancel: () => void;
}

function JournalForm({ trade, onSave, onCancel }: JournalFormProps) {
  const [form, setForm] = useState({
    symbol: trade?.symbol || '',
    side: trade?.side || 'LONG' as 'LONG' | 'SHORT',
    entryPrice: trade?.entryPrice || 0,
    exitPrice: trade?.exitPrice || 0,
    quantity: trade?.quantity || 0,
    pnl: trade?.pnl || 0,
    pnlPercent: trade?.pnlPercent || 0,
    notes: trade?.notes || '',
    rating: trade?.rating || 3,
    strategy: trade?.strategy || '',
    emotions: trade?.emotions || '',
    lessons: trade?.lessons || '',
    date: trade?.date || new Date(),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onSave(form);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-3">
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Symbol</label>
          <input
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.symbol}
            onChange={(e) => setForm({ ...form, symbol: e.target.value })}
            required
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Side</label>
          <select
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.side}
            onChange={(e) => setForm({ ...form, side: e.target.value as 'LONG' | 'SHORT' })}
          >
            <option value="LONG">LONG</option>
            <option value="SHORT">SHORT</option>
          </select>
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Entry Price</label>
          <input type="number" step="any"
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.entryPrice}
            onChange={(e) => setForm({ ...form, entryPrice: parseFloat(e.target.value) })}
            required
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Exit Price</label>
          <input type="number" step="any"
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.exitPrice}
            onChange={(e) => setForm({ ...form, exitPrice: parseFloat(e.target.value) })}
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Quantity</label>
          <input type="number" step="any"
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.quantity}
            onChange={(e) => setForm({ ...form, quantity: parseFloat(e.target.value) })}
            required
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">P&L ($)</label>
          <input type="number" step="any"
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.pnl}
            onChange={(e) => setForm({ ...form, pnl: parseFloat(e.target.value) })}
            required
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Strategy</label>
          <input
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.strategy}
            onChange={(e) => setForm({ ...form, strategy: e.target.value })}
          />
        </div>
        <div>
          <label className="text-xs text-gray-600 dark:text-gray-400">Emotions</label>
          <input
            className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
            value={form.emotions}
            onChange={(e) => setForm({ ...form, emotions: e.target.value })}
          />
        </div>
      </div>
      <div>
        <label className="text-xs text-gray-600 dark:text-gray-400">Notes</label>
        <textarea
          className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
          rows={2}
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
        />
      </div>
      <div>
        <label className="text-xs text-gray-600 dark:text-gray-400">Lessons Learned</label>
        <textarea
          className="w-full mt-1 px-2 py-1.5 text-sm border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-800"
          rows={2}
          value={form.lessons}
          onChange={(e) => setForm({ ...form, lessons: e.target.value })}
        />
      </div>
      <div className="flex justify-end gap-2 pt-2">
        <Button variant="secondary" onClick={onCancel} size="sm" type="button">Cancel</Button>
        <Button variant="primary" size="sm" type="submit">Save Trade</Button>
      </div>
    </form>
  );
}
