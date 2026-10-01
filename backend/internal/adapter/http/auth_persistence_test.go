package http

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"testing"
)

// The shared memoryUserStore below stands in for the users table: a new
// AuthHandler over the same store is what a process restart looks like once
// accounts are persisted (cmd/main.go wires database.UserRepository).

func postJSON(t *testing.T, h http.HandlerFunc, path string, body any) *httptest.ResponseRecorder {
	t.Helper()
	b, _ := json.Marshal(body)
	req := httptest.NewRequest(http.MethodPost, path, bytes.NewReader(b))
	req.RemoteAddr = "192.0.2.10:1234"
	w := httptest.NewRecorder()
	h(w, req)
	return w
}

func clearFirstAdminEnv(t *testing.T) {
	t.Helper()
	t.Setenv("FIRST_ADMIN_EMAIL", "")
	t.Setenv("FIRST_ADMIN_PASSWORD", "")
	t.Setenv("FIRST_ADMIN_NAME", "")
}

func TestRegisteredUserSurvivesRestart(t *testing.T) {
	clearFirstAdminEnv(t)
	store := newMemoryUserStore()

	before := NewAuthHandlerWithUsers(nil, store)
	if w := postJSON(t, before.Register, "/api/auth/register",
		RegisterRequest{Email: "Trader@Example.test", Password: "Secret123", Name: "T"}); w.Code != http.StatusCreated {
		t.Fatalf("register: %d %s", w.Code, w.Body)
	}

	// "Restart": fresh handler and sessions, same user store.
	after := NewAuthHandlerWithUsers(nil, store)
	w := postJSON(t, after.Login, "/api/auth/login", LoginRequest{Email: "trader@example.test", Password: "Secret123"})
	if w.Code != http.StatusOK {
		t.Fatalf("login after restart: %d %s", w.Code, w.Body)
	}
	var resp LoginResponse
	if err := json.Unmarshal(w.Body.Bytes(), &resp); err != nil {
		t.Fatal(err)
	}
	if resp.User.Role != "trader" || resp.User.Email != "trader@example.test" {
		t.Fatalf("user = %+v", resp.User)
	}
	if after.IsAdmin(resp.User.ID) {
		t.Fatal("self-registered user is admin")
	}

	// Email is unique regardless of case.
	if w := postJSON(t, after.Register, "/api/auth/register",
		RegisterRequest{Email: "TRADER@example.test", Password: "Secret123"}); w.Code != http.StatusConflict {
		t.Fatalf("duplicate register: %d, want 409", w.Code)
	}
}

func TestFirstAdminBootstrapIsIdempotentAndFollowsEnvPassword(t *testing.T) {
	t.Setenv("FIRST_ADMIN_EMAIL", "Admin@Example.test")
	t.Setenv("FIRST_ADMIN_PASSWORD", "FirstPass1")
	t.Setenv("FIRST_ADMIN_NAME", "")
	store := newMemoryUserStore()

	h := NewAuthHandlerWithUsers(nil, store)
	admin, err := store.GetUserByEmail(context.Background(), "admin@example.test")
	if err != nil {
		t.Fatalf("admin not created: %v", err)
	}
	if admin.ID != firstAdminID || admin.Role != RoleAdmin || admin.Name != "Admin" || !h.IsAdmin(admin.ID) {
		t.Fatalf("admin = %+v", admin)
	}

	// Restart with the same env: no duplicate, same account.
	NewAuthHandlerWithUsers(nil, store)
	if n := len(store.users); n != 1 {
		t.Fatalf("%d users after second start, want 1", n)
	}

	// Restart with a new password: the env value is the working one.
	t.Setenv("FIRST_ADMIN_PASSWORD", "SecondPass2")
	h = NewAuthHandlerWithUsers(nil, store)
	if w := postJSON(t, h.Login, "/api/auth/login", LoginRequest{Email: "admin@example.test", Password: "FirstPass1"}); w.Code != http.StatusUnauthorized {
		t.Fatalf("old password: %d, want 401", w.Code)
	}
	if w := postJSON(t, h.Login, "/api/auth/login", LoginRequest{Email: "admin@example.test", Password: "SecondPass2"}); w.Code != http.StatusOK {
		t.Fatalf("new password: %d %s", w.Code, w.Body)
	}
}

func TestFirstAdminBootstrapNeverPromotesSelfRegisteredEmail(t *testing.T) {
	// Registration does not verify email ownership: whoever registered the
	// admin address first must not become admin at the next start.
	clearFirstAdminEnv(t)
	store := newMemoryUserStore()
	h := NewAuthHandlerWithUsers(nil, store)
	if w := postJSON(t, h.Register, "/api/auth/register",
		RegisterRequest{Email: "admin@example.test", Password: "Squatter1"}); w.Code != http.StatusCreated {
		t.Fatalf("register: %d", w.Code)
	}

	env := map[string]string{"FIRST_ADMIN_EMAIL": "admin@example.test", "FIRST_ADMIN_PASSWORD": "AdminPass1"}
	err := bootstrapFirstAdmin(context.Background(), store, func(k string) string { return env[k] })
	if !errors.Is(err, errFirstAdminEmailTaken) {
		t.Fatalf("bootstrap err = %v, want errFirstAdminEmailTaken", err)
	}
	u, _ := store.GetUserByEmail(context.Background(), "admin@example.test")
	if u.Role == RoleAdmin {
		t.Fatal("self-registered account was promoted")
	}
	if w := postJSON(t, h.Login, "/api/auth/login", LoginRequest{Email: "admin@example.test", Password: "AdminPass1"}); w.Code != http.StatusUnauthorized {
		t.Fatalf("env password on squatted account: %d, want 401", w.Code)
	}
}

func TestFirstAdminBootstrapUsesFreshIDWhenOneIsTaken(t *testing.T) {
	// ID "1" belongs to the admin created under an earlier FIRST_ADMIN_EMAIL.
	store := newMemoryUserStore(authUser{ID: firstAdminID, Email: "old@example.test", Role: RoleAdmin, PasswordHash: "x"})
	env := map[string]string{"FIRST_ADMIN_EMAIL": "new@example.test", "FIRST_ADMIN_PASSWORD": "AdminPass1"}
	if err := bootstrapFirstAdmin(context.Background(), store, func(k string) string { return env[k] }); err != nil {
		t.Fatalf("bootstrap: %v", err)
	}
	u, err := store.GetUserByEmail(context.Background(), "new@example.test")
	if err != nil || u.ID == firstAdminID || u.Role != RoleAdmin {
		t.Fatalf("new admin = %+v, %v", u, err)
	}
}

type failingUserStore struct{ memoryUserStore }

func (f *failingUserStore) GetUserByEmail(context.Context, string) (*authUser, error) {
	return nil, errors.New("db down")
}
func (f *failingUserStore) GetUserByID(context.Context, string) (*authUser, error) {
	return nil, errors.New("db down")
}

func TestAuthStoreOutageFailsClosed(t *testing.T) {
	clearFirstAdminEnv(t)
	h := NewAuthHandlerWithUsers(nil, &failingUserStore{})
	if w := postJSON(t, h.Login, "/api/auth/login", LoginRequest{Email: "a@example.test", Password: "x"}); w.Code != http.StatusInternalServerError {
		t.Fatalf("login during outage: %d, want 500", w.Code)
	}
	if h.IsAdmin(firstAdminID) {
		t.Fatal("IsAdmin true during outage")
	}
}
