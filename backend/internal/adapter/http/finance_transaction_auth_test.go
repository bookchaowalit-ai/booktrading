package http

import (
	"context"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
	"trading-bot-system/backend/internal/domain/service"
)

type transactionAuthRepo struct {
	repository.FinanceTransactionRepository
	stored  *model.FinanceTransaction
	written *model.FinanceTransaction
	writes  int
}

func (r *transactionAuthRepo) GetByID(context.Context, string) (*model.FinanceTransaction, error) {
	return r.stored, nil
}
func (r *transactionAuthRepo) Create(_ context.Context, v *model.FinanceTransaction) error {
	r.writes++
	r.written = v
	return nil
}
func (r *transactionAuthRepo) Update(_ context.Context, v *model.FinanceTransaction) error {
	r.writes++
	r.written = v
	return nil
}
func (r *transactionAuthRepo) Delete(context.Context, string) error { r.writes++; return nil }

type transactionAccountRepo struct {
	repository.FinanceAccountRepository
	accounts map[string]*model.FinanceAccount
	balances int
}

func (r *transactionAccountRepo) GetByID(_ context.Context, id string) (*model.FinanceAccount, error) {
	return r.accounts[id], nil
}
func (r *transactionAccountRepo) UpdateBalance(context.Context, string, float64, bool) error {
	r.balances++
	return nil
}

type transactionCategoryRepo struct {
	repository.FinanceCategoryRepository
	category *model.FinanceCategory
}

func (r *transactionCategoryRepo) GetByID(context.Context, string) (*model.FinanceCategory, error) {
	return r.category, nil
}

func TestFinanceTransactionAuthorization(t *testing.T) {
	for _, method := range []string{"POST", "PUT", "DELETE"} {
		for _, scenario := range []string{"owner", "foreign-transaction", "unowned-transaction", "missing-transaction", "foreign-account", "missing-account", "foreign-old-account", "foreign-category", "missing-category", "unowned-category", "system-category", "forged-system-category", "anonymous"} {
			// Creation has no stored transaction; deletion does not change category.
			if method == "POST" && (strings.Contains(scenario, "transaction") || scenario == "foreign-old-account") {
				continue
			}
			if method == "DELETE" && strings.Contains(scenario, "category") {
				continue
			}
			t.Run(method+"/"+scenario, func(t *testing.T) {
				tx := &transactionAuthRepo{stored: &model.FinanceTransaction{ID: "tx-a", UserID: "user-a", AccountID: "old-account", Type: model.TransactionTypeExpense, Amount: 10}}
				accounts := &transactionAccountRepo{accounts: map[string]*model.FinanceAccount{
					"old-account": {UserID: "user-a"},
					"new-account": {UserID: "user-a"},
				}}
				categories := &transactionCategoryRepo{category: &model.FinanceCategory{UserID: "user-a"}}
				userID := "user-a"
				want := 404
				switch scenario {
				case "owner":
					want = 200
				case "foreign-transaction":
					tx.stored.UserID = "user-b"
				case "unowned-transaction":
					tx.stored.UserID = ""
				case "missing-transaction":
					tx.stored = nil
				case "foreign-account":
					accounts.accounts["new-account"].UserID = "user-b"
					if method == "DELETE" {
						accounts.accounts["old-account"].UserID = "user-b"
					}
				case "missing-account":
					delete(accounts.accounts, "new-account")
					if method == "DELETE" {
						delete(accounts.accounts, "old-account")
					}
				case "foreign-old-account":
					accounts.accounts["old-account"].UserID = "user-b"
				case "foreign-category":
					categories.category.UserID = "user-b"
				case "missing-category":
					categories.category = nil
				case "unowned-category":
					categories.category.UserID = ""
				case "system-category":
					categories.category.UserID = "system"
					categories.category.IsSystem = true
					want = 200
				case "forged-system-category":
					categories.category.UserID = "user-b"
					categories.category.IsSystem = true
				case "anonymous":
					userID = ""
					want = 401
				}
				sessions := &memorySessionStore{}
				if userID != "" {
					_ = sessions.SetSession(context.Background(), "fixture", userID, time.Hour)
				}
				h := &FinanceHandler{transactionService: service.NewFinanceTransactionService(tx, accounts, categories), authHandler: &AuthHandler{sessions: sessions}}
				req := httptest.NewRequest(method, "/api/finance/transactions/tx-a?user_id=user-b", strings.NewReader(`{"id":"spoofed","user_id":"user-b","account_id":"new-account","category_id":"category-a","type":"expense","amount":10}`))
				req.Header.Set("Authorization", "Bearer fixture")
				res := httptest.NewRecorder()
				switch method {
				case "POST":
					h.CreateTransaction(res, req)
					if want == 200 {
						want = 201
					}
				case "PUT":
					h.UpdateTransaction(res, req)
				case "DELETE":
					h.DeleteTransaction(res, req)
					if want == 200 {
						want = 204
					}
				}
				if res.Code != want {
					t.Fatalf("got %d want %d", res.Code, want)
				}
				if want >= 400 && (tx.writes != 0 || accounts.balances != 0) {
					t.Fatal("rejected request mutated transaction or balance")
				}
				if want < 400 {
					if tx.writes != 1 {
						t.Fatal("owner write missing")
					}
					if method != "PUT" && accounts.balances != 1 {
						t.Fatal("owner balance update missing")
					}
					if tx.written != nil && (tx.written.UserID != "user-a" || tx.written.ID == "spoofed") {
						t.Fatal("identity spoofing")
					}
					if method == "PUT" && tx.written.ID != "tx-a" {
						t.Fatal("URL identity not enforced")
					}
				}
			})
		}
	}
}

func TestFinanceTransactionAnonymousNeverReachesStorage(t *testing.T) {
	s := service.NewFinanceTransactionService(nil, nil, nil)
	ctx := context.Background()
	if _, err := s.CreateTransaction(ctx, "", &model.CreateTransactionRequest{}); err != service.ErrFinanceAccessDenied {
		t.Fatal(err)
	}
	if err := s.UpdateTransaction(ctx, "", &model.FinanceTransaction{}); err != service.ErrFinanceAccessDenied {
		t.Fatal(err)
	}
	if err := s.DeleteTransaction(ctx, "", "tx-a"); err != service.ErrFinanceAccessDenied {
		t.Fatal(err)
	}
}
