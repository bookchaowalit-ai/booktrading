package http

import (
	"net"
	"net/http"
	"strings"
	"time"

	"trading-bot-system/backend/internal/domain/service"
	"trading-bot-system/backend/internal/logger"
)

// AuditMiddleware wraps an http.Handler and logs requests to the audit table
type AuditMiddleware struct {
	auditService *service.AuditService
	authHandler  *AuthHandler
	skipPaths    map[string]bool
}

// NewAuditMiddleware creates a new audit middleware
func NewAuditMiddleware(auditService *service.AuditService, authHandler *AuthHandler) *AuditMiddleware {
	return &AuditMiddleware{
		auditService: auditService,
		authHandler:  authHandler,
		skipPaths: map[string]bool{
			"/api/health":  true,
			"/api/metrics": true,
		},
	}
}

// responseWriter wraps http.ResponseWriter to capture the status code
type responseWriter struct {
	http.ResponseWriter
	statusCode int
}

func newResponseWriter(w http.ResponseWriter) *responseWriter {
	return &responseWriter{w, http.StatusOK}
}

func (rw *responseWriter) WriteHeader(code int) {
	rw.statusCode = code
	rw.ResponseWriter.WriteHeader(code)
}

// Middleware returns the http.Handler that wraps the next handler
func (m *AuditMiddleware) Middleware(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		// Skip logging for health and metrics endpoints
		if m.skipPaths[r.URL.Path] {
			next.ServeHTTP(w, r)
			return
		}

		start := time.Now()

		// Capture the response
		rw := newResponseWriter(w)

		// Call the next handler
		next.ServeHTTP(rw, r)

		// Extract user ID from the Authorization token
		var userID string
		token := extractBearerToken(r)
		if token != "" && m.authHandler != nil {
			if uid, ok := m.authHandler.ValidateToken(token); ok {
				userID = uid
			}
		}

		// Extract IP address (check X-Forwarded-For and X-Real-IP first)
		ip := m.extractIP(r)

		// Extract User-Agent
		userAgent := r.UserAgent()

		// Build action from method and path
		action := r.Method + " " + r.URL.Path

		// Log asynchronously
		m.auditService.Log(
			r.Context(),
			userID,
			action,
			r.URL.Path,
			"",
			map[string]any{
				"method":     r.Method,
				"path":       r.URL.Path,
				"query":      r.URL.RawQuery,
				"duration_ms": time.Since(start).Milliseconds(),
			},
			ip,
			userAgent,
			rw.statusCode,
		)

		logger.Info("Audit log recorded",
			"action", action,
			"user_id", userID,
			"status", rw.statusCode,
			"ip", ip,
			"duration_ms", time.Since(start).Milliseconds(),
		)
	})
}

// extractIP extracts the client IP from the request, checking proxy headers first
func (m *AuditMiddleware) extractIP(r *http.Request) string {
	// Check X-Forwarded-For header
	if xff := r.Header.Get("X-Forwarded-For"); xff != "" {
		// X-Forwarded-For can contain multiple IPs; take the first one
		parts := strings.Split(xff, ",")
		ip := strings.TrimSpace(parts[0])
		if ip != "" {
			return ip
		}
	}

	// Check X-Real-IP header
	if xri := r.Header.Get("X-Real-IP"); xri != "" {
		return xri
	}

	// Fall back to RemoteAddr
	ip, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return ip
}
