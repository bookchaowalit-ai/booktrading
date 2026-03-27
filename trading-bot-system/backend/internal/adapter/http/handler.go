package http

import (
	"encoding/json"
	"log"
	"net/http"
	"strconv"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/port/input"
)

// OrderHandler handles HTTP requests for order operations
type OrderHandler struct {
	orderHandler input.OrderHandler
}

// NewOrderHandler creates a new order HTTP handler
func NewOrderHandler(handler input.OrderHandler) *OrderHandler {
	return &OrderHandler{
		orderHandler: handler,
	}
}

// CreateOrder handles POST /api/orders
func (h *OrderHandler) CreateOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req model.OrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	response, err := h.orderHandler.CreateOrder(r.Context(), &req)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(response)
}

// GetOrder handles GET /api/orders/{id}
func (h *OrderHandler) GetOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract order ID from URL path - simple implementation
	// In production, use a router like chi or gorilla/mux
	orderID := r.URL.Path[len("/api/orders/"):]
	if orderID == "" {
		http.Error(w, "Order ID required", http.StatusBadRequest)
		return
	}

	order, err := h.orderHandler.GetOrder(r.Context(), orderID)
	if err != nil {
		http.Error(w, err.Error(), http.StatusNotFound)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(order)
}

// GetAllOrders handles GET /api/orders
func (h *OrderHandler) GetAllOrders(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	orders, err := h.orderHandler.GetAllOrders(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(orders)
}

// CancelOrder handles DELETE /api/orders/{id}
func (h *OrderHandler) CancelOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	// Extract order ID from URL path
	orderID := r.URL.Path[len("/api/orders/"):]
	if orderID == "" {
		http.Error(w, "Order ID required", http.StatusBadRequest)
		return
	}

	if err := h.orderHandler.CancelOrder(r.Context(), orderID); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// BotHandler handles HTTP requests for bot operations
type BotHandler struct {
	botHandler input.BotHandler
}

// NewBotHandler creates a new bot HTTP handler
func NewBotHandler(handler input.BotHandler) *BotHandler {
	return &BotHandler{
		botHandler: handler,
	}
}

// StartBot handles POST /api/bot/start
func (h *BotHandler) StartBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if err := h.botHandler.Start(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "started"})
}

// StopBot handles POST /api/bot/stop
func (h *BotHandler) StopBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if err := h.botHandler.Stop(r.Context()); err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "stopped"})
}

// GetBotStatus handles GET /api/bot/status
func (h *BotHandler) GetBotStatus(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	status, err := h.botHandler.GetStatus(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(status)
}

// PortfolioHandler handles HTTP requests for portfolio operations
type PortfolioHandler struct {
	portfolioHandler input.PortfolioHandler
}

// NewPortfolioHandler creates a new portfolio HTTP handler
func NewPortfolioHandler(handler input.PortfolioHandler) *PortfolioHandler {
	return &PortfolioHandler{
		portfolioHandler: handler,
	}
}

// GetPortfolio handles GET /api/portfolio
func (h *PortfolioHandler) GetPortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	portfolio, err := h.portfolioHandler.GetPortfolio(r.Context())
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(portfolio)
}

// TradeHistoryHandler handles HTTP requests for trade history
type TradeHistoryHandler struct {
	tradeHistoryHandler input.TradeHistoryHandler
}

// NewTradeHistoryHandler creates a new trade history HTTP handler
func NewTradeHistoryHandler(handler input.TradeHistoryHandler) *TradeHistoryHandler {
	return &TradeHistoryHandler{
		tradeHistoryHandler: handler,
	}
}

// GetTradeHistory handles GET /api/trades
func (h *TradeHistoryHandler) GetTradeHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limitStr := r.URL.Query().Get("limit")
	limit := 50 // default limit
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	trades, err := h.tradeHistoryHandler.GetTradeHistory(r.Context(), limit)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(trades)
}

// HealthHandler handles health check requests
type HealthHandler struct{}

// NewHealthHandler creates a new health handler
func NewHealthHandler() *HealthHandler {
	return &HealthHandler{}
}

// HealthCheck handles GET /api/health
func (h *HealthHandler) HealthCheck(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "healthy",
	})
}

// Router configures HTTP routes
type Router struct {
	mux *http.ServeMux
}

// NewRouter creates a new router
func NewRouter() *Router {
	return &Router{
		mux: http.NewServeMux(),
	}
}

// RegisterOrderRoutes registers order-related routes
func (r *Router) RegisterOrderRoutes(handler *OrderHandler) {
	r.mux.HandleFunc("/api/orders", func(w http.ResponseWriter, req *http.Request) {
		switch req.Method {
		case http.MethodPost:
			handler.CreateOrder(w, req)
		case http.MethodGet:
			handler.GetAllOrders(w, req)
		case http.MethodDelete:
			handler.CancelOrder(w, req)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/orders/", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetOrder(w, req)
		} else if req.Method == http.MethodDelete {
			handler.CancelOrder(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterBotRoutes registers bot-related routes
func (r *Router) RegisterBotRoutes(handler *BotHandler) {
	r.mux.HandleFunc("/api/bot/start", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.StartBot(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/bot/stop", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.StopBot(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/bot/status", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetBotStatus(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterPortfolioRoutes registers portfolio-related routes
func (r *Router) RegisterPortfolioRoutes(handler *PortfolioHandler) {
	r.mux.HandleFunc("/api/portfolio", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetPortfolio(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterTradeHistoryRoutes registers trade history routes
func (r *Router) RegisterTradeHistoryRoutes(handler *TradeHistoryHandler) {
	r.mux.HandleFunc("/api/trades", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetTradeHistory(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterHealthRoute registers health check route
func (r *Router) RegisterHealthRoute(handler *HealthHandler) {
	r.mux.HandleFunc("/api/health", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.HealthCheck(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterExchangeRoutes registers exchange-related routes
func (r *Router) RegisterExchangeRoutes(handler *ExchangeHandler) {
	r.mux.HandleFunc("/api/exchange", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetExchanges(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/exchange/set", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.SetExchange(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/exchange/configure", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.ConfigureExchange(w, req)
		} else if req.Method == http.MethodDelete {
			handler.DeleteExchange(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/exchange/balances", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetBalances(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// RegisterSettingsRoutes registers settings-related routes
func (r *Router) RegisterSettingsRoutes(handler *SettingsHandler) {
	r.mux.HandleFunc("/api/settings/preferences", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			handler.GetPreferences(w, req)
		} else if req.Method == http.MethodPost {
			handler.UpdatePreferences(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/settings/export", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.ExportData(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
	r.mux.HandleFunc("/api/settings/reset", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			handler.ResetSettings(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}

// ServeHTTP implements http.Handler
func (r *Router) ServeHTTP(w http.ResponseWriter, req *http.Request) {
	// Add CORS headers
	w.Header().Set("Access-Control-Allow-Origin", "*")
	w.Header().Set("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
	w.Header().Set("Access-Control-Allow-Headers", "Content-Type, Authorization")

	if req.Method == http.MethodOptions {
		w.WriteHeader(http.StatusOK)
		return
	}

	r.mux.ServeHTTP(w, req)
}

// Logger middleware for logging requests
func Logger(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		log.Printf("%s %s", r.Method, r.URL.Path)
		next.ServeHTTP(w, r)
	})
}
