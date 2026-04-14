package http

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/service"
)

// FinanceHandler handles all finance-related HTTP requests
type FinanceHandler struct {
	pool              *pgxpool.Pool
	accountService    *service.FinanceAccountService
	transactionService *service.FinanceTransactionService
	categoryService   *service.FinanceCategoryService
	budgetService     *service.FinanceBudgetService
	goalService       *service.FinanceGoalService
	assetService      *service.FinanceAssetService
	liabilityService  *service.FinanceLiabilityService
	subscriptionService *service.FinanceSubscriptionService
	diaryService      *service.FinanceDiaryService
	dashboardService  *service.DashboardService
	calculatorService *service.FinancialCalculatorService
	netWorthService   *service.NetWorthService
	authHandler       *AuthHandler
}

// NewFinanceHandler creates a new finance handler
func NewFinanceHandler(
	pool *pgxpool.Pool,
	accountService *service.FinanceAccountService,
	transactionService *service.FinanceTransactionService,
	categoryService *service.FinanceCategoryService,
	budgetService *service.FinanceBudgetService,
	goalService *service.FinanceGoalService,
	assetService *service.FinanceAssetService,
	liabilityService *service.FinanceLiabilityService,
	subscriptionService *service.FinanceSubscriptionService,
	diaryService *service.FinanceDiaryService,
	dashboardService *service.DashboardService,
	calculatorService *service.FinancialCalculatorService,
	netWorthService *service.NetWorthService,
	authHandler *AuthHandler,
) *FinanceHandler {
	return &FinanceHandler{
		pool:              pool,
		accountService:    accountService,
		transactionService: transactionService,
		categoryService:   categoryService,
		budgetService:     budgetService,
		goalService:       goalService,
		assetService:      assetService,
		liabilityService:  liabilityService,
		subscriptionService: subscriptionService,
		diaryService:      diaryService,
		dashboardService:  dashboardService,
		calculatorService: calculatorService,
		netWorthService:   netWorthService,
		authHandler:       authHandler,
	}
}

// getUserID extracts user ID from the authenticated request's token
func (h *FinanceHandler) getUserID(r *http.Request) string {
	token := extractBearerToken(r)
	if token == "" {
		return ""
	}
	if h.authHandler != nil {
		userID, _ := h.authHandler.ValidateToken(token)
		return userID
	}
	return ""
}

// ============================================
// Dashboard
// ============================================

// GetDashboard handles GET /api/finance/dashboard
func (h *FinanceHandler) GetDashboard(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	summary, err := h.dashboardService.GetDashboardSummary(r.Context(), userID)
	if err != nil {
		respondError(w, "Failed to get dashboard data", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(summary)
}

// ============================================
// Accounts
// ============================================

// GetAccounts handles GET /api/finance/accounts
func (h *FinanceHandler) GetAccounts(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	accounts, err := h.accountService.GetAccounts(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get accounts", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(accounts)
}

// CreateAccount handles POST /api/finance/accounts
func (h *FinanceHandler) CreateAccount(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.CreateAccountRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	account, err := h.accountService.CreateAccount(r.Context(), userID, &req)
	if err != nil {
		respondError(w, "Failed to create account", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(account)
}

// UpdateAccount handles PUT /api/finance/accounts/{id}
func (h *FinanceHandler) UpdateAccount(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/accounts/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Account ID required", http.StatusBadRequest)
		return
	}

	var account model.FinanceAccount
	if err := json.NewDecoder(r.Body).Decode(&account); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	account.ID = id
	if err := h.accountService.UpdateAccount(r.Context(), &account); err != nil {
		http.Error(w, "Failed to update account", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(account)
}

// DeleteAccount handles DELETE /api/finance/accounts/{id}
func (h *FinanceHandler) DeleteAccount(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/accounts/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Account ID required", http.StatusBadRequest)
		return
	}

	if err := h.accountService.DeleteAccount(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete account", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Transactions
// ============================================

// GetTransactions handles GET /api/finance/transactions
func (h *FinanceHandler) GetTransactions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)

	// Parse query parameters
	limit := 50
	offset := 0
	startDateStr := r.URL.Query().Get("start")
	endDateStr := r.URL.Query().Get("end")

	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	var transactions []*model.FinanceTransaction
	var err error

	if startDateStr != "" && endDateStr != "" {
		startDate, _ := time.Parse(time.RFC3339, startDateStr)
		endDate, _ := time.Parse(time.RFC3339, endDateStr)
		transactions, err = h.transactionService.GetTransactionsByDateRange(r.Context(), userID, startDate, endDate)
	} else {
		transactions, err = h.transactionService.GetTransactions(r.Context(), userID, limit, offset)
	}

	if err != nil {
		http.Error(w, "Failed to get transactions", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(transactions)
}

// CreateTransaction handles POST /api/finance/transactions
func (h *FinanceHandler) CreateTransaction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.CreateTransactionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	transaction, err := h.transactionService.CreateTransaction(r.Context(), userID, &req)
	if err != nil {
		respondError(w, "Failed to create transaction", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(transaction)
}

// UpdateTransaction handles PUT /api/finance/transactions/{id}
func (h *FinanceHandler) UpdateTransaction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/transactions/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Transaction ID required", http.StatusBadRequest)
		return
	}

	var transaction model.FinanceTransaction
	if err := json.NewDecoder(r.Body).Decode(&transaction); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	transaction.ID = id
	if err := h.transactionService.UpdateTransaction(r.Context(), &transaction); err != nil {
		http.Error(w, "Failed to update transaction", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(transaction)
}

// DeleteTransaction handles DELETE /api/finance/transactions/{id}
func (h *FinanceHandler) DeleteTransaction(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/transactions/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Transaction ID required", http.StatusBadRequest)
		return
	}

	if err := h.transactionService.DeleteTransaction(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete transaction", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Categories
// ============================================

// GetCategories handles GET /api/finance/categories
func (h *FinanceHandler) GetCategories(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	categoryType := r.URL.Query().Get("type")

	var categories []*model.FinanceCategory
	var err error

	if categoryType != "" {
		categories, err = h.categoryService.GetCategoriesByType(r.Context(), userID, model.CategoryType(categoryType))
	} else {
		categories, err = h.categoryService.GetCategories(r.Context(), userID)
	}

	if err != nil {
		http.Error(w, "Failed to get categories", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(categories)
}

// CreateCategory handles POST /api/finance/categories
func (h *FinanceHandler) CreateCategory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var category model.FinanceCategory
	if err := json.NewDecoder(r.Body).Decode(&category); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	result, err := h.categoryService.CreateCategory(r.Context(), userID, &category)
	if err != nil {
		http.Error(w, "Failed to create category", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// ============================================
// Budgets
// ============================================

// GetBudgets handles GET /api/finance/budgets
func (h *FinanceHandler) GetBudgets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	budgets, err := h.budgetService.GetBudgets(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get budgets", http.StatusInternalServerError)
		return
	}

	// Get status for each budget
	results := make([]map[string]interface{}, 0)
	for _, budget := range budgets {
		status, err := h.budgetService.GetBudgetStatus(r.Context(), budget)
		if err != nil {
			status = &model.BudgetStatus{}
		}
		results = append(results, map[string]interface{}{
			"budget": budget,
			"status": status,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

// CreateBudget handles POST /api/finance/budgets
func (h *FinanceHandler) CreateBudget(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.CreateBudgetRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	budget, err := h.budgetService.CreateBudget(r.Context(), userID, &req)
	if err != nil {
		http.Error(w, "Failed to create budget", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(budget)
}

// UpdateBudget handles PUT /api/finance/budgets/{id}
func (h *FinanceHandler) UpdateBudget(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/budgets/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Budget ID required", http.StatusBadRequest)
		return
	}

	var budget model.FinanceBudget
	if err := json.NewDecoder(r.Body).Decode(&budget); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	budget.ID = id
	if err := h.budgetService.UpdateBudget(r.Context(), &budget); err != nil {
		http.Error(w, "Failed to update budget", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(budget)
}

// DeleteBudget handles DELETE /api/finance/budgets/{id}
func (h *FinanceHandler) DeleteBudget(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/budgets/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Budget ID required", http.StatusBadRequest)
		return
	}

	if err := h.budgetService.DeleteBudget(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete budget", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Goals
// ============================================

// GetGoals handles GET /api/finance/goals
func (h *FinanceHandler) GetGoals(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	goals, err := h.goalService.GetGoals(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get goals", http.StatusInternalServerError)
		return
	}

	// Get progress for each goal
	results := make([]map[string]interface{}, 0)
	for _, goal := range goals {
		progress, err := h.goalService.GetGoalProgress(r.Context(), goal)
		if err != nil {
			progress = &model.GoalProgress{}
		}
		results = append(results, map[string]interface{}{
			"goal":     goal,
			"progress": progress,
		})
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(results)
}

// CreateGoal handles POST /api/finance/goals
func (h *FinanceHandler) CreateGoal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.CreateGoalRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	goal, err := h.goalService.CreateGoal(r.Context(), userID, &req)
	if err != nil {
		http.Error(w, "Failed to create goal", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(goal)
}

// UpdateGoal handles PUT /api/finance/goals/{id}
func (h *FinanceHandler) UpdateGoal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/goals/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Goal ID required", http.StatusBadRequest)
		return
	}

	var goal model.FinanceGoal
	if err := json.NewDecoder(r.Body).Decode(&goal); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	goal.ID = id
	if err := h.goalService.UpdateGoal(r.Context(), &goal); err != nil {
		http.Error(w, "Failed to update goal", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(goal)
}

// AddToGoal handles POST /api/finance/goals/{id}/add
func (h *FinanceHandler) AddToGoal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	path := strings.TrimPrefix(r.URL.Path, "/api/finance/goals/")
	parts := strings.Split(path, "/")
	if len(parts) < 2 || parts[0] == "" || parts[1] != "add" {
		http.Error(w, "Goal ID required", http.StatusBadRequest)
		return
	}
	id := parts[0]

	var req struct {
		Amount float64 `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.goalService.AddToGoal(r.Context(), id, req.Amount); err != nil {
		http.Error(w, "Failed to add to goal", http.StatusInternalServerError)
		return
	}

	goal, _ := h.goalService.GetGoal(r.Context(), id)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(goal)
}

// DeleteGoal handles DELETE /api/finance/goals/{id}
func (h *FinanceHandler) DeleteGoal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/goals/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Goal ID required", http.StatusBadRequest)
		return
	}

	if err := h.goalService.DeleteGoal(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete goal", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Assets
// ============================================

// GetAssets handles GET /api/finance/assets
func (h *FinanceHandler) GetAssets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	assets, err := h.assetService.GetAssets(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get assets", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(assets)
}

// CreateAsset handles POST /api/finance/assets
func (h *FinanceHandler) CreateAsset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var asset model.FinanceAsset
	if err := json.NewDecoder(r.Body).Decode(&asset); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	result, err := h.assetService.CreateAsset(r.Context(), userID, &asset)
	if err != nil {
		http.Error(w, "Failed to create asset", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// UpdateAsset handles PUT /api/finance/assets/{id}
func (h *FinanceHandler) UpdateAsset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/assets/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Asset ID required", http.StatusBadRequest)
		return
	}

	var asset model.FinanceAsset
	if err := json.NewDecoder(r.Body).Decode(&asset); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	asset.ID = id
	if err := h.assetService.UpdateAsset(r.Context(), &asset); err != nil {
		http.Error(w, "Failed to update asset", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(asset)
}

// DeleteAsset handles DELETE /api/finance/assets/{id}
func (h *FinanceHandler) DeleteAsset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/assets/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Asset ID required", http.StatusBadRequest)
		return
	}

	if err := h.assetService.DeleteAsset(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete asset", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Liabilities
// ============================================

// GetLiabilities handles GET /api/finance/liabilities
func (h *FinanceHandler) GetLiabilities(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	liabilities, err := h.liabilityService.GetLiabilities(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get liabilities", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(liabilities)
}

// CreateLiability handles POST /api/finance/liabilities
func (h *FinanceHandler) CreateLiability(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var liability model.FinanceLiability
	if err := json.NewDecoder(r.Body).Decode(&liability); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	result, err := h.liabilityService.CreateLiability(r.Context(), userID, &liability)
	if err != nil {
		http.Error(w, "Failed to create liability", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// UpdateLiability handles PUT /api/finance/liabilities/{id}
func (h *FinanceHandler) UpdateLiability(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/liabilities/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Liability ID required", http.StatusBadRequest)
		return
	}

	var liability model.FinanceLiability
	if err := json.NewDecoder(r.Body).Decode(&liability); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	liability.ID = id
	if err := h.liabilityService.UpdateLiability(r.Context(), &liability); err != nil {
		http.Error(w, "Failed to update liability", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(liability)
}

// MakePayment handles POST /api/finance/liabilities/{id}/payment
func (h *FinanceHandler) MakePayment(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	path := strings.TrimPrefix(r.URL.Path, "/api/finance/liabilities/")
	parts := strings.Split(path, "/")
	if len(parts) < 2 || parts[0] == "" || parts[1] != "payment" {
		http.Error(w, "Liability ID required", http.StatusBadRequest)
		return
	}
	id := parts[0]

	var req struct {
		Amount float64 `json:"amount"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if err := h.liabilityService.MakePayment(r.Context(), id, req.Amount); err != nil {
		http.Error(w, "Failed to make payment", http.StatusInternalServerError)
		return
	}

	liability, _ := h.liabilityService.GetLiability(r.Context(), id)
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(liability)
}

// DeleteLiability handles DELETE /api/finance/liabilities/{id}
func (h *FinanceHandler) DeleteLiability(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/liabilities/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Liability ID required", http.StatusBadRequest)
		return
	}

	if err := h.liabilityService.DeleteLiability(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete liability", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Subscriptions
// ============================================

// GetSubscriptions handles GET /api/finance/subscriptions
func (h *FinanceHandler) GetSubscriptions(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	subscriptions, err := h.subscriptionService.GetSubscriptions(r.Context(), userID)
	if err != nil {
		http.Error(w, "Failed to get subscriptions", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subscriptions)
}

// GetUpcomingBills handles GET /api/finance/subscriptions/upcoming
func (h *FinanceHandler) GetUpcomingBills(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	days := 7
	if d := r.URL.Query().Get("days"); d != "" {
		if parsed, err := strconv.Atoi(d); err == nil && parsed > 0 {
			days = parsed
		}
	}

	subscriptions, err := h.subscriptionService.GetUpcoming(r.Context(), userID, days)
	if err != nil {
		http.Error(w, "Failed to get upcoming bills", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subscriptions)
}

// CreateSubscription handles POST /api/finance/subscriptions
func (h *FinanceHandler) CreateSubscription(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var subscription model.FinanceSubscription
	if err := json.NewDecoder(r.Body).Decode(&subscription); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	result, err := h.subscriptionService.CreateSubscription(r.Context(), userID, &subscription)
	if err != nil {
		http.Error(w, "Failed to create subscription", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(result)
}

// UpdateSubscription handles PUT /api/finance/subscriptions/{id}
func (h *FinanceHandler) UpdateSubscription(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/subscriptions/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Subscription ID required", http.StatusBadRequest)
		return
	}

	var subscription model.FinanceSubscription
	if err := json.NewDecoder(r.Body).Decode(&subscription); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	subscription.ID = id
	if err := h.subscriptionService.UpdateSubscription(r.Context(), &subscription); err != nil {
		http.Error(w, "Failed to update subscription", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(subscription)
}

// DeleteSubscription handles DELETE /api/finance/subscriptions/{id}
func (h *FinanceHandler) DeleteSubscription(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/subscriptions/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Subscription ID required", http.StatusBadRequest)
		return
	}

	if err := h.subscriptionService.DeleteSubscription(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete subscription", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Financial Diary
// ============================================

// GetDiaryEntries handles GET /api/finance/diary
func (h *FinanceHandler) GetDiaryEntries(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	limit := 30
	offset := 0

	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}
	if o := r.URL.Query().Get("offset"); o != "" {
		if parsed, err := strconv.Atoi(o); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	entries, err := h.diaryService.GetEntries(r.Context(), userID, limit, offset)
	if err != nil {
		http.Error(w, "Failed to get diary entries", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(entries)
}

// GetDiaryEntryByDate handles GET /api/finance/diary/date/{date}
func (h *FinanceHandler) GetDiaryEntryByDate(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	dateStr := r.URL.Query().Get("date")
	if dateStr == "" {
		dateStr = time.Now().Format("2006-01-02")
	}

	date, err := time.Parse("2006-01-02", dateStr)
	if err != nil {
		http.Error(w, "Invalid date format", http.StatusBadRequest)
		return
	}

	entry, err := h.diaryService.GetEntryByDate(r.Context(), userID, date)
	if err != nil {
		// Return empty entry if not found
		entry = &model.FinanceDiaryEntry{
			Date: date,
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(entry)
}

// CreateDiaryEntry handles POST /api/finance/diary
func (h *FinanceHandler) CreateDiaryEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.CreateDiaryEntryRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	userID := h.getUserID(r)
	entry, err := h.diaryService.CreateEntry(r.Context(), userID, &req)
	if err != nil {
		http.Error(w, "Failed to create diary entry", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(entry)
}

// UpdateDiaryEntry handles PUT /api/finance/diary/{id}
func (h *FinanceHandler) UpdateDiaryEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/diary/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Diary entry ID required", http.StatusBadRequest)
		return
	}

	var entry model.FinanceDiaryEntry
	if err := json.NewDecoder(r.Body).Decode(&entry); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	entry.ID = id
	if err := h.diaryService.UpdateEntry(r.Context(), &entry); err != nil {
		http.Error(w, "Failed to update diary entry", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(entry)
}

// DeleteDiaryEntry handles DELETE /api/finance/diary/{id}
func (h *FinanceHandler) DeleteDiaryEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/finance/diary/")
	if id == "" || strings.Contains(id, "/") {
		http.Error(w, "Diary entry ID required", http.StatusBadRequest)
		return
	}

	if err := h.diaryService.DeleteEntry(r.Context(), id); err != nil {
		http.Error(w, "Failed to delete diary entry", http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// ============================================
// Financial Calculators
// ============================================

// CalculateCompoundInterest handles POST /api/finance/calculators/compound-interest
func (h *FinanceHandler) CalculateCompoundInterest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var input model.CompoundInterestInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	result := h.calculatorService.CalculateCompoundInterest(&input)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// CalculateLoan handles POST /api/finance/calculators/loan
func (h *FinanceHandler) CalculateLoan(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var input model.LoanCalculatorInput
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	result := h.calculatorService.CalculateLoan(&input)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// CalculateSavingsGoal handles POST /api/finance/calculators/savings-goal
func (h *FinanceHandler) CalculateSavingsGoal(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var input struct {
		TargetAmount       float64 `json:"targetAmount"`
		CurrentAmount      float64 `json:"currentAmount"`
		MonthlyContribution float64 `json:"monthlyContribution"`
		AnnualRate         float64 `json:"annualRate"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	months := h.calculatorService.CalculateTimeToGoal(
		input.TargetAmount,
		input.CurrentAmount,
		input.MonthlyContribution,
		input.AnnualRate,
	)

	result := map[string]interface{}{
		"monthsToGoal": months,
		"yearsToGoal":  float64(months) / 12,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// CalculateROI handles POST /api/finance/calculators/roi
func (h *FinanceHandler) CalculateROI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var input struct {
		InitialInvestment float64 `json:"initialInvestment"`
		FinalValue        float64 `json:"finalValue"`
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	roi := h.calculatorService.CalculateROI(input.InitialInvestment, input.FinalValue)

	result := map[string]interface{}{
		"roi": roi,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// CalculateAssetAllocation handles POST /api/finance/calculators/asset-allocation
func (h *FinanceHandler) CalculateAssetAllocation(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var input struct {
		Age             int    `json:"age"`
		RiskTolerance   string `json:"riskTolerance"` // low, medium, high
	}
	if err := json.NewDecoder(r.Body).Decode(&input); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	result := h.calculatorService.CalculateRuleOf110(input.Age, input.RiskTolerance)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(result)
}

// ============================================
// Net Worth
// ============================================

// GetNetWorth handles GET /api/finance/net-worth
func (h *FinanceHandler) GetNetWorth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	history, err := h.netWorthService.GetLatestNetWorth(r.Context(), userID)
	if err != nil {
		// Calculate fresh net worth
		assets, _ := h.accountService.GetTotalBalance(r.Context(), userID)
		assetTotal, _ := h.assetService.GetTotalValue(r.Context(), userID)
		liabilityTotal, _ := h.liabilityService.GetTotalBalance(r.Context(), userID)

		history = &model.NetWorthHistory{
			TotalAssets:      assets + assetTotal,
			TotalLiabilities: liabilityTotal,
			NetWorth:         (assets + assetTotal) - liabilityTotal,
		}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}

// GetNetWorthHistory handles GET /api/finance/net-worth/history
func (h *FinanceHandler) GetNetWorthHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)
	limit := 12
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	history, err := h.netWorthService.GetNetWorthHistory(r.Context(), userID, limit)
	if err != nil {
		http.Error(w, "Failed to get net worth history", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}

// RecalculateNetWorth handles POST /api/finance/net-worth/calculate
func (h *FinanceHandler) RecalculateNetWorth(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := h.getUserID(r)

	// Calculate fresh net worth
	assets, _ := h.accountService.GetTotalBalance(r.Context(), userID)
	assetTotal, _ := h.assetService.GetTotalValue(r.Context(), userID)
	liabilityTotal, _ := h.liabilityService.GetTotalBalance(r.Context(), userID)

	now := time.Now()
	history := &model.NetWorthHistory{
		UserID:           userID,
		Date:             now,
		TotalAssets:      assets + assetTotal,
		TotalLiabilities: liabilityTotal,
		NetWorth:         (assets + assetTotal) - liabilityTotal,
		CreatedAt:        now,
	}

	// Save to database using direct SQL (simplified)
	_, err := h.pool.Exec(r.Context(), `
		INSERT INTO finance_net_worth_history (user_id, date, total_assets, total_liabilities, net_worth, created_at)
		VALUES ($1, $2, $3, $4, $5, $6)
	`, userID, history.Date, history.TotalAssets, history.TotalLiabilities, history.NetWorth, history.CreatedAt)

	if err != nil {
		http.Error(w, "Failed to save net worth", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}
