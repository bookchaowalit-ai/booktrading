package http

import (
	"encoding/json"
	"net/http"
	"sync"

	"trading-bot-system/backend/internal/domain/service"
)

// TradingHandler handles trading-related HTTP requests
type TradingHandler struct {
	tradingService *service.TradingService
	once           sync.Once
}

// NewTradingHandler creates a new trading handler
func NewTradingHandler() *TradingHandler {
	return &TradingHandler{
		tradingService: service.NewTradingService(),
	}
}

// ConfigureRequest represents API key configuration request
type ConfigureRequest struct {
	APIKey    string `json:"apiKey"`
	APISecret string `json:"apiSecret"`
	Testnet   bool   `json:"testnet"`
}

// StartBotRequest represents bot start request
type StartBotRequest struct {
	Symbol         string  `json:"symbol"`
	Quantity       float64 `json:"quantity"`
	GridLevels     int     `json:"gridLevels"`
	LowerPrice     float64 `json:"lowerPrice"`
	UpperPrice     float64 `json:"upperPrice"`
	Investment     float64 `json:"investment"`
}

// StartBot starts the trading bot
func (h *TradingHandler) StartBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req StartBotRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Initialize once
	h.once.Do(func() {
		// In production, load API keys from secure storage
		// For now, using mock keys - you should load from your API keys page
		h.tradingService.ConfigureBot("YOUR_API_KEY", "YOUR_API_SECRET", false)
	})

	// Start the bot
	err := h.tradingService.StartBot(r.Context(), req.Symbol, req.Quantity, req.GridLevels, req.LowerPrice, req.UpperPrice, req.Investment)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "started",
	})
}

// StopBot stops the trading bot
func (h *TradingHandler) StopBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	err := h.tradingService.StopBot()
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "stopped",
	})
}

// GetBotStatus returns the bot status
func (h *TradingHandler) GetBotStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	status := h.tradingService.GetStatus()

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

// GetPortfolio returns the user's portfolio
func (h *TradingHandler) GetPortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	portfolio, err := h.tradingService.GetPortfolio()
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]string{
			"error": err.Error(),
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(portfolio)
}

// ConfigureAPI configures API keys (called from frontend)
func (h *TradingHandler) ConfigureAPI(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req ConfigureRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	// Configure the trading service with real API keys
	h.tradingService.ConfigureBot(req.APIKey, req.APISecret, req.Testnet)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "configured",
	})
}
