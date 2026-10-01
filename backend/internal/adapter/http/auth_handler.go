package http

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"

	"trading-bot-system/backend/internal/adapter/database"
	"trading-bot-system/backend/internal/logger"

	"golang.org/x/crypto/bcrypt"
)

// sessionStore is a small interface so AuthHandler can use Redis or fall back to in-memory.
type sessionStore interface {
	SetSession(ctx context.Context, token, userID string, ttl time.Duration) error
	GetSession(ctx context.Context, token string) (string, bool)
	DeleteSession(ctx context.Context, token string)
}

// memorySessionStore is the fallback in-memory implementation.
type memorySessionStore struct {
	mu      sync.RWMutex
	tokens  map[string]string
	expires map[string]time.Time
}

func (m *memorySessionStore) SetSession(_ context.Context, token, userID string, ttl time.Duration) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	if m.tokens == nil {
		m.tokens = make(map[string]string)
	}
	if m.expires == nil {
		m.expires = make(map[string]time.Time)
	}
	m.tokens[token] = userID
	m.expires[token] = time.Now().Add(ttl)
	return nil
}

func (m *memorySessionStore) GetSession(_ context.Context, token string) (string, bool) {
	m.mu.Lock()
	defer m.mu.Unlock()
	v, ok := m.tokens[token]
	if !ok || !time.Now().Before(m.expires[token]) {
		delete(m.tokens, token)
		delete(m.expires, token)
		return "", false
	}
	return v, ok
}

func (m *memorySessionStore) DeleteSession(_ context.Context, token string) {
	m.mu.Lock()
	delete(m.tokens, token)
	delete(m.expires, token)
	m.mu.Unlock()
}

const sessionTTL = 7 * 24 * time.Hour // 7 days

// authUser is an account with its bcrypt password hash.
type authUser = database.User

// UserStore persists accounts. *database.UserRepository implements it on the
// users table (migration 008); memoryUserStore is the fallback when no
// database is wired (tests).
type UserStore interface {
	// GetUserByEmail and GetUserByID return database.ErrUserNotFound when absent.
	GetUserByEmail(ctx context.Context, email string) (*authUser, error)
	GetUserByID(ctx context.Context, id string) (*authUser, error)
	// CreateUser returns database.ErrEmailTaken for a duplicate email or ID.
	CreateUser(ctx context.Context, u authUser) error
	UpdatePasswordHash(ctx context.Context, id, hash string) error
}

// memoryUserStore keeps accounts in process memory (lost on restart).
type memoryUserStore struct {
	mu    sync.RWMutex
	users []authUser
}

func newMemoryUserStore(users ...authUser) *memoryUserStore {
	return &memoryUserStore{users: append([]authUser(nil), users...)}
}

func (m *memoryUserStore) find(match func(*authUser) bool) (*authUser, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	for i := range m.users {
		if match(&m.users[i]) {
			u := m.users[i]
			return &u, nil
		}
	}
	return nil, database.ErrUserNotFound
}

func (m *memoryUserStore) GetUserByEmail(_ context.Context, email string) (*authUser, error) {
	return m.find(func(u *authUser) bool { return u.Email == email })
}

func (m *memoryUserStore) GetUserByID(_ context.Context, id string) (*authUser, error) {
	return m.find(func(u *authUser) bool { return u.ID == id })
}

func (m *memoryUserStore) CreateUser(_ context.Context, u authUser) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for i := range m.users {
		if m.users[i].Email == u.Email || m.users[i].ID == u.ID {
			return database.ErrEmailTaken
		}
	}
	m.users = append(m.users, u)
	return nil
}

func (m *memoryUserStore) UpdatePasswordHash(_ context.Context, id, hash string) error {
	m.mu.Lock()
	defer m.mu.Unlock()
	for i := range m.users {
		if m.users[i].ID == id {
			m.users[i].PasswordHash = hash
			return nil
		}
	}
	return database.ErrUserNotFound
}

// AuthHandler handles authentication
type AuthHandler struct {
	mu            sync.RWMutex
	users         UserStore
	sessions      sessionStore
	loginAttempts map[string]*loginAttempt // IP -> attempt tracking
	loginMu       sync.Mutex               // separate lock for login attempts
}

type loginAttempt struct {
	count        int
	lastReset    time.Time
	blockedUntil time.Time
}

// NewAuthHandler creates an AuthHandler with in-memory accounts. Pass a
// Redis-backed sessionStore (or nil for in-memory fallback).
func NewAuthHandler(store sessionStore) *AuthHandler {
	return NewAuthHandlerWithUsers(store, nil)
}

// NewAuthHandlerWithUsers creates an AuthHandler whose accounts live in
// users (nil: in memory), then applies the FIRST_ADMIN_* bootstrap.
func NewAuthHandlerWithUsers(store sessionStore, users UserStore) *AuthHandler {
	if store == nil {
		store = &memorySessionStore{tokens: make(map[string]string)}
	}
	if users == nil {
		users = newMemoryUserStore()
	}
	h := &AuthHandler{
		sessions:      store,
		users:         users,
		loginAttempts: make(map[string]*loginAttempt),
	}

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()
	if err := bootstrapFirstAdmin(ctx, users, os.Getenv); err != nil {
		logger.Error("FIRST_ADMIN bootstrap failed", "error", err)
	}
	return h
}

// firstAdminID is the ID the bootstrap admin has always had, so data it owns
// keeps its owner when accounts move from memory to the database.
const firstAdminID = "1"

// errFirstAdminEmailTaken means FIRST_ADMIN_EMAIL belongs to a self-registered
// (non-admin) account. Registration does not verify email ownership, so that
// account is never promoted.
var errFirstAdminEmailTaken = errors.New("FIRST_ADMIN_EMAIL is registered to a non-admin account; refusing to promote it (use another email or fix the row by hand)")

// bootstrapFirstAdmin makes FIRST_ADMIN_EMAIL / FIRST_ADMIN_PASSWORD a working
// admin login, as the in-memory bootstrap did on every start:
//   - no account with that email: create it as admin (ID "1" when free);
//   - an admin account: keep it, resetting the password when the env value
//     changed;
//   - a non-admin account: leave it alone and report an error.
func bootstrapFirstAdmin(ctx context.Context, users UserStore, getenv func(string) string) error {
	email := normalizeEmail(getenv("FIRST_ADMIN_EMAIL"))
	password := getenv("FIRST_ADMIN_PASSWORD")
	if email == "" || password == "" {
		return nil
	}

	existing, err := users.GetUserByEmail(ctx, email)
	switch {
	case err == nil && existing.Role != RoleAdmin:
		return errFirstAdminEmailTaken
	case err == nil:
		if bcrypt.CompareHashAndPassword([]byte(existing.PasswordHash), []byte(password)) == nil {
			return nil
		}
		hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
		if err != nil {
			return fmt.Errorf("hash admin password: %w", err)
		}
		if err := users.UpdatePasswordHash(ctx, existing.ID, string(hash)); err != nil {
			return err
		}
		logger.Info("Admin password updated from FIRST_ADMIN_PASSWORD")
		return nil
	case !errors.Is(err, database.ErrUserNotFound):
		return err
	}

	hash, err := bcrypt.GenerateFromPassword([]byte(password), bcrypt.DefaultCost)
	if err != nil {
		return fmt.Errorf("hash admin password: %w", err)
	}
	admin := authUser{
		ID:           firstAdminID,
		Email:        email,
		Name:         envOrDefaultFn(getenv, "FIRST_ADMIN_NAME", "Admin"),
		Role:         RoleAdmin,
		PasswordHash: string(hash),
	}
	err = users.CreateUser(ctx, admin)
	if errors.Is(err, database.ErrEmailTaken) {
		// ID "1" is held by an earlier admin email; the email itself was free.
		admin.ID = generateID()
		err = users.CreateUser(ctx, admin)
	}
	if err != nil {
		return err
	}
	logger.Info("Default admin user created from environment variables")
	return nil
}

func envOrDefaultFn(getenv func(string) string, key, def string) string {
	if v := getenv(key); v != "" {
		return v
	}
	return def
}

// normalizeEmail makes email lookups case- and whitespace-insensitive.
func normalizeEmail(email string) string {
	return strings.ToLower(strings.TrimSpace(email))
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

	found, err := h.users.GetUserByEmail(r.Context(), normalizeEmail(req.Email))
	if err != nil && !errors.Is(err, database.ErrUserNotFound) {
		logger.Error("Login user lookup failed", "error", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}
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

	found, err := h.users.GetUserByID(r.Context(), userID)
	if err != nil && !errors.Is(err, database.ErrUserNotFound) {
		logger.Error("Session user lookup failed", "error", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

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

// IsAdmin reports whether userID belongs to a user with the admin role.
// Only the FIRST_ADMIN_EMAIL bootstrap account is admin; self-registration
// always creates the non-admin "trader" role. A lookup failure counts as
// not admin.
func (h *AuthHandler) IsAdmin(userID string) bool {
	if userID == "" || h.users == nil {
		return false
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	u, err := h.users.GetUserByID(ctx, userID)
	if err != nil {
		if !errors.Is(err, database.ErrUserNotFound) {
			logger.Error("Admin check user lookup failed", "error", err)
		}
		return false
	}
	return u.Role == RoleAdmin
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

	hash, err := bcrypt.GenerateFromPassword([]byte(req.Password), bcrypt.DefaultCost)
	if err != nil {
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	newUser := authUser{
		ID:           generateID(),
		Email:        normalizeEmail(req.Email),
		Name:         req.Name,
		Role:         "trader",
		PasswordHash: string(hash),
	}
	if err := h.users.CreateUser(r.Context(), newUser); err != nil {
		if errors.Is(err, database.ErrEmailTaken) {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusConflict)
			json.NewEncoder(w).Encode(map[string]string{"error": "Email already registered"})
			return
		}
		logger.Error("Failed to create user", "error", err)
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

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
