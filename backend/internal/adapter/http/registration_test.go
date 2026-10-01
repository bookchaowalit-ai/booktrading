package http

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"trading-bot-system/backend/internal/adapter/database"
)

func envMap(m map[string]string) func(string) string {
	return func(k string) string { return m[k] }
}

func TestRegistrationPolicyFromEnv(t *testing.T) {
	cases := []struct {
		name string
		env  map[string]string
		want RegistrationMode
	}{
		{"production default is closed", map[string]string{"ENVIRONMENT": "production"}, RegistrationClosed},
		{"production is case-insensitive", map[string]string{"ENVIRONMENT": " Production "}, RegistrationClosed},
		{"development default is open", map[string]string{"ENVIRONMENT": "development"}, RegistrationOpen},
		{"unset environment is development", map[string]string{}, RegistrationOpen},
		{"production opened explicitly", map[string]string{"ENVIRONMENT": "production", "ALLOW_REGISTRATION": "true"}, RegistrationOpen},
		{"development closed explicitly", map[string]string{"ALLOW_REGISTRATION": "false"}, RegistrationClosed},
		{"unparsable flag fails closed", map[string]string{"ALLOW_REGISTRATION": "yes please"}, RegistrationClosed},
		{"invite code alone enables invites in production", map[string]string{"ENVIRONMENT": "production", "REGISTRATION_INVITE_CODE": "fixture-invite-code-0001"}, RegistrationInvite},
		{"invite code restricts an open flag", map[string]string{"ALLOW_REGISTRATION": "1", "REGISTRATION_INVITE_CODE": "fixture-invite-code-0001"}, RegistrationInvite},
		{"explicit false beats invite code", map[string]string{"ALLOW_REGISTRATION": "false", "REGISTRATION_INVITE_CODE": "fixture-invite-code-0001"}, RegistrationClosed},
		{"blank invite code is ignored", map[string]string{"ENVIRONMENT": "production", "REGISTRATION_INVITE_CODE": "   "}, RegistrationClosed},
	}
	for _, c := range cases {
		t.Run(c.name, func(t *testing.T) {
			if got := RegistrationPolicyFromEnv(envMap(c.env)).Mode; got != c.want {
				t.Fatalf("mode = %s, want %s", got, c.want)
			}
		})
	}
}

// A zero AuthHandler (no policy wired) must not accept sign-ups.
func TestZeroRegistrationPolicyIsClosed(t *testing.T) {
	var p RegistrationPolicy
	if p.Mode != RegistrationClosed {
		t.Fatalf("zero policy = %s, want closed", p.Mode)
	}
}

func newRegistrationHandler(t *testing.T, env map[string]string) (*AuthHandler, *memoryUserStore) {
	t.Helper()
	clearFirstAdminEnv(t)
	for _, k := range []string{"ENVIRONMENT", "ALLOW_REGISTRATION", "REGISTRATION_INVITE_CODE"} {
		t.Setenv(k, env[k])
	}
	store := newMemoryUserStore()
	return NewAuthHandlerWithUsers(nil, store), store
}

func decodeBody(t *testing.T, w *httptest.ResponseRecorder) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal(w.Body.Bytes(), &m); err != nil {
		t.Fatalf("body %q: %v", w.Body.String(), err)
	}
	return m
}

func TestRegisterClosedByDefaultInProduction(t *testing.T) {
	h, store := newRegistrationHandler(t, map[string]string{"ENVIRONMENT": "production"})

	w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "stranger@example.test", Password: "Secret123", Name: "S"})
	if w.Code != http.StatusForbidden {
		t.Fatalf("register: %d %s, want 403", w.Code, w.Body)
	}
	body := decodeBody(t, w)
	if body["code"] != registrationErrClosed || body["error"] == "" {
		t.Fatalf("body = %v", body)
	}
	if _, err := store.GetUserByEmail(context.Background(), "stranger@example.test"); err != database.ErrUserNotFound {
		t.Fatalf("account was created while registration is closed (err=%v)", err)
	}

	// Even a malformed body gets the 403, not a 400 that hints at the form.
	req := httptest.NewRequest(http.MethodPost, "/api/auth/register", nil)
	rec := httptest.NewRecorder()
	h.Register(rec, req)
	if rec.Code != http.StatusForbidden {
		t.Fatalf("empty body: %d, want 403", rec.Code)
	}
}

func TestRegisterOpenInDevelopment(t *testing.T) {
	h, _ := newRegistrationHandler(t, map[string]string{"ENVIRONMENT": "development"})
	w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "dev@example.test", Password: "Secret123", Name: "D"})
	if w.Code != http.StatusCreated {
		t.Fatalf("register: %d %s, want 201", w.Code, w.Body)
	}
}

func TestRegisterOpenedExplicitlyInProduction(t *testing.T) {
	h, _ := newRegistrationHandler(t, map[string]string{"ENVIRONMENT": "production", "ALLOW_REGISTRATION": "true"})
	w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "invited@example.test", Password: "Secret123", Name: "I"})
	if w.Code != http.StatusCreated {
		t.Fatalf("register: %d %s, want 201", w.Code, w.Body)
	}
}

func TestRegisterInviteCode(t *testing.T) {
	const code = "fixture-invite-code-0001"
	h, _ := newRegistrationHandler(t, map[string]string{"ENVIRONMENT": "production", "REGISTRATION_INVITE_CODE": code})

	for _, bad := range []string{"", "fixture-invite-code-0002", "fixture-invite-code-0001x", "f"} {
		w := postJSON(t, h.Register, "/api/auth/register",
			RegisterRequest{Email: "guess@example.test", Password: "Secret123", InviteCode: bad})
		if w.Code != http.StatusForbidden {
			t.Fatalf("invite %q: %d %s, want 403", bad, w.Code, w.Body)
		}
		if body := decodeBody(t, w); body["code"] != registrationErrInviteInvalid {
			t.Fatalf("invite %q: body = %v", bad, body)
		}
	}

	// Surrounding whitespace (copy/paste) is tolerated.
	w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "friend@example.test", Password: "Secret123", Name: "F", InviteCode: " " + code + "\n"})
	if w.Code != http.StatusCreated {
		t.Fatalf("valid invite: %d %s, want 201", w.Code, w.Body)
	}
	var resp LoginResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.User.Role != "trader" {
		t.Fatalf("invited user role = %q, want trader", resp.User.Role)
	}
}

// Wrong invite codes share the login lockout, so the code cannot be guessed
// faster than a password.
func TestRegisterInviteCodeIsRateLimited(t *testing.T) {
	const code = "fixture-invite-code-0001"
	h, _ := newRegistrationHandler(t, map[string]string{"REGISTRATION_INVITE_CODE": code})
	for i := 0; i < loginMaxAttempts; i++ {
		postJSON(t, h.Register, "/api/auth/register",
			RegisterRequest{Email: "guess@example.test", Password: "Secret123", InviteCode: "wrong"})
	}
	w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "guess@example.test", Password: "Secret123", InviteCode: code})
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("after %d wrong codes: %d, want 429", loginMaxAttempts, w.Code)
	}
}

func TestAuthConfigEndpoint(t *testing.T) {
	cases := []struct {
		env        map[string]string
		wantOpen   bool
		wantInvite bool
	}{
		{map[string]string{"ENVIRONMENT": "production"}, false, false},
		{map[string]string{"ENVIRONMENT": "development"}, true, false},
		{map[string]string{"ENVIRONMENT": "production", "REGISTRATION_INVITE_CODE": "fixture-invite-code-0001"}, true, true},
	}
	for _, c := range cases {
		h, _ := newRegistrationHandler(t, c.env)
		router := NewRouter(h)
		router.RegisterAuthRoutes(h)

		// Anonymous caller through the real gate.
		req := httptest.NewRequest(http.MethodGet, "/api/auth/config", nil)
		req.RemoteAddr = "192.0.2.20:1234"
		w := httptest.NewRecorder()
		router.ServeHTTP(w, req)
		if w.Code != http.StatusOK {
			t.Fatalf("%v: GET /api/auth/config = %d %s", c.env, w.Code, w.Body)
		}
		var got AuthConfigResponse
		if err := json.Unmarshal(w.Body.Bytes(), &got); err != nil {
			t.Fatal(err)
		}
		if got.RegistrationOpen != c.wantOpen || got.InviteRequired != c.wantInvite {
			t.Fatalf("%v: config = %+v", c.env, got)
		}
		if body := w.Body.String(); len(body) > 80 {
			t.Fatalf("config leaks more than the two flags: %s", body)
		}

		post := httptest.NewRequest(http.MethodPost, "/api/auth/config", nil)
		post.RemoteAddr = "192.0.2.20:1234"
		pw := httptest.NewRecorder()
		router.ServeHTTP(pw, post)
		if pw.Code != http.StatusMethodNotAllowed {
			t.Fatalf("POST /api/auth/config = %d, want 405", pw.Code)
		}
	}
}
