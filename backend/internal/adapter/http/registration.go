package http

import (
	"crypto/sha256"
	"crypto/subtle"
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"trading-bot-system/backend/internal/logger"
)

// RegistrationMode says who may call POST /api/auth/register.
type RegistrationMode int

const (
	// RegistrationClosed rejects every sign-up with 403.
	RegistrationClosed RegistrationMode = iota
	// RegistrationInvite accepts only sign-ups carrying REGISTRATION_INVITE_CODE.
	RegistrationInvite
	// RegistrationOpen accepts anyone.
	RegistrationOpen
)

func (m RegistrationMode) String() string {
	switch m {
	case RegistrationOpen:
		return "open"
	case RegistrationInvite:
		return "invite"
	default:
		return "closed"
	}
}

// RegistrationPolicy is the server's self-registration setting.
//
// The server is single-operator: a self-registered "trader" session can read
// the operator's exchange balances, orders, trades and settings (userReadAdmin
// routes), so registration is closed by default in production.
type RegistrationPolicy struct {
	Mode RegistrationMode
	// inviteHash is sha256(REGISTRATION_INVITE_CODE); comparing fixed-length
	// digests keeps the check constant-time regardless of the input length.
	inviteHash [32]byte
}

// RegistrationPolicyFromEnv resolves the policy:
//
//   - ALLOW_REGISTRATION=false (any strconv.ParseBool false value): closed,
//     even when an invite code is set.
//   - REGISTRATION_INVITE_CODE set (and ALLOW_REGISTRATION not false): invite
//     only. This works with the production default, so setting just the code
//     enables invited sign-ups.
//   - ALLOW_REGISTRATION=true without a code: open.
//   - ALLOW_REGISTRATION unset: closed when ENVIRONMENT=production, open
//     otherwise (development).
//
// An unparsable ALLOW_REGISTRATION counts as false (fail closed).
func RegistrationPolicyFromEnv(getenv func(string) string) RegistrationPolicy {
	production := strings.EqualFold(strings.TrimSpace(getenv("ENVIRONMENT")), "production")
	invite := strings.TrimSpace(getenv("REGISTRATION_INVITE_CODE"))

	raw := strings.TrimSpace(getenv("ALLOW_REGISTRATION"))
	allow := !production
	explicit := raw != ""
	if explicit {
		v, err := strconv.ParseBool(raw)
		if err != nil {
			logger.Error("ALLOW_REGISTRATION is not a boolean; registration stays closed", "value", raw)
			return RegistrationPolicy{Mode: RegistrationClosed}
		}
		allow = v
	}

	switch {
	case explicit && !allow:
		if invite != "" {
			logger.Warn("REGISTRATION_INVITE_CODE is ignored because ALLOW_REGISTRATION=false")
		}
		return RegistrationPolicy{Mode: RegistrationClosed}
	case invite != "":
		if len(invite) < 16 {
			logger.Warn("REGISTRATION_INVITE_CODE is shorter than 16 characters; use a long random value")
		}
		return RegistrationPolicy{Mode: RegistrationInvite, inviteHash: sha256.Sum256([]byte(invite))}
	case allow:
		return RegistrationPolicy{Mode: RegistrationOpen}
	default:
		return RegistrationPolicy{Mode: RegistrationClosed}
	}
}

// inviteMatches compares code with the configured invite code in constant time.
func (p RegistrationPolicy) inviteMatches(code string) bool {
	if p.Mode != RegistrationInvite || code == "" {
		return false
	}
	got := sha256.Sum256([]byte(strings.TrimSpace(code)))
	return subtle.ConstantTimeCompare(got[:], p.inviteHash[:]) == 1
}

// Machine-readable reasons in a 403 from /api/auth/register.
const (
	registrationErrClosed        = "registration_closed"
	registrationErrInviteInvalid = "invite_invalid"
)

// AuthConfigResponse is the public GET /api/auth/config payload. It tells the
// login screen whether to offer sign-up; it exposes no secret.
type AuthConfigResponse struct {
	RegistrationOpen bool `json:"registrationOpen"`
	InviteRequired   bool `json:"inviteRequired"`
}

// SetRegistrationPolicy replaces the policy (tests and wiring).
func (h *AuthHandler) SetRegistrationPolicy(p RegistrationPolicy) {
	h.mu.Lock()
	h.registration = p
	h.mu.Unlock()
}

func (h *AuthHandler) registrationPolicy() RegistrationPolicy {
	h.mu.RLock()
	defer h.mu.RUnlock()
	return h.registration
}

// Config handles GET /api/auth/config (public).
func (h *AuthHandler) Config(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	p := h.registrationPolicy()
	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Cache-Control", "no-store")
	_ = json.NewEncoder(w).Encode(AuthConfigResponse{
		RegistrationOpen: p.Mode != RegistrationClosed,
		InviteRequired:   p.Mode == RegistrationInvite,
	})
}

// checkRegistrationAllowed writes a 403 and returns false when the policy
// rejects this sign-up. Wrong invite codes count as failed logins for the
// caller's IP, so the code cannot be brute-forced faster than a password.
func (h *AuthHandler) checkRegistrationAllowed(w http.ResponseWriter, r *http.Request, inviteCode string) bool {
	p := h.registrationPolicy()
	switch p.Mode {
	case RegistrationOpen:
		return true
	case RegistrationInvite:
		clientIP := extractClientIPForLogin(r)
		if blocked, remaining := h.checkLoginRate(clientIP); blocked {
			w.Header().Set("Content-Type", "application/json")
			w.Header().Set("Retry-After", strconv.Itoa(remaining))
			w.WriteHeader(http.StatusTooManyRequests)
			_ = json.NewEncoder(w).Encode(map[string]string{"error": "Too many attempts. Try again later."})
			return false
		}
		if p.inviteMatches(inviteCode) {
			return true
		}
		h.recordFailedLogin(clientIP)
		writeRegistrationForbidden(w, registrationErrInviteInvalid,
			"Registration on this server is invite-only: a valid invite code is required.")
		return false
	default:
		writeRegistrationForbidden(w, registrationErrClosed,
			"Registration is disabled on this server. Ask the operator for an account.")
		return false
	}
}

func writeRegistrationForbidden(w http.ResponseWriter, code, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusForbidden)
	_ = json.NewEncoder(w).Encode(map[string]string{"error": msg, "code": code})
}
