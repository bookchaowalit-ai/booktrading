package http

import (
	"context"
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"

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

var defaultUsers = []authUser{
	{
		ID:    "1",
		Email: "demo@tradepro.com",
		Name:  "Demo Trader",
		Role:  "trader",
	},
	{
		ID:    "2",
		Email: "admin@tradepro.com",
		Name:  "Admin User",
		Role:  "admin",
	},
}

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
	mu      sync.RWMutex
	users   []authUser
	sessions sessionStore
}

// NewAuthHandler creates an AuthHandler. Pass a Redis-backed sessionStore (or nil for in-memory fallback).
func NewAuthHandler(store sessionStore) *AuthHandler {
	if store == nil {
		store = &memorySessionStore{tokens: make(map[string]string)}
	}
	h := &AuthHandler{
		sessions: store,
	}

	passwords := map[string]string{
		"1": "demo123",
		"2": "admin123",
	}

	for _, u := range defaultUsers {
		hash, _ := bcrypt.GenerateFromPassword([]byte(passwords[u.ID]), bcrypt.DefaultCost)
		h.users = append(h.users, authUser{
			ID:           u.ID,
			Email:        u.Email,
			Name:         u.Name,
			Role:         u.Role,
			PasswordHash: string(hash),
		})
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
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid email or password"})
		return
	}

	token, err := generateToken()
	if err != nil {
		http.Error(w, "Internal server error", http.StatusInternalServerError)
		return
	}

	h.mu.Lock()
	h.sessions.SetSession(r.Context(), token, found.ID, sessionTTL) //nolint:errcheck
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

// extractBearerToken gets the token from Authorization header or query param
func extractBearerToken(r *http.Request) string {
	auth := r.Header.Get("Authorization")
	if strings.HasPrefix(auth, "Bearer ") {
		return strings.TrimPrefix(auth, "Bearer ")
	}
	return r.URL.Query().Get("token")
}
