package http

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
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

// recordSleeps replaces the login delay with a recorder, so tests see the
// per-account delay without sleeping.
func recordSleeps(h *AuthHandler) *[]time.Duration {
	var got []time.Duration
	h.loginSleep = func(_ context.Context, d time.Duration) error {
		got = append(got, d)
		return nil
	}
	return &got
}

func lastSleep(t *testing.T, sleeps *[]time.Duration) time.Duration {
	t.Helper()
	if len(*sleeps) == 0 {
		t.Fatal("login did not go through the delay")
	}
	return (*sleeps)[len(*sleeps)-1]
}

// An attacker hammering the admin's email from many IPs must not lock the
// admin out: per-account failures only add a bounded delay, while rotating
// IPs still cannot guess quickly.
func TestAccountAttackFromManyIPsCannotBlockAdmin(t *testing.T) {
	h := newLockoutHandler(t)
	sleeps := recordSleeps(h)
	const attempts = 12
	for i := 0; i < attempts; i++ {
		w := loginFrom(t, h, fmt.Sprintf("203.0.113.%d:1000", i+1), nil, " Admin@Example.test", "wrong")
		if w.Code != http.StatusUnauthorized {
			t.Fatalf("attempt %d: %d, want 401 (never a block across IPs)", i+1, w.Code)
		}
		want := time.Duration(0)
		if i >= accountDelayFreeFailures {
			want = accountDelayBase << (i - accountDelayFreeFailures)
			if want > accountDelayMax || want <= 0 {
				want = accountDelayMax
			}
		}
		if got := lastSleep(t, sleeps); got != want {
			t.Fatalf("attempt %d: delay %v, want %v", i+1, got, want)
		}
	}

	w := loginFrom(t, h, "198.51.100.10:1000", nil, "admin@example.test", "AdminSecret123")
	if w.Code != http.StatusOK {
		t.Fatalf("admin from a fresh IP: %d %s, want 200", w.Code, w.Body)
	}
	if got := lastSleep(t, sleeps); got != accountDelayMax {
		t.Fatalf("admin delay %v, want the cap %v", got, accountDelayMax)
	}
	// Other accounts are not slowed down.
	if w := loginFrom(t, h, "198.51.100.11:1000", nil, "victim@example.test", "Secret123"); w.Code != http.StatusOK {
		t.Fatalf("other account: %d, want 200", w.Code)
	}
	if got := lastSleep(t, sleeps); got != 0 {
		t.Fatalf("other account delay %v, want 0", got)
	}
}

// Guessing one account from one IP still hits a hard lockout that a correct
// password cannot bypass, and only that IP is locked for the account.
func TestSameIPBruteForceLocks(t *testing.T) {
	h := newLockoutHandler(t)
	recordSleeps(h)
	const ip = "203.0.113.70:1000"
	for i := 0; i < pairMaxAttempts; i++ {
		if w := loginFrom(t, h, ip, nil, "victim@example.test", "wrong"); w.Code != http.StatusUnauthorized {
			t.Fatalf("attempt %d: %d, want 401", i+1, w.Code)
		}
	}
	w := loginFrom(t, h, ip, nil, "victim@example.test", "Secret123")
	if w.Code != http.StatusTooManyRequests || w.Header().Get("Retry-After") == "" {
		t.Fatalf("locked pair: %d (Retry-After %q), want 429 with Retry-After", w.Code, w.Header().Get("Retry-After"))
	}
	if blocked, _ := h.checkPairRate("VICTIM@example.test ", "203.0.113.70"); !blocked {
		t.Fatal("(email, IP) pair is not locked")
	}
	if w := loginFrom(t, h, "203.0.113.71:1000", nil, "victim@example.test", "Secret123"); w.Code != http.StatusOK {
		t.Fatalf("same account from another IP: %d, want 200", w.Code)
	}
}

// A success clears only that (email, IP) counter: failures recorded from
// other IPs keep slowing the account down.
func TestSuccessfulLoginClearsOnlyThePair(t *testing.T) {
	h := newLockoutHandler(t)
	sleeps := recordSleeps(h)
	for i := 0; i < accountDelayFreeFailures+2; i++ {
		loginFrom(t, h, fmt.Sprintf("203.0.113.%d:1000", i+80), nil, "victim@example.test", "wrong")
	}
	const ip = "203.0.113.80"
	if w := loginFrom(t, h, ip+":1000", nil, "victim@example.test", "Secret123"); w.Code != http.StatusOK {
		t.Fatalf("login: %d", w.Code)
	}
	h.loginMu.Lock()
	_, pairLeft := h.loginAttempts[pairLoginKey("victim@example.test", ip)]
	_, otherPairLeft := h.loginAttempts[pairLoginKey("victim@example.test", "203.0.113.81")]
	h.loginMu.Unlock()
	if pairLeft || !otherPairLeft {
		t.Fatalf("pair counters after success: own=%v other=%v, want false/true", pairLeft, otherPairLeft)
	}
	loginFrom(t, h, "203.0.113.99:1000", nil, "victim@example.test", "wrong")
	if got := lastSleep(t, sleeps); got == 0 {
		t.Fatal("account delay was reset by one successful login")
	}
}

// Unknown and known emails get the same statuses, bodies, delays and
// lockouts, so neither reveals whether an account exists.
func TestLoginUnknownEmailParity(t *testing.T) {
	type result struct {
		code  int
		body  string
		delay time.Duration
	}
	run := func(email string) []result {
		h := newLockoutHandler(t)
		sleeps := recordSleeps(h)
		var out []result
		for i := 0; i < accountDelayFreeFailures+3; i++ {
			w := loginFrom(t, h, fmt.Sprintf("203.0.113.%d:1000", i+1), nil, email, "wrong")
			out = append(out, result{w.Code, w.Body.String(), lastSleep(t, sleeps)})
		}
		for i := 0; i <= pairMaxAttempts; i++ {
			w := loginFrom(t, h, "198.51.100.20:1000", nil, email, "wrong")
			out = append(out, result{w.Code, w.Body.String() + w.Header().Get("Retry-After"), 0})
		}
		return out
	}
	known, unknown := run("victim@example.test"), run("ghost@example.test")
	if len(known) != len(unknown) {
		t.Fatalf("result count differs: %d vs %d", len(known), len(unknown))
	}
	for i := range known {
		if known[i] != unknown[i] {
			t.Fatalf("step %d: known %+v, unknown %+v", i, known[i], unknown[i])
		}
	}
	if last := known[len(known)-1]; last.code != http.StatusTooManyRequests {
		t.Fatalf("final step: %d, want 429", last.code)
	}
}

func TestSleepContextStopsWhenClientLeaves(t *testing.T) {
	ctx, cancel := context.WithCancel(context.Background())
	cancel()
	start := time.Now()
	if err := sleepContext(ctx, time.Hour); err == nil {
		t.Fatal("want ctx error")
	}
	if time.Since(start) > time.Second {
		t.Fatal("sleepContext ignored cancellation")
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
