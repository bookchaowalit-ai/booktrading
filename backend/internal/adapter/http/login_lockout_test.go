package http

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
)

// caddyAddr is a Docker-network peer, trusted by the default TRUSTED_PROXIES.
const caddyAddr = "172.18.0.5:41000"

func loginFrom(t *testing.T, h *AuthHandler, remoteAddr string, headers map[string]string, email, password string) *httptest.ResponseRecorder {
	t.Helper()
	b, _ := json.Marshal(LoginRequest{Email: email, Password: password})
	req := httptest.NewRequest(http.MethodPost, "/api/auth/login", bytes.NewReader(b))
	req.RemoteAddr = remoteAddr
	for k, v := range headers {
		req.Header.Set(k, v)
	}
	w := httptest.NewRecorder()
	h.Login(w, req)
	return w
}

func newLockoutHandler(t *testing.T) *AuthHandler {
	t.Helper()
	clearFirstAdminEnv(t)
	t.Setenv("TRUSTED_PROXIES", "")
	t.Setenv("FIRST_ADMIN_EMAIL", "admin@example.test")
	t.Setenv("FIRST_ADMIN_PASSWORD", "AdminSecret123")
	h := NewAuthHandlerWithUsers(nil, newMemoryUserStore())
	for _, email := range []string{"victim@example.test", "attacker@example.test"} {
		if w := postJSON(t, h.Register, "/api/auth/register",
			RegisterRequest{Email: email, Password: "Secret123"}); w.Code != http.StatusCreated {
			t.Fatalf("register %s: %d %s", email, w.Code, w.Body)
		}
	}
	return h
}

func TestClientIPIgnoresHeadersFromUntrustedPeer(t *testing.T) {
	t.Setenv("TRUSTED_PROXIES", "")
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = "203.0.113.9:5555"
	req.Header.Set("X-Real-IP", "198.51.100.1")
	req.Header.Set("X-Forwarded-For", "198.51.100.2")
	for name, fn := range map[string]func(*http.Request) string{
		"login": extractClientIPForLogin, "global": extractClientIP,
		"audit": (&AuditMiddleware{}).extractIP,
	} {
		if got := fn(req); got != "203.0.113.9" {
			t.Errorf("%s: got %q, want the TCP peer 203.0.113.9", name, got)
		}
	}
}

func TestClientIPFromTrustedProxy(t *testing.T) {
	t.Setenv("TRUSTED_PROXIES", "")
	cases := []struct {
		name    string
		headers map[string]string
		want    string
	}{
		{"x-real-ip", map[string]string{"X-Real-IP": "198.51.100.7"}, "198.51.100.7"},
		{"xff single", map[string]string{"X-Forwarded-For": "198.51.100.7"}, "198.51.100.7"},
		// Client prepended a fake hop; Caddy/Next appended the real one.
		{"xff spoofed left hop", map[string]string{"X-Forwarded-For": "1.2.3.4, 198.51.100.7"}, "198.51.100.7"},
		// Caddy -> Next.js -> backend: Next appends Caddy's private IP.
		{"xff through two proxies", map[string]string{"X-Forwarded-For": "198.51.100.7, 172.18.0.5"}, "198.51.100.7"},
		{"xff wins over x-real-ip", map[string]string{"X-Forwarded-For": "198.51.100.7", "X-Real-IP": "1.2.3.4"}, "198.51.100.7"},
		{"no headers", nil, "172.18.0.5"},
	}
	for _, c := range cases {
		req := httptest.NewRequest(http.MethodGet, "/", nil)
		req.RemoteAddr = caddyAddr
		for k, v := range c.headers {
			req.Header.Set(k, v)
		}
		if got := extractClientIP(req); got != c.want {
			t.Errorf("%s: got %q, want %q", c.name, got, c.want)
		}
	}
}

func TestTrustedProxiesEnvOverride(t *testing.T) {
	t.Setenv("TRUSTED_PROXIES", "10.9.9.9, 192.0.2.0/24")
	req := httptest.NewRequest(http.MethodGet, "/", nil)
	req.RemoteAddr = caddyAddr // private, but no longer trusted
	req.Header.Set("X-Real-IP", "198.51.100.7")
	if got := extractClientIP(req); got != "172.18.0.5" {
		t.Fatalf("untrusted private peer: got %q", got)
	}
	req.RemoteAddr = "192.0.2.44:1"
	if got := extractClientIP(req); got != "198.51.100.7" {
		t.Fatalf("trusted CIDR peer: got %q", got)
	}
}

// A direct client rotating X-Real-IP used to get a fresh bucket per request.
func TestLoginLockoutCannotBeEvadedBySpoofedHeaders(t *testing.T) {
	h := newLockoutHandler(t)
	for i := 0; i < loginMaxAttempts; i++ {
		w := loginFrom(t, h, "203.0.113.50:1000", map[string]string{
			"X-Real-IP": fmt.Sprintf("198.51.100.%d", i+1), "X-Forwarded-For": fmt.Sprintf("198.51.100.%d", i+100),
		}, fmt.Sprintf("nobody%d@example.test", i), "wrong")
		if w.Code != http.StatusUnauthorized {
			t.Fatalf("attempt %d: %d, want 401", i+1, w.Code)
		}
	}
	w := loginFrom(t, h, "203.0.113.50:1001", map[string]string{"X-Real-IP": "198.51.100.250"},
		"attacker@example.test", "Secret123")
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("spoofed header after lockout: %d, want 429", w.Code)
	}
}

// Behind Caddy every request shares the proxy's TCP peer. One client's
// failures must not lock out other clients (including the admin).
func TestLoginLockoutBehindSharedProxyIsPerClient(t *testing.T) {
	h := newLockoutHandler(t)
	for i := 0; i < loginMaxAttempts; i++ {
		w := loginFrom(t, h, caddyAddr, map[string]string{"X-Forwarded-For": "198.51.100.66"},
			fmt.Sprintf("nobody%d@example.test", i), "wrong")
		if w.Code != http.StatusUnauthorized {
			t.Fatalf("attempt %d: %d, want 401", i+1, w.Code)
		}
	}
	if w := loginFrom(t, h, caddyAddr, map[string]string{"X-Forwarded-For": "198.51.100.66"},
		"attacker@example.test", "Secret123"); w.Code != http.StatusTooManyRequests {
		t.Fatalf("locked client: %d, want 429", w.Code)
	}
	if w := loginFrom(t, h, caddyAddr, map[string]string{"X-Forwarded-For": "198.51.100.77"},
		"admin@example.test", "AdminSecret123"); w.Code != http.StatusOK {
		t.Fatalf("admin via same proxy: %d %s, want 200", w.Code, w.Body)
	}
}

// Rotating source IPs must not allow unlimited guesses against one account.
func TestLoginPerAccountLockout(t *testing.T) {
	h := newLockoutHandler(t)
	for i := 0; i < accountMaxAttempts; i++ {
		w := loginFrom(t, h, fmt.Sprintf("203.0.113.%d:1000", i+1), nil, "Victim@Example.test ", "wrong")
		if w.Code != http.StatusUnauthorized {
			t.Fatalf("attempt %d: %d, want 401", i+1, w.Code)
		}
	}
	w := loginFrom(t, h, "203.0.113.200:1000", nil, "victim@example.test", "Secret123")
	if w.Code != http.StatusTooManyRequests {
		t.Fatalf("locked account from fresh IP: %d, want 429", w.Code)
	}
	lockedBody := w.Body.String()
	if w.Header().Get("Retry-After") == "" {
		t.Fatal("missing Retry-After")
	}

	// The admin (and other accounts) still log in.
	if w := loginFrom(t, h, "203.0.113.201:1000", nil, "admin@example.test", "AdminSecret123"); w.Code != http.StatusOK {
		t.Fatalf("admin while another account is locked: %d %s, want 200", w.Code, w.Body)
	}
	if w := loginFrom(t, h, "203.0.113.202:1000", nil, "attacker@example.test", "Secret123"); w.Code != http.StatusOK {
		t.Fatalf("other account: %d, want 200", w.Code)
	}

	// An unknown email locks the same way with the same body, so the 429
	// does not reveal whether an account exists.
	for i := 0; i < accountMaxAttempts; i++ {
		loginFrom(t, h, fmt.Sprintf("203.0.113.%d:2000", i+100), nil, "ghost@example.test", "wrong")
	}
	w = loginFrom(t, h, "203.0.113.203:1000", nil, "ghost@example.test", "whatever")
	if w.Code != http.StatusTooManyRequests || w.Body.String() != lockedBody {
		t.Fatalf("unknown email lockout: %d %q, want 429 %q", w.Code, w.Body, lockedBody)
	}
}

// A successful login to the attacker's own account must not refill the IP
// budget used for guessing other accounts' passwords.
func TestSuccessfulLoginDoesNotResetIPBudget(t *testing.T) {
	h := newLockoutHandler(t)
	const ip = "203.0.113.60:1000"
	for i := 0; i < loginMaxAttempts-1; i++ {
		loginFrom(t, h, ip, nil, "victim@example.test", "wrong")
	}
	if w := loginFrom(t, h, ip, nil, "attacker@example.test", "Secret123"); w.Code != http.StatusOK {
		t.Fatalf("own login: %d", w.Code)
	}
	if w := loginFrom(t, h, ip, nil, "victim@example.test", "wrong"); w.Code != http.StatusUnauthorized {
		t.Fatalf("5th failure: %d, want 401", w.Code)
	}
	if w := loginFrom(t, h, ip, nil, "victim@example.test", "Secret123"); w.Code != http.StatusTooManyRequests {
		t.Fatalf("after 5 failures: %d, want 429", w.Code)
	}
}
