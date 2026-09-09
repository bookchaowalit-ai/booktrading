package http

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
	"trading-bot-system/backend/internal/domain/service"
)

type resourceMutationTracker struct{ lookups, writes int }

type budgetAuthRepo struct {
	repository.FinanceBudgetRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *budgetAuthRepo) GetByID(context.Context, string) (*model.FinanceBudget, error) {
	r.tracker.lookups++
	return &model.FinanceBudget{ID: "resource", UserID: r.owner}, nil
}
func (r *budgetAuthRepo) Update(context.Context, *model.FinanceBudget) error {
	r.tracker.writes++
	return nil
}
func (r *budgetAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type goalAuthRepo struct {
	repository.FinanceGoalRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *goalAuthRepo) GetByID(context.Context, string) (*model.FinanceGoal, error) {
	r.tracker.lookups++
	return &model.FinanceGoal{ID: "resource", UserID: r.owner, TargetAmount: 100}, nil
}
func (r *goalAuthRepo) Update(context.Context, *model.FinanceGoal) error {
	r.tracker.writes++
	return nil
}
func (r *goalAuthRepo) UpdateProgress(context.Context, string, float64, bool) error {
	r.tracker.writes++
	return nil
}
func (r *goalAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type assetAuthRepo struct {
	repository.FinanceAssetRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *assetAuthRepo) GetByID(context.Context, string) (*model.FinanceAsset, error) {
	r.tracker.lookups++
	return &model.FinanceAsset{ID: "resource", UserID: r.owner}, nil
}
func (r *assetAuthRepo) Update(context.Context, *model.FinanceAsset) error {
	r.tracker.writes++
	return nil
}
func (r *assetAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type liabilityAuthRepo struct {
	repository.FinanceLiabilityRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *liabilityAuthRepo) GetByID(context.Context, string) (*model.FinanceLiability, error) {
	r.tracker.lookups++
	return &model.FinanceLiability{ID: "resource", UserID: r.owner, CurrentBalance: 100}, nil
}
func (r *liabilityAuthRepo) Update(context.Context, *model.FinanceLiability) error {
	r.tracker.writes++
	return nil
}
func (r *liabilityAuthRepo) UpdateBalance(context.Context, string, float64, bool) error {
	r.tracker.writes++
	return nil
}
func (r *liabilityAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type subscriptionAuthRepo struct {
	repository.FinanceSubscriptionRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *subscriptionAuthRepo) GetByID(context.Context, string) (*model.FinanceSubscription, error) {
	r.tracker.lookups++
	return &model.FinanceSubscription{ID: "resource", UserID: r.owner}, nil
}
func (r *subscriptionAuthRepo) Update(context.Context, *model.FinanceSubscription) error {
	r.tracker.writes++
	return nil
}
func (r *subscriptionAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type diaryAuthRepo struct {
	repository.FinanceDiaryRepository
	owner   string
	tracker *resourceMutationTracker
}

func (r *diaryAuthRepo) GetByID(context.Context, string) (*model.FinanceDiaryEntry, error) {
	r.tracker.lookups++
	return &model.FinanceDiaryEntry{ID: "resource", UserID: r.owner}, nil
}
func (r *diaryAuthRepo) Update(context.Context, *model.FinanceDiaryEntry) error {
	r.tracker.writes++
	return nil
}
func (r *diaryAuthRepo) Delete(context.Context, string) error { r.tracker.writes++; return nil }

type financeMutationCase struct {
	name, method, path, body string
	setup                    func(string, *resourceMutationTracker) *FinanceHandler
	invoke                   func(*FinanceHandler, http.ResponseWriter, *http.Request)
}

func newResourceAuthHandler(sessions *memorySessionStore, userID string) *AuthHandler {
	if userID != "" {
		_ = sessions.SetSession(context.Background(), "fixture", userID, time.Hour)
	}
	return &AuthHandler{sessions: sessions}
}

func TestFinanceResourceMutationsRequireOwnership(t *testing.T) {
	cases := []financeMutationCase{
		{
			name: "budget/update", method: http.MethodPut, path: "/api/finance/budgets/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{budgetService: service.NewFinanceBudgetService(&budgetAuthRepo{owner: owner, tracker: tracker}, nil)}
			}, invoke: (*FinanceHandler).UpdateBudget,
		},
		{
			name: "budget/delete", method: http.MethodDelete, path: "/api/finance/budgets/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{budgetService: service.NewFinanceBudgetService(&budgetAuthRepo{owner: owner, tracker: tracker}, nil)}
			}, invoke: (*FinanceHandler).DeleteBudget,
		},
		{
			name: "goal/update", method: http.MethodPut, path: "/api/finance/goals/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{goalService: service.NewFinanceGoalService(&goalAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).UpdateGoal,
		},
		{
			name: "goal/add", method: http.MethodPost, path: "/api/finance/goals/resource/add", body: `{"amount":1}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{goalService: service.NewFinanceGoalService(&goalAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).AddToGoal,
		},
		{
			name: "goal/delete", method: http.MethodDelete, path: "/api/finance/goals/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{goalService: service.NewFinanceGoalService(&goalAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).DeleteGoal,
		},
		{
			name: "asset/update", method: http.MethodPut, path: "/api/finance/assets/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{assetService: service.NewFinanceAssetService(&assetAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).UpdateAsset,
		},
		{
			name: "asset/delete", method: http.MethodDelete, path: "/api/finance/assets/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{assetService: service.NewFinanceAssetService(&assetAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).DeleteAsset,
		},
		{
			name: "liability/update", method: http.MethodPut, path: "/api/finance/liabilities/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{liabilityService: service.NewFinanceLiabilityService(&liabilityAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).UpdateLiability,
		},
		{
			name: "liability/payment", method: http.MethodPost, path: "/api/finance/liabilities/resource/payment", body: `{"amount":1}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{liabilityService: service.NewFinanceLiabilityService(&liabilityAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).MakePayment,
		},
		{
			name: "liability/delete", method: http.MethodDelete, path: "/api/finance/liabilities/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{liabilityService: service.NewFinanceLiabilityService(&liabilityAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).DeleteLiability,
		},
		{
			name: "subscription/update", method: http.MethodPut, path: "/api/finance/subscriptions/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{subscriptionService: service.NewFinanceSubscriptionService(&subscriptionAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).UpdateSubscription,
		},
		{
			name: "subscription/delete", method: http.MethodDelete, path: "/api/finance/subscriptions/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{subscriptionService: service.NewFinanceSubscriptionService(&subscriptionAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).DeleteSubscription,
		},
		{
			name: "diary/update", method: http.MethodPut, path: "/api/finance/diary/resource", body: `{}`,
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{diaryService: service.NewFinanceDiaryService(&diaryAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).UpdateDiaryEntry,
		},
		{
			name: "diary/delete", method: http.MethodDelete, path: "/api/finance/diary/resource",
			setup: func(owner string, tracker *resourceMutationTracker) *FinanceHandler {
				return &FinanceHandler{diaryService: service.NewFinanceDiaryService(&diaryAuthRepo{owner: owner, tracker: tracker})}
			}, invoke: (*FinanceHandler).DeleteDiaryEntry,
		},
	}

	for _, tc := range cases {
		for _, scenario := range []struct {
			name, owner, user string
			want              int
		}{
			{name: "owner", owner: "user-a", user: "user-a", want: http.StatusOK},
			{name: "foreign", owner: "user-a", user: "user-b", want: http.StatusNotFound},
			{name: "unowned", owner: "", user: "user-a", want: http.StatusNotFound},
			{name: "anonymous", owner: "user-a", user: "", want: http.StatusUnauthorized},
		} {
			t.Run(tc.name+"/"+scenario.name, func(t *testing.T) {
				tracker := &resourceMutationTracker{}
				sessions := &memorySessionStore{}
				h := tc.setup(scenario.owner, tracker)
				h.authHandler = newResourceAuthHandler(sessions, scenario.user)
				req := httptest.NewRequest(tc.method, tc.path+"?user_id=forged", strings.NewReader(tc.body))
				if scenario.user != "" {
					req.Header.Set("Authorization", "Bearer fixture")
				}
				res := httptest.NewRecorder()
				tc.invoke(h, res, req)
				want := scenario.want
				if scenario.name == "owner" && tc.method == http.MethodDelete {
					want = http.StatusNoContent
				}
				if res.Code != want {
					t.Fatalf("got %d want %d", res.Code, want)
				}
				if scenario.name != "owner" && tracker.writes != 0 {
					t.Fatalf("rejected request performed %d writes", tracker.writes)
				}
				if scenario.name == "anonymous" && tracker.lookups != 0 {
					t.Fatal("anonymous request reached resource storage")
				}
				if scenario.name == "owner" && tracker.writes != 1 {
					t.Fatalf("owner mutation writes=%d", tracker.writes)
				}
			})
		}
	}
}
