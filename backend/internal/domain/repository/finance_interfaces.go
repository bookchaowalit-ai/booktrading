package repository

import (
	"context"
	"time"

	"trading-bot-system/backend/internal/domain/model"
)

// FinanceAccountRepository defines the interface for account persistence
type FinanceAccountRepository interface {
	Create(ctx context.Context, account *model.FinanceAccount) error
	GetByID(ctx context.Context, id string) (*model.FinanceAccount, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceAccount, error)
	GetByType(ctx context.Context, userID string, accountType model.AccountType) ([]*model.FinanceAccount, error)
	Update(ctx context.Context, account *model.FinanceAccount) error
	Delete(ctx context.Context, id string) error
	UpdateBalance(ctx context.Context, id string, amount float64, isAdd bool) error
	GetTotalBalanceByType(ctx context.Context, userID string) (map[model.AccountType]float64, error)
}

// FinanceCategoryRepository defines the interface for category persistence
type FinanceCategoryRepository interface {
	Create(ctx context.Context, category *model.FinanceCategory) error
	GetByID(ctx context.Context, id string) (*model.FinanceCategory, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceCategory, error)
	GetByType(ctx context.Context, userID string, categoryType model.CategoryType) ([]*model.FinanceCategory, error)
	GetSystemCategories(ctx context.Context) ([]*model.FinanceCategory, error)
	Update(ctx context.Context, category *model.FinanceCategory) error
	Delete(ctx context.Context, id string) error
}

// FinanceTransactionRepository defines the interface for transaction persistence
type FinanceTransactionRepository interface {
	Create(ctx context.Context, transaction *model.FinanceTransaction) error
	GetByID(ctx context.Context, id string) (*model.FinanceTransaction, error)
	GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceTransaction, error)
	GetByAccountID(ctx context.Context, accountID string, limit int) ([]*model.FinanceTransaction, error)
	GetByCategoryID(ctx context.Context, categoryID string, startDate, endDate time.Time) ([]*model.FinanceTransaction, error)
	GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.FinanceTransaction, error)
	GetByType(ctx context.Context, userID string, transactionType model.TransactionType, startDate, endDate time.Time) ([]*model.FinanceTransaction, error)
	Update(ctx context.Context, transaction *model.FinanceTransaction) error
	Delete(ctx context.Context, id string) error
	GetTotalByType(ctx context.Context, userID string, transactionType model.TransactionType, startDate, endDate time.Time) (float64, error)
	GetTotalByCategory(ctx context.Context, userID string, startDate, endDate time.Time) (map[string]float64, error)
	GetRecent(ctx context.Context, userID string, limit int) ([]*model.FinanceTransaction, error)
}

// FinanceBudgetRepository defines the interface for budget persistence
type FinanceBudgetRepository interface {
	Create(ctx context.Context, budget *model.FinanceBudget) error
	GetByID(ctx context.Context, id string) (*model.FinanceBudget, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceBudget, error)
	GetActive(ctx context.Context, userID string) ([]*model.FinanceBudget, error)
	GetByCategoryID(ctx context.Context, categoryID string) (*model.FinanceBudget, error)
	Update(ctx context.Context, budget *model.FinanceBudget) error
	Delete(ctx context.Context, id string) error
}

// FinanceGoalRepository defines the interface for goal persistence
type FinanceGoalRepository interface {
	Create(ctx context.Context, goal *model.FinanceGoal) error
	GetByID(ctx context.Context, id string) (*model.FinanceGoal, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceGoal, error)
	GetActive(ctx context.Context, userID string) ([]*model.FinanceGoal, error)
	GetByStatus(ctx context.Context, userID string, status model.GoalStatus) ([]*model.FinanceGoal, error)
	Update(ctx context.Context, goal *model.FinanceGoal) error
	UpdateProgress(ctx context.Context, id string, amount float64, isAdd bool) error
	Delete(ctx context.Context, id string) error
}

// FinanceAssetRepository defines the interface for asset persistence
type FinanceAssetRepository interface {
	Create(ctx context.Context, asset *model.FinanceAsset) error
	GetByID(ctx context.Context, id string) (*model.FinanceAsset, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceAsset, error)
	GetByType(ctx context.Context, userID string, assetType model.AssetType) ([]*model.FinanceAsset, error)
	Update(ctx context.Context, asset *model.FinanceAsset) error
	Delete(ctx context.Context, id string) error
	GetTotalValue(ctx context.Context, userID string) (float64, error)
	GetTotalValueByType(ctx context.Context, userID string) (map[model.AssetType]float64, error)
}

// FinanceLiabilityRepository defines the interface for liability persistence
type FinanceLiabilityRepository interface {
	Create(ctx context.Context, liability *model.FinanceLiability) error
	GetByID(ctx context.Context, id string) (*model.FinanceLiability, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceLiability, error)
	GetByType(ctx context.Context, userID string, liabilityType model.LiabilityType) ([]*model.FinanceLiability, error)
	GetByStatus(ctx context.Context, userID string, status model.LiabilityStatus) ([]*model.FinanceLiability, error)
	Update(ctx context.Context, liability *model.FinanceLiability) error
	UpdateBalance(ctx context.Context, id string, amount float64, isReduce bool) error
	Delete(ctx context.Context, id string) error
	GetTotalBalance(ctx context.Context, userID string) (float64, error)
	GetTotalBalanceByType(ctx context.Context, userID string) (map[model.LiabilityType]float64, error)
}

// FinanceSubscriptionRepository defines the interface for subscription persistence
type FinanceSubscriptionRepository interface {
	Create(ctx context.Context, subscription *model.FinanceSubscription) error
	GetByID(ctx context.Context, id string) (*model.FinanceSubscription, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.FinanceSubscription, error)
	GetActive(ctx context.Context, userID string) ([]*model.FinanceSubscription, error)
	GetUpcoming(ctx context.Context, userID string, days int) ([]*model.FinanceSubscription, error)
	Update(ctx context.Context, subscription *model.FinanceSubscription) error
	Delete(ctx context.Context, id string) error
	GetTotalMonthly(ctx context.Context, userID string) (float64, error)
}

// FinanceDiaryRepository defines the interface for diary persistence
type FinanceDiaryRepository interface {
	Create(ctx context.Context, entry *model.FinanceDiaryEntry) error
	GetByID(ctx context.Context, id string) (*model.FinanceDiaryEntry, error)
	GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceDiaryEntry, error)
	GetByDate(ctx context.Context, userID string, date time.Time) (*model.FinanceDiaryEntry, error)
	GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.FinanceDiaryEntry, error)
	Update(ctx context.Context, entry *model.FinanceDiaryEntry) error
	Delete(ctx context.Context, id string) error
}

// RecurringTransactionRepository defines the interface for recurring transaction persistence
type RecurringTransactionRepository interface {
	Create(ctx context.Context, recurring *model.RecurringTransaction) error
	GetByID(ctx context.Context, id string) (*model.RecurringTransaction, error)
	GetByUserID(ctx context.Context, userID string) ([]*model.RecurringTransaction, error)
	GetActive(ctx context.Context, userID string) ([]*model.RecurringTransaction, error)
	GetDueForProcessing(ctx context.Context, before time.Time) ([]*model.RecurringTransaction, error)
	Update(ctx context.Context, recurring *model.RecurringTransaction) error
	UpdateAfterProcessing(ctx context.Context, id string, lastOccurrence, nextOccurrence time.Time) error
	Delete(ctx context.Context, id string) error
}

// NetWorthHistoryRepository defines the interface for net worth history persistence
type NetWorthHistoryRepository interface {
	Create(ctx context.Context, history *model.NetWorthHistory) error
	GetByUserID(ctx context.Context, userID string, limit int) ([]*model.NetWorthHistory, error)
	GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.NetWorthHistory, error)
	GetLatest(ctx context.Context, userID string) (*model.NetWorthHistory, error)
	GetForMonth(ctx context.Context, userID string, month time.Time) (*model.NetWorthHistory, error)
	DeleteOlderThan(ctx context.Context, userID string, before time.Time) error
}

// FinanceDashboardRepository defines the interface for dashboard data aggregation
type FinanceDashboardRepository interface {
	GetDashboardSummary(ctx context.Context, userID string) (*model.DashboardSummary, error)
	GetMonthlySummary(ctx context.Context, userID string, month time.Time) (*model.DashboardSummary, error)
	GetSpendingByCategory(ctx context.Context, userID string, startDate, endDate time.Time) ([]model.CategorySpending, error)
	GetIncomeVsExpense(ctx context.Context, userID string, months int) ([]MonthlyIncomeExpense, error)
}

// MonthlyIncomeExpense represents monthly income vs expense data
type MonthlyIncomeExpense struct {
	Month     time.Time `json:"month"`
	Income    float64   `json:"income"`
	Expense   float64   `json:"expense"`
	Savings   float64   `json:"savings"`
}