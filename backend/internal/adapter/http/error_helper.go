package http

import (
	"encoding/json"
	"net/http"
	"strings"

	"trading-bot-system/backend/internal/logger"
)

// safeError masks internal error details before sending to clients.
// It logs the real error server-side and returns a generic message to the client.
func safeError(w http.ResponseWriter, msg string, err error, status int) {
	logger.Error(msg, "error", err)
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": msg})
}

// containsSensitiveInfo checks if an error message might leak internal details.
func containsSensitiveInfo(errMsg string) bool {
	sensitive := []string{
		"pq:", "pgx:", "sql:", "postgres:",
		"panic", "stack trace", "goroutine",
		"/home/", "/app/", "/root/",
		"password", "secret", "token",
	}
	lower := strings.ToLower(errMsg)
	for _, s := range sensitive {
		if strings.Contains(lower, s) {
			return true
		}
	}
	return false
}

// respondError sends an error response to the client.
// If the error message contains sensitive internal details, it masks them.
func respondError(w http.ResponseWriter, msg string, err error, status int) {
	if containsSensitiveInfo(err.Error()) {
		safeError(w, msg, err, status)
		return
	}
	// Safe to share the error message
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
}
