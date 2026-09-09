package http

import (
	"context"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestSensitiveRoutesRequireSession(t *testing.T) {
	paths := []string{"/api/paper", "/api/trade", "/api/metrics", "/api/journal", "/api/bot", "/api/portfolio", "/api/trades", "/api/performance", "/api/exchange", "/api/orders", "/api/notifications", "/api/settings", "/api/price-alerts", "/api/risk", "/api/poly-paper", "/api/command-center", "/api/real-grid", "/api/dashboard", "/api/auth/login/extra", "/api/health/private"}
	sessions := &memorySessionStore{}
	_ = sessions.SetSession(context.Background(), "fixture-session", "fixture-user", time.Hour)
	mux := http.NewServeMux()
	mux.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) { w.WriteHeader(http.StatusNoContent) })
	router := &Router{mux: mux, authHandler: &AuthHandler{sessions: sessions}}
	for _, path := range paths {
		for _, method := range []string{http.MethodGet, http.MethodPost} {
			for _, token := range []string{"", "invalid-session", "fixture-session"} {
				req := httptest.NewRequest(method, path, nil)
				if token != "" {
					req.Header.Set("Authorization", "Bearer "+token)
				}
				// Use distinct clients to keep the authentication assertion independent of rate limiting.
				req.RemoteAddr = path + method + token + ":1234"
				res := httptest.NewRecorder()
				router.ServeHTTP(res, req)
				want := http.StatusUnauthorized
				if token == "fixture-session" {
					want = http.StatusNoContent
				}
				if res.Code != want {
					t.Fatalf("%s %s token-present=%t: got %d want %d", method, path, token != "", res.Code, want)
				}
			}
		}
	}
}

func TestPublicRoutesAreExact(t *testing.T) {
	for _, path := range []string{"/api/auth/login", "/api/auth/register", "/api/health"} {
		if !isPublicRoute(path) {
			t.Fatalf("bootstrap endpoint protected: %s", path)
		}
		if isPublicRoute(path + "/extra") {
			t.Fatalf("public prefix bypass: %s", path)
		}
	}
}

func TestMemorySessionLifecycle(t *testing.T) {
	store := &memorySessionStore{}
	ctx := context.Background()
	_ = store.SetSession(ctx, "fixture", "user", time.Hour)
	if user, ok := store.GetSession(ctx, "fixture"); !ok || user != "user" {
		t.Fatal("valid session rejected")
	}
	// Force expiry deterministically, without sleeping.
	store.expires["fixture"] = time.Now().Add(-time.Second)
	if _, ok := store.GetSession(ctx, "fixture"); ok {
		t.Fatal("expired session accepted")
	}
	if len(store.tokens) != 0 || len(store.expires) != 0 {
		t.Fatal("expired session not removed")
	}
	for _, ttl := range []time.Duration{0, -time.Hour} {
		_ = store.SetSession(ctx, "fixture", "user", ttl)
		if _, ok := store.GetSession(ctx, "fixture"); ok {
			t.Fatal("nonpositive TTL accepted")
		}
	}
	_ = store.SetSession(ctx, "fixture", "user", time.Hour)
	store.DeleteSession(ctx, "fixture")
	if _, ok := store.GetSession(ctx, "fixture"); ok {
		t.Fatal("revoked session accepted")
	}
}
