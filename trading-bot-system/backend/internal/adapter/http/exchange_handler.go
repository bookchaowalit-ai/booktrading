package http

import (
	"encoding/json"
	"net/http"
	"trading-bot-system/backend/internal/adapter/exchange"
	"trading-bot-system/backend/internal/config"
)

// ExchangeHandler handles exchange-related HTTP requests
type ExchangeHandler struct {
	manager *exchange.ExchangeManager
}

// NewExchangeHandler creates a new exchange handler
func NewExchangeHandler(manager *exchange.ExchangeManager) *ExchangeHandler {
	return &ExchangeHandler{
		manager: manager,
	}
}

// GetExchanges returns list of supported exchanges
func (h *ExchangeHandler) GetExchanges(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	exchanges := h.manager.GetSupportedExchanges()
	currentProvider := h.manager.GetCurrentProvider()

	response := map[string]interface{}{
		"exchanges":       exchanges,
		"current_provider": currentProvider,
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// SetExchangeRequest represents request to set exchange
type SetExchangeRequest struct {
	Provider string `json:"provider"`
}

// ConfigureExchangeRequest represents request to configure exchange API keys
type ConfigureExchangeRequest struct {
	Provider  string `json:"provider"`
	APIKey    string `json:"api_key"`
	APISecret string `json:"api_secret"`
	UseTestnet bool  `json:"use_testnet"`
}

// SetExchange sets the active exchange provider
func (h *ExchangeHandler) SetExchange(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	var req SetExchangeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Invalid request body",
		})
		return
	}

	provider := config.ExchangeProvider(req.Provider)
	if err := h.manager.SetCurrentProvider(provider); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status":   "success",
		"provider": string(provider),
	})
}

// ConfigureExchange configures API keys for an exchange provider
func (h *ExchangeHandler) ConfigureExchange(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	var req ConfigureExchangeRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Invalid request body",
		})
		return
	}

	// Validate required fields
	if req.APIKey == "" || req.APISecret == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "API key and secret are required",
		})
		return
	}

	// Configure the exchange in the manager
	if err := h.manager.ConfigureExchange(req.Provider, req.APIKey, req.APISecret, req.UseTestnet); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status":   "success",
		"provider": req.Provider,
	})
}

// DeleteExchange deletes API keys for an exchange provider
func (h *ExchangeHandler) DeleteExchange(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	// Read provider from request body
	var req struct {
		Provider string `json:"provider"`
	}
	
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Invalid request body",
		})
		return
	}

	if req.Provider == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Provider is required",
		})
		return
	}

	// Delete from the manager
	if err := h.manager.DeleteExchange(req.Provider); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status":   "success",
		"provider": req.Provider,
	})
}

// GetBalances returns balances for the current exchange
func (h *ExchangeHandler) GetBalances(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	balances, err := h.manager.GetBalances(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"balances": balances,
	})
}
