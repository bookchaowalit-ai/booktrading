/**
 * Finance Accounts Page
 * Manage bank accounts, credit cards, wallets, etc.
 */
'use client';

import { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import { useTranslation } from '@/i18n/translations';
import { useToast } from '@/components/ui/Toast';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import Badge from '@/components/ui/Badge';
import EmptyState from '@/components/EmptyState';
import {
  Plus, Edit2, Trash2, CreditCard, Wallet, Building2,
  PiggyBank, Banknote, TrendingUp, Landmark, DollarSign,
  X, Check
} from 'lucide-react';

// Simple types to avoid import issues
interface AccountData {
  id?: string;
  name: string;
  type: string;
  institution?: string;
  accountNumber?: string;
  currency: string;
  balance: number;
  creditLimit?: number;
  interestRate?: number;
  color?: string;
  includeInNetWorth: boolean;
  notes?: string;
  created_at?: string;
  updated_at?: string;
}

const ACCOUNT_TYPES = [
  { value: 'checking', label: 'Checking', icon: <Banknote className="w-5 h-5" /> },
  { value: 'savings', label: 'Savings', icon: <PiggyBank className="w-5 h-5" /> },
  { value: 'credit_card', label: 'Credit Card', icon: <CreditCard className="w-5 h-5" /> },
  { value: 'cash', label: 'Cash', icon: <DollarSign className="w-5 h-5" /> },
  { value: 'wallet', label: 'Wallet', icon: <Wallet className="w-5 h-5" /> },
  { value: 'investment', label: 'Investment', icon: <TrendingUp className="w-5 h-5" /> },
  { value: 'loan', label: 'Loan', icon: <Landmark className="w-5 h-5" /> },
];

const ACCOUNT_COLORS = ['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#EC4899', '#14B8A6'];

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return base;
}

export default function AccountsPage() {
  const { t } = useTranslation();
  const { success, error: showError, warning } = useToast();
  const router = useRouter();
  const pathname = usePathname();
  const locale = pathname?.split('/')[1] || 'th';

  const [accounts, setAccounts] = useState<AccountData[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [editingAccount, setEditingAccount] = useState<AccountData | null>(null);
  const [hasError, setHasError] = useState(false);

  const [formData, setFormData] = useState({
    name: '',
    type: 'checking',
    institution: '',
    accountNumber: '',
    currency: 'THB',
    balance: 0,
    creditLimit: 0,
    interestRate: 0,
    color: ACCOUNT_COLORS[0],
    includeInNetWorth: true,
    notes: '',
  });

  useEffect(() => {
    loadAccounts();
  }, []);

  const loadAccounts = async () => {
    try {
      setLoading(true);
      const response = await fetch(`${API_BASE_URL}/api/finance/accounts`, {
        headers: authHeaders(),
      });
      if (!response.ok) {
        // Endpoint may not exist yet - show empty state
        setAccounts([]);
        return;
      }
      const data = await response.json();
      setAccounts(Array.isArray(data) ? data : []);
    } catch (err) {
      // API not available - show empty state
      setAccounts([]);
    } finally {
      setLoading(false);
    }
  };

  const openNewAccount = () => {
    setEditingAccount(null);
    setFormData({
      name: '',
      type: 'checking',
      institution: '',
      accountNumber: '',
      currency: 'THB',
      balance: 0,
      creditLimit: 0,
      interestRate: 0,
      color: ACCOUNT_COLORS[accounts.length % ACCOUNT_COLORS.length],
      includeInNetWorth: true,
      notes: '',
    });
    setShowModal(true);
  };

  const openEditAccount = (account: AccountData) => {
    setEditingAccount(account);
    setFormData({
      name: account.name || '',
      type: account.type || 'checking',
      institution: account.institution || '',
      accountNumber: account.accountNumber || '',
      currency: account.currency || 'THB',
      balance: account.balance || 0,
      creditLimit: account.creditLimit || 0,
      interestRate: account.interestRate || 0,
      color: account.color || ACCOUNT_COLORS[0],
      includeInNetWorth: account.includeInNetWorth ?? true,
      notes: account.notes || '',
    });
    setShowModal(true);
  };

  const handleSave = async () => {
    if (!formData.name) {
      warning('Account name is required');
      return;
    }

    try {
      // For now, just store locally - backend endpoint may not exist
      const newAccount: AccountData = {
        id: editingAccount?.id || `acc_${Date.now()}`,
        ...formData,
        creditLimit: formData.type === 'credit_card' ? formData.creditLimit : undefined,
        interestRate: formData.interestRate || undefined,
      };

      if (editingAccount) {
        // Update existing
        setAccounts(accounts.map(a => a.id === editingAccount.id ? { ...a, ...formData } : a));
        success('Account updated');
      } else {
        // Add new
        setAccounts([...accounts, newAccount]);
        success('Account added');
      }
      setShowModal(false);
    } catch (err: any) {
      showError(err.message || 'Failed to save account');
    }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Are you sure you want to delete this account?')) return;
    try {
      setAccounts(accounts.filter(a => a.id !== id));
      success('Account deleted');
    } catch (err: any) {
      showError(err.message || 'Failed to delete account');
    }
  };

  const formatCurrency = (amount: number, currency: string = 'THB') => {
    try {
      return new Intl.NumberFormat('th-TH', {
        style: 'currency',
        currency,
        minimumFractionDigits: 0,
      }).format(amount);
    } catch {
      return `${amount.toLocaleString()} ${currency}`;
    }
  };

  const totalBalance = accounts
    .filter(a => a.includeInNetWorth)
    .reduce((sum, a) => {
      if (a.type === 'credit_card' || a.type === 'loan') {
        return sum - (a.balance || 0);
      }
      return sum + (a.balance || 0);
    }, 0);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">Loading accounts...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Accounts</h1>
          <p className="text-gray-500 dark:text-gray-400">Manage your bank accounts, credit cards, and wallets</p>
        </div>
        <Button onClick={openNewAccount} leftIcon={<Plus className="w-4 h-4" />}>
          Add Account
        </Button>
      </div>

      {/* Summary */}
      {accounts.length > 0 && (
        <Card variant="elevated" className="p-6">
          <div className="flex items-center gap-4">
            <div className="p-4 bg-purple-100 dark:bg-purple-900/30 rounded-xl">
              <Wallet className="w-8 h-8 text-purple-600" />
            </div>
            <div>
              <p className="text-sm text-gray-500 dark:text-gray-400">Net Balance</p>
              <p className={`text-3xl font-bold ${totalBalance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(totalBalance)}
              </p>
            </div>
          </div>
        </Card>
      )}

      {/* Accounts Grid */}
      {accounts.length === 0 ? (
        <Card variant="elevated" className="p-12 text-center">
          <Building2 className="w-16 h-16 mx-auto mb-4 text-gray-300 dark:text-gray-600" />
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">No accounts yet</h3>
          <p className="text-gray-500 dark:text-gray-400 mb-4">Add your first bank account, credit card, or wallet</p>
          <Button onClick={openNewAccount} leftIcon={<Plus className="w-4 h-4" />}>
            Add Account
          </Button>
        </Card>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {accounts.map((account) => (
            <Card key={account.id} variant="elevated" className="p-4 relative overflow-hidden">
              <div
                className="absolute top-0 left-0 w-1 h-full"
                style={{ backgroundColor: account.color || ACCOUNT_COLORS[0] }}
              />
              <div className="pl-3">
                <div className="flex items-start justify-between mb-3">
                  <div className="flex items-center gap-3">
                    <div
                      className="p-2 rounded-lg"
                      style={{ backgroundColor: `${account.color || ACCOUNT_COLORS[0]}20` }}
                    >
                      <span style={{ color: account.color || ACCOUNT_COLORS[0] }}>
                        {ACCOUNT_TYPES.find(t => t.value === account.type)?.icon || <Banknote className="w-5 h-5" />}
                      </span>
                    </div>
                    <div>
                      <h3 className="font-semibold text-gray-900 dark:text-white">{account.name}</h3>
                      <p className="text-sm text-gray-500 capitalize">{account.type?.replace('_', ' ')}</p>
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button
                      onClick={() => openEditAccount(account)}
                      className="p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 rounded"
                    >
                      <Edit2 className="w-4 h-4" />
                    </button>
                    <button
                      onClick={() => account.id && handleDelete(account.id)}
                      className="p-1.5 text-gray-400 hover:text-red-500 rounded"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>

                <div className="mb-2">
                  <p className={`text-2xl font-bold ${account.type === 'credit_card' || account.type === 'loan'
                    ? (account.balance >= 0 ? 'text-green-600' : 'text-red-600')
                    : 'text-gray-900 dark:text-white'
                    }`}>
                    {formatCurrency(account.balance || 0, account.currency)}
                  </p>
                  {account.institution && (
                    <p className="text-xs text-gray-500">{account.institution}</p>
                  )}
                </div>

                {account.type === 'credit_card' && account.creditLimit && (
                  <div className="mt-2">
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                      <span>Credit Used</span>
                      <span>{((account.balance / account.creditLimit) * 100).toFixed(0)}%</span>
                    </div>
                    <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-purple-500 rounded-full"
                        style={{ width: `${Math.min(((account.balance || 0) / account.creditLimit) * 100, 100)}%` }}
                      />
                    </div>
                    <p className="text-xs text-gray-500 mt-1">
                      Limit: {formatCurrency(account.creditLimit, account.currency)}
                    </p>
                  </div>
                )}

                {!account.includeInNetWorth && (
                  <p className="text-xs text-gray-400 mt-2 italic">Excluded from net worth</p>
                )}
              </div>
            </Card>
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
          <div className="bg-white dark:bg-gray-800 rounded-2xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            {/* Modal Header */}
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-lg font-bold text-gray-900 dark:text-white">
                {editingAccount ? 'Edit Account' : 'Add Account'}
              </h2>
              <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal Content */}
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account Name *</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Main Checking"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Account Type</label>
                <div className="grid grid-cols-2 gap-2">
                  {ACCOUNT_TYPES.map((accType) => (
                    <button
                      key={accType.value}
                      type="button"
                      className={`flex items-center gap-2 p-3 rounded-lg border-2 transition-colors ${formData.type === accType.value
                        ? 'border-purple-500 bg-purple-50 dark:bg-purple-900/30'
                        : 'border-gray-200 dark:border-gray-600 hover:border-purple-300'
                        }`}
                      onClick={() => setFormData({ ...formData, type: accType.value })}
                    >
                      {accType.icon}
                      <span className="text-sm">{accType.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Institution</label>
                <input
                  type="text"
                  className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                  value={formData.institution}
                  onChange={(e) => setFormData({ ...formData, institution: e.target.value })}
                  placeholder="e.g. Bangkok Bank"
                />
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Balance</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.balance}
                    onChange={(e) => setFormData({ ...formData, balance: parseFloat(e.target.value) || 0 })}
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Currency</label>
                  <select
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.currency}
                    onChange={(e) => setFormData({ ...formData, currency: e.target.value })}
                  >
                    <option value="THB">THB</option>
                    <option value="USD">USD</option>
                    <option value="EUR">EUR</option>
                  </select>
                </div>
              </div>

              {formData.type === 'credit_card' && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">Credit Limit</label>
                  <input
                    type="number"
                    className="w-full px-3 py-2 border dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                    value={formData.creditLimit}
                    onChange={(e) => setFormData({ ...formData, creditLimit: parseFloat(e.target.value) || 0 })}
                  />
                </div>
              )}

              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="includeInNetWorth"
                  checked={formData.includeInNetWorth}
                  onChange={(e) => setFormData({ ...formData, includeInNetWorth: e.target.checked })}
                  className="w-4 h-4 rounded"
                />
                <label htmlFor="includeInNetWorth" className="text-sm text-gray-700 dark:text-gray-300">
                  Include in net worth
                </label>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="flex justify-end gap-3 p-6 border-t border-gray-200 dark:border-gray-700">
              <Button variant="ghost" onClick={() => setShowModal(false)}>Cancel</Button>
              <Button onClick={handleSave} leftIcon={<Check className="w-4 h-4" />}>
                {editingAccount ? 'Update' : 'Add'} Account
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
