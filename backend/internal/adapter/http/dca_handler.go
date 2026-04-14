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

// DCABotHandler handles DCA bot HTTP requests
type DCABotHandler struct {
	dcaService *service.DCABotService
	authHandler *AuthHandler
}

// NewDCABotHandler creates a new DCA bot handler
func NewDCABotHandler(dcaService *service.DCABotService, authHandler *AuthHandler) *DCABotHandler {
	return &DCABotHandler{
		dcaService:  dcaService,
		authHandler: authHandler,
	}
}

// getUserID extracts user ID from the request's auth token
func (h *DCABotHandler) getUserID(r *http.Request) string {
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
func (h *DCABotHandler) writeJSON(w http.ResponseWriter, status int, data interface{}) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(data)
}

// writeError writes a JSON error response
func (h *DCABotHandler) writeError(w http.ResponseWriter, status int, msg string) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// CreateBot handles POST /api/dca/bots
func (h *DCABotHandler) CreateBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	var req model.DCABotCreateRequest
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		h.writeError(w, http.StatusBadRequest, "Invalid request body")
		return
	}

	bot, err := h.dcaService.CreateBot(r.Context(), &req, userID)
	if err != nil {
		logger.Error("Failed to create DCA bot", "user_id", userID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusCreated, bot)
}

// GetBots handles GET /api/dca/bots
func (h *DCABotHandler) GetBots(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	bots, err := h.dcaService.GetUserBots(r.Context(), userID)
	if err != nil {
		logger.Error("Failed to get user DCA bots", "user_id", userID, "error", err)
		h.writeError(w, http.StatusInternalServerError, "Failed to retrieve bots")
		return
	}

	if bots == nil {
		bots = []model.DCABot{}
	}

	h.writeJSON(w, http.StatusOK, bots)
}

// GetBot handles GET /api/dca/bots/{id}
func (h *DCABotHandler) GetBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	botID := strings.TrimPrefix(r.URL.Path, "/api/dca/bots/")
	if botID == "" {
		h.writeError(w, http.StatusBadRequest, "Bot ID is required")
		return
	}

	bot, err := h.dcaService.GetBot(r.Context(), botID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "Bot not found")
		return
	}

	// Verify ownership
	if bot.UserID != "" && bot.UserID != userID {
		h.writeError(w, http.StatusForbidden, "Access denied: bot belongs to another user")
		return
	}

	h.writeJSON(w, http.StatusOK, bot)
}

// StartBot handles POST /api/dca/bots/{id}/start
func (h *DCABotHandler) StartBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	// Extract bot ID from path: /api/dca/bots/{id}/start
	path := strings.TrimPrefix(r.URL.Path, "/api/dca/bots/")
	botID := strings.TrimSuffix(path, "/start")
	if botID == "" {
		h.writeError(w, http.StatusBadRequest, "Bot ID is required")
		return
	}

	// Verify ownership before starting
	bot, err := h.dcaService.GetBot(r.Context(), botID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "Bot not found")
		return
	}
	if bot.UserID != "" && bot.UserID != userID {
		h.writeError(w, http.StatusForbidden, "Access denied: bot belongs to another user")
		return
	}

	if err := h.dcaService.StartBot(r.Context(), botID); err != nil {
		logger.Error("Failed to start DCA bot", "bot_id", botID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "started"})
}

// StopBot handles POST /api/dca/bots/{id}/stop
func (h *DCABotHandler) StopBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	// Extract bot ID from path: /api/dca/bots/{id}/stop
	path := strings.TrimPrefix(r.URL.Path, "/api/dca/bots/")
	botID := strings.TrimSuffix(path, "/stop")
	if botID == "" {
		h.writeError(w, http.StatusBadRequest, "Bot ID is required")
		return
	}

	// Verify ownership before stopping
	bot, err := h.dcaService.GetBot(r.Context(), botID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "Bot not found")
		return
	}
	if bot.UserID != "" && bot.UserID != userID {
		h.writeError(w, http.StatusForbidden, "Access denied: bot belongs to another user")
		return
	}

	if err := h.dcaService.StopBot(r.Context(), botID); err != nil {
		logger.Error("Failed to stop DCA bot", "bot_id", botID, "error", err)
		h.writeError(w, http.StatusBadRequest, err.Error())
		return
	}

	h.writeJSON(w, http.StatusOK, map[string]string{"status": "stopped"})
}

// DeleteBot handles DELETE /api/dca/bots/{id}
func (h *DCABotHandler) DeleteBot(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	botID := strings.TrimPrefix(r.URL.Path, "/api/dca/bots/")
	if botID == "" {
		h.writeError(w, http.StatusBadRequest, "Bot ID is required")
		return
	}

	// Verify ownership before deleting
	bot, err := h.dcaService.GetBot(r.Context(), botID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "Bot not found")
		return
	}
	if bot.UserID != "" && bot.UserID != userID {
		h.writeError(w, http.StatusForbidden, "Access denied: bot belongs to another user")
		return
	}

	if err := h.dcaService.DeleteBot(r.Context(), botID); err != nil {
		logger.Error("Failed to delete DCA bot", "bot_id", botID, "error", err)
		h.writeError(w, http.StatusInternalServerError, err.Error())
		return
	}

	w.WriteHeader(http.StatusNoContent)
}

// GetBotOrders handles GET /api/dca/bots/{id}/orders
func (h *DCABotHandler) GetBotOrders(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		return
	}

	userID := h.getUserID(r)
	if userID == "" {
		h.writeError(w, http.StatusUnauthorized, "Unauthorized")
		return
	}

	// Extract bot ID from path: /api/dca/bots/{id}/orders
	path := strings.TrimPrefix(r.URL.Path, "/api/dca/bots/")
	botID := strings.TrimSuffix(path, "/orders")
	if botID == "" {
		h.writeError(w, http.StatusBadRequest, "Bot ID is required")
		return
	}

	// Verify ownership before accessing orders
	bot, err := h.dcaService.GetBot(r.Context(), botID)
	if err != nil {
		h.writeError(w, http.StatusNotFound, "Bot not found")
		return
	}
	if bot.UserID != "" && bot.UserID != userID {
		h.writeError(w, http.StatusForbidden, "Access denied: bot belongs to another user")
		return
	}

	// Parse optional limit query parameter
	limit := 50
	if l := r.URL.Query().Get("limit"); l != "" {
		if parsed, err := strconv.Atoi(l); err == nil && parsed > 0 {
			limit = parsed
		}
	}

	orders, err := h.dcaService.GetBotOrders(r.Context(), botID, limit)
	if err != nil {
		logger.Error("Failed to get bot orders", "bot_id", botID, "error", err)
		h.writeError(w, http.StatusInternalServerError, "Failed to retrieve orders")
		return
	}

	if orders == nil {
		orders = []model.DCAOrder{}
	}

	h.writeJSON(w, http.StatusOK, orders)
}

// RegisterRoutes registers all DCA bot routes to the mux
func (h *DCABotHandler) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/dca/bots", func(w http.ResponseWriter, r *http.Request) {
		// Exact path: /api/dca/bots
		if r.URL.Path == "/api/dca/bots" {
			switch r.Method {
			case http.MethodPost:
				h.CreateBot(w, r)
			case http.MethodGet:
				h.GetBots(w, r)
			default:
				h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
			}
			return
		}
		// Paths with prefix: /api/dca/bots/...
		h.handleBotPath(w, r)
	})
}

// handleBotPath handles sub-paths under /api/dca/bots/
func (h *DCABotHandler) handleBotPath(w http.ResponseWriter, r *http.Request) {
	path := r.URL.Path
	prefix := "/api/dca/bots/"

	if !strings.HasPrefix(path, prefix) {
		h.writeError(w, http.StatusNotFound, "Not found")
		return
	}

	remainder := strings.TrimPrefix(path, prefix)

	// Check for {id}/start
	if strings.HasSuffix(remainder, "/start") {
		if r.Method == http.MethodPost {
			h.StartBot(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
		return
	}

	// Check for {id}/stop
	if strings.HasSuffix(remainder, "/stop") {
		if r.Method == http.MethodPost {
			h.StopBot(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
		return
	}

	// Check for {id}/orders
	if strings.HasSuffix(remainder, "/orders") {
		if r.Method == http.MethodGet {
			h.GetBotOrders(w, r)
		} else {
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
		return
	}

	// Check for {id} (no trailing slash = single bot)
	if !strings.HasSuffix(remainder, "/") {
		switch r.Method {
		case http.MethodGet:
			h.GetBot(w, r)
		case http.MethodDelete:
			h.DeleteBot(w, r)
		default:
			h.writeError(w, http.StatusMethodNotAllowed, "Method not allowed")
		}
		return
	}

	h.writeError(w, http.StatusNotFound, "Not found")
}
