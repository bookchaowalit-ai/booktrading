package http

import (
	"context"
	"encoding/json"
	"net/http"
	"strings"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
)

// Notification types
const (
	NotifTypeOrderFilled = "ORDER_FILLED"
	NotifTypePriceAlert  = "PRICE_ALERT"
	NotifTypeBotStatus   = "BOT_STATUS"
	NotifTypePnLAlert    = "PNL_ALERT"
	NotifTypeError       = "ERROR"
)

// Notification represents a single notification entry
type Notification struct {
	ID        string    `json:"id"`
	Type      string    `json:"type"`
	Title     string    `json:"title"`
	Message   string    `json:"message"`
	Timestamp time.Time `json:"timestamp"`
	Read      bool      `json:"read"`
	Priority  string    `json:"priority"` // LOW | MEDIUM | HIGH
}

// NotificationHandler persists notifications to PostgreSQL
type NotificationHandler struct {
	pool *pgxpool.Pool
}

func NewNotificationHandler(pool *pgxpool.Pool) *NotificationHandler {
	return &NotificationHandler{pool: pool}
}

// AddNotification inserts a new notification into the DB
func (h *NotificationHandler) AddNotification(notif Notification) {
	if notif.ID == "" {
		notif.ID = uuid.NewString()
	}
	if notif.Timestamp.IsZero() {
		notif.Timestamp = time.Now()
	}
	_, _ = h.pool.Exec(context.Background(), `
		INSERT INTO notifications (id, type, title, message, timestamp, read, priority)
		VALUES ($1,$2,$3,$4,$5,$6,$7)
		ON CONFLICT (id) DO NOTHING`,
		notif.ID, notif.Type, notif.Title, notif.Message, notif.Timestamp, notif.Read, notif.Priority)
}

// GetNotifications handles GET /api/notifications
func (h *NotificationHandler) GetNotifications(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	rows, err := h.pool.Query(context.Background(), `
		SELECT id, type, title, message, timestamp, read, priority
		FROM notifications
		ORDER BY timestamp DESC
		LIMIT 100`)
	if err != nil {
		http.Error(w, "Failed to fetch notifications", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	list := []Notification{}
	for rows.Next() {
		var n Notification
		if err := rows.Scan(&n.ID, &n.Type, &n.Title, &n.Message, &n.Timestamp, &n.Read, &n.Priority); err != nil {
			continue
		}
		list = append(list, n)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(list)
}

// MarkRead handles PUT /api/notifications/{id}/read
func (h *NotificationHandler) MarkRead(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	parts := strings.Split(strings.TrimPrefix(r.URL.Path, "/api/notifications/"), "/")
	id := parts[0]

	h.pool.Exec(context.Background(), `UPDATE notifications SET read=TRUE WHERE id=$1`, id)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// MarkAllRead handles PUT /api/notifications/read-all
func (h *NotificationHandler) MarkAllRead(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.pool.Exec(context.Background(), `UPDATE notifications SET read=TRUE`)

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{"status": "ok"})
}

// DeleteNotification handles DELETE /api/notifications/{id}
func (h *NotificationHandler) DeleteNotification(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/notifications/")
	h.pool.Exec(context.Background(), `DELETE FROM notifications WHERE id=$1`, id)
	w.WriteHeader(http.StatusNoContent)
}

// ClearAll handles DELETE /api/notifications
func (h *NotificationHandler) ClearAll(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	h.pool.Exec(context.Background(), `DELETE FROM notifications`)
	w.WriteHeader(http.StatusNoContent)
}
