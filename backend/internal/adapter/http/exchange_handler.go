package http

import (
	"encoding/json"
	"net/http"
	"strings"
	"sync"
	"time"
	"trading-bot-system/backend/internal/adapter/exchange"
	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/logger"
)

// ExchangeHandler handles exchange-related HTTP requests
type ExchangeHandler struct {
	manager *exchange.ExchangeManager

	// Balance cache — reduces API calls to exchanges
	balanceCache map[string]*cachedBalance
	cacheMu      sync.RWMutex
	cacheTTL     time.Duration
}

// cachedBalance stores a cached balance response
type cachedBalance struct {
	data      interface{}
	timestamp time.Time
}

// NewExchangeHandler creates a new exchange handler
func NewExchangeHandler(manager *exchange.ExchangeManager) *ExchangeHandler {
	return &ExchangeHandler{
		manager:      manager,
		balanceCache: make(map[string]*cachedBalance),
		cacheTTL:     5 * time.Minute,
	}
}

// getBalanceFromCache returns cached balance if available and not expired
func (h *ExchangeHandler) getBalanceFromCache(key string) (interface{}, bool) {
	h.cacheMu.RLock()
	defer h.cacheMu.RUnlock()
	if cached, ok := h.balanceCache[key]; ok && time.Since(cached.timestamp) < h.cacheTTL {
		return cached.data, true
	}
	return nil, false
}

// setBalanceCache stores balance data in cache
func (h *ExchangeHandler) setBalanceCache(key string, data interface{}) {
	h.cacheMu.Lock()
	defer h.cacheMu.Unlock()
	h.balanceCache[key] = &cachedBalance{
		data:      data,
		timestamp: time.Now(),
	}
}

// invalidateCache removes all cached data
func (h *ExchangeHandler) invalidateCache() {
	h.cacheMu.Lock()
	defer h.cacheMu.Unlock()
	h.balanceCache = make(map[string]*cachedBalance)
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
		"exchanges":        exchanges,
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
	Provider   string `json:"provider"`
	APIKey     string `json:"api_key"`
	APISecret  string `json:"api_secret"`
	UseTestnet bool   `json:"use_testnet"`
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

	// Reject masked keys (contain "****") — these are display-only values, not real credentials
	if strings.Contains(req.APIKey, "****") || strings.Contains(req.APISecret, "****") {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Cannot save masked API key. Please enter the full API key and secret.",
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

// GetConfiguredExchanges returns exchanges that have API keys configured (from DB)
func (h *ExchangeHandler) GetConfiguredExchanges(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{"error": "Method not allowed"})
		return
	}

	keys, _ := h.manager.GetStoredAPIKeyInfos(r.Context())

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"keys":             keys,
		"current_provider": string(h.manager.GetCurrentProvider()),
	})
}

// GetBalances returns balances for the current exchange (with caching)
func (h *ExchangeHandler) GetBalances(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Check cache first
	if cached, ok := h.getBalanceFromCache("current"); ok {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(cached)
		return
	}

	balances, err := h.manager.GetBalances(r.Context())
	if err != nil {
		respondError(w, "Failed to fetch balances", err, http.StatusInternalServerError)
		return
	}

	response := map[string]interface{}{
		"balances": balances,
		"cached":   false,
		"exchange": string(h.manager.GetCurrentProvider()),
	}

	// Store in cache
	h.setBalanceCache("current", response)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// GetAllBalances returns aggregated balances from ALL configured exchanges
func (h *ExchangeHandler) GetAllBalances(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Check cache first
	if cached, ok := h.getBalanceFromCache("all"); ok {
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(cached)
		return
	}

	ctx := r.Context()
	provider := h.manager.GetCurrentProvider()

	// Get all configured exchanges from DB
	configuredKeys, _ := h.manager.GetStoredAPIKeyInfos(ctx)
	allBalances := make(map[string]interface{})
	var totalBalanceTHB float64
	var totalBalanceUSD float64

	for _, key := range configuredKeys {
		exchangeProvider := config.ExchangeProvider(key.Exchange)
		var balances []exchange.Balance
		var err error

		// Temporarily switch provider to get balances
		originalProvider := h.manager.GetCurrentProvider()
		_ = h.manager.SetCurrentProvider(exchangeProvider)

		balances, err = h.manager.GetBalances(ctx)

		// Switch back
		_ = h.manager.SetCurrentProvider(originalProvider)

		if err != nil {
			logger.Warn("Failed to fetch balances from exchange", "exchange", key.Exchange, "error", err)
			allBalances[key.Exchange] = map[string]interface{}{
				"connected": false,
				"error":     err.Error(),
				"balances":  []exchange.Balance{},
			}
			continue
		}

		// Calculate totals for this exchange
		var exchangeTotalTHB, exchangeTotalUSD float64
		for _, b := range balances {
			// Convert to THB/USD for summary
			switch b.Currency {
			case "THB":
				exchangeTotalTHB += b.Total
			case "USDT", "USD", "BUSD":
				exchangeTotalUSD += b.Total
			}
		}

		allBalances[key.Exchange] = map[string]interface{}{
			"connected":    true,
			"balances":     balances,
			"totalTHB":     exchangeTotalTHB,
			"totalUSDT":    exchangeTotalUSD,
			"balanceCount": len(balances),
		}

		totalBalanceTHB += exchangeTotalTHB
		totalBalanceUSD += exchangeTotalUSD
	}

	response := map[string]interface{}{
		"exchanges":       allBalances,
		"totalTHB":        totalBalanceTHB,
		"totalUSDT":       totalBalanceUSD,
		"currentProvider": string(provider),
		"exchangeCount":   len(allBalances),
		"cached":          false,
		"timestamp":       time.Now().Format(time.RFC3339),
	}

	// Store in cache
	h.setBalanceCache("all", response)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// RefreshBalances forces a refresh of all exchange balances (bypasses cache)
func (h *ExchangeHandler) RefreshBalances(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Invalidate cache
	h.invalidateCache()

	// Fetch all balances to repopulate cache
	h.GetAllBalances(w, r)
}
