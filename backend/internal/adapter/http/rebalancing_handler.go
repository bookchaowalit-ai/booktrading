package http

import (
	"encoding/json"
	"net/http"
	"strconv"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

// RebalancingHandler handles HTTP requests for portfolio rebalancing
type RebalancingHandler struct {
	service     *service.RebalancingService
	authHandler *AuthHandler
}

// NewRebalancingHandler creates a new rebalancing handler
func NewRebalancingHandler(svc *service.RebalancingService, auth *AuthHandler) *RebalancingHandler {
	return &RebalancingHandler{
		service:     svc,
		authHandler: auth,
	}
}

// getUserID extracts the user ID from the request's auth token
func (h *RebalancingHandler) getUserID(r *http.Request) (string, error) {
	token := extractBearerToken(r)
	if token == "" {
		return "", nil
	}
	userID, _ := h.authHandler.ValidateToken(token)
	return userID, nil
}

// requireAuth ensures the request has a valid auth token and returns the user ID
func (h *RebalancingHandler) requireAuth(w http.ResponseWriter, r *http.Request) (string, bool) {
	userID, err := h.getUserID(r)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]string{"error": "Failed to validate token"})
		return "", false
	}
	if userID == "" {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		json.NewEncoder(w).Encode(map[string]string{"error": "Unauthorized"})
		return "", false
	}
	return userID, true
}

// GetTargets handles GET /api/rebalance/targets
func (h *RebalancingHandler) GetTargets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID, ok := h.requireAuth(w, r)
	if !ok {
		return
	}

	targets, err := h.service.GetTargets(r.Context(), userID)
	if err != nil {
		respondError(w, "Failed to get rebalance targets", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(targets)
}

// SetTargets handles POST /api/rebalance/targets
func (h *RebalancingHandler) SetTargets(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID, ok := h.requireAuth(w, r)
	if !ok {
		return
	}

	var req model.SetRebalanceTargetsRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid request body"})
		return
	}

	if len(req.Targets) == 0 {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "At least one target is required"})
		return
	}

	// Convert request targets to domain model
	targets := make([]model.RebalanceTarget, 0, len(req.Targets))
	for _, t := range req.Targets {
		if t.Symbol == "" {
			w.Header().Set("Content-Type", "application/json")
			w.WriteHeader(http.StatusBadRequest)
			json.NewEncoder(w).Encode(map[string]string{"error": "Symbol is required for each target"})
			return
		}
		targets = append(targets, model.RebalanceTarget{
			Symbol:        t.Symbol,
			TargetPercent: t.TargetPercent,
		})
	}

	if err := h.service.SetTargets(r.Context(), userID, targets); err != nil {
		respondError(w, "Failed to set rebalance targets", err, http.StatusBadRequest)
		return
	}

	logger.Info("Rebalance targets set via API", "user_id", userID, "count", len(targets))

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{"status": "targets updated"})
}

// AnalyzePortfolio handles GET /api/rebalance/analyze
func (h *RebalancingHandler) AnalyzePortfolio(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID, ok := h.requireAuth(w, r)
	if !ok {
		return
	}

	plan, err := h.service.AnalyzePortfolio(r.Context(), userID)
	if err != nil {
		respondError(w, "Failed to analyze portfolio", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(plan)
}

// ExecuteRebalance handles POST /api/rebalance/execute
func (h *RebalancingHandler) ExecuteRebalance(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID, ok := h.requireAuth(w, r)
	if !ok {
		return
	}

	// Determine trigger type from query param (default: manual)
	triggeredBy := r.URL.Query().Get("triggered_by")
	if triggeredBy == "" {
		triggeredBy = "manual"
	}

	// Validate triggered_by value
	validTriggers := map[string]bool{
		"manual":    true,
		"scheduled": true,
		"threshold": true,
	}
	if !validTriggers[triggeredBy] {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "Invalid triggered_by value. Must be: manual, scheduled, or threshold"})
		return
	}

	history, err := h.service.ExecuteRebalance(r.Context(), userID, triggeredBy)
	if err != nil {
		respondError(w, "Failed to execute rebalance", err, http.StatusInternalServerError)
		return
	}

	logger.Info("Rebalance executed via API",
		"user_id", userID,
		"triggered_by", triggeredBy,
		"trades_executed", history.TradesExecuted,
	)

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(history)
}

// GetRebalanceHistory handles GET /api/rebalance/history
func (h *RebalancingHandler) GetRebalanceHistory(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	userID, ok := h.requireAuth(w, r)
	if !ok {
		return
	}

	// Parse limit from query param
	limitStr := r.URL.Query().Get("limit")
	limit := 20 // default
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	history, err := h.service.GetRebalanceHistory(r.Context(), userID, limit)
	if err != nil {
		respondError(w, "Failed to get rebalance history", err, http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(history)
}

// RegisterRoutes registers all rebalancing routes on the given mux
func (h *RebalancingHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/rebalance/targets", func(w http.ResponseWriter, req *http.Request) {
		switch req.Method {
		case http.MethodGet:
			h.GetTargets(w, req)
		case http.MethodPost:
			h.SetTargets(w, req)
		default:
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/rebalance/analyze", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			h.AnalyzePortfolio(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/rebalance/execute", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodPost {
			h.ExecuteRebalance(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})

	mux.HandleFunc("/api/rebalance/history", func(w http.ResponseWriter, req *http.Request) {
		if req.Method == http.MethodGet {
			h.GetRebalanceHistory(w, req)
		} else {
			http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		}
	})
}
