package http

import (
	"encoding/json"
	"net/http"
	"strconv"
	"strings"

	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

// CopyTradingHandler handles copy trading HTTP requests
type CopyTradingHandler struct {
	service     *service.CopyTradingService
	authHandler *AuthHandler
}

// NewCopyTradingHandler creates a new copy trading handler
func NewCopyTradingHandler(svc *service.CopyTradingService, authHandler *AuthHandler) *CopyTradingHandler {
	return &CopyTradingHandler{
		service:     svc,
		authHandler: authHandler,
	}
}

// getUserID extracts user ID from the request's auth token
func (h *CopyTradingHandler) getUserID(r *http.Request) string {
	token := extractBearerToken(r)
	if token == "" {
		return ""
	}
	if h.authHandler != nil {
		userID, _ := h.authHandler.ValidateToken(token)
		return userID
	}
	return ""
}

// writeJSON writes a JSON response
func (h *CopyTradingHandler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes a JSON error response
func (h *CopyTradingHandler) writeError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// CreateStrategy handles POST /api/copy/strategies
func (h *CopyTradingHandler) CreateStrategy(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req model.CreateStrategyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	profile, err := h.service.CreateStrategy(r.Context(), userID, req)
	if err != nil {
		logger.Error("Failed to create strategy", "user_id", userID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, profile)
}

// GetMyStrategies handles GET /api/copy/strategies/my
func (h *CopyTradingHandler) GetMyStrategies(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	strategies, err := h.service.GetMyStrategies(r.Context(), userID)
	if err != nil {
		logger.Error("Failed to get user strategies", "user_id", userID, "error", err)
		h.writeError(w, http.StatusInternalServerError, "Failed to retrieve strategies")
		return
	}

	h.writeJSON(w, http.StatusOK, strategies)
}

// GetLeaderboard handles GET /api/copy/leaderboard
func (h *CopyTradingHandler) GetLeaderboard(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	limitStr := r.URL.Query().Get("limit")
	offsetStr := r.URL.Query().Get("offset")

	limit := 50
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	offset := 0
	if offsetStr != "" {
		if parsed, err := strconv.Atoi(offsetStr); err == nil && parsed >= 0 {
			offset = parsed
		}
	}

	entries, err := h.service.GetPublicLeaderboard(r.Context(), limit, offset)
	if err != nil {
		logger.Error("Failed to get leaderboard", "error", err)
		h.writeError(w, http.StatusInternalServerError, "Failed to retrieve leaderboard")
		return
	}

	h.writeJSON(w, http.StatusOK, entries)
}

// StartCopying handles POST /api/copy/copy
func (h *CopyTradingHandler) StartCopying(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req model.CopyStrategyRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	relationship, err := h.service.StartCopying(r.Context(), userID, req)
	if err != nil {
		logger.Error("Failed to start copying", "user_id", userID, "strategy_id", req.StrategyID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, relationship)
}

// StopCopying handles DELETE /api/copy/copy/{id}
func (h *CopyTradingHandler) StopCopying(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	relationshipID := strings.TrimPrefix(r.URL.Path, "/api/copy/copy/")
	if relationshipID == "" {
		h.writeError(w, http.StatusBadRequest, "Relationship ID is required")
		return
	}

	if err := h.service.StopCopying(r.Context(), userID, relationshipID); err != nil {
		logger.Error("Failed to stop copying", "user_id", userID, "relationship_id", relationshipID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "stopped"})
}

// GetMyCopied handles GET /api/copy/copied
func (h *CopyTradingHandler) GetMyCopied(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	strategies, err := h.service.GetMyCopiedStrategies(r.Context(), userID)
	if err != nil {
		logger.Error("Failed to get copied strategies", "user_id", userID, "error", err)
		h.writeError(w, http.StatusInternalServerError, "Failed to retrieve copied strategies")
		return
	}

	h.writeJSON(w, http.StatusOK, strategies)
}

// GetCopyTrades handles GET /api/copy/copied/{id}/trades
func (h *CopyTradingHandler) GetCopyTrades(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	// Extract relationship ID from path: /api/copy/copied/{id}/trades
	path := strings.TrimPrefix(r.URL.Path, "/api/copy/copied/")
	relationshipID := strings.TrimSuffix(path, "/trades")
	if relationshipID == "" {
		h.writeError(w, http.StatusBadRequest, "Relationship ID is required")
		return
	}

	limitStr := r.URL.Query().Get("limit")
	limit := 50
	if limitStr != "" {
		if parsed, err := strconv.Atoi(limitStr); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	trades, err := h.service.GetCopyTradeHistory(r.Context(), relationshipID, limit)
	if err != nil {
		logger.Error("Failed to get copy trades", "relationship_id", relationshipID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, trades)
}

// RegisterRoutes registers all copy trading routes to the mux
func (h *CopyTradingHandler) RegisterRoutes(mux *http.ServeMux) {
	// Strategy creation: POST /api/copy/strategies
	mux.HandleFunc("/api/copy/strategies", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/copy/strategies" {
			h.writeError(w, http.StatusNotFound, "Not found")
			return
		}
		switch r.Method {
		case http.MethodPost:
			h.CreateStrategy(w, r)
		case http.MethodGet:
			// Redirect to /my for user's own strategies (for backwards compatibility)
			h.writeError(w, http.StatusMethodNotAllowed, "Use /api/copy/strategies/my to get your strategies")
		default:
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
	})

	// My strategies: GET /api/copy/strategies/my
	mux.HandleFunc("/api/copy/strategies/my", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			h.GetMyStrategies(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
	})

	// Leaderboard: GET /api/copy/leaderboard
	mux.HandleFunc("/api/copy/leaderboard", func(w http.ResponseWriter, r *http.Request) {
		if r.Method == http.MethodGet {
			h.GetLeaderboard(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
	})

	// Start copying: POST /api/copy/copy
	mux.HandleFunc("/api/copy/copy", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/copy/copy" {
			// Handle DELETE /api/copy/copy/{id}
			if r.Method == http.MethodDelete {
				h.StopCopying(w, r)
			} else {
				h.writeError(w, http.StatusNotFound, "Not found")
			}
			return
		}
		if r.Method == http.MethodPost {
			h.StartCopying(w, r)
		} else if r.Method == http.MethodDelete {
			h.StopCopying(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
	})

	// My copied strategies: GET /api/copy/copied
	mux.HandleFunc("/api/copy/copied", func(w http.ResponseWriter, r *http.Request) {
		if r.URL.Path != "/api/copy/copied" {
			// Handle /api/copy/copied/{id}/trades
			if strings.HasSuffix(r.URL.Path, "/trades") && r.Method == http.MethodGet {
				h.GetCopyTrades(w, r)
			} else {
				h.writeError(w, http.StatusNotFound, "Not found")
			}
			return
		}
		if r.Method == http.MethodGet {
			h.GetMyCopied(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
	})
}
