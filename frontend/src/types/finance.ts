// Finance Types for Personal Finance Management

// ============================================
// Account Types
// ============================================

export type AccountType = 
  | 'checking' 
  | 'savings' 
  | 'credit_card' 
  | 'cash' 
  | 'wallet' 
  | 'investment' 
  | 'loan';

export interface FinanceAccount {
  id: string;
  userId: string;
  name: string;
  type: AccountType;
  institution?: string;
  accountNumber?: string;
  currency: string;
  balance: number;
  creditLimit?: number;
  interestRate?: number;
  color?: string;
  icon?: string;
  isActive: boolean;
  includeInNetWorth: boolean;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateAccountRequest {
  name: string;
  type: AccountType;
  institution?: string;
  accountNumber?: string;
  currency: string;
  balance: number;
  creditLimit?: number;
  interestRate?: number;
  color?: string;
  icon?: string;
  includeInNetWorth?: boolean;
  notes?: string;
}

// ============================================
// Category Types
// ============================================

export type CategoryType = 'income' | 'expense' | 'transfer';

export interface FinanceCategory {
  id: string;
  userId: string;
  name: string;
  type: CategoryType;
  parentId?: string;
  color?: string;
  icon?: string;
  budgetAmount: number;
  isSystem: boolean;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// Transaction Types
// ============================================

export type TransactionType = 'income' | 'expense' | 'transfer';

export interface FinanceTransaction {
  id: string;
  userId: string;
  accountId: string;
  categoryId?: string;
  type: TransactionType;
  amount: number;
  currency: string;
  description?: string;
  payee?: string;
  date: string;
  isRecurring: boolean;
  recurringId?: string;
  tags?: string[];
  attachments?: string[];
  latitude?: number;
  longitude?: number;
  locationName?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateTransactionRequest {
  accountId: string;
  categoryId?: string;
  type: TransactionType;
  amount: number;
  currency?: string;
  description?: string;
  payee?: string;
  date?: string;
  isRecurring?: boolean;
  tags?: string[];
  latitude?: number;
  longitude?: number;
  locationName?: string;
}

// ============================================
// Budget Types
// ============================================

export type BudgetPeriod = 'weekly' | 'monthly' | 'yearly';

export interface FinanceBudget {
  id: string;
  userId: string;
  name: string;
  categoryId?: string;
  amount: number;
  currency: string;
  period: BudgetPeriod;
  startDate: string;
  endDate?: string;
  isActive: boolean;
  alertThreshold: number;
  createdAt: string;
  updatedAt: string;
}

export interface CreateBudgetRequest {
  name: string;
  categoryId?: string;
  amount: number;
  currency?: string;
  period: BudgetPeriod;
  startDate?: string;
  endDate?: string;
  alertThreshold?: number;
}

export interface BudgetStatus {
  budgetId: string;
  budgetName: string;
  budgetAmount: number;
  spentAmount: number;
  remaining: number;
  percentUsed: number;
  isOverBudget: boolean;
}

// ============================================
// Goal Types
// ============================================

export type GoalType = 'savings' | 'debt_payoff' | 'investment' | 'emergency_fund' | 'custom';
export type GoalPriority = 'low' | 'medium' | 'high';
export type GoalStatus = 'active' | 'completed' | 'paused' | 'cancelled';

export interface FinanceGoal {
  id: string;
  userId: string;
  name: string;
  type: GoalType;
  targetAmount: number;
  currentAmount: number;
  currency: string;
  targetDate?: string;
  monthlyContribution: number;
  priority: GoalPriority;
  status: GoalStatus;
  color?: string;
  icon?: string;
  notes?: string;
  createdAt: string;
  updatedAt: string;
}

export interface CreateGoalRequest {
  name: string;
  type: GoalType;
  targetAmount: number;
  currentAmount?: number;
  currency?: string;
  targetDate?: string;
  monthlyContribution?: number;
  priority?: GoalPriority;
  color?: string;
  icon?: string;
  notes?: string;
}

export interface GoalProgress {
  goalId: string;
  goalName: string;
  targetAmount: number;
  currentAmount: number;
  progress: number;
  daysRemaining: number;
  onTrack: boolean;
}

// ============================================
// Asset Types
// ============================================

export type AssetType = 'real_estate' | 'vehicle' | 'jewelry' | 'collectibles' | 'business' | 'other';

export interface FinanceAsset {
  id: string;
  userId: string;
  name: string;
  type: AssetType;
  description?: string;
  purchasePrice: number;
  currentValue: number;
  currency: string;
  purchaseDate?: string;
  location?: string;
  documents?: string[];
  isActive: boolean;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// Liability Types
// ============================================

export type LiabilityType = 'mortgage' | 'car_loan' | 'student_loan' | 'credit_card' | 'personal_loan' | 'other';
export type InterestType = 'fixed' | 'variable';
export type LiabilityStatus = 'active' | 'paid_off' | 'defaulted';

export interface FinanceLiability {
  id: string;
  userId: string;
  name: string;
  type: LiabilityType;
  lender?: string;
  originalAmount: number;
  currentBalance: number;
  currency: string;
  interestRate?: number;
  interestType?: InterestType;
  minimumPayment?: number;
  dueDate?: number;
  startDate?: string;
  endDate?: string;
  status: LiabilityStatus;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// Subscription Types
// ============================================

export type BillingCycle = 'weekly' | 'monthly' | 'quarterly' | 'yearly';

export interface FinanceSubscription {
  id: string;
  userId: string;
  name: string;
  description?: string;
  amount: number;
  currency: string;
  billingCycle: BillingCycle;
  nextBillingDate?: string;
  lastBillingDate?: string;
  accountId?: string;
  categoryId?: string;
  provider?: string;
  isActive: boolean;
  reminderDays: number;
  color?: string;
  icon?: string;
  createdAt: string;
  updatedAt: string;
}

// ============================================
// Financial Diary Types
// ============================================

export type MoodType = 'great' | 'good' | 'neutral' | 'bad' | 'terrible';
export type FinancialMoodType = 'confident' | 'anxious' | 'stressed' | 'hopeful' | 'neutral';

export interface FinanceDiaryEntry {
  id: string;
  userId: string;
  date: string;
  title?: string;
  content?: string;
  mood?: MoodType;
  financialMood?: FinancialMoodType;
  spendingReflection?: string;
  savingsWins?: string;
  lessonsLearned?: string;
  tomorrowGoals?: string;
  gratitude?: string;
  totalSpent: number;
  totalEarned: number;
  tags?: string[];
  createdAt: string;
  updatedAt: string;
}

export interface CreateDiaryEntryRequest {
  date?: string;
  title?: string;
  content?: string;
  mood?: MoodType;
  financialMood?: FinancialMoodType;
  spendingReflection?: string;
  savingsWins?: string;
  lessonsLearned?: string;
  tomorrowGoals?: string;
  gratitude?: string;
  totalSpent?: number;
  totalEarned?: number;
  tags?: string[];
}

// ============================================
// Net Worth Types
// ============================================

export interface NetWorthBreakdown {
  assets: {
    accounts: number;
    investments: number;
    property: number;
    other: number;
  };
  liabilities: {
    loans: number;
    creditCards: number;
    other: number;
  };
}

export interface NetWorthHistory {
  id: number;
  userId: string;
  date: string;
  totalAssets: number;
  totalLiabilities: number;
  netWorth: number;
  breakdown?: NetWorthBreakdown;
  createdAt: string;
}

// ============================================
// Dashboard Types
// ============================================

export interface AccountBalance {
  accountId: string;
  accountName: string;
  type: string;
  balance: number;
  currency: string;
}

export interface CategorySpending {
  categoryId: string;
  categoryName: string;
  amount: number;
  percentage: number;
  color: string;
}

export interface DashboardSummary {
  netWorth: number;
  totalAssets: number;
  totalLiabilities: number;
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlySavings: number;
  savingsRate: number;
  accountBalances: AccountBalance[];
  recentTransactions: FinanceTransaction[];
  upcomingBills: FinanceSubscription[];
  goalsProgress: GoalProgress[];
  budgetStatus: BudgetStatus[];
  spendingByCategory: CategorySpending[];
}

// ============================================
// Calculator Types
// ============================================

export interface CompoundInterestInput {
  principal: number;
  annualRate: number;
  years: number;
  compoundsPerYear: number;
  monthlyContribution: number;
}

export interface YearlyBreakdown {
  year: number;
  startBalance: number;
  contributions: number;
  interest: number;
  endBalance: number;
}

export interface CompoundInterestResult {
  futureValue: number;
  totalContributions: number;
  totalInterest: number;
  yearlyBreakdown: YearlyBreakdown[];
}

export interface LoanCalculatorInput {
  principal: number;
  annualRate: number;
  years: number;
  downPayment?: number;
}

export interface LoanPayment {
  month: number;
  payment: number;
  principal: number;
  interest: number;
  balance: number;
}

export interface LoanCalculatorResult {
  monthlyPayment: number;
  totalPayment: number;
  totalInterest: number;
  loanAmount: number;
  schedule: LoanPayment[];
}

export interface AssetAllocationResult {
  stocks: number;
  bonds: number;
  cash: number;
  realEstate?: number;
  alternative?: number;
}