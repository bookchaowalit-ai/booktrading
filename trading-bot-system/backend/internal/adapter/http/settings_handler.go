package http

import (
	"encoding/json"
	"net/http"
	"trading-bot-system/backend/internal/adapter/database"
	"trading-bot-system/backend/internal/config"
)

// SettingsHandler handles user settings
type SettingsHandler struct {
	cfg  *config.Config
	repo *database.UserPreferencesRepository
}

// NewSettingsHandler creates a new settings handler
func NewSettingsHandler(cfg *config.Config, repo *database.UserPreferencesRepository) *SettingsHandler {
	return &SettingsHandler{
		cfg:  cfg,
		repo: repo,
	}
}

// NotificationPreferences represents notification settings
type NotificationPreferences struct {
	TradeExecutions bool `json:"trade_executions"`
	PriceAlerts     bool `json:"price_alerts"`
	BotStatus       bool `json:"bot_status"`
	Errors          bool `json:"errors"`
}

// UserPreferences represents all user preferences
type UserPreferences struct {
	Language        string                 `json:"language"`
	Theme           string                 `json:"theme"`
	Notifications   NotificationPreferences `json:"notifications"`
}

// GetPreferences returns user preferences
func (h *SettingsHandler) GetPreferences(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	// Get preferences from database (single user for now)
	prefs, err := h.repo.GetPreferences(r.Context(), "default")
	if err != nil {
		// Return defaults if not found
		defaultPrefs := UserPreferences{
			Language: "en",
			Theme:    "system",
			Notifications: NotificationPreferences{
				TradeExecutions: true,
				PriceAlerts:     false,
				BotStatus:       true,
				Errors:          true,
			},
		}
		w.Header().Set("Content-Type", "application/json")
		json.NewEncoder(w).Encode(defaultPrefs)
		return
	}

	response := UserPreferences{
		Language: prefs.Language,
		Theme:    prefs.Theme,
		Notifications: NotificationPreferences{
			TradeExecutions: prefs.NotificationsTradeExecutions,
			PriceAlerts:     prefs.NotificationsPriceAlerts,
			BotStatus:       prefs.NotificationsBotStatus,
			Errors:          prefs.NotificationsErrors,
		},
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

// UpdatePreferences updates user preferences
func (h *SettingsHandler) UpdatePreferences(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	var prefs UserPreferences
	if err := json.NewDecoder(r.Body).Decode(&prefs); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Invalid request body",
		})
		return
	}

	// Save to database
	dbPrefs := &database.UserPreferences{
		UserID:                      "default",
		Language:                    prefs.Language,
		Theme:                       prefs.Theme,
		NotificationsTradeExecutions: prefs.Notifications.TradeExecutions,
		NotificationsPriceAlerts:    prefs.Notifications.PriceAlerts,
		NotificationsBotStatus:      prefs.Notifications.BotStatus,
		NotificationsErrors:         prefs.Notifications.Errors,
	}

	if err := h.repo.UpdatePreferences(r.Context(), dbPrefs); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Failed to save preferences",
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusOK)
	json.NewEncoder(w).Encode(map[string]string{
		"status": "success",
	})
}

// ExportData exports user trading data
func (h *SettingsHandler) ExportData(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	prefs, err := h.repo.GetPreferences(r.Context(), "default")
	if err != nil {
		prefs = &database.UserPreferences{
			UserID:   "default",
			Language: "en",
			Theme:    "system",
		}
	}

	export := map[string]interface{}{
		"preferences": map[string]interface{}{
			"language": prefs.Language,
			"theme":    prefs.Theme,
			"notifications": map[string]interface{}{
				"trade_executions": prefs.NotificationsTradeExecutions,
				"price_alerts":     prefs.NotificationsPriceAlerts,
				"bot_status":       prefs.NotificationsBotStatus,
				"errors":           prefs.NotificationsErrors,
			},
		},
	}

	w.Header().Set("Content-Type", "application/json")
	w.Header().Set("Content-Disposition", "attachment; filename=\"trading-data-export.json\"")
	json.NewEncoder(w).Encode(map[string]interface{}{
		"status": "success",
		"data":   export,
	})
}

// ResetSettings resets all user settings to defaults
func (h *SettingsHandler) ResetSettings(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusMethodNotAllowed)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Method not allowed",
		})
		return
	}

	if err := h.repo.ResetPreferences(r.Context(), "default"); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]string{
			"error": "Failed to reset settings",
		})
		return
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status":  "success",
		"message": "Settings reset successfully",
	})
}
