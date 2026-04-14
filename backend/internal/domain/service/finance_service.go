package service

import (
	"context"
	"fmt"
	"math"
	"time"

	"github.com/google/uuid"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// FinanceAccountService implements finance account operations
type FinanceAccountService struct {
	accountRepo repository.FinanceAccountRepository
}

// NewFinanceAccountService creates a new finance account service
func NewFinanceAccountService(accountRepo repository.FinanceAccountRepository) *FinanceAccountService {
	return &FinanceAccountService{accountRepo: accountRepo}
}

func (s *FinanceAccountService) CreateAccount(ctx context.Context, userID string, req *model.CreateAccountRequest) (*model.FinanceAccount, error) {
	account := &model.FinanceAccount{
		ID:                uuid.New().String(),
		UserID:            userID,
		Name:              req.Name,
		Type:              req.Type,
		Institution:       req.Institution,
		AccountNumber:     req.AccountNumber,
		Currency:          req.Currency,
		Balance:           req.Balance,
		CreditLimit:       req.CreditLimit,
		InterestRate:      req.InterestRate,
		Color:             req.Color,
		Icon:              req.Icon,
		IsActive:          true,
		IncludeInNetWorth: true,
		Notes:             req.Notes,
		CreatedAt:         time.Now(),
		UpdatedAt:         time.Now(),
	}

	if req.IncludeInNetWorth != nil {
		account.IncludeInNetWorth = *req.IncludeInNetWorth
	}

	if err := s.accountRepo.Create(ctx, account); err != nil {
		return nil, fmt.Errorf("failed to create account: %w", err)
	}

	return account, nil
}

func (s *FinanceAccountService) GetAccount(ctx context.Context, id string) (*model.FinanceAccount, error) {
	return s.accountRepo.GetByID(ctx, id)
}

func (s *FinanceAccountService) GetAccounts(ctx context.Context, userID string) ([]*model.FinanceAccount, error) {
	return s.accountRepo.GetByUserID(ctx, userID)
}

func (s *FinanceAccountService) UpdateAccount(ctx context.Context, account *model.FinanceAccount) error {
	return s.accountRepo.Update(ctx, account)
}

func (s *FinanceAccountService) DeleteAccount(ctx context.Context, id string) error {
	return s.accountRepo.Delete(ctx, id)
}

func (s *FinanceAccountService) GetTotalBalance(ctx context.Context, userID string) (float64, error) {
	accounts, err := s.accountRepo.GetByUserID(ctx, userID)
	if err != nil {
		return 0, err
	}

	var total float64
	for _, acc := range accounts {
		if acc.IncludeInNetWorth {
			if acc.Type == model.AccountTypeCreditCard {
				// Credit card balance is negative (liability)
				total -= acc.Balance
			} else {
				total += acc.Balance
			}
		}
	}
	return total, nil
}

// FinanceTransactionService implements finance transaction operations
type FinanceTransactionService struct {
	transactionRepo repository.FinanceTransactionRepository
	accountRepo     repository.FinanceAccountRepository
	categoryRepo    repository.FinanceCategoryRepository
}

// NewFinanceTransactionService creates a new finance transaction service
func NewFinanceTransactionService(
	transactionRepo repository.FinanceTransactionRepository,
	accountRepo repository.FinanceAccountRepository,
	categoryRepo repository.FinanceCategoryRepository,
) *FinanceTransactionService {
	return &FinanceTransactionService{
		transactionRepo: transactionRepo,
		accountRepo:     accountRepo,
		categoryRepo:    categoryRepo,
	}
}

func (s *FinanceTransactionService) CreateTransaction(ctx context.Context, userID string, req *model.CreateTransactionRequest) (*model.FinanceTransaction, error) {
	// Validate account exists
	account, err := s.accountRepo.GetByID(ctx, req.AccountID)
	if err != nil {
		return nil, fmt.Errorf("account not found: %w", err)
	}

	date := time.Now()
	if req.Date != nil {
		date = *req.Date
	}

	transaction := &model.FinanceTransaction{
		ID:           uuid.New().String(),
		UserID:       userID,
		AccountID:    req.AccountID,
		CategoryID:   req.CategoryID,
		Type:         req.Type,
		Amount:       req.Amount,
		Currency:     req.Currency,
		Description:  req.Description,
		Payee:        req.Payee,
		Date:         date,
		IsRecurring:  req.IsRecurring,
		Tags:         req.Tags,
		Latitude:     req.Latitude,
		Longitude:    req.Longitude,
		LocationName: req.LocationName,
		CreatedAt:    time.Now(),
		UpdatedAt:    time.Now(),
	}

	if req.Currency == "" {
		transaction.Currency = account.Currency
	}

	// Save transaction
	if err := s.transactionRepo.Create(ctx, transaction); err != nil {
		return nil, fmt.Errorf("failed to create transaction: %w", err)
	}

	// Update account balance
	switch req.Type {
	case model.TransactionTypeIncome:
		s.accountRepo.UpdateBalance(ctx, req.AccountID, req.Amount, true)
	case model.TransactionTypeExpense:
		s.accountRepo.UpdateBalance(ctx, req.AccountID, req.Amount, false)
	case model.TransactionTypeTransfer:
		// Transfer logic handled separately
	}

	return transaction, nil
}

func (s *FinanceTransactionService) GetTransaction(ctx context.Context, id string) (*model.FinanceTransaction, error) {
	return s.transactionRepo.GetByID(ctx, id)
}

func (s *FinanceTransactionService) GetTransactions(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceTransaction, error) {
	if limit <= 0 {
		limit = 50
	}
	return s.transactionRepo.GetByUserID(ctx, userID, limit, offset)
}

func (s *FinanceTransactionService) GetTransactionsByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.FinanceTransaction, error) {
	return s.transactionRepo.GetByDateRange(ctx, userID, startDate, endDate)
}

func (s *FinanceTransactionService) UpdateTransaction(ctx context.Context, transaction *model.FinanceTransaction) error {
	return s.transactionRepo.Update(ctx, transaction)
}

func (s *FinanceTransactionService) DeleteTransaction(ctx context.Context, id string) error {
	// Get transaction first to adjust account balance
	transaction, err := s.transactionRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	// Reverse the balance effect
	switch transaction.Type {
	case model.TransactionTypeIncome:
		s.accountRepo.UpdateBalance(ctx, transaction.AccountID, transaction.Amount, false)
	case model.TransactionTypeExpense:
		s.accountRepo.UpdateBalance(ctx, transaction.AccountID, transaction.Amount, true)
	}

	return s.transactionRepo.Delete(ctx, id)
}

func (s *FinanceTransactionService) GetMonthlyIncomeExpense(ctx context.Context, userID string, months int) ([]repository.MonthlyIncomeExpense, error) {
	result := make([]repository.MonthlyIncomeExpense, 0, months)

	now := time.Now()
	for i := 0; i < months; i++ {
		monthStart := time.Date(now.Year(), now.Month()-time.Month(i), 1, 0, 0, 0, 0, time.UTC)
		monthEnd := monthStart.AddDate(0, 1, 0)

		income, err := s.transactionRepo.GetTotalByType(ctx, userID, model.TransactionTypeIncome, monthStart, monthEnd)
		if err != nil {
			return nil, err
		}

		expense, err := s.transactionRepo.GetTotalByType(ctx, userID, model.TransactionTypeExpense, monthStart, monthEnd)
		if err != nil {
			return nil, err
		}

		result = append(result, repository.MonthlyIncomeExpense{
			Month:   monthStart,
			Income:  income,
			Expense: expense,
			Savings: income - expense,
		})
	}

	return result, nil
}

// FinanceCategoryService implements category operations
type FinanceCategoryService struct {
	categoryRepo repository.FinanceCategoryRepository
}

// NewFinanceCategoryService creates a new category service
func NewFinanceCategoryService(categoryRepo repository.FinanceCategoryRepository) *FinanceCategoryService {
	return &FinanceCategoryService{categoryRepo: categoryRepo}
}

func (s *FinanceCategoryService) CreateCategory(ctx context.Context, userID string, category *model.FinanceCategory) (*model.FinanceCategory, error) {
	category.ID = uuid.New().String()
	category.UserID = userID
	category.IsSystem = false
	category.CreatedAt = time.Now()
	category.UpdatedAt = time.Now()

	if err := s.categoryRepo.Create(ctx, category); err != nil {
		return nil, err
	}
	return category, nil
}

func (s *FinanceCategoryService) GetCategories(ctx context.Context, userID string) ([]*model.FinanceCategory, error) {
	return s.categoryRepo.GetByUserID(ctx, userID)
}

func (s *FinanceCategoryService) GetCategoriesByType(ctx context.Context, userID string, categoryType model.CategoryType) ([]*model.FinanceCategory, error) {
	return s.categoryRepo.GetByType(ctx, userID, categoryType)
}

func (s *FinanceCategoryService) UpdateCategory(ctx context.Context, category *model.FinanceCategory) error {
	return s.categoryRepo.Update(ctx, category)
}

func (s *FinanceCategoryService) DeleteCategory(ctx context.Context, id string) error {
	return s.categoryRepo.Delete(ctx, id)
}

// FinanceBudgetService implements budget operations
type FinanceBudgetService struct {
	budgetRepo      repository.FinanceBudgetRepository
	transactionRepo repository.FinanceTransactionRepository
}

// NewFinanceBudgetService creates a new budget service
func NewFinanceBudgetService(budgetRepo repository.FinanceBudgetRepository, transactionRepo repository.FinanceTransactionRepository) *FinanceBudgetService {
	return &FinanceBudgetService{budgetRepo: budgetRepo, transactionRepo: transactionRepo}
}

func (s *FinanceBudgetService) CreateBudget(ctx context.Context, userID string, req *model.CreateBudgetRequest) (*model.FinanceBudget, error) {
	startDate := time.Now()
	if req.StartDate != nil {
		startDate = *req.StartDate
	}

	budget := &model.FinanceBudget{
		ID:             uuid.New().String(),
		UserID:         userID,
		Name:           req.Name,
		CategoryID:     req.CategoryID,
		Amount:         req.Amount,
		Currency:       req.Currency,
		Period:         req.Period,
		StartDate:      startDate,
		EndDate:        req.EndDate,
		IsActive:       true,
		AlertThreshold: 80,
		CreatedAt:      time.Now(),
		UpdatedAt:      time.Now(),
	}

	if req.Currency == "" {
		budget.Currency = "THB"
	}
	if req.AlertThreshold != nil {
		budget.AlertThreshold = *req.AlertThreshold
	}

	if err := s.budgetRepo.Create(ctx, budget); err != nil {
		return nil, err
	}
	return budget, nil
}

func (s *FinanceBudgetService) GetBudget(ctx context.Context, id string) (*model.FinanceBudget, error) {
	return s.budgetRepo.GetByID(ctx, id)
}

func (s *FinanceBudgetService) GetBudgets(ctx context.Context, userID string) ([]*model.FinanceBudget, error) {
	return s.budgetRepo.GetByUserID(ctx, userID)
}

func (s *FinanceBudgetService) GetBudgetStatus(ctx context.Context, budget *model.FinanceBudget) (*model.BudgetStatus, error) {
	// Calculate spending for this budget period
	startDate, endDate := s.getBudgetPeriodDates(budget)

	var spent float64
	if budget.CategoryID != nil {
		transactions, err := s.transactionRepo.GetByCategoryID(ctx, *budget.CategoryID, startDate, endDate)
		if err != nil {
			return nil, err
		}
		for _, t := range transactions {
			spent += t.Amount
		}
	} else {
		// Overall budget - get all expenses
		spent, _ = s.transactionRepo.GetTotalByType(ctx, budget.UserID, model.TransactionTypeExpense, startDate, endDate)
	}

	percentUsed := (spent / budget.Amount) * 100
	if percentUsed > 100 {
		percentUsed = 100
	}

	return &model.BudgetStatus{
		BudgetID:     budget.ID,
		BudgetName:   budget.Name,
		BudgetAmount: budget.Amount,
		SpentAmount:  spent,
		Remaining:    budget.Amount - spent,
		PercentUsed:  percentUsed,
		IsOverBudget: spent > budget.Amount,
	}, nil
}

func (s *FinanceBudgetService) getBudgetPeriodDates(budget *model.FinanceBudget) (time.Time, time.Time) {
	now := time.Now()

	switch budget.Period {
	case model.BudgetPeriodWeekly:
		// Current week
		start := time.Date(now.Year(), now.Month(), now.Day()-int(now.Weekday()), 0, 0, 0, 0, time.UTC)
		return start, start.AddDate(0, 0, 7)
	case model.BudgetPeriodYearly:
		// Current year
		start := time.Date(now.Year(), 1, 1, 0, 0, 0, 0, time.UTC)
		return start, start.AddDate(1, 0, 0)
	default: // Monthly
		// Current month
		start := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
		return start, start.AddDate(0, 1, 0)
	}
}

func (s *FinanceBudgetService) UpdateBudget(ctx context.Context, budget *model.FinanceBudget) error {
	return s.budgetRepo.Update(ctx, budget)
}

func (s *FinanceBudgetService) DeleteBudget(ctx context.Context, id string) error {
	return s.budgetRepo.Delete(ctx, id)
}

// FinanceGoalService implements goal operations
type FinanceGoalService struct {
	goalRepo repository.FinanceGoalRepository
}

// NewFinanceGoalService creates a new goal service
func NewFinanceGoalService(goalRepo repository.FinanceGoalRepository) *FinanceGoalService {
	return &FinanceGoalService{goalRepo: goalRepo}
}

func (s *FinanceGoalService) CreateGoal(ctx context.Context, userID string, req *model.CreateGoalRequest) (*model.FinanceGoal, error) {
	priority := model.GoalPriorityMedium
	if req.Priority != "" {
		priority = req.Priority
	}

	goal := &model.FinanceGoal{
		ID:                 uuid.New().String(),
		UserID:             userID,
		Name:               req.Name,
		Type:               req.Type,
		TargetAmount:       req.TargetAmount,
		CurrentAmount:      req.CurrentAmount,
		Currency:           req.Currency,
		TargetDate:         req.TargetDate,
		MonthlyContribution: req.MonthlyContribution,
		Priority:           priority,
		Status:             model.GoalStatusActive,
		Color:              req.Color,
		Icon:               req.Icon,
		Notes:              req.Notes,
		CreatedAt:          time.Now(),
		UpdatedAt:          time.Now(),
	}

	if req.Currency == "" {
		goal.Currency = "THB"
	}

	if err := s.goalRepo.Create(ctx, goal); err != nil {
		return nil, err
	}
	return goal, nil
}

func (s *FinanceGoalService) GetGoal(ctx context.Context, id string) (*model.FinanceGoal, error) {
	return s.goalRepo.GetByID(ctx, id)
}

func (s *FinanceGoalService) GetGoals(ctx context.Context, userID string) ([]*model.FinanceGoal, error) {
	return s.goalRepo.GetByUserID(ctx, userID)
}

func (s *FinanceGoalService) GetGoalProgress(ctx context.Context, goal *model.FinanceGoal) (*model.GoalProgress, error) {
	progress := (goal.CurrentAmount / goal.TargetAmount) * 100
	if progress > 100 {
		progress = 100
	}

	daysRemaining := 0
	onTrack := true
	if goal.TargetDate != nil {
		daysRemaining = int((*goal.TargetDate).Sub(time.Now()).Hours() / 24)
		if daysRemaining > 0 {
			requiredMonthly := (goal.TargetAmount - goal.CurrentAmount) / float64(daysRemaining/30)
			onTrack = goal.MonthlyContribution >= requiredMonthly
		}
	}

	return &model.GoalProgress{
		GoalID:        goal.ID,
		GoalName:      goal.Name,
		TargetAmount:  goal.TargetAmount,
		CurrentAmount: goal.CurrentAmount,
		Progress:      progress,
		DaysRemaining: daysRemaining,
		OnTrack:       onTrack,
	}, nil
}

func (s *FinanceGoalService) UpdateGoal(ctx context.Context, goal *model.FinanceGoal) error {
	// Check if goal is completed
	if goal.CurrentAmount >= goal.TargetAmount && goal.Status == model.GoalStatusActive {
		goal.Status = model.GoalStatusCompleted
	}
	return s.goalRepo.Update(ctx, goal)
}

func (s *FinanceGoalService) AddToGoal(ctx context.Context, id string, amount float64) error {
	goal, err := s.goalRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if err := s.goalRepo.UpdateProgress(ctx, id, amount, true); err != nil {
		return err
	}

	// Check if completed
	if goal.CurrentAmount+amount >= goal.TargetAmount {
		goal.Status = model.GoalStatusCompleted
		s.goalRepo.Update(ctx, goal)
	}

	return nil
}

func (s *FinanceGoalService) DeleteGoal(ctx context.Context, id string) error {
	return s.goalRepo.Delete(ctx, id)
}

// FinanceAssetService implements asset operations
type FinanceAssetService struct {
	assetRepo repository.FinanceAssetRepository
}

// NewFinanceAssetService creates a new asset service
func NewFinanceAssetService(assetRepo repository.FinanceAssetRepository) *FinanceAssetService {
	return &FinanceAssetService{assetRepo: assetRepo}
}

func (s *FinanceAssetService) CreateAsset(ctx context.Context, userID string, asset *model.FinanceAsset) (*model.FinanceAsset, error) {
	asset.ID = uuid.New().String()
	asset.UserID = userID
	asset.IsActive = true
	asset.CreatedAt = time.Now()
	asset.UpdatedAt = time.Now()

	if err := s.assetRepo.Create(ctx, asset); err != nil {
		return nil, err
	}
	return asset, nil
}

func (s *FinanceAssetService) GetAsset(ctx context.Context, id string) (*model.FinanceAsset, error) {
	return s.assetRepo.GetByID(ctx, id)
}

func (s *FinanceAssetService) GetAssets(ctx context.Context, userID string) ([]*model.FinanceAsset, error) {
	return s.assetRepo.GetByUserID(ctx, userID)
}

func (s *FinanceAssetService) GetTotalValue(ctx context.Context, userID string) (float64, error) {
	return s.assetRepo.GetTotalValue(ctx, userID)
}

func (s *FinanceAssetService) UpdateAsset(ctx context.Context, asset *model.FinanceAsset) error {
	return s.assetRepo.Update(ctx, asset)
}

func (s *FinanceAssetService) DeleteAsset(ctx context.Context, id string) error {
	return s.assetRepo.Delete(ctx, id)
}

// FinanceLiabilityService implements liability operations
type FinanceLiabilityService struct {
	liabilityRepo repository.FinanceLiabilityRepository
}

// NewFinanceLiabilityService creates a new liability service
func NewFinanceLiabilityService(liabilityRepo repository.FinanceLiabilityRepository) *FinanceLiabilityService {
	return &FinanceLiabilityService{liabilityRepo: liabilityRepo}
}

func (s *FinanceLiabilityService) CreateLiability(ctx context.Context, userID string, liability *model.FinanceLiability) (*model.FinanceLiability, error) {
	liability.ID = uuid.New().String()
	liability.UserID = userID
	liability.Status = model.LiabilityStatusActive
	liability.CreatedAt = time.Now()
	liability.UpdatedAt = time.Now()

	if err := s.liabilityRepo.Create(ctx, liability); err != nil {
		return nil, err
	}
	return liability, nil
}

func (s *FinanceLiabilityService) GetLiability(ctx context.Context, id string) (*model.FinanceLiability, error) {
	return s.liabilityRepo.GetByID(ctx, id)
}

func (s *FinanceLiabilityService) GetLiabilities(ctx context.Context, userID string) ([]*model.FinanceLiability, error) {
	return s.liabilityRepo.GetByUserID(ctx, userID)
}

func (s *FinanceLiabilityService) GetTotalBalance(ctx context.Context, userID string) (float64, error) {
	return s.liabilityRepo.GetTotalBalance(ctx, userID)
}

func (s *FinanceLiabilityService) UpdateLiability(ctx context.Context, liability *model.FinanceLiability) error {
	// Check if paid off
	if liability.CurrentBalance <= 0 && liability.Status == model.LiabilityStatusActive {
		liability.Status = model.LiabilityStatusPaidOff
		liability.CurrentBalance = 0
	}
	return s.liabilityRepo.Update(ctx, liability)
}

func (s *FinanceLiabilityService) MakePayment(ctx context.Context, id string, amount float64) error {
	liability, err := s.liabilityRepo.GetByID(ctx, id)
	if err != nil {
		return err
	}

	if err := s.liabilityRepo.UpdateBalance(ctx, id, amount, true); err != nil {
		return err
	}

	// Check if paid off
	if liability.CurrentBalance-amount <= 0 {
		liability.Status = model.LiabilityStatusPaidOff
		liability.CurrentBalance = 0
		s.liabilityRepo.Update(ctx, liability)
	}

	return nil
}

func (s *FinanceLiabilityService) DeleteLiability(ctx context.Context, id string) error {
	return s.liabilityRepo.Delete(ctx, id)
}

// FinanceSubscriptionService implements subscription operations
type FinanceSubscriptionService struct {
	subscriptionRepo repository.FinanceSubscriptionRepository
}

// NewFinanceSubscriptionService creates a new subscription service
func NewFinanceSubscriptionService(subscriptionRepo repository.FinanceSubscriptionRepository) *FinanceSubscriptionService {
	return &FinanceSubscriptionService{subscriptionRepo: subscriptionRepo}
}

func (s *FinanceSubscriptionService) CreateSubscription(ctx context.Context, userID string, subscription *model.FinanceSubscription) (*model.FinanceSubscription, error) {
	subscription.ID = uuid.New().String()
	subscription.UserID = userID
	subscription.IsActive = true
	subscription.CreatedAt = time.Now()
	subscription.UpdatedAt = time.Now()

	if err := s.subscriptionRepo.Create(ctx, subscription); err != nil {
		return nil, err
	}
	return subscription, nil
}

func (s *FinanceSubscriptionService) GetSubscription(ctx context.Context, id string) (*model.FinanceSubscription, error) {
	return s.subscriptionRepo.GetByID(ctx, id)
}

func (s *FinanceSubscriptionService) GetSubscriptions(ctx context.Context, userID string) ([]*model.FinanceSubscription, error) {
	return s.subscriptionRepo.GetByUserID(ctx, userID)
}

func (s *FinanceSubscriptionService) GetUpcoming(ctx context.Context, userID string, days int) ([]*model.FinanceSubscription, error) {
	return s.subscriptionRepo.GetUpcoming(ctx, userID, days)
}

func (s *FinanceSubscriptionService) GetTotalMonthly(ctx context.Context, userID string) (float64, error) {
	return s.subscriptionRepo.GetTotalMonthly(ctx, userID)
}

func (s *FinanceSubscriptionService) UpdateSubscription(ctx context.Context, subscription *model.FinanceSubscription) error {
	return s.subscriptionRepo.Update(ctx, subscription)
}

func (s *FinanceSubscriptionService) DeleteSubscription(ctx context.Context, id string) error {
	return s.subscriptionRepo.Delete(ctx, id)
}

// FinanceDiaryService implements diary operations
type FinanceDiaryService struct {
	diaryRepo repository.FinanceDiaryRepository
}

// NewFinanceDiaryService creates a new diary service
func NewFinanceDiaryService(diaryRepo repository.FinanceDiaryRepository) *FinanceDiaryService {
	return &FinanceDiaryService{diaryRepo: diaryRepo}
}

func (s *FinanceDiaryService) CreateEntry(ctx context.Context, userID string, req *model.CreateDiaryEntryRequest) (*model.FinanceDiaryEntry, error) {
	date := time.Now()
	if req.Date != nil {
		date = *req.Date
	}

	entry := &model.FinanceDiaryEntry{
		ID:                 uuid.New().String(),
		UserID:             userID,
		Date:               date,
		Title:              req.Title,
		Content:            req.Content,
		Mood:               req.Mood,
		FinancialMood:      req.FinancialMood,
		SpendingReflection: req.SpendingReflection,
		SavingsWins:        req.SavingsWins,
		LessonsLearned:     req.LessonsLearned,
		TomorrowGoals:      req.TomorrowGoals,
		Gratitude:          req.Gratitude,
		TotalSpent:         req.TotalSpent,
		TotalEarned:        req.TotalEarned,
		Tags:               req.Tags,
		CreatedAt:          time.Now(),
		UpdatedAt:          time.Now(),
	}

	if err := s.diaryRepo.Create(ctx, entry); err != nil {
		return nil, err
	}
	return entry, nil
}

func (s *FinanceDiaryService) GetEntry(ctx context.Context, id string) (*model.FinanceDiaryEntry, error) {
	return s.diaryRepo.GetByID(ctx, id)
}

func (s *FinanceDiaryService) GetEntryByDate(ctx context.Context, userID string, date time.Time) (*model.FinanceDiaryEntry, error) {
	return s.diaryRepo.GetByDate(ctx, userID, date)
}

func (s *FinanceDiaryService) GetEntries(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceDiaryEntry, error) {
	return s.diaryRepo.GetByUserID(ctx, userID, limit, offset)
}

func (s *FinanceDiaryService) UpdateEntry(ctx context.Context, entry *model.FinanceDiaryEntry) error {
	return s.diaryRepo.Update(ctx, entry)
}

func (s *FinanceDiaryService) DeleteEntry(ctx context.Context, id string) error {
	return s.diaryRepo.Delete(ctx, id)
}

// NetWorthService implements net worth calculations
type NetWorthService struct {
	accountRepo    repository.FinanceAccountRepository
	assetRepo      repository.FinanceAssetRepository
	liabilityRepo  repository.FinanceLiabilityRepository
	historyRepo    repository.NetWorthHistoryRepository
	transactionRepo repository.FinanceTransactionRepository
}

// NewNetWorthService creates a new net worth service
func NewNetWorthService(
	accountRepo repository.FinanceAccountRepository,
	assetRepo repository.FinanceAssetRepository,
	liabilityRepo repository.FinanceLiabilityRepository,
	historyRepo repository.NetWorthHistoryRepository,
	transactionRepo repository.FinanceTransactionRepository,
) *NetWorthService {
	return &NetWorthService{
		accountRepo:    accountRepo,
		assetRepo:      assetRepo,
		liabilityRepo:  liabilityRepo,
		historyRepo:    historyRepo,
		transactionRepo: transactionRepo,
	}
}

func (s *NetWorthService) CalculateNetWorth(ctx context.Context, userID string) (*model.NetWorthHistory, error) {
	// Get account balances
	accounts, err := s.accountRepo.GetByUserID(ctx, userID)
	if err != nil {
		return nil, err
	}

	var accountAssets, accountLiabilities float64
	for _, acc := range accounts {
		if acc.IncludeInNetWorth {
			if acc.Type == model.AccountTypeCreditCard || acc.Type == model.AccountTypeLoan {
				accountLiabilities += acc.Balance
			} else {
				accountAssets += acc.Balance
			}
		}
	}

	// Get asset values
	assetTotal, err := s.assetRepo.GetTotalValue(ctx, userID)
	if err != nil {
		return nil, err
	}

	// Get liability balances
	liabilityTotal, err := s.liabilityRepo.GetTotalBalance(ctx, userID)
	if err != nil {
		return nil, err
	}

	totalAssets := accountAssets + assetTotal
	totalLiabilities := accountLiabilities + liabilityTotal
	netWorth := totalAssets - totalLiabilities

	breakdown := &model.NetWorthBreakdown{}
	breakdown.Assets.Accounts = accountAssets
	breakdown.Assets.Other = assetTotal
	breakdown.Liabilities.Loans = liabilityTotal
	breakdown.Liabilities.CreditCards = accountLiabilities

	history := &model.NetWorthHistory{
		UserID:           userID,
		Date:             time.Now(),
		TotalAssets:      totalAssets,
		TotalLiabilities: totalLiabilities,
		NetWorth:         netWorth,
		Breakdown:        breakdown,
		CreatedAt:        time.Now(),
	}

	// Save to history
	if err := s.historyRepo.Create(ctx, history); err != nil {
		return nil, err
	}

	return history, nil
}

func (s *NetWorthService) GetNetWorthHistory(ctx context.Context, userID string, limit int) ([]*model.NetWorthHistory, error) {
	return s.historyRepo.GetByUserID(ctx, userID, limit)
}

func (s *NetWorthService) GetLatestNetWorth(ctx context.Context, userID string) (*model.NetWorthHistory, error) {
	return s.historyRepo.GetLatest(ctx, userID)
}

// DashboardService implements dashboard data aggregation
type DashboardService struct {
	accountRepo       repository.FinanceAccountRepository
	transactionRepo   repository.FinanceTransactionRepository
	budgetRepo        repository.FinanceBudgetRepository
	goalRepo          repository.FinanceGoalRepository
	subscriptionRepo  repository.FinanceSubscriptionRepository
	categoryRepo      repository.FinanceCategoryRepository
	assetRepo         repository.FinanceAssetRepository
	liabilityRepo     repository.FinanceLiabilityRepository
	historyRepo       repository.NetWorthHistoryRepository
}

// NewDashboardService creates a new dashboard service
func NewDashboardService(
	accountRepo repository.FinanceAccountRepository,
	transactionRepo repository.FinanceTransactionRepository,
	budgetRepo repository.FinanceBudgetRepository,
	goalRepo repository.FinanceGoalRepository,
	subscriptionRepo repository.FinanceSubscriptionRepository,
	categoryRepo repository.FinanceCategoryRepository,
	assetRepo repository.FinanceAssetRepository,
	liabilityRepo repository.FinanceLiabilityRepository,
	historyRepo repository.NetWorthHistoryRepository,
) *DashboardService {
	return &DashboardService{
		accountRepo:       accountRepo,
		transactionRepo:   transactionRepo,
		budgetRepo:        budgetRepo,
		goalRepo:          goalRepo,
		subscriptionRepo:  subscriptionRepo,
		categoryRepo:      categoryRepo,
		assetRepo:         assetRepo,
		liabilityRepo:     liabilityRepo,
		historyRepo:       historyRepo,
	}
}

func (s *DashboardService) GetDashboardSummary(ctx context.Context, userID string) (*model.DashboardSummary, error) {
	now := time.Now()
	monthStart := time.Date(now.Year(), now.Month(), 1, 0, 0, 0, 0, time.UTC)
	monthEnd := monthStart.AddDate(0, 1, 0)

	// Get net worth (latest or calculate)
	history, err := s.historyRepo.GetLatest(ctx, userID)
	if err != nil || history == nil {
		// Calculate net worth
		assets, _ := s.accountRepo.GetByUserID(ctx, userID)
		assetTotal, _ := s.assetRepo.GetTotalValue(ctx, userID)
		liabilityTotal, _ := s.liabilityRepo.GetTotalBalance(ctx, userID)

		var accountBalance float64
		for _, acc := range assets {
			if acc.IncludeInNetWorth {
				if acc.Type == model.AccountTypeCreditCard || acc.Type == model.AccountTypeLoan {
					accountBalance -= acc.Balance
				} else {
					accountBalance += acc.Balance
				}
			}
		}

		totalAssets := accountBalance + assetTotal
		history = &model.NetWorthHistory{
			TotalAssets:      totalAssets,
			TotalLiabilities: liabilityTotal,
			NetWorth:         totalAssets - liabilityTotal,
		}
	}

	// Monthly income/expense
	monthlyIncome, _ := s.transactionRepo.GetTotalByType(ctx, userID, model.TransactionTypeIncome, monthStart, monthEnd)
	monthlyExpenses, _ := s.transactionRepo.GetTotalByType(ctx, userID, model.TransactionTypeExpense, monthStart, monthEnd)
	monthlySavings := monthlyIncome - monthlyExpenses

	savingsRate := 0.0
	if monthlyIncome > 0 {
		savingsRate = (monthlySavings / monthlyIncome) * 100
	}

	// Account balances
	accounts, _ := s.accountRepo.GetByUserID(ctx, userID)
	accountBalances := make([]model.AccountBalance, 0, len(accounts))
	for _, acc := range accounts {
		accountBalances = append(accountBalances, model.AccountBalance{
			AccountID:   acc.ID,
			AccountName: acc.Name,
			Type:        string(acc.Type),
			Balance:     acc.Balance,
			Currency:    acc.Currency,
		})
	}

	// Recent transactions
	recentTxns, _ := s.transactionRepo.GetRecent(ctx, userID, 10)

	// Upcoming bills
	upcomingBills, _ := s.subscriptionRepo.GetUpcoming(ctx, userID, 7)

	// Goals progress
	goals, _ := s.goalRepo.GetActive(ctx, userID)
	goalsProgress := make([]model.GoalProgress, 0, len(goals))
	for _, goal := range goals {
		progress := (goal.CurrentAmount / goal.TargetAmount) * 100
		if progress > 100 {
			progress = 100
		}
		daysRemaining := 0
		if goal.TargetDate != nil {
			daysRemaining = int((*goal.TargetDate).Sub(now).Hours() / 24)
		}
		goalsProgress = append(goalsProgress, model.GoalProgress{
			GoalID:        goal.ID,
			GoalName:      goal.Name,
			TargetAmount:  goal.TargetAmount,
			CurrentAmount: goal.CurrentAmount,
			Progress:      progress,
			DaysRemaining: daysRemaining,
			OnTrack:       goal.MonthlyContribution > 0,
		})
	}

	// Budget status
	budgets, _ := s.budgetRepo.GetActive(ctx, userID)
	budgetStatus := make([]model.BudgetStatus, 0, len(budgets))
	for _, budget := range budgets {
		var spent float64
		if budget.CategoryID != nil {
			txnByCat, _ := s.transactionRepo.GetByCategoryID(ctx, *budget.CategoryID, monthStart, monthEnd)
			for _, t := range txnByCat {
				spent += t.Amount
			}
		} else {
			spent, _ = s.transactionRepo.GetTotalByType(ctx, userID, model.TransactionTypeExpense, monthStart, monthEnd)
		}

		percentUsed := (spent / budget.Amount) * 100
		budgetStatus = append(budgetStatus, model.BudgetStatus{
			BudgetID:     budget.ID,
			BudgetName:   budget.Name,
			BudgetAmount: budget.Amount,
			SpentAmount:  spent,
			Remaining:    budget.Amount - spent,
			PercentUsed:  math.Min(percentUsed, 100),
			IsOverBudget: spent > budget.Amount,
		})
	}

	// Spending by category
	categoryTotals, _ := s.transactionRepo.GetTotalByCategory(ctx, userID, monthStart, monthEnd)
	categories, _ := s.categoryRepo.GetByUserID(ctx, userID)
	catMap := make(map[string]*model.FinanceCategory)
	for _, cat := range categories {
		catMap[cat.ID] = cat
	}

	totalExpense := monthlyExpenses
	spendingByCategory := make([]model.CategorySpending, 0)
	for catID, amount := range categoryTotals {
		cat := catMap[catID]
		if cat == nil {
			cat = &model.FinanceCategory{Name: "Uncategorized", Color: "#95A5A6"}
		}
		percentage := (amount / totalExpense) * 100
		spendingByCategory = append(spendingByCategory, model.CategorySpending{
			CategoryID:   catID,
			CategoryName: cat.Name,
			Amount:       amount,
			Percentage:   math.Min(percentage, 100),
			Color:        cat.Color,
		})
	}

	// Convert pointer slices to value slices for the response
	recentTransactions := make([]model.FinanceTransaction, len(recentTxns))
	for i, t := range recentTxns {
		recentTransactions[i] = *t
	}

	upcomingBillsResult := make([]model.FinanceSubscription, len(upcomingBills))
	for i, s := range upcomingBills {
		upcomingBillsResult[i] = *s
	}

	return &model.DashboardSummary{
		NetWorth:           history.NetWorth,
		TotalAssets:        history.TotalAssets,
		TotalLiabilities:   history.TotalLiabilities,
		MonthlyIncome:      monthlyIncome,
		MonthlyExpenses:    monthlyExpenses,
		MonthlySavings:     monthlySavings,
		SavingsRate:        savingsRate,
		AccountBalances:    accountBalances,
		RecentTransactions: recentTransactions,
		UpcomingBills:      upcomingBillsResult,
		GoalsProgress:      goalsProgress,
		BudgetStatus:       budgetStatus,
		SpendingByCategory: spendingByCategory,
	}, nil
}
