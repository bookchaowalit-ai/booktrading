/**
 * Finance Budgets Page - Real API Only
 * Manage your budgets and track spending
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
  Target,
  Plus,
  X,
  Check,
  AlertTriangle,
  DollarSign,
  TrendingUp,
  Calendar,
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function FinanceBudgetsPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning } = useToast();

  const [budgets, setBudgets] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingBudget, setEditingBudget] = useState<any>(null);

  const [formData, setFormData] = useState({
    name: '',
    category: '',
    amount: 0,
    period: 'monthly',
  });

  const loadBudgets = useCallback(async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/finance/budgets`, {
        headers: authHeaders(),
      });
      if (response.ok) {
        const data = await response.json();
        setBudgets(Array.isArray(data) ? data : []);
      } else {
        setBudgets([]);
      }
    } catch {
      setBudgets([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadBudgets();
  }, [loadBudgets]);

  const openNewBudget = () => {
    setEditingBudget(null);
    setFormData({ name: '', category: '', amount: 0, period: 'monthly' });
    setShowModal(true);
  };

  const openEditBudget = (budget: any) => {
    setEditingBudget(budget);
    setFormData({
      name: budget.name || '',
      category: budget.category || '',
      amount: budget.amount || 0,
      period: budget.period || 'monthly',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formData.name || !formData.category || formData.amount <= 0) {
      warning('Please fill in all required fields');
      return;
    }

    try {
      if (editingBudget) {
        // Update existing
        setBudgets(budgets.map(b => b.id === editingBudget.id ? { ...b, ...formData } : b));
        success('Budget updated');
      } else {
        // Add new
        setBudgets([...budgets, { id: `budget_${Date.now()}`, ...formData, spent: 0 }]);
        success('Budget created');
      }
      setShowModal(false);
    } catch (err: any) {
      showError(err.message || 'Failed to save budget');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Delete this budget?')) return;
    setBudgets(budgets.filter(b => b.id !== id));
    success('Budget deleted');
  };

  const formatCurrency = (amount: number) => {
    return new Intl.NumberFormat('th-TH', {
      style: 'currency',
      currency: 'THB',
      minimumFractionDigits: 0,
    }).format(amount);
  };

  const totalBudget = budgets.reduce((sum, b) => sum + (b.amount || 0), 0);
  const totalSpent = budgets.reduce((sum, b) => sum + (b.spent || 0), 0);
  const remaining = totalBudget - totalSpent;

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading budgets...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Budgets</h1>
          <p className="text-gray-500 dark:text-gray-400">Track your spending against budgets</p>
        </div>
        <Button onClick={openNewBudget} leftIcon={<Plus className="w-4 h-4" />}>
          Add Budget
        </Button>
      </div>

      {/* Summary */}
      {budgets.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Budget</p>
            <p className="text-2xl font-bold text-gray-900 dark:text-white">{formatCurrency(totalBudget)}</p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Total Spent</p>
            <p className="text-2xl font-bold text-red-600">{formatCurrency(totalSpent)}</p>
          </Card>
          <Card variant="elevated" className="p-4">
            <p className="text-sm text-gray-500 dark:text-gray-400">Remaining</p>
            <p className={`text-2xl font-bold ${remaining >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              {formatCurrency(remaining)}
            </p>
          </Card>
        </div>
      )}

      {/* Budgets Grid */}
      {budgets.length === 0 ? (
        <EmptyState
          icon={<Target className="w-16 h-16 text-gray-300 dark:text-gray-600" />}
          title="No Budgets Yet"
          description="Create your first budget to start tracking spending"
          action={{ label: "Add Budget", onClick: openNewBudget }}
        />
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {budgets.map((budget) => {
            const spent = budget.spent || 0;
            const remaining = (budget.amount || 0) - spent;
            const percent = budget.amount > 0 ? (spent / budget.amount) * 100 : 0;
            const isOverBudget = spent > budget.amount;

            return (
              <Card key={budget.id} variant="elevated" className="p-6">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h3 className="font-bold text-gray-900 dark:text-white">{budget.name}</h3>
                    <p className="text-sm text-gray-500 capitalize">{budget.category}</p>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => openEditBudget(budget)} className="p-1.5 text-gray-400 hover:text-gray-600 rounded">
                      <Check className="w-4 h-4" />
                    </button>
                    <button onClick={() => budget.id && handleDelete(budget.id)} className="p-1.5 text-gray-400 hover:text-red-500 rounded">
                      <X className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="mb-3">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-500 dark:text-gray-400">Progress</span>
                    <span className={`font-bold ${isOverBudget ? 'text-red-600' : 'text-gray-900 dark:text-white'}`}>
                      {percent.toFixed(0)}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full ${isOverBudget ? 'bg-red-500' : 'bg-green-500'}`}
                      style={{ width: `${Math.min(percent, 100)}%` }}
                    />
                  </div>
                </div>

                <div className="flex items-center justify-between text-sm">
                  <span className="text-gray-500 dark:text-gray-400">
                    Spent: {formatCurrency(spent)}
                  </span>
                  <span className={`font-bold ${isOverBudget ? 'text-red-600' : 'text-green-600'}`}>
                    Remaining: {formatCurrency(remaining)}
                  </span>
                </div>

                {isOverBudget && (
                  <div className="mt-3 flex items-center gap-2 text-xs text-red-600 dark:text-red-400">
                    <AlertTriangle className="w-4 h-4" />
                    Over budget by {formatCurrency(Math.abs(remaining))}
                  </div>
                )}
              </Card>
            );
          })}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-md">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                {editingBudget ? 'Edit Budget' : 'Add Budget'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Name</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g., Food & Dining"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Category</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.category}
                  onChange={(e) => setFormData({ ...formData, category: e.target.value })}
                  placeholder="e.g., Food, Transport, Entertainment"
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Amount</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.amount}
                    onChange={(e) => setFormData({ ...formData, amount: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Period</label>
                  <select
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.period}
                    onChange={(e) => setFormData({ ...formData, period: e.target.value })}
                  >
                    <option value="weekly">Weekly</option>
                    <option value="monthly">Monthly</option>
                    <option value="yearly">Yearly</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <Button variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button onClick={handleSave} leftIcon={<Check className="w-4 h-4" />}>
                {editingBudget ? 'Update' : 'Create'} Budget
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
