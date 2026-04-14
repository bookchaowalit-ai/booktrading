package http

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"trading-bot-system/backend/internal/logger"

	"golang.org/x/crypto/bcrypt"
)

// envOrDefault returns the value of an environment variable or a default value if not set
func envOrDefault(key, defaultValue string) string {
	if v := os.Getenv(key); v != "" {
		return v
	}
	return defaultValue
}

// sessionStore is a small interface so AuthHandler can use Redis or fall back to in-memory.
type sessionStore interface {
	SetSession(ctx context.Context, token, userID string, ttl time.Duration) error
	GetSession(ctx context.Context, token string) (string, bool)
	DeleteSession(ctx context.Context, token string)
}

// memorySessionStore is the fallback in-memory implementation.
type memorySessionStore struct {
	mu     sync.RWMutex
	tokens map[string]string
}

func (m *memorySessionStore) SetSession(_ context.Context, token, userID string, _ time.Duration) error {
	m.mu.Lock()
	m.tokens[token] = userID
	m.mu.Unlock()
	return nil
}

func (m *memorySessionStore) GetSession(_ context.Context, token string) (string, bool) {
	m.mu.RLock()
	v, ok := m.tokens[token]
	m.mu.RUnlock()
	return v, ok
}

func (m *memorySessionStore) DeleteSession(_ context.Context, token string) {
	m.mu.Lock()
	delete(m.tokens, token)
	m.mu.Unlock()
}

const sessionTTL = 7 * 24 * time.Hour // 7 days

// authUser stores hashed password
type authUser struct {
	ID           string
	Email        string
	Name         string
	Role         string
	PasswordHash string
}

// AuthHandler handles authentication
type AuthHandler struct {
	mu           sync.RWMutex
	users        []authUser
	sessions     sessionStore
	loginAttempts map[string]*loginAttempt // IP -> attempt tracking
	loginMu      sync.Mutex               // separate lock for login attempts
}

type loginAttempt struct {
	count     int
	lastReset time.Time
	blockedUntil time.Time
}

// NewAuthHandler creates an AuthHandler. Pass a Redis-backed sessionStore (or nil for in-memory fallback).
func NewAuthHandler(store sessionStore) *AuthHandler {
	if store == nil {
		store = &memorySessionStore{tokens: make(map[string]string)}
	}
	h := &AuthHandler{
		sessions:      store,
		users:         make([]authUser, 0),
		loginAttempts: make(map[string]*loginAttempt),
	}

	// Create a default admin user if FIRST_ADMIN_EMAIL is set
	adminEmail := os.Getenv("FIRST_ADMIN_EMAIL")
	adminPassword := os.Getenv("FIRST_ADMIN_PASSWORD")
	if adminEmail != "" && adminPassword != "" {
		hash, err := bcrypt.GenerateFromPassword([]byte(adminPassword), bcrypt.DefaultCost)
		if err != nil {
			logger.Error("Failed to hash admin password", "error", err)
		} else {
			h.users = append(h.users, authUser{
				ID:           "1",
				Email:        adminEmail,
				Name:         envOrDefault("FIRST_ADMIN_NAME", "Admin"),
				Role:         "admin",
				PasswordHash: string(hash),
			})
			logger.Info("Default admin user created from environment variables")
		}
	}

	return h
}

// LoginRequest is the login payload
type LoginRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
}

// LoginResponse is the auth response
type LoginResponse struct {
	Token string   `json:"token"`
	User  UserInfo `json:"user"`
}

// UserInfo is the public user representation
type UserInfo struct {
	ID    string `json:"id"`
	Email string `json:"email"`
	Name  string `json:"name"`
	Role  string `json:"role"`
}

func generateToken() (string, error) {
	b := make([]byte, 32)
	if _, err := rand.Read(b); err != nil {
		return "", err
	}
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:]), nil
}

// Login handles POST /api/auth/login
func (h *AuthHandler) Login(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Rate limit login attempts per IP (5 attempts per 15 minutes, then 15 min block)
	clientIP := extractClientIPForLogin(r)
	if blocked, remaining := h.checkLoginRate(clientIP); blocked {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Retry-After", "900")
		w.WriteHeader(http.StatusTooManyRequests)
		json.NewEncoder(w).Encode(map[string]string{
			"error": fmt.Sprintf("Too many login attempts. Try again in %d minutes.", remaining/60+1),
		})
		return
	}

	var req LoginRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid request"})
		return
	}

	h.mu.RLock()
	var found *authUser
	for i := range h.users {
		if h.users[i].Email == req.Email {
			found = &h.users[i]
			break
		}
	}
	h.mu.RUnlock()

	if found == nil || bcrypt.CompareHashAndPassword([]byte(found.PasswordHash), []byte(req.Password)) != nil {
		// Record failed attempt for rate limiting
		h.recordFailedLogin(clientIP)
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid email or password"})
		return
	}

	// Successful login - reset attempt counter
	h.resetLoginAttempts(clientIP)

	token, err := generateToken()
	if err != nil {
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	h.mu.Lock()
	if err := h.sessions.SetSession(r.Context(), token, found.ID, sessionTTL); err != nil {
		logger.Error("Failed to set session", "error", err)
		// Continue anyway - token is still valid, just won't be tracked in session store
	}
	h.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(LoginResponse{
		Token: token,
		User: UserInfo{
			ID:    found.ID,
			Email: found.Email,
			Name:  found.Name,
			Role:  found.Role,
		},
	})
}

// Me handles GET /api/auth/me
func (h *AuthHandler) Me(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	token := extractBearerToken(r)
	if token == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "Unauthorized"})
		return
	}

	h.mu.RLock()
	userID, ok := h.sessions.GetSession(r.Context(), token)
	h.mu.RUnlock()

	if !ok {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid or expired token"})
		return
	}

	h.mu.RLock()
	var found *authUser
	for i := range h.users {
		if h.users[i].ID == userID {
			found = &h.users[i]
			break
		}
	}
	h.mu.RUnlock()

	if found == nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "User not found"})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(UserInfo{
		ID:    found.ID,
		Email: found.Email,
		Name:  found.Name,
		Role:  found.Role,
	})
}

// Logout handles POST /api/auth/logout
func (h *AuthHandler) Logout(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	token := extractBearerToken(r)
	if token != "" {
		h.sessions.DeleteSession(r.Context(), token)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "logged out"})
}

// ValidateToken checks if the given token is valid and returns the associated userID
func (h *AuthHandler) ValidateToken(token string) (string, bool) {
	return h.sessions.GetSession(context.Background(), token)
}

// extractBearerToken gets the token from Authorization header only (NOT query params for security)
func extractBearerToken(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "Bearer ") {
		return strings.TrimPrefix(auth, "Bearer ")
	}
	return ""
}

// RegisterRequest is the registration payload
type RegisterRequest struct {
	Email    string `json:"email"`
	Password string `json:"password"`
	Name     string `json:"name"`
}

// Register handles POST /api/auth/register
func (h *AuthHandler) Register(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req RegisterRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid request"})
		return
	}

	if req.Email == "" || req.Password == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Email and password are required"})
		return
	}

	if len(req.Password) < 8 {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Password must be at least 8 characters"})
		return
	}

	// Password strength requirements
	hasUpper := false
	hasLower := false
	hasDigit := false
	for _, c := range req.Password {
		if c >= 'A' && c <= 'Z' {
			hasUpper = true
		}
		if c >= 'a' && c <= 'z' {
			hasLower = true
		}
		if c >= '0' && c <= '9' {
			hasDigit = true
		}
	}
	if !hasUpper || !hasLower || !hasDigit {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Password must contain at least one uppercase letter, one lowercase letter, and one digit",
		})
		return
	}

	h.mu.RLock()
	for _, u := range h.users {
		if u.Email == req.Email {
			h.mu.RUnlock()
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{"error": "Email already registered"})
			return
		}
	}
	h.mu.RUnlock()

	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	h.mu.Lock()
	newUser := authUser{
		ID:           generateID(),
		Email:        req.Email,
		Name:         req.Name,
		Role:         "trader",
		PasswordHash: string(hash),
	}
	h.users = append(h.users, newUser)
	h.mu.Unlock()

	token, err := generateToken()
	if err != nil {
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	if err := h.sessions.SetSession(r.Context(), token, newUser.ID, sessionTTL); err != nil {
		logger.Error("Failed to set session", "error", err)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(LoginResponse{
		Token: token,
		User: UserInfo{
			ID:    newUser.ID,
			Email: newUser.Email,
			Name:  newUser.Name,
			Role:  newUser.Role,
		},
	})
}

// generateID creates a simple unique ID
func generateID() string {
	b := make([]byte, 16)
	if _, err := rand.Read(b); err != nil {
		return "0"
	}
	return hex.EncodeToString(b)
}

// ── Login Rate Limiting ──────────────────────────────────────────────

// extractClientIPForLogin extracts the client IP for login rate limiting.
// Uses X-Real-IP (set by trusted proxy) or falls back to RemoteAddr.
func extractClientIPForLogin(r *http.Request) string {
	if ip := r.Header.Get("X-Real-IP"); ip != "" {
		return ip
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

const (
	loginMaxAttempts   = 5
	loginWindowMinutes = 15
	loginBlockMinutes  = 15
)

// checkLoginRate returns (blocked, remainingSeconds)
func (h *AuthHandler) checkLoginRate(ip string) (bool, int) {
	h.loginMu.Lock()
	defer h.loginMu.Unlock()

	now := time.Now()
	attempt, exists := h.loginAttempts[ip]

	if !exists {
		return false, 0
	}

	// Check if block period has expired
	if now.After(attempt.blockedUntil) {
		// Reset the counter
		delete(h.loginAttempts, ip)
		return false, 0
	}

	// Still blocked
	if attempt.count >= loginMaxAttempts {
		remaining := int(attempt.blockedUntil.Sub(now).Seconds())
		return true, remaining
	}

	// Check if window has expired
	if now.After(attempt.lastReset.Add(loginWindowMinutes * time.Minute)) {
		// Reset the counter after window expires
		delete(h.loginAttempts, ip)
		return false, 0
	}

	return false, 0
}

// recordFailedLogin increments the failed attempt counter for an IP
func (h *AuthHandler) recordFailedLogin(ip string) {
	h.loginMu.Lock()
	defer h.loginMu.Unlock()

	now := time.Now()
	attempt, exists := h.loginAttempts[ip]

	if !exists {
		h.loginAttempts[ip] = &loginAttempt{
			count:        1,
			lastReset:    now,
			blockedUntil: now,
		}
		return
	}

	attempt.count++

	// If max attempts reached, set block period
	if attempt.count >= loginMaxAttempts {
		attempt.blockedUntil = now.Add(loginBlockMinutes * time.Minute)
	}
}

// resetLoginAttempts clears the failed attempt counter for an IP (successful login)
func (h *AuthHandler) resetLoginAttempts(ip string) {
	h.loginMu.Lock()
	defer h.loginMu.Unlock()
	delete(h.loginAttempts, ip)
}
