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

// JournalEntry represents a trading journal record
type JournalEntry struct {
	ID         string    `json:"id"`
	Date       time.Time `json:"date"`
	Symbol     string    `json:"symbol"`
	Side       string    `json:"side"` // LONG | SHORT
	EntryPrice float64   `json:"entryPrice"`
	ExitPrice  float64   `json:"exitPrice,omitempty"`
	Quantity   float64   `json:"quantity"`
	PnL        float64   `json:"pnl"`
	PnLPercent float64   `json:"pnlPercent"`
	Notes      string    `json:"notes,omitempty"`
	Rating     int       `json:"rating,omitempty"` // 1-5
	Strategy   string    `json:"strategy,omitempty"`
	Emotions   string    `json:"emotions,omitempty"`
	Lessons    string    `json:"lessons,omitempty"`
	CreatedAt  time.Time `json:"createdAt"`
	UpdatedAt  time.Time `json:"updatedAt"`
}

// JournalHandler persists journal entries to PostgreSQL
type JournalHandler struct {
	pool *pgxpool.Pool
}

func NewJournalHandler(pool *pgxpool.Pool) *JournalHandler {
	return &JournalHandler{pool: pool}
}

// GetEntries handles GET /api/journal
func (h *JournalHandler) GetEntries(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	rows, err := h.pool.Query(context.Background(), `
		SELECT id, date, symbol, side, entry_price, exit_price, quantity,
		       pnl, pnl_percent, notes, rating, strategy, emotions, lessons,
		       created_at, updated_at
		FROM journal_entries
		ORDER BY date DESC`)
	if err != nil {
		http.Error(w, "Failed to fetch journal entries", http.StatusInternalServerError)
		return
	}
	defer rows.Close()

	entries := []JournalEntry{}
	for rows.Next() {
		var e JournalEntry
		if err := rows.Scan(&e.ID, &e.Date, &e.Symbol, &e.Side, &e.EntryPrice,
			&e.ExitPrice, &e.Quantity, &e.PnL, &e.PnLPercent, &e.Notes,
			&e.Rating, &e.Strategy, &e.Emotions, &e.Lessons,
			&e.CreatedAt, &e.UpdatedAt); err != nil {
			continue
		}
		entries = append(entries, e)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(entries)
}

// CreateEntry handles POST /api/journal
func (h *JournalHandler) CreateEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	var entry JournalEntry
	if err := json.NewDecoder(r.Body).Decode(&entry); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	entry.ID = uuid.NewString()
	now := time.Now()
	entry.CreatedAt = now
	entry.UpdatedAt = now
	if entry.Date.IsZero() {
		entry.Date = now
	}

	_, err := h.pool.Exec(context.Background(), `
		INSERT INTO journal_entries
		  (id, date, symbol, side, entry_price, exit_price, quantity,
		   pnl, pnl_percent, notes, rating, strategy, emotions, lessons,
		   created_at, updated_at)
		VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)`,
		entry.ID, entry.Date, entry.Symbol, entry.Side, entry.EntryPrice,
		entry.ExitPrice, entry.Quantity, entry.PnL, entry.PnLPercent,
		entry.Notes, entry.Rating, entry.Strategy, entry.Emotions, entry.Lessons,
		entry.CreatedAt, entry.UpdatedAt)
	if err != nil {
		http.Error(w, "Failed to create journal entry", http.StatusInternalServerError)
		return
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusCreated)
	json.NewEncoder(w).Encode(entry)
}

// UpdateEntry handles PUT /api/journal/{id}
func (h *JournalHandler) UpdateEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPut {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/journal/")
	if id == "" {
		http.Error(w, "ID required", http.StatusBadRequest)
		return
	}

	var incoming JournalEntry
	if err := json.NewDecoder(r.Body).Decode(&incoming); err != nil {
		http.Error(w, "Invalid request body", http.StatusBadRequest)
		return
	}

	incoming.UpdatedAt = time.Now()
	ct, err := h.pool.Exec(context.Background(), `
		UPDATE journal_entries SET
		  date=$1, symbol=$2, side=$3, entry_price=$4, exit_price=$5,
		  quantity=$6, pnl=$7, pnl_percent=$8, notes=$9, rating=$10,
		  strategy=$11, emotions=$12, lessons=$13, updated_at=$14
		WHERE id=$15`,
		incoming.Date, incoming.Symbol, incoming.Side, incoming.EntryPrice,
		incoming.ExitPrice, incoming.Quantity, incoming.PnL, incoming.PnLPercent,
		incoming.Notes, incoming.Rating, incoming.Strategy, incoming.Emotions,
		incoming.Lessons, incoming.UpdatedAt, id)

	if err != nil || ct.RowsAffected() == 0 {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}

	incoming.ID = id
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(incoming)
}

// DeleteEntry handles DELETE /api/journal/{id}
func (h *JournalHandler) DeleteEntry(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodDelete {
		http.Error(w, "Method not allowed", http.StatusMethodNotAllowed)
		return
	}

	id := strings.TrimPrefix(r.URL.Path, "/api/journal/")
	if id == "" {
		http.Error(w, "ID required", http.StatusBadRequest)
		return
	}

	ct, err := h.pool.Exec(context.Background(), `DELETE FROM journal_entries WHERE id=$1`, id)
	if err != nil || ct.RowsAffected() == 0 {
		http.Error(w, "Not found", http.StatusNotFound)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}
