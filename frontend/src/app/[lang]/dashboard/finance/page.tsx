'use client';

import { useEffect, useState } from 'react';
import { usePathname } from 'next/navigation';
import { useTranslation } from '@/i18n/translations';
import { financeApi } from '@/services/financeApi';
import { DashboardSummary, FinanceAccount, FinanceGoal, FinanceBudget } from '@/types/finance';
import Card from '@/components/ui/Card';
import Button from '@/components/ui/Button';
import {
  Wallet, TrendingUp, TrendingDown, PiggyBank, CreditCard,
  DollarSign, Target, Calendar, ArrowUpRight, ArrowDownRight,
  Plus, RefreshCw
} from 'lucide-react';
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, BarChart, Bar, Legend
} from 'recharts';

const COLORS = ['#8B5CF6', '#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#6366F1', '#EC4899'];

export default function FinanceDashboardPage() {
  const pathname = usePathname();
  const locale = pathname.split('/')[1] || 'th';
  const { t } = useTranslation();

  const [dashboard, setDashboard] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadDashboard();
  }, []);

  const loadDashboard = async () => {
    try {
      setLoading(true);
      const data = await financeApi.getDashboard();
      setDashboard(data);
      setError(null);
    } catch (err: any) {
      setError(err.message || t('finance.failed-load'));
    } finally {
      setLoading(false);
    }
  };

  const formatCurrency = (amount: number, currency: string = 'THB') => {
    return new Intl.NumberFormat('th-TH', {
      style: 'currency',
      currency,
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(amount);
  };

  const formatPercent = (value: number) => {
    return `${value >= 0 ? '+' : ''}${value.toFixed(1)}%`;
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[60vh]">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-purple-200 border-t-purple-600 rounded-full animate-spin mx-auto mb-4" />
          <p className="text-gray-600 dark:text-gray-400">{t('finance.loading-dashboard')}</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500 mb-4">{error}</p>
        <Button onClick={loadDashboard}>{t('finance.retry')}</Button>
      </div>
    );
  }

  if (!dashboard) return null;

  // Ensure all values are defined with safe defaults
  const netWorth = dashboard.netWorth ?? 0;
  const totalAssets = dashboard.totalAssets ?? 0;
  const totalLiabilities = dashboard.totalLiabilities ?? 0;
  const monthlyIncome = dashboard.monthlyIncome ?? 0;
  const monthlyExpenses = dashboard.monthlyExpenses ?? 0;
  const monthlySavings = dashboard.monthlySavings ?? 0;
  const savingsRate = dashboard.savingsRate ?? 0;

  // Ensure arrays are defined
  const spendingByCategory = dashboard.spendingByCategory || [];
  const goalsProgress = dashboard.goalsProgress || [];
  const budgetStatus = dashboard.budgetStatus || [];
  const accountBalances = dashboard.accountBalances || [];
  const upcomingBills = dashboard.upcomingBills || [];
  const recentTransactions = dashboard.recentTransactions || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
            {t('finance.dashboard')}
          </h1>
          <p className="text-gray-600 dark:text-gray-400">
            {t('finance.dashboard-overview')}
          </p>
        </div>
        <Button onClick={loadDashboard} variant="ghost" size="sm">
          <RefreshCw className="w-4 h-4 mr-2" />
          {t('finance.refresh')}
        </Button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Net Worth */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
              <Wallet className="w-6 h-6 text-purple-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('finance.net-worth')}</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {formatCurrency(netWorth)}
              </p>
            </div>
          </div>
        </Card>

        {/* Total Assets */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
              <TrendingUp className="w-6 h-6 text-green-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('finance.total-assets')}</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {formatCurrency(totalAssets)}
              </p>
            </div>
          </div>
        </Card>

        {/* Total Liabilities */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
              <TrendingDown className="w-6 h-6 text-red-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('finance.total-liabilities')}</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {formatCurrency(totalLiabilities)}
              </p>
            </div>
          </div>
        </Card>

        {/* Savings Rate */}
        <Card variant="elevated" className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
              <PiggyBank className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <p className="text-sm text-gray-500 dark:text-gray-400">{t('finance.savings-rate')}</p>
              <p className="text-xl font-bold text-gray-900 dark:text-white">
                {formatPercent(savingsRate)}
              </p>
            </div>
          </div>
        </Card>
      </div>

      {/* Monthly Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {t('finance.this-month')}
          </h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ArrowUpRight className="w-5 h-5 text-green-500" />
                <span className="text-gray-600 dark:text-gray-400">{t('finance.income')}</span>
              </div>
              <span className="font-semibold text-green-600">
                {formatCurrency(monthlyIncome)}
              </span>
            </div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <ArrowDownRight className="w-5 h-5 text-red-500" />
                <span className="text-gray-600 dark:text-gray-400">{t('finance.expenses')}</span>
              </div>
              <span className="font-semibold text-red-600">
                {formatCurrency(monthlyExpenses)}
              </span>
            </div>
            <div className="border-t dark:border-gray-700 pt-4">
              <div className="flex items-center justify-between">
                <span className="text-gray-600 dark:text-gray-400">{t('finance.savings')}</span>
                <span className={`font-bold ${monthlySavings >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {formatCurrency(monthlySavings)}
                </span>
              </div>
            </div>
          </div>
        </Card>

        {/* Spending by Category */}
        <Card variant="elevated" className="p-6 lg:col-span-2">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {t('finance.spending-by-category')}
          </h3>
          {spendingByCategory.length > 0 ? (
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={spendingByCategory}
                    dataKey="amount"
                    nameKey="categoryName"
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    label={({ categoryName, percentage }) => `${categoryName}: ${percentage?.toFixed(0) || 0}%`}
                  >
                    {spendingByCategory.map((entry, index) => (
                      <Cell key={`cell-${index}`} fill={entry.color || COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip formatter={(value: number) => formatCurrency(value)} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <div className="flex items-center justify-center h-64 text-gray-500">
              {t('finance.no-spending-data')}
            </div>
          )}
        </Card>
      </div>

      {/* Goals & Budgets */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Goals Progress */}
        <Card variant="elevated" className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {t('finance.goals-progress')}
            </h3>
            <a href={`/${locale}/dashboard/finance/goals`} className="text-sm text-purple-600 hover:underline">
              {t('finance.view-all')}
            </a>
          </div>
          {goalsProgress.length > 0 ? (
            <div className="space-y-4">
              {goalsProgress.slice(0, 3).map((goal) => (
                <div key={goal.goalId} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {goal.goalName}
                    </span>
                    <span className="text-sm text-gray-500">
                      {goal.progress?.toFixed(0) || 0}%
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-purple-600 rounded-full transition-all duration-300"
                      style={{ width: `${Math.min(goal.progress || 0, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>{formatCurrency(goal.currentAmount || 0)} / {formatCurrency(goal.targetAmount || 0)}</span>
                    <span>{goal.daysRemaining || 0} {t('finance.days-left')}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Target className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>{t('finance.no-active-goals')}</p>
              <a href={`/${locale}/dashboard/finance/goals`} className="text-purple-600 hover:underline text-sm">
                {t('finance.create-first-goal')}
              </a>
            </div>
          )}
        </Card>

        {/* Budget Status */}
        <Card variant="elevated" className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
              {t('finance.budget-status')}
            </h3>
            <a href={`/${locale}/dashboard/finance/budgets`} className="text-sm text-purple-600 hover:underline">
              {t('finance.view-all')}
            </a>
          </div>
          {budgetStatus.length > 0 ? (
            <div className="space-y-4">
              {budgetStatus.slice(0, 4).map((budget) => (
                <div key={budget.budgetId} className="space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium text-gray-900 dark:text-white">
                      {budget.budgetName}
                    </span>
                    <span className={`text-sm font-medium ${budget.isOverBudget ? 'text-red-600' : 'text-green-600'}`}>
                      {formatCurrency(budget.remaining || 0)} {t('finance.left')}
                    </span>
                  </div>
                  <div className="h-2 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                    <div
                      className={`h-full rounded-full transition-all duration-300 ${budget.isOverBudget ? 'bg-red-500' : 'bg-green-500'
                        }`}
                      style={{ width: `${Math.min(budget.percentUsed, 100)}%` }}
                    />
                  </div>
                  <div className="flex items-center justify-between text-xs text-gray-500">
                    <span>{formatCurrency(budget.spentAmount || 0)} {t('finance.spent')}</span>
                    <span>{formatCurrency(budget.budgetAmount || 0)} {t('finance.budget')}</span>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="text-center py-8 text-gray-500">
              <Calendar className="w-12 h-12 mx-auto mb-2 opacity-50" />
              <p>{t('finance.no-budgets-set')}</p>
              <a href={`/${locale}/dashboard/finance/budgets`} className="text-purple-600 hover:underline text-sm">
                {t('finance.create-first-budget')}
              </a>
            </div>
          )}
        </Card>
      </div>

      {/* Account Balances */}
      <Card variant="elevated" className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t('finance.account-balances')}
          </h3>
          <a href={`/${locale}/dashboard/finance/accounts`} className="text-sm text-purple-600 hover:underline">
            {t('finance.manage-accounts')}
          </a>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {accountBalances.map((account) => (
            <div
              key={account.accountId}
              className="p-4 bg-gray-50 dark:bg-gray-800 rounded-lg"
            >
              <div className="flex items-center gap-2 mb-2">
                <CreditCard className="w-4 h-4 text-gray-400" />
                <span className="text-sm text-gray-500">{account.type}</span>
              </div>
              <p className="font-semibold text-gray-900 dark:text-white">
                {account.accountName}
              </p>
              <p className={`text-lg font-bold ${account.balance >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                {formatCurrency(account.balance, account.currency)}
              </p>
            </div>
          ))}
        </div>
      </Card>

      {/* Upcoming Bills */}
      {upcomingBills.length > 0 && (
        <Card variant="elevated" className="p-6">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
            {t('finance.upcoming-bills')}
          </h3>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {upcomingBills.slice(0, 6).map((bill) => (
              <div
                key={bill.id}
                className="p-4 border dark:border-gray-700 rounded-lg"
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium text-gray-900 dark:text-white">
                    {bill.name}
                  </span>
                  <span className="text-sm text-gray-500">
                    {bill.nextBillingDate
                      ? new Date(bill.nextBillingDate).toLocaleDateString()
                      : t('finance.n-a')}
                  </span>
                </div>
                <p className="text-lg font-bold text-gray-900 dark:text-white">
                  {formatCurrency(bill.amount, bill.currency)}
                </p>
                <p className="text-xs text-gray-500">{bill.billingCycle}</p>
              </div>
            ))}
          </div>
        </Card>
      )}

      {/* Recent Transactions */}
      <Card variant="elevated" className="p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
            {t('finance.recent-transactions')}
          </h3>
          <a href={`/${locale}/dashboard/finance/transactions`} className="text-sm text-purple-600 hover:underline">
            {t('finance.view-all')}
          </a>
        </div>
        {recentTransactions.length > 0 ? (
          <div className="space-y-2">
            {recentTransactions.slice(0, 5).map((txn) => (
              <div
                key={txn.id}
                className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-800 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <div className={`p-2 rounded-full ${txn.type === 'income' ? 'bg-green-100 text-green-600' : 'bg-red-100 text-red-600'
                    }`}>
                    {txn.type === 'income' ? (
                      <ArrowUpRight className="w-4 h-4" />
                    ) : (
                      <ArrowDownRight className="w-4 h-4" />
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-gray-900 dark:text-white">
                      {txn.description || txn.payee || t('finance.transaction')}
                    </p>
                    <p className="text-sm text-gray-500">
                      {new Date(txn.date).toLocaleDateString()}
                    </p>
                  </div>
                </div>
                <span className={`font-semibold ${txn.type === 'income' ? 'text-green-600' : 'text-red-600'
                  }`}>
                  {txn.type === 'income' ? '+' : '-'}{formatCurrency(txn.amount, txn.currency)}
                </span>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-8 text-gray-500">
            {t('finance.no-transaction')}
          </div>
        )}
      </Card>
    </div>
  );
}
