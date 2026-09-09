package http

import (
	"context"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"trading-bot-system/backend/internal/domain/model"
)

type dcaAuthService struct {
	dcaBotService
	bot              *model.DCABot
	err              error
	lookups, actions int
}

func (s *dcaAuthService) GetBot(context.Context, string) (*model.DCABot, error) {
	s.lookups++
	return s.bot, s.err
}
func (s *dcaAuthService) StartBot(context.Context, string) error  { s.actions++; return nil }
func (s *dcaAuthService) StopBot(context.Context, string) error   { s.actions++; return nil }
func (s *dcaAuthService) DeleteBot(context.Context, string) error { s.actions++; return nil }
func (s *dcaAuthService) GetBotOrders(context.Context, string, int) ([]model.DCAOrder, error) {
	s.actions++
	return nil, nil
}

func TestDCABotOwnership(t *testing.T) {
	for _, endpoint := range []struct {
		name, method, suffix string
		handle               func(*DCABotHandler, http.ResponseWriter, *http.Request)
	}{
		{"get", "GET", "", (*DCABotHandler).GetBot},
		{"start", "POST", "/start", (*DCABotHandler).StartBot},
		{"stop", "POST", "/stop", (*DCABotHandler).StopBot},
		{"delete", "DELETE", "", (*DCABotHandler).DeleteBot},
		{"orders", "GET", "/orders", (*DCABotHandler).GetBotOrders},
	} {
		for _, tc := range []struct {
			name, user string
			bot        *model.DCABot
			err        error
			want       int
		}{
			{"owner", "user-a", &model.DCABot{UserID: "user-a"}, nil, 200},
			{"foreign", "user-b", &model.DCABot{UserID: "user-a"}, nil, 403},
			{"unowned", "user-a", &model.DCABot{}, nil, 403},
			{"nil", "user-a", nil, nil, 403},
			{"missing", "user-a", nil, errors.New("missing"), 404},
			{"anonymous", "", &model.DCABot{UserID: "user-a"}, nil, 401},
		} {
			t.Run(endpoint.name+"/"+tc.name, func(t *testing.T) {
				svc := &dcaAuthService{bot: tc.bot, err: tc.err}
				sessions := &memorySessionStore{}
				if tc.user != "" {
					_ = sessions.SetSession(context.Background(), "fixture", tc.user, time.Hour)
				}
				h := &DCABotHandler{dcaService: svc, authHandler: &AuthHandler{sessions: sessions}}
				req := httptest.NewRequest(endpoint.method, "/api/dca/bots/bot-a"+endpoint.suffix+"?user_id=user-a", nil)
				req.Header.Set("Authorization", "Bearer fixture")
				res := httptest.NewRecorder()
				endpoint.handle(h, res, req)
				want := tc.want
				if endpoint.name == "delete" && want == 200 {
					want = 204
				}
				if res.Code != want {
					t.Fatalf("got %d want %d", res.Code, want)
				}
				if want >= 400 && svc.actions != 0 {
					t.Fatal("unauthorized downstream action")
				}
				if want < 400 && endpoint.name != "get" && svc.actions != 1 {
					t.Fatal("owner action not executed")
				}
				if tc.user == "" && svc.lookups != 0 {
					t.Fatal("anonymous request reached storage")
				}
			})
		}
	}
}
