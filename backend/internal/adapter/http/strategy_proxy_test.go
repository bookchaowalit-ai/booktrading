package http

import (
	"context"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"strings"
	"sync/atomic"
	"testing"
	"time"
)

const (
	testServiceToken = "fixture-service-token"
	testUserSession  = "fixture-user-session"
	testTraderSess   = "fixture-trader-session"
)

type upstreamRecorder struct {
	calls   atomic.Int32
	auth    atomic.Value
	cookie  atomic.Value
	path    atomic.Value
	query   atomic.Value
	body    atomic.Value
	xff     atomic.Value
	handler http.HandlerFunc
}

func newStrategyUpstream(t *testing.T, rec *upstreamRecorder) *httptest.Server {
	t.Helper()
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		rec.calls.Add(1)
		rec.auth.Store(r.Header.Get("Authorization"))
		rec.cookie.Store(r.Header.Get("Cookie"))
		rec.path.Store(r.URL.Path)
		rec.query.Store(r.URL.RawQuery)
		rec.xff.Store(r.Header.Get("X-Forwarded-For"))
		b, _ := io.ReadAll(r.Body)
		rec.body.Store(string(b))
		if rec.handler != nil {
			rec.handler(w, r)
			return
		}
		w.Header().Set("Access-Control-Allow-Origin", "*")
		w.Header().Set("Set-Cookie", "upstream=1")
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"ok":true}`))
	}))
	t.Cleanup(srv.Close)
	return srv
}

func newTestStrategyProxy(t *testing.T, upstream string, timeout time.Duration) *StrategyProxy {
	t.Helper()
	sessions := &memorySessionStore{}
	_ = sessions.SetSession(context.Background(), testUserSession, "fixture-user", time.Hour)
	_ = sessions.SetSession(context.Background(), testTraderSess, "fixture-trader", time.Hour)
	auth := &AuthHandler{sessions: sessions, users: newMemoryUserStore(
		authUser{ID: "fixture-user", Email: "admin@example.test", Role: RoleAdmin},
		authUser{ID: "fixture-trader", Email: "trader@example.test", Role: "trader"},
	)}
	p, err := NewStrategyProxy(StrategyProxyConfig{
		UpstreamURL:  upstream,
		ServiceToken: testServiceToken,
		Validate:     auth.ValidateToken,
		IsAdmin:      auth.IsAdmin,
		Timeout:      timeout,
		MaxBody:      64,
	})
	if err != nil {
		t.Fatalf("NewStrategyProxy: %v", err)
	}
	return p
}

func TestStrategyProxyRejectsUnauthenticatedWithoutUpstreamCall(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	for _, auth := range []string{"", "Bearer ", "Bearer not-a-session", "Basic " + testUserSession, "Bearer " + testServiceToken} {
		for _, method := range []string{http.MethodGet, http.MethodPost} {
			req := httptest.NewRequest(method, "/strategy-api/api/real-grid/kill", strings.NewReader(`{}`))
			if auth != "" {
				req.Header.Set("Authorization", auth)
			}
			w := httptest.NewRecorder()
			p.ServeHTTP(w, req)
			if w.Code != http.StatusUnauthorized {
				t.Fatalf("%s auth=%q: status %d, want 401", method, auth, w.Code)
			}
		}
	}
	if n := rec.calls.Load(); n != 0 {
		t.Fatalf("upstream called %d times for unauthenticated requests", n)
	}
}

func TestStrategyProxyForwardsServiceTokenNotUserToken(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	req := httptest.NewRequest(http.MethodPost, "/strategy-api/api/backtest/run?symbol=BTCTHB&x=1", strings.NewReader(`{"a":1}`))
	req.Header.Set("Authorization", "Bearer "+testUserSession)
	req.Header.Set("Cookie", "session=browser")
	req.Header.Set("X-Forwarded-For", "203.0.113.9")
	w := httptest.NewRecorder()
	p.ServeHTTP(w, req)

	if w.Code != http.StatusOK {
		t.Fatalf("status %d, body %s", w.Code, w.Body.String())
	}
	if got := rec.auth.Load(); got != "Bearer "+testServiceToken {
		t.Fatalf("upstream Authorization = %q, want service token", got)
	}
	if got := rec.auth.Load().(string); strings.Contains(got, testUserSession) {
		t.Fatal("user session token leaked upstream")
	}
	if got := rec.cookie.Load(); got != "" {
		t.Fatalf("cookie forwarded upstream: %q", got)
	}
	if got := rec.xff.Load(); got != "" {
		t.Fatalf("client X-Forwarded-For forwarded: %q", got)
	}
	if got := rec.path.Load(); got != "/api/backtest/run" {
		t.Fatalf("upstream path = %q", got)
	}
	if got := rec.query.Load(); got != "symbol=BTCTHB&x=1" {
		t.Fatalf("upstream query = %q", got)
	}
	if got := rec.body.Load(); got != `{"a":1}` {
		t.Fatalf("upstream body = %q", got)
	}
	if w.Header().Get("Access-Control-Allow-Origin") != "" || w.Header().Get("Set-Cookie") != "" {
		t.Fatal("upstream CORS/cookie headers must be stripped")
	}
}

func TestStrategyProxyRejectsTraversalAndUnlistedPaths(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	cases := map[string]int{
		"/strategy-api/api/real-grid/../../v1/world/import": http.StatusBadRequest,
		"/strategy-api/api/real-grid/%2e%2e/v1/world":       http.StatusBadRequest,
		"/strategy-api/api/real-grid/%2E%2E/v1/world":       http.StatusBadRequest,
		"/strategy-api/api/real-grid%2fstatus":              http.StatusBadRequest,
		"/strategy-api/api/real-grid/%5c..%5cx":             http.StatusBadRequest,
		"/strategy-api/api//real-grid/status":               http.StatusBadRequest,
		"/strategy-api/api/./real-grid/status":              http.StatusBadRequest,
		"/strategy-api/api/v1/world/import":                 http.StatusNotFound,
		"/strategy-api/docs":                                http.StatusNotFound,
		"/strategy-api/openapi.json":                        http.StatusNotFound,
		"/strategy-api/":                                    http.StatusNotFound,
		"/strategy-api/api":                                 http.StatusNotFound,
		"/strategy-apix/api/health":                         http.StatusNotFound,
	}
	for path, want := range cases {
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		if err := setRawPath(req, path); err != nil {
			t.Fatalf("%s: %v", path, err)
		}
		req.Header.Set("Authorization", "Bearer "+testUserSession)
		w := httptest.NewRecorder()
		p.ServeHTTP(w, req)
		if w.Code != want {
			t.Errorf("%s: status %d, want %d", path, w.Code, want)
		}
	}
	if n := rec.calls.Load(); n != 0 {
		t.Fatalf("upstream called %d times for rejected paths", n)
	}
}

func TestStrategyProxyHealthIsPublicGetOnly(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	w := httptest.NewRecorder()
	p.ServeHTTP(w, httptest.NewRequest(http.MethodGet, "/strategy-api/api/health", nil))
	if w.Code != http.StatusOK {
		t.Fatalf("public health: status %d", w.Code)
	}
	if got := rec.auth.Load(); got != "Bearer "+testServiceToken {
		t.Fatalf("health upstream Authorization = %q", got)
	}

	w = httptest.NewRecorder()
	p.ServeHTTP(w, httptest.NewRequest(http.MethodPost, "/strategy-api/api/health", nil))
	if w.Code != http.StatusUnauthorized {
		t.Fatalf("POST health without session: status %d, want 401", w.Code)
	}
	if !isPublicRoute(StrategyProxyPrefix + "/api/health") {
		t.Fatal("router must treat the proxied health probe as public")
	}
	if isPublicRoute(StrategyProxyPrefix + "/api/real-grid/kill") {
		t.Fatal("router must not treat proxied routes as public")
	}
}

func TestStrategyProxyLimitsBodyMethodAndTime(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	req := httptest.NewRequest(http.MethodPost, "/strategy-api/api/backtest/run", strings.NewReader(strings.Repeat("x", 65)))
	req.Header.Set("Authorization", "Bearer "+testUserSession)
	w := httptest.NewRecorder()
	p.ServeHTTP(w, req)
	if w.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("oversized body: status %d, want 413", w.Code)
	}

	req = httptest.NewRequest("TRACE", "/strategy-api/api/health", nil)
	w = httptest.NewRecorder()
	p.ServeHTTP(w, req)
	if w.Code != http.StatusMethodNotAllowed {
		t.Fatalf("TRACE: status %d, want 405", w.Code)
	}
	if n := rec.calls.Load(); n != 0 {
		t.Fatalf("upstream called %d times", n)
	}

	slow := &upstreamRecorder{handler: func(w http.ResponseWriter, r *http.Request) {
		select {
		case <-time.After(2 * time.Second):
		case <-r.Context().Done():
		}
	}}
	slowSrv := newStrategyUpstream(t, slow)
	sp := newTestStrategyProxy(t, slowSrv.URL, 50*time.Millisecond)
	req = httptest.NewRequest(http.MethodGet, "/strategy-api/api/real-grid/status", nil)
	req.Header.Set("Authorization", "Bearer "+testUserSession)
	w = httptest.NewRecorder()
	sp.ServeHTTP(w, req)
	if w.Code != http.StatusGatewayTimeout {
		t.Fatalf("slow upstream: status %d, want 504", w.Code)
	}
}

func TestStrategyProxyUpstreamValidation(t *testing.T) {
	validate := func(string) (string, bool) { return "", false }
	for _, bad := range []string{"", "strategy:8000", "ftp://strategy", "http://user:pw@strategy:8000", "http://strategy:8000/api", "http://strategy:8000?x=1"} {
		if _, err := NewStrategyProxy(StrategyProxyConfig{UpstreamURL: bad, Validate: validate}); err == nil {
			t.Errorf("upstream %q accepted", bad)
		}
	}
	if _, err := NewStrategyProxy(StrategyProxyConfig{UpstreamURL: "http://strategy:8000"}); err == nil {
		t.Error("missing validator accepted")
	}
	if _, err := NewStrategyProxy(StrategyProxyConfig{UpstreamURL: "http://strategy:8000/", Validate: validate}); err != nil {
		t.Errorf("trailing slash rejected: %v", err)
	}
}

// setRawPath sets the request path from an already-escaped form, the way the
// server would parse it off the wire.
// privilegedStrategyRoutes mirrors the write routes of the strategy service
// that are reachable through the allow-list.
var privilegedStrategyRoutes = []struct{ method, path string }{
	{http.MethodPost, "/strategy-api/api/real-grid/kill"},
	{http.MethodPost, "/strategy-api/api/real-grid/enable"},
	{http.MethodPost, "/strategy-api/api/real-grid/restart"},
	{http.MethodPut, "/strategy-api/api/real-grid/config/BTCTHB"},
	{http.MethodPost, "/strategy-api/api/strategy/config"},
	{http.MethodPost, "/strategy-api/api/strategy/reset"},
	{http.MethodPost, "/strategy-api/api/risk/reset"},
	{http.MethodPost, "/strategy-api/api/brain/refresh"},
	{http.MethodPost, "/strategy-api/api/brain/reset-cb"},
	{http.MethodPost, "/strategy-api/api/poly-paper/reset-kill-switch"},
	{http.MethodPost, "/strategy-api/api/arb-paper/reset"},
	{http.MethodPost, "/strategy-api/api/backtest"},
	{http.MethodPost, "/strategy-api/api/backtest/run"},
	{http.MethodPost, "/strategy-api/api/backtest/sweep"},
	{http.MethodPost, "/strategy-api/api/backtest/compare"},
	{http.MethodPost, "/strategy-api/api/backtest/walk-forward"},
	{http.MethodPost, "/strategy-api/api/airdrop-tracker/tasks"},
	{http.MethodPatch, "/strategy-api/api/airdrop-tracker/tasks/t1"},
	{http.MethodPatch, "/strategy-api/api/airdrop-tracker/tasks/t1/subtasks/0"},
	{http.MethodDelete, "/strategy-api/api/airdrop-tracker/tasks/t1"},
	{http.MethodPost, "/strategy-api/api/signal-tracker/evaluate"},
}

func TestStrategyProxyPrivilegedRoutesRequireAdmin(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	for _, rt := range privilegedStrategyRoutes {
		req := httptest.NewRequest(rt.method, rt.path, strings.NewReader(`{}`))
		req.Header.Set("Authorization", "Bearer "+testTraderSess)
		w := httptest.NewRecorder()
		p.ServeHTTP(w, req)
		if w.Code != http.StatusForbidden {
			t.Fatalf("trader %s %s: status %d, want 403", rt.method, rt.path, w.Code)
		}
	}
	if n := rec.calls.Load(); n != 0 {
		t.Fatalf("upstream called %d times for forbidden requests", n)
	}

	for _, rt := range privilegedStrategyRoutes {
		req := httptest.NewRequest(rt.method, rt.path, strings.NewReader(`{}`))
		req.Header.Set("Authorization", "Bearer "+testUserSession)
		w := httptest.NewRecorder()
		p.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("admin %s %s: status %d, want 200", rt.method, rt.path, w.Code)
		}
	}
	if n := int(rec.calls.Load()); n != len(privilegedStrategyRoutes) {
		t.Fatalf("upstream calls = %d, want %d", n, len(privilegedStrategyRoutes))
	}
}

func TestStrategyProxyReadRoutesOpenToAnyUser(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	p := newTestStrategyProxy(t, srv.URL, time.Second)

	for _, path := range []string{
		"/strategy-api/api/real-grid/status",
		"/strategy-api/api/real-grid/config/BTCTHB",
		"/strategy-api/api/strategy/config",
		"/strategy-api/api/airdrop-tracker/tasks",
		"/strategy-api/api/command-center",
	} {
		for _, method := range []string{http.MethodGet, http.MethodHead} {
			req := httptest.NewRequest(method, path, nil)
			req.Header.Set("Authorization", "Bearer "+testTraderSess)
			w := httptest.NewRecorder()
			p.ServeHTTP(w, req)
			if w.Code != http.StatusOK {
				t.Fatalf("trader %s %s: status %d, want 200", method, path, w.Code)
			}
		}
	}
}

func TestStrategyProxyWithoutRoleCheckDeniesWrites(t *testing.T) {
	rec := &upstreamRecorder{}
	srv := newStrategyUpstream(t, rec)
	sessions := &memorySessionStore{}
	_ = sessions.SetSession(context.Background(), testUserSession, "fixture-user", time.Hour)
	p, err := NewStrategyProxy(StrategyProxyConfig{
		UpstreamURL: srv.URL,
		Validate:    (&AuthHandler{sessions: sessions}).ValidateToken,
	})
	if err != nil {
		t.Fatal(err)
	}
	req := httptest.NewRequest(http.MethodPost, "/strategy-api/api/real-grid/kill", nil)
	req.Header.Set("Authorization", "Bearer "+testUserSession)
	w := httptest.NewRecorder()
	p.ServeHTTP(w, req)
	if w.Code != http.StatusForbidden || rec.calls.Load() != 0 {
		t.Fatalf("status %d calls %d, want 403 and no upstream call", w.Code, rec.calls.Load())
	}
}

func TestAuthHandlerIsAdmin(t *testing.T) {
	h := &AuthHandler{users: newMemoryUserStore(
		authUser{ID: "a", Role: RoleAdmin},
		authUser{ID: "b", Role: "trader"},
	)}
	if !h.IsAdmin("a") || h.IsAdmin("b") || h.IsAdmin("") || h.IsAdmin("missing") {
		t.Fatal("IsAdmin classification wrong")
	}
}

func setRawPath(r *http.Request, escaped string) error {
	u, err := url.Parse(escaped)
	if err != nil {
		return err
	}
	r.URL = u
	r.RequestURI = escaped
	return nil
}
