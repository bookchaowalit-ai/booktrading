package http

import (
	"encoding/json"
	"net/http"
	"strconv"
	"time"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

// NewFeatureHandler creates handlers for new feature endpoints
func NewFeatureHandler(
	paperEngine *service.PaperEngine,
	riskManager *service.RiskManager,
	alertService *service.AlertService,
	metricsService *service.MetricsService,
	backtestService *service.BacktestService,
	auditService *service.AuditService,
	priceAlertMonitor *service.PriceAlertMonitor,
) *FeatureHandler {
	return &FeatureHandler{
		paperEngine:     paperEngine,
		riskManager:     riskManager,
		alertService:    alertService,
		metricsService:  metricsService,
		backtestService: backtestService,
		auditService:    auditService,
		priceAlertMon:   priceAlertMonitor,
	}
}

// FeatureHandler handles new feature endpoints
type FeatureHandler struct {
	paperEngine     *service.PaperEngine
	riskManager     *service.RiskManager
	alertService    *service.AlertService
	metricsService  *service.MetricsService
	backtestService *service.BacktestService
	auditService    *service.AuditService
	priceAlertMon   *service.PriceAlertMonitor
}

// RegisterRoutes registers all new feature routes
func (h *FeatureHandler) RegisterRoutes(mux *http.ServeMux) {
	// Paper Trading
	mux.HandleFunc("/api/paper/order", h.PaperOrder)
	mux.HandleFunc("/api/paper/portfolio", h.PaperPortfolio)
	mux.HandleFunc("/api/paper/history", h.PaperHistory)
	mux.HandleFunc("/api/paper/reset", h.PaperReset)
	mux.HandleFunc("/api/paper/update-price", h.PaperUpdatePrice)
	mux.HandleFunc("/api/paper/orders", h.PaperOpenOrders)
	mux.HandleFunc("/api/paper/cancel", h.PaperCancelOrder)
	mux.HandleFunc("/api/paper/seed", h.PaperSeedPosition)
	mux.HandleFunc("/api/paper/snapshots", h.PaperSnapshots)

	// Risk Management
	mux.HandleFunc("/api/risk/config", h.RiskConfig)
	mux.HandleFunc("/api/risk/metrics", h.RiskMetrics)
	mux.HandleFunc("/api/risk/check", h.RiskCheck)

	// Alerts
	mux.HandleFunc("/api/alerts/config", h.AlertsConfig)
	mux.HandleFunc("/api/alerts/test", h.AlertsTest)
	mux.HandleFunc("/api/alerts/history", h.AlertsHistory)

	// Price Alerts
	mux.HandleFunc("/api/price-alerts", h.PriceAlerts)
	mux.HandleFunc("/api/price-alerts/reset", h.PriceAlertsReset)

	// Backtesting
	mux.HandleFunc("/api/backtest/run", h.BacktestRun)
	mux.HandleFunc("/api/backtest/history", h.BacktestFetchHistory)

	// Metrics (Prometheus)
	mux.Handle("/api/metrics", h.metricsService.Handler())

	// Audit logs
	mux.HandleFunc("/api/audit/logs", h.GetAuditLogs)
	mux.HandleFunc("/api/audit/stats", h.GetAuditStats)
}

// ── Paper Trading Handlers ──

type PaperOrderRequest struct {
	Symbol       string  `json:"symbol"`
	Side         string  `json:"side"`
	Quantity     float64 `json:"quantity"`
	LimitPrice   float64 `json:"limit_price"`
	CurrentPrice float64 `json:"current_price,omitempty"` // Market price for realistic simulation
}

func (h *FeatureHandler) PaperOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req PaperOrderRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request body"})
		return
	}

	side := model.OrderSide(req.Side)
	if side != model.SideBuy && side != model.SideSell {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Side must be BUY or SELL"})
		return
	}

	// Use provided current_price (market price) for realistic limit order simulation.
	// If not provided, use limit_price as fallback (backward compat).
	currentPrice := req.CurrentPrice
	if currentPrice <= 0 {
		currentPrice = req.LimitPrice
	}

	order, err := h.paperEngine.PlaceOrder(r.Context(), req.Symbol, side, req.Quantity, req.LimitPrice, currentPrice)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	h.metricsService.RecordPaperTrade(0)
	writeJSON(w, http.StatusCreated, order)
}

func (h *FeatureHandler) PaperPortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	portfolio := h.paperEngine.GetPortfolio()
	h.metricsService.UpdateActiveBots(0)
	h.metricsService.RecordPaperTrade(portfolio.TotalPnL)
	writeJSON(w, http.StatusOK, portfolio)
}

func (h *FeatureHandler) PaperHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	trades := h.paperEngine.GetTradeHistory()
	writeJSON(w, http.StatusOK, trades)
}

func (h *FeatureHandler) PaperReset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.paperEngine.Reset()
	writeJSON(w, http.StatusOK, map[string]string{"status": "reset"})
}

// PaperUpdatePrice updates the market price for a symbol, triggering pending order fills.
type PaperUpdatePriceRequest struct {
	Symbol string  `json:"symbol"`
	Price  float64 `json:"price"`
}

func (h *FeatureHandler) PaperUpdatePrice(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req PaperUpdatePriceRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request body"})
		return
	}

	if req.Price <= 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Price must be > 0"})
		return
	}

	h.paperEngine.UpdatePrice(req.Symbol, req.Price)
	writeJSON(w, http.StatusOK, map[string]string{"status": "updated"})
}

// PaperOpenOrders returns all pending (unfilled) orders.
func (h *FeatureHandler) PaperOpenOrders(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	orders := h.paperEngine.GetOpenOrders()
	writeJSON(w, http.StatusOK, orders)
}

func (h *FeatureHandler) PaperCancelOrder(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		OrderID string `json:"order_id"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.OrderID == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "order_id required"})
		return
	}

	if err := h.paperEngine.CancelOrder(req.OrderID); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "cancelled", "order_id": req.OrderID})
}

// PaperSeedPosition creates an initial position for a symbol (enables SELL orders).
type PaperSeedPositionRequest struct {
	Symbol   string  `json:"symbol"`
	Quantity float64 `json:"quantity"`
	Price    float64 `json:"price"`
}

func (h *FeatureHandler) PaperSeedPosition(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req PaperSeedPositionRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request body"})
		return
	}

	if req.Symbol == "" || req.Quantity <= 0 || req.Price <= 0 {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol, quantity > 0, and price > 0 required"})
		return
	}

	if err := h.paperEngine.SeedPosition(req.Symbol, req.Quantity, req.Price); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":   "seeded",
		"symbol":   req.Symbol,
		"quantity": req.Quantity,
		"price":    req.Price,
	})
}

// ── Risk Management Handlers ──

func (h *FeatureHandler) RiskConfig(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		writeJSON(w, http.StatusOK, h.riskManager.GetConfig())
	case http.MethodPost:
		var config model.RiskConfig
		if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
			return
		}
		h.riskManager.UpdateConfig(&config)
		writeJSON(w, http.StatusOK, map[string]string{"status": "updated"})
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (h *FeatureHandler) RiskMetrics(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	metrics := h.riskManager.GetMetrics()
	writeJSON(w, http.StatusOK, metrics)
}

type RiskCheckRequest struct {
	Symbol    string  `json:"symbol"`
	Side      string  `json:"side"`
	Quantity  float64 `json:"quantity"`
	Price     float64 `json:"price"`
	Portfolio float64 `json:"portfolio_value"`
}

func (h *FeatureHandler) RiskCheck(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req RiskCheckRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
		return
	}

	blocked := h.riskManager.CheckTradeApproval(req.Symbol, model.OrderSide(req.Side), req.Quantity, req.Price, req.Portfolio)
	h.metricsService.RecordRiskCheck(len(blocked) > 0)

	resp := map[string]any{
		"approved": len(blocked) == 0,
	}
	if len(blocked) > 0 {
		resp["reasons"] = blocked
	}

	writeJSON(w, http.StatusOK, resp)
}

// ── Alert handlers ──

func (h *FeatureHandler) AlertsConfig(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		// Return config without sensitive fields
		cfg := h.alertService.GetConfig()
		safe := map[string]any{
			"enabled":             cfg.Enabled,
			"has_discord":        cfg.DiscordWebhookURL != "",
			"has_telegram":       cfg.TelegramBotToken != "",
			"has_email":          cfg.EmailSMTPHost != "",
			"has_webhook":        cfg.CustomWebhookURL != "",
			"notify_on_trade":    cfg.NotifyOnTrade,
			"notify_on_bot_start": cfg.NotifyOnBotStart,
			"notify_on_error":    cfg.NotifyOnError,
			"notify_on_risk":     cfg.NotifyOnRisk,
			"notify_on_price":    cfg.NotifyOnPrice,
		}
		writeJSON(w, http.StatusOK, safe)
	case http.MethodPost:
		var config model.AlertConfig
		if err := json.NewDecoder(r.Body).Decode(&config); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
			return
		}
		h.alertService.UpdateConfig(&config)
		writeJSON(w, http.StatusOK, map[string]string{"status": "updated"})
	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (h *FeatureHandler) AlertsTest(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	if err := h.alertService.SendTest(r.Context()); err != nil {
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{"status": "test alert sent"})
}

func (h *FeatureHandler) AlertsHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	alerts := h.alertService.GetHistory(limit)
	writeJSON(w, http.StatusOK, alerts)
}

// ── Backtest handlers ──

type BacktestRunRequest struct {
	Symbol          string    `json:"symbol"`
	StartDate       string    `json:"start_date"`
	EndDate         string    `json:"end_date"`
	InitialCapital  float64   `json:"initial_capital"`
	Commission      float64   `json:"commission"`
	Slippage        float64   `json:"slippage"`
	Strategy        string    `json:"strategy"`
	RSIPeriod       int       `json:"rsi_period"`
	RSIOversold     float64   `json:"rsi_oversold"`
	RSIOverbought   float64   `json:"rsi_overbought"`
	EMAFastPeriod   int       `json:"ema_fast_period"`
	EMASlowPeriod   int       `json:"ema_slow_period"`
}

func (h *FeatureHandler) BacktestRun(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var req BacktestRunRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
		return
	}

	// Parse dates
	startDate, err := time.Parse("2006-01-02", req.StartDate)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "start_date must be YYYY-MM-DD"})
		return
	}
	endDate, err := time.Parse("2006-01-02", req.EndDate)
	if err != nil {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "end_date must be YYYY-MM-DD"})
		return
	}

	if req.InitialCapital <= 0 {
		req.InitialCapital = 10000
	}
	if req.Strategy == "" {
		req.Strategy = "rsi"
	}
	if req.RSIPeriod <= 0 {
		req.RSIPeriod = 14
	}
	if req.RSIOversold <= 0 {
		req.RSIOversold = 30
	}
	if req.RSIOverbought <= 0 {
		req.RSIOverbought = 70
	}

	config := service.BacktestConfig{
		Symbol:         req.Symbol,
		StartDate:      startDate,
		EndDate:        endDate,
		InitialCapital: req.InitialCapital,
		Commission:     req.Commission,
		Slippage:       req.Slippage,
		Strategy:       req.Strategy,
		RSIPeriod:      req.RSIPeriod,
		RSIOversold:    req.RSIOversold,
		RSIOverbought:  req.RSIOverbought,
		EMAFastPeriod:  req.EMAFastPeriod,
		EMASlowPeriod:  req.EMASlowPeriod,
	}

	result, err := h.backtestService.RunBacktest(r.Context(), config)
	if err != nil {
		logger.Error("Backtest failed", "error", err)
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, result)
}

func (h *FeatureHandler) BacktestFetchHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	symbol := r.URL.Query().Get("symbol")
	if symbol == "" {
		writeJSON(w, http.StatusBadRequest, map[string]string{"error": "symbol is required"})
		return
	}

	klines, err := h.backtestService.FetchHistoricalKlines(r.Context(), symbol, "1d", time.Now().AddDate(0, -3, 0), time.Now())
	if err != nil {
		writeJSON(w, http.StatusBadGateway, map[string]string{"error": err.Error()})
		return
	}

	writeJSON(w, http.StatusOK, klines)
}

// ── Audit Log Handlers ──

// GetAuditLogs handles GET /api/audit/logs
func (h *FeatureHandler) GetAuditLogs(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID := r.URL.Query().Get("user_id")
	action := r.URL.Query().Get("action")

	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	logs, err := h.auditService.GetLogs(r.Context(), userID, action, limit)
	if err != nil {
		logger.Error("Failed to get audit logs", "error", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to retrieve audit logs"})
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"logs": logs,
		"count": len(logs),
	})
}

// GetAuditStats handles GET /api/audit/stats
func (h *FeatureHandler) GetAuditStats(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	ctx := r.Context()

	// Count by action
	actionCounts, err := h.auditService.GetLogs(ctx, "", "", 1000)
	if err != nil {
		logger.Error("Failed to get audit logs for stats", "error", err)
		writeJSON(w, http.StatusInternalServerError, map[string]string{"error": "Failed to retrieve audit stats"})
		return
	}

	byAction := make(map[string]int)
	byUser := make(map[string]int)
	var recent []service.AuditLog

	for _, log := range actionCounts {
		byAction[log.Action]++
		if log.UserID != nil {
			byUser[*log.UserID]++
		}
		if len(recent) < 10 {
			recent = append(recent, log)
		}
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"by_action":     byAction,
		"by_user":       byUser,
		"recent_activity": recent,
		"total":         len(actionCounts),
	})
}

// ── Portfolio Snapshots ──

func (h *FeatureHandler) PaperSnapshots(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	limitStr := r.URL.Query().Get("limit")
	limit := 200
	if limitStr != "" {
		if l, err := strconv.Atoi(limitStr); err == nil && l > 0 {
			limit = l
		}
	}

	snapshots := h.paperEngine.GetSnapshots(limit)
	writeJSON(w, http.StatusOK, snapshots)
}

// ── Price Alert Handlers ──

func (h *FeatureHandler) PriceAlerts(w http.ResponseWriter, r *http.Request) {
	switch r.Method {
	case http.MethodGet:
		alerts := h.priceAlertMon.GetAlerts()
		writeJSON(w, http.StatusOK, alerts)

	case http.MethodPost:
		var req struct {
			Symbol      string  `json:"symbol"`
			TargetPrice float64 `json:"target_price"`
			Direction   string  `json:"direction"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "Invalid request"})
			return
		}
		alert, err := h.priceAlertMon.AddAlert(req.Symbol, req.TargetPrice, req.Direction)
		if err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusCreated, alert)

	case http.MethodDelete:
		var req struct {
			ID string `json:"id"`
		}
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil || req.ID == "" {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": "id required"})
			return
		}
		if err := h.priceAlertMon.RemoveAlert(req.ID); err != nil {
			writeJSON(w, http.StatusBadRequest, map[string]string{"error": err.Error()})
			return
		}
		writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})

	default:
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
	}
}

func (h *FeatureHandler) PriceAlertsReset(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}
	h.priceAlertMon.ResetTriggered()
	writeJSON(w, http.StatusOK, map[string]string{"status": "reset"})
}

// writeJSON is a helper to write JSON responses
func writeJSON(w http.ResponseWriter, status int, data any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}
