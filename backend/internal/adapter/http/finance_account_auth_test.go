package http

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
	"trading-bot-system/backend/internal/domain/service"
)

type accountAuthRepo struct {
	repository.FinanceAccountRepository
	owner            string
	missing          bool
	updates, deletes int
	updated          *model.FinanceAccount
}

func (r *accountAuthRepo) GetByID(context.Context, string) (*model.FinanceAccount, error) {
	if r.missing {
		return nil, errors.New("missing")
	}
	return &model.FinanceAccount{ID: "account-a", UserID: r.owner}, nil
}
func (r *accountAuthRepo) Update(_ context.Context, a *model.FinanceAccount) error {
	r.updates++
	r.updated = a
	return nil
}
func (r *accountAuthRepo) Delete(context.Context, string) error { r.deletes++; return nil }

func TestAccountMutationsRequireOwnership(t *testing.T) {
	for _, method := range []string{http.MethodPut, http.MethodDelete} {
		for _, tc := range []struct {
			name, owner, user string
			missing           bool
			want              int
		}{
			{"owner", "user-a", "user-a", false, 200},
			{"foreign", "user-a", "user-b", false, 404},
			{"unowned", "", "user-a", false, 404},
			{"missing", "user-a", "user-a", true, 404},
			{"anonymous", "user-a", "", false, 401},
		} {
			t.Run(method+"/"+tc.name, func(t *testing.T) {
				repo := &accountAuthRepo{owner: tc.owner, missing: tc.missing}
				sessions := &memorySessionStore{}
				if tc.user != "" {
					_ = sessions.SetSession(context.Background(), "fixture", tc.user, time.Hour)
				}
				handler := &FinanceHandler{accountService: service.NewFinanceAccountService(repo), authHandler: &AuthHandler{sessions: sessions}}
				req := httptest.NewRequest(method, "/api/finance/accounts/account-a?user_id=forged-user", strings.NewReader(`{"id":"other-account","user_id":"forged-user","name":"fixture"}`))
				req.Header.Set("Authorization", "Bearer fixture")
				res := httptest.NewRecorder()
				want := tc.want
				if method == http.MethodPut {
					handler.UpdateAccount(res, req)
				} else {
					handler.DeleteAccount(res, req)
					if want == 200 {
						want = 204
					}
				}
				if res.Code != want {
					t.Fatalf("got %d want %d", res.Code, want)
				}
				if want >= 400 && repo.updates+repo.deletes != 0 {
					t.Fatal("unauthorized persistence")
				}
				if want < 400 && repo.updates+repo.deletes != 1 {
					t.Fatal("owner operation not persisted")
				}
				if repo.updated != nil && (repo.updated.UserID != tc.user || repo.updated.ID != "account-a") {
					t.Fatal("request spoofed identity")
				}
			})
		}
	}
}
