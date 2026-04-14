package model

import "time"

// ============================================
// Account Types
// ============================================

type AccountType string

const (
	AccountTypeChecking   AccountType = "checking"
	AccountTypeSavings    AccountType = "savings"
	AccountTypeCreditCard AccountType = "credit_card"
	AccountTypeCash       AccountType = "cash"
	AccountTypeWallet    AccountType = "wallet"
	AccountTypeInvestment AccountType = "investment"
	AccountTypeLoan       AccountType = "loan"
)

// FinanceAccount represents a financial account
type FinanceAccount struct {
	ID                string      `json:"id"`
	UserID            string      `json:"user_id"`
	Name              string      `json:"name"`
	Type              AccountType `json:"type"`
	Institution       string      `json:"institution,omitempty"`
	AccountNumber     string      `json:"account_number,omitempty"`
	Currency          string      `json:"currency"`
	Balance           float64     `json:"balance"`
	CreditLimit       *float64    `json:"credit_limit,omitempty"`
	InterestRate      *float64    `json:"interest_rate,omitempty"`
	Color             string      `json:"color,omitempty"`
	Icon              string      `json:"icon,omitempty"`
	IsActive          bool        `json:"is_active"`
	IncludeInNetWorth bool        `json:"include_in_net_worth"`
	Notes             string      `json:"notes,omitempty"`
	CreatedAt         time.Time   `json:"created_at"`
	UpdatedAt         time.Time   `json:"updated_at"`
}

// ============================================
// Category Types
// ============================================

type CategoryType string

const (
	CategoryTypeIncome   CategoryType = "income"
	CategoryTypeExpense  CategoryType = "expense"
	CategoryTypeTransfer CategoryType = "transfer"
)

// FinanceCategory represents a transaction category
type FinanceCategory struct {
	ID           string        `json:"id"`
	UserID       string        `json:"user_id"`
	Name         string        `json:"name"`
	Type         CategoryType  `json:"type"`
	ParentID     *string       `json:"parent_id,omitempty"`
	Color        string        `json:"color,omitempty"`
	Icon         string        `json:"icon,omitempty"`
	BudgetAmount float64       `json:"budget_amount"`
	IsSystem     bool          `json:"is_system"`
	CreatedAt    time.Time     `json:"created_at"`
	UpdatedAt    time.Time     `json:"updated_at"`
}

// ============================================
// Transaction Types
// ============================================

type TransactionType string

const (
	TransactionTypeIncome   TransactionType = "income"
	TransactionTypeExpense  TransactionType = "expense"
	TransactionTypeTransfer TransactionType = "transfer"
)

// FinanceTransaction represents a financial transaction
type FinanceTransaction struct {
	ID            string          `json:"id"`
	UserID        string          `json:"user_id"`
	AccountID     string          `json:"account_id"`
	CategoryID    *string         `json:"category_id,omitempty"`
	Type          TransactionType `json:"type"`
	Amount        float64         `json:"amount"`
	Currency      string          `json:"currency"`
	Description   string          `json:"description,omitempty"`
	Payee         string          `json:"payee,omitempty"`
	Date          time.Time       `json:"date"`
	IsRecurring   bool            `json:"is_recurring"`
	RecurringID   *string         `json:"recurring_id,omitempty"`
	Tags          []string        `json:"tags,omitempty"`
	Attachments   []string        `json:"attachments,omitempty"`
	Latitude      *float64        `json:"latitude,omitempty"`
	Longitude     *float64        `json:"longitude,omitempty"`
	LocationName  string          `json:"location_name,omitempty"`
	CreatedAt     time.Time       `json:"created_at"`
	UpdatedAt     time.Time       `json:"updated_at"`
}

// ============================================
// Budget
// ============================================

type BudgetPeriod string

const (
	BudgetPeriodWeekly  BudgetPeriod = "weekly"
	BudgetPeriodMonthly BudgetPeriod = "monthly"
	BudgetPeriodYearly  BudgetPeriod = "yearly"
)

// FinanceBudget represents a budget
type FinanceBudget struct {
	ID              string       `json:"id"`
	UserID          string       `json:"user_id"`
	Name            string       `json:"name"`
	CategoryID      *string      `json:"category_id,omitempty"`
	Amount          float64      `json:"amount"`
	Currency        string       `json:"currency"`
	Period          BudgetPeriod `json:"period"`
	StartDate       time.Time    `json:"start_date"`
	EndDate         *time.Time   `json:"end_date,omitempty"`
	IsActive        bool         `json:"is_active"`
	AlertThreshold  float64      `json:"alert_threshold"`
	CreatedAt       time.Time    `json:"created_at"`
	UpdatedAt       time.Time    `json:"updated_at"`
}

// ============================================
// Goal
// ============================================

type GoalType string
type GoalPriority string
type GoalStatus string

const (
	GoalTypeSavings        GoalType = "savings"
	GoalTypeDebtPayoff     GoalType = "debt_payoff"
	GoalTypeInvestment     GoalType = "investment"
	GoalTypeEmergencyFund  GoalType = "emergency_fund"
	GoalTypeCustom         GoalType = "custom"

	GoalPriorityLow    GoalPriority = "low"
	GoalPriorityMedium GoalPriority = "medium"
	GoalPriorityHigh   GoalPriority = "high"

	GoalStatusActive    GoalStatus = "active"
	GoalStatusCompleted  GoalStatus = "completed"
	GoalStatusPaused     GoalStatus = "paused"
	GoalStatusCancelled  GoalStatus = "cancelled"
)

// FinanceGoal represents a financial goal
type FinanceGoal struct {
	ID                 string        `json:"id"`
	UserID             string        `json:"user_id"`
	Name               string        `json:"name"`
	Type               GoalType      `json:"type"`
	TargetAmount       float64       `json:"target_amount"`
	CurrentAmount      float64       `json:"current_amount"`
	Currency           string        `json:"currency"`
	TargetDate         *time.Time    `json:"target_date,omitempty"`
	MonthlyContribution float64      `json:"monthly_contribution"`
	Priority           GoalPriority  `json:"priority"`
	Status             GoalStatus    `json:"status"`
	Color              string        `json:"color,omitempty"`
	Icon               string        `json:"icon,omitempty"`
	Notes              string        `json:"notes,omitempty"`
	CreatedAt          time.Time     `json:"created_at"`
	UpdatedAt          time.Time     `json:"updated_at"`
}

// ============================================
// Asset
// ============================================

type AssetType string

const (
	AssetTypeRealEstate  AssetType = "real_estate"
	AssetTypeVehicle     AssetType = "vehicle"
	AssetTypeJewelry     AssetType = "jewelry"
	AssetTypeCollectibles AssetType = "collectibles"
	AssetTypeBusiness    AssetType = "business"
	AssetTypeOther       AssetType = "other"
)

// FinanceAsset represents a non-trading asset
type FinanceAsset struct {
	ID            string     `json:"id"`
	UserID        string     `json:"user_id"`
	Name          string     `json:"name"`
	Type          AssetType  `json:"type"`
	Description   string     `json:"description,omitempty"`
	PurchasePrice float64    `json:"purchase_price"`
	CurrentValue  float64    `json:"current_value"`
	Currency      string     `json:"currency"`
	PurchaseDate  *time.Time `json:"purchase_date,omitempty"`
	Location      string     `json:"location,omitempty"`
	Documents     []string   `json:"documents,omitempty"`
	IsActive      bool       `json:"is_active"`
	CreatedAt     time.Time  `json:"created_at"`
	UpdatedAt     time.Time  `json:"updated_at"`
}

// ============================================
// Liability
// ============================================

type LiabilityType string
type InterestType string
type LiabilityStatus string

const (
	LiabilityTypeMortgage     LiabilityType = "mortgage"
	LiabilityTypeCarLoan      LiabilityType = "car_loan"
	LiabilityTypeStudentLoan  LiabilityType = "student_loan"
	LiabilityTypeCreditCard   LiabilityType = "credit_card"
	LiabilityTypePersonalLoan LiabilityType = "personal_loan"
	LiabilityTypeOther        LiabilityType = "other"

	InterestTypeFixed    InterestType = "fixed"
	InterestTypeVariable InterestType = "variable"

	LiabilityStatusActive    LiabilityStatus = "active"
	LiabilityStatusPaidOff   LiabilityStatus = "paid_off"
	LiabilityStatusDefaulted LiabilityStatus = "defaulted"
)

// FinanceLiability represents a debt or loan
type FinanceLiability struct {
	ID              string           `json:"id"`
	UserID          string           `json:"user_id"`
	Name            string           `json:"name"`
	Type            LiabilityType    `json:"type"`
	Lender          string           `json:"lender,omitempty"`
	OriginalAmount  float64          `json:"original_amount"`
	CurrentBalance  float64          `json:"current_balance"`
	Currency        string           `json:"currency"`
	InterestRate    *float64         `json:"interest_rate,omitempty"`
	InterestType    InterestType     `json:"interest_type,omitempty"`
	MinimumPayment  *float64         `json:"minimum_payment,omitempty"`
	DueDate         *int             `json:"due_date,omitempty"` // Day of month
	StartDate       *time.Time       `json:"start_date,omitempty"`
	EndDate         *time.Time       `json:"end_date,omitempty"`
	Status          LiabilityStatus  `json:"status"`
	CreatedAt       time.Time        `json:"created_at"`
	UpdatedAt       time.Time        `json:"updated_at"`
}

// ============================================
// Subscription
// ============================================

type BillingCycle string

const (
	BillingCycleWeekly    BillingCycle = "weekly"
	BillingCycleMonthly   BillingCycle = "monthly"
	BillingCycleQuarterly BillingCycle = "quarterly"
	BillingCycleYearly    BillingCycle = "yearly"
)

// FinanceSubscription represents a recurring subscription
type FinanceSubscription struct {
	ID              string       `json:"id"`
	UserID          string       `json:"user_id"`
	Name            string       `json:"name"`
	Description     string       `json:"description,omitempty"`
	Amount          float64      `json:"amount"`
	Currency        string       `json:"currency"`
	BillingCycle    BillingCycle `json:"billing_cycle"`
	NextBillingDate *time.Time   `json:"next_billing_date,omitempty"`
	LastBillingDate *time.Time   `json:"last_billing_date,omitempty"`
	AccountID       *string      `json:"account_id,omitempty"`
	CategoryID      *string      `json:"category_id,omitempty"`
	Provider        string       `json:"provider,omitempty"`
	IsActive        bool         `json:"is_active"`
	ReminderDays    int          `json:"reminder_days"`
	Color           string       `json:"color,omitempty"`
	Icon            string       `json:"icon,omitempty"`
	CreatedAt       time.Time    `json:"created_at"`
	UpdatedAt       time.Time    `json:"updated_at"`
}

// ============================================
// Financial Diary
// ============================================

type MoodType string
type FinancialMoodType string

const (
	MoodTypeGreat    MoodType = "great"
	MoodTypeGood     MoodType = "good"
	MoodTypeNeutral  MoodType = "neutral"
	MoodTypeBad      MoodType = "bad"
	MoodTypeTerrible MoodType = "terrible"

	FinancialMoodConfident FinancialMoodType = "confident"
	FinancialMoodAnxious   FinancialMoodType = "anxious"
	FinancialMoodStressed  FinancialMoodType = "stressed"
	FinancialMoodHopeful   FinancialMoodType = "hopeful"
	FinancialMoodNeutral   FinancialMoodType = "neutral"
)

// FinanceDiaryEntry represents a daily financial journal entry
type FinanceDiaryEntry struct {
	ID                 string            `json:"id"`
	UserID             string            `json:"user_id"`
	Date               time.Time         `json:"date"`
	Title              string            `json:"title,omitempty"`
	Content            string            `json:"content,omitempty"`
	Mood               MoodType          `json:"mood,omitempty"`
	FinancialMood      FinancialMoodType `json:"financial_mood,omitempty"`
	SpendingReflection string            `json:"spending_reflection,omitempty"`
	SavingsWins        string            `json:"savings_wins,omitempty"`
	LessonsLearned     string            `json:"lessons_learned,omitempty"`
	TomorrowGoals      string            `json:"tomorrow_goals,omitempty"`
	Gratitude          string            `json:"gratitude,omitempty"`
	TotalSpent         float64           `json:"total_spent"`
	TotalEarned        float64           `json:"total_earned"`
	Tags               []string          `json:"tags,omitempty"`
	CreatedAt          time.Time         `json:"created_at"`
	UpdatedAt          time.Time         `json:"updated_at"`
}

// ============================================
// Recurring Transaction
// ============================================

type Frequency string

const (
	FrequencyDaily     Frequency = "daily"
	FrequencyWeekly    Frequency = "weekly"
	FrequencyBiweekly  Frequency = "biweekly"
	FrequencyMonthly   Frequency = "monthly"
	FrequencyQuarterly Frequency = "quarterly"
	FrequencyYearly    Frequency = "yearly"
)

// RecurringTransaction represents a recurring transaction template
type RecurringTransaction struct {
	ID              string          `json:"id"`
	UserID          string          `json:"user_id"`
	AccountID       *string         `json:"account_id,omitempty"`
	CategoryID      *string         `json:"category_id,omitempty"`
	Type            TransactionType `json:"type"`
	Amount          float64         `json:"amount"`
	Currency        string          `json:"currency"`
	Description     string          `json:"description,omitempty"`
	Payee           string          `json:"payee,omitempty"`
	Frequency       Frequency       `json:"frequency"`
	StartDate       time.Time       `json:"start_date"`
	EndDate         *time.Time      `json:"end_date,omitempty"`
	NextOccurrence  time.Time       `json:"next_occurrence"`
	LastOccurrence  *time.Time      `json:"last_occurrence,omitempty"`
	IsActive        bool            `json:"is_active"`
	AutoCreate      bool            `json:"auto_create"`
	CreatedAt       time.Time       `json:"created_at"`
	UpdatedAt       time.Time       `json:"updated_at"`
}

// ============================================
// Net Worth History
// ============================================

// NetWorthBreakdown represents the breakdown of net worth by category
type NetWorthBreakdown struct {
	Assets struct {
		Accounts   float64 `json:"accounts"`
		Investments float64 `json:"investments"`
		Property   float64 `json:"property"`
		Other      float64 `json:"other"`
	} `json:"assets"`
	Liabilities struct {
		Loans      float64 `json:"loans"`
		CreditCards float64 `json:"credit_cards"`
		Other      float64 `json:"other"`
	} `json:"liabilities"`
}

// NetWorthHistory represents a snapshot of net worth at a point in time
type NetWorthHistory struct {
	ID               int                `json:"id"`
	UserID           string             `json:"user_id"`
	Date             time.Time          `json:"date"`
	TotalAssets      float64            `json:"total_assets"`
	TotalLiabilities float64            `json:"total_liabilities"`
	NetWorth         float64            `json:"net_worth"`
	Breakdown        *NetWorthBreakdown `json:"breakdown,omitempty"`
	CreatedAt        time.Time          `json:"created_at"`
}

// ============================================
// Request/Response Types
// ============================================

// CreateAccountRequest
type CreateAccountRequest struct {
	Name              string      `json:"name"`
	Type              AccountType `json:"type"`
	Institution       string      `json:"institution,omitempty"`
	AccountNumber     string      `json:"account_number,omitempty"`
	Currency          string      `json:"currency"`
	Balance           float64     `json:"balance"`
	CreditLimit       *float64    `json:"credit_limit,omitempty"`
	InterestRate      *float64    `json:"interest_rate,omitempty"`
	Color             string      `json:"color,omitempty"`
	Icon              string      `json:"icon,omitempty"`
	IncludeInNetWorth *bool       `json:"include_in_net_worth,omitempty"`
	Notes             string      `json:"notes,omitempty"`
}

// CreateTransactionRequest
type CreateTransactionRequest struct {
	AccountID     string          `json:"account_id"`
	CategoryID    *string         `json:"category_id,omitempty"`
	Type          TransactionType `json:"type"`
	Amount        float64         `json:"amount"`
	Currency      string          `json:"currency,omitempty"`
	Description   string          `json:"description,omitempty"`
	Payee         string          `json:"payee,omitempty"`
	Date          *time.Time      `json:"date,omitempty"`
	IsRecurring   bool            `json:"is_recurring,omitempty"`
	Tags          []string        `json:"tags,omitempty"`
	Latitude      *float64        `json:"latitude,omitempty"`
	Longitude     *float64        `json:"longitude,omitempty"`
	LocationName  string          `json:"location_name,omitempty"`
}

// CreateBudgetRequest
type CreateBudgetRequest struct {
	Name            string       `json:"name"`
	CategoryID      *string      `json:"category_id,omitempty"`
	Amount          float64      `json:"amount"`
	Currency        string       `json:"currency,omitempty"`
	Period          BudgetPeriod `json:"period"`
	StartDate       *time.Time   `json:"start_date,omitempty"`
	EndDate         *time.Time   `json:"end_date,omitempty"`
	AlertThreshold  *float64     `json:"alert_threshold,omitempty"`
}

// CreateGoalRequest
type CreateGoalRequest struct {
	Name                string        `json:"name"`
	Type                GoalType      `json:"type"`
	TargetAmount        float64       `json:"target_amount"`
	CurrentAmount       float64       `json:"current_amount,omitempty"`
	Currency            string        `json:"currency,omitempty"`
	TargetDate          *time.Time    `json:"target_date,omitempty"`
	MonthlyContribution float64       `json:"monthly_contribution,omitempty"`
	Priority            GoalPriority  `json:"priority,omitempty"`
	Color               string        `json:"color,omitempty"`
	Icon                string        `json:"icon,omitempty"`
	Notes               string        `json:"notes,omitempty"`
}

// CreateDiaryEntryRequest
type CreateDiaryEntryRequest struct {
	Date               *time.Time        `json:"date,omitempty"`
	Title              string            `json:"title,omitempty"`
	Content            string            `json:"content,omitempty"`
	Mood               MoodType          `json:"mood,omitempty"`
	FinancialMood      FinancialMoodType `json:"financial_mood,omitempty"`
	SpendingReflection string            `json:"spending_reflection,omitempty"`
	SavingsWins        string            `json:"savings_wins,omitempty"`
	LessonsLearned     string            `json:"lessons_learned,omitempty"`
	TomorrowGoals      string            `json:"tomorrow_goals,omitempty"`
	Gratitude          string            `json:"gratitude,omitempty"`
	TotalSpent         float64           `json:"total_spent,omitempty"`
	TotalEarned        float64           `json:"total_earned,omitempty"`
	Tags               []string          `json:"tags,omitempty"`
}

// DashboardSummary represents the finance dashboard summary
type DashboardSummary struct {
	NetWorth           float64                   `json:"net_worth"`
	TotalAssets        float64                   `json:"total_assets"`
	TotalLiabilities   float64                   `json:"total_liabilities"`
	MonthlyIncome      float64                   `json:"monthly_income"`
	MonthlyExpenses    float64                   `json:"monthly_expenses"`
	MonthlySavings     float64                   `json:"monthly_savings"`
	SavingsRate        float64                   `json:"savings_rate"`
	AccountBalances    []AccountBalance          `json:"account_balances"`
	RecentTransactions []FinanceTransaction      `json:"recent_transactions"`
	UpcomingBills     []FinanceSubscription     `json:"upcoming_bills"`
	GoalsProgress      []GoalProgress            `json:"goals_progress"`
	BudgetStatus       []BudgetStatus            `json:"budget_status"`
	SpendingByCategory []CategorySpending        `json:"spending_by_category"`
}

type AccountBalance struct {
	AccountID   string  `json:"account_id"`
	AccountName string  `json:"account_name"`
	Type        string  `json:"type"`
	Balance     float64 `json:"balance"`
	Currency    string  `json:"currency"`
}

type GoalProgress struct {
	GoalID           string  `json:"goal_id"`
	GoalName         string  `json:"goal_name"`
	TargetAmount     float64 `json:"target_amount"`
	CurrentAmount    float64 `json:"current_amount"`
	Progress         float64 `json:"progress"`
	DaysRemaining    int     `json:"days_remaining"`
	OnTrack          bool    `json:"on_track"`
}

type BudgetStatus struct {
	BudgetID      string  `json:"budget_id"`
	BudgetName    string  `json:"budget_name"`
	BudgetAmount  float64 `json:"budget_amount"`
	SpentAmount   float64 `json:"spent_amount"`
	Remaining     float64 `json:"remaining"`
	PercentUsed   float64 `json:"percent_used"`
	IsOverBudget  bool    `json:"is_over_budget"`
}

type CategorySpending struct {
	CategoryID   string  `json:"category_id"`
	CategoryName string  `json:"category_name"`
	Amount       float64 `json:"amount"`
	Percentage   float64 `json:"percentage"`
	Color        string  `json:"color"`
}

// FinancialCalculatorInputs
type CompoundInterestInput struct {
	Principal     float64 `json:"principal"`
	AnnualRate    float64 `json:"annual_rate"`
	Years         int     `json:"years"`
	CompoundsPerYear int   `json:"compounds_per_year"`
	MonthlyContribution float64 `json:"monthly_contribution"`
}

type CompoundInterestResult struct {
	FutureValue        float64 `json:"future_value"`
	TotalContributions float64 `json:"total_contributions"`
	TotalInterest      float64 `json:"total_interest"`
	YearlyBreakdown    []YearlyBreakdown `json:"yearly_breakdown"`
}

type YearlyBreakdown struct {
	Year          int     `json:"year"`
	StartBalance  float64 `json:"start_balance"`
	Contributions float64 `json:"contributions"`
	Interest      float64 `json:"interest"`
	EndBalance    float64 `json:"end_balance"`
}

type LoanCalculatorInput struct {
	Principal      float64 `json:"principal"`
	AnnualRate     float64 `json:"annual_rate"`
	Years          int     `json:"years"`
	DownPayment    float64 `json:"down_payment,omitempty"`
}

type LoanCalculatorResult struct {
	MonthlyPayment float64           `json:"monthly_payment"`
	TotalPayment   float64           `json:"total_payment"`
	TotalInterest  float64           `json:"total_interest"`
	LoanAmount     float64           `json:"loan_amount"`
	Schedule       []LoanPayment    `json:"schedule"`
}

type LoanPayment struct {
	Month        int     `json:"month"`
	Payment      float64 `json:"payment"`
	Principal    float64 `json:"principal"`
	Interest     float64 `json:"interest"`
	Balance      float64 `json:"balance"`
}