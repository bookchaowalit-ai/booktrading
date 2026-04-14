/**
 * Finance API service for personal finance management
 */
import {
  FinanceAccount,
  CreateAccountRequest,
  FinanceCategory,
  FinanceTransaction,
  CreateTransactionRequest,
  FinanceBudget,
  CreateBudgetRequest,
  BudgetStatus,
  FinanceGoal,
  CreateGoalRequest,
  GoalProgress,
  FinanceAsset,
  FinanceLiability,
  FinanceSubscription,
  FinanceDiaryEntry,
  CreateDiaryEntryRequest,
  NetWorthHistory,
  DashboardSummary,
  CompoundInterestInput,
  CompoundInterestResult,
  LoanCalculatorInput,
  LoanCalculatorResult,
  AssetAllocationResult,
} from '@/types/finance';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '';

function authHeaders(extra?: Record<string, string>): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('auth_token') : null;
  const base: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) base['Authorization'] = `Bearer ${token}`;
  return { ...base, ...extra };
}

async function handleResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const error = await response.json().catch(() => ({ error: 'Request failed' }));
    throw new Error(error.error || `HTTP ${response.status}`);
  }
  return response.json();
}

export const financeApi = {
  // ============================================
  // Dashboard
  // ============================================

  async getDashboard(): Promise<DashboardSummary> {
    const response = await fetch(`${API_BASE_URL}/api/finance/dashboard`, {
      headers: authHeaders(),
    });
    return handleResponse<DashboardSummary>(response);
  },

  // ============================================
  // Accounts
  // ============================================

  async getAccounts(): Promise<FinanceAccount[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/accounts`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceAccount[]>(response);
  },

  async createAccount(data: CreateAccountRequest): Promise<FinanceAccount> {
    const response = await fetch(`${API_BASE_URL}/api/finance/accounts`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceAccount>(response);
  },

  async updateAccount(id: string, data: Partial<FinanceAccount>): Promise<FinanceAccount> {
    const response = await fetch(`${API_BASE_URL}/api/finance/accounts/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceAccount>(response);
  },

  async deleteAccount(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/accounts/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete account');
  },

  // ============================================
  // Transactions
  // ============================================

  async getTransactions(params?: {
    limit?: number;
    offset?: number;
    start?: string;
    end?: string;
  }): Promise<FinanceTransaction[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());
    if (params?.start) query.set('start', params.start);
    if (params?.end) query.set('end', params.end);

    const response = await fetch(`${API_BASE_URL}/api/finance/transactions?${query}`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceTransaction[]>(response);
  },

  async createTransaction(data: CreateTransactionRequest): Promise<FinanceTransaction> {
    const response = await fetch(`${API_BASE_URL}/api/finance/transactions`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceTransaction>(response);
  },

  async updateTransaction(id: string, data: Partial<FinanceTransaction>): Promise<FinanceTransaction> {
    const response = await fetch(`${API_BASE_URL}/api/finance/transactions/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceTransaction>(response);
  },

  async deleteTransaction(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/transactions/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete transaction');
  },

  // ============================================
  // Categories
  // ============================================

  async getCategories(type?: 'income' | 'expense' | 'transfer'): Promise<FinanceCategory[]> {
    const query = type ? `?type=${type}` : '';
    const response = await fetch(`${API_BASE_URL}/api/finance/categories${query}`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceCategory[]>(response);
  },

  async createCategory(data: Partial<FinanceCategory>): Promise<FinanceCategory> {
    const response = await fetch(`${API_BASE_URL}/api/finance/categories`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceCategory>(response);
  },

  // ============================================
  // Budgets
  // ============================================

  async getBudgets(): Promise<Array<{ budget: FinanceBudget; status: BudgetStatus }>> {
    const response = await fetch(`${API_BASE_URL}/api/finance/budgets`, {
      headers: authHeaders(),
    });
    return handleResponse<Array<{ budget: FinanceBudget; status: BudgetStatus }>>(response);
  },

  async createBudget(data: CreateBudgetRequest): Promise<FinanceBudget> {
    const response = await fetch(`${API_BASE_URL}/api/finance/budgets`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceBudget>(response);
  },

  async updateBudget(id: string, data: Partial<FinanceBudget>): Promise<FinanceBudget> {
    const response = await fetch(`${API_BASE_URL}/api/finance/budgets/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceBudget>(response);
  },

  async deleteBudget(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/budgets/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete budget');
  },

  // ============================================
  // Goals
  // ============================================

  async getGoals(): Promise<Array<{ goal: FinanceGoal; progress: GoalProgress }>> {
    const response = await fetch(`${API_BASE_URL}/api/finance/goals`, {
      headers: authHeaders(),
    });
    return handleResponse<Array<{ goal: FinanceGoal; progress: GoalProgress }>>(response);
  },

  async createGoal(data: CreateGoalRequest): Promise<FinanceGoal> {
    const response = await fetch(`${API_BASE_URL}/api/finance/goals`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceGoal>(response);
  },

  async updateGoal(id: string, data: Partial<FinanceGoal>): Promise<FinanceGoal> {
    const response = await fetch(`${API_BASE_URL}/api/finance/goals/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceGoal>(response);
  },

  async addToGoal(id: string, amount: number): Promise<FinanceGoal> {
    const response = await fetch(`${API_BASE_URL}/api/finance/goals/${id}/add`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ amount }),
    });
    return handleResponse<FinanceGoal>(response);
  },

  async deleteGoal(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/goals/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete goal');
  },

  // ============================================
  // Assets
  // ============================================

  async getAssets(): Promise<FinanceAsset[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/assets`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceAsset[]>(response);
  },

  async createAsset(data: Partial<FinanceAsset>): Promise<FinanceAsset> {
    const response = await fetch(`${API_BASE_URL}/api/finance/assets`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceAsset>(response);
  },

  async updateAsset(id: string, data: Partial<FinanceAsset>): Promise<FinanceAsset> {
    const response = await fetch(`${API_BASE_URL}/api/finance/assets/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceAsset>(response);
  },

  async deleteAsset(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/assets/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete asset');
  },

  // ============================================
  // Liabilities
  // ============================================

  async getLiabilities(): Promise<FinanceLiability[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/liabilities`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceLiability[]>(response);
  },

  async createLiability(data: Partial<FinanceLiability>): Promise<FinanceLiability> {
    const response = await fetch(`${API_BASE_URL}/api/finance/liabilities`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceLiability>(response);
  },

  async updateLiability(id: string, data: Partial<FinanceLiability>): Promise<FinanceLiability> {
    const response = await fetch(`${API_BASE_URL}/api/finance/liabilities/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceLiability>(response);
  },

  async makePayment(id: string, amount: number): Promise<FinanceLiability> {
    const response = await fetch(`${API_BASE_URL}/api/finance/liabilities/${id}/payment`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ amount }),
    });
    return handleResponse<FinanceLiability>(response);
  },

  async deleteLiability(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/liabilities/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete liability');
  },

  // ============================================
  // Subscriptions
  // ============================================

  async getSubscriptions(): Promise<FinanceSubscription[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/subscriptions`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceSubscription[]>(response);
  },

  async getUpcomingBills(days: number = 7): Promise<FinanceSubscription[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/subscriptions/upcoming?days=${days}`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceSubscription[]>(response);
  },

  async createSubscription(data: Partial<FinanceSubscription>): Promise<FinanceSubscription> {
    const response = await fetch(`${API_BASE_URL}/api/finance/subscriptions`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceSubscription>(response);
  },

  async updateSubscription(id: string, data: Partial<FinanceSubscription>): Promise<FinanceSubscription> {
    const response = await fetch(`${API_BASE_URL}/api/finance/subscriptions/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceSubscription>(response);
  },

  async deleteSubscription(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/subscriptions/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete subscription');
  },

  // ============================================
  // Financial Diary
  // ============================================

  async getDiaryEntries(params?: { limit?: number; offset?: number }): Promise<FinanceDiaryEntry[]> {
    const query = new URLSearchParams();
    if (params?.limit) query.set('limit', params.limit.toString());
    if (params?.offset) query.set('offset', params.offset.toString());

    const response = await fetch(`${API_BASE_URL}/api/finance/diary?${query}`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceDiaryEntry[]>(response);
  },

  async getDiaryEntryByDate(date: string): Promise<FinanceDiaryEntry> {
    const response = await fetch(`${API_BASE_URL}/api/finance/diary/date?date=${date}`, {
      headers: authHeaders(),
    });
    return handleResponse<FinanceDiaryEntry>(response);
  },

  async createDiaryEntry(data: CreateDiaryEntryRequest): Promise<FinanceDiaryEntry> {
    const response = await fetch(`${API_BASE_URL}/api/finance/diary`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceDiaryEntry>(response);
  },

  async updateDiaryEntry(id: string, data: Partial<FinanceDiaryEntry>): Promise<FinanceDiaryEntry> {
    const response = await fetch(`${API_BASE_URL}/api/finance/diary/${id}`, {
      method: 'PUT',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<FinanceDiaryEntry>(response);
  },

  async deleteDiaryEntry(id: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/finance/diary/${id}`, {
      method: 'DELETE',
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error('Failed to delete diary entry');
  },

  // ============================================
  // Net Worth
  // ============================================

  async getNetWorth(): Promise<NetWorthHistory> {
    const response = await fetch(`${API_BASE_URL}/api/finance/net-worth`, {
      headers: authHeaders(),
    });
    return handleResponse<NetWorthHistory>(response);
  },

  async getNetWorthHistory(limit: number = 12): Promise<NetWorthHistory[]> {
    const response = await fetch(`${API_BASE_URL}/api/finance/net-worth/history?limit=${limit}`, {
      headers: authHeaders(),
    });
    return handleResponse<NetWorthHistory[]>(response);
  },

  async recalculateNetWorth(): Promise<NetWorthHistory> {
    const response = await fetch(`${API_BASE_URL}/api/finance/net-worth/calculate`, {
      method: 'POST',
      headers: authHeaders(),
    });
    return handleResponse<NetWorthHistory>(response);
  },

  // ============================================
  // Financial Calculators
  // ============================================

  async calculateCompoundInterest(data: CompoundInterestInput): Promise<CompoundInterestResult> {
    const response = await fetch(`${API_BASE_URL}/api/finance/calculators/compound-interest`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<CompoundInterestResult>(response);
  },

  async calculateLoan(data: LoanCalculatorInput): Promise<LoanCalculatorResult> {
    const response = await fetch(`${API_BASE_URL}/api/finance/calculators/loan`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<LoanCalculatorResult>(response);
  },

  async calculateSavingsGoal(data: {
    targetAmount: number;
    currentAmount: number;
    monthlyContribution: number;
    annualRate: number;
  }): Promise<{ monthsToGoal: number; yearsToGoal: number }> {
    const response = await fetch(`${API_BASE_URL}/api/finance/calculators/savings-goal`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<{ monthsToGoal: number; yearsToGoal: number }>(response);
  },

  async calculateROI(data: {
    initialInvestment: number;
    finalValue: number;
  }): Promise<{ roi: number }> {
    const response = await fetch(`${API_BASE_URL}/api/finance/calculators/roi`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<{ roi: number }>(response);
  },

  async calculateAssetAllocation(data: {
    age: number;
    riskTolerance: 'low' | 'medium' | 'high';
  }): Promise<AssetAllocationResult> {
    const response = await fetch(`${API_BASE_URL}/api/finance/calculators/asset-allocation`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify(data),
    });
    return handleResponse<AssetAllocationResult>(response);
  },
};