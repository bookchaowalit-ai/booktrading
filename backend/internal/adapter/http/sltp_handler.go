package http

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"
)

// SLTPConfig represents stop-loss / take-profit configuration for a symbol
type SLTPConfig struct {
	UserID               string  `json:"userId"`
	Symbol               string  `json:"symbol"`
	StopLossPercent      float64 `json:"stopLossPercent"`
	TakeProfitPercent    float64 `json:"takeProfitPercent"`
	StopLossPrice        float64 `json:"stopLossPrice"`
	TakeProfitPrice      float64 `json:"takeProfitPrice"`
	TrailingStop         bool    `json:"trailingStop"`
	TrailingStopPercent  float64 `json:"trailingStopPercent"`
	Enabled              bool    `json:"enabled"`
}

// SLTPHandler manages stop-loss / take-profit configurations (in-memory with DB
// persistence via migration 005 tables — full DB wiring left for future sprint).
type SLTPHandler struct {
	mu      sync.RWMutex
	configs map[string]*SLTPConfig // key: userID+":"+symbol
}

func NewSLTPHandler() *SLTPHandler {
	return &SLTPHandler{configs: make(map[string]*SLTPConfig)}
}

func sltpKey(userID, symbol string) string {
	return strings.ToLower(userID + ":" + symbol)
}

// GetSLTP handles GET /api/sltp/{symbol}
func (h *SLTPHandler) GetSLTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	symbol := strings.TrimPrefix(r.URL.Path, "/api/sltp/")
	if symbol == "" {
		http.Error(w, "Symbol required", http.StatusBadRequest)
		return
	}

	userID := getUserIDFromContext(r)

	h.mu.RLock()
	cfg, ok := h.configs[sltpKey(userID, symbol)]
	h.mu.RUnlock()

	if !ok {
		// Return default (disabled) config
		cfg = &SLTPConfig{UserID: userID, Symbol: symbol, Enabled: false}
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(cfg)
}

// SetSLTP handles POST /api/sltp
func (h *SLTPHandler) SetSLTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var cfg SLTPConfig
	if err := json.NewDecoder(r.Body).Decode(&cfg); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	if cfg.Symbol == "" {
		http.Error(w, "Symbol is required", http.StatusBadRequest)
		return
	}

	cfg.UserID = getUserIDFromContext(r)

	h.mu.Lock()
	h.configs[sltpKey(cfg.UserID, cfg.Symbol)] = &cfg
	h.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "saved"})
}

// DeleteSLTP handles DELETE /api/sltp/{symbol}
func (h *SLTPHandler) DeleteSLTP(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	symbol := strings.TrimPrefix(r.URL.Path, "/api/sltp/")
	if symbol == "" {
		http.Error(w, "Symbol required", http.StatusBadRequest)
		return
	}

	userID := getUserIDFromContext(r)

	h.mu.Lock()
	delete(h.configs, sltpKey(userID, symbol))
	h.mu.Unlock()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "deleted"})
}

// getUserIDFromContext extracts userID from request — reads it from a header
// set by the auth middleware (future: use context value).
func getUserIDFromContext(r *http.Request) string {
	if uid := r.Header.Get("X-User-ID"); uid != "" {
		return uid
	}
	return "default"
}
