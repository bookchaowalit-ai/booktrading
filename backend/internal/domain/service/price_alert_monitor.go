package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/logger"
)

// PriceAlert represents a configured price alert level
type PriceAlert struct {
	ID          string     `json:"id"`
	Symbol      string     `json:"symbol"`
	TargetPrice float64    `json:"target_price"`
	Direction   string     `json:"direction"` // ABOVE or BELOW
	Triggered   bool       `json:"triggered"`
	TriggeredAt *time.Time `json:"triggered_at,omitempty"`
	CreatedAt   time.Time  `json:"created_at"`
}

// PriceAlertMonitor monitors prices and triggers alerts when levels are crossed
type PriceAlertMonitor struct {
	mu     sync.RWMutex
	alerts map[string]*PriceAlert // id -> alert
	db     *pgxpool.Pool
	alert  *AlertService
}

// NewPriceAlertMonitor creates a new price alert monitor
func NewPriceAlertMonitor(db *pgxpool.Pool, alertService *AlertService) *PriceAlertMonitor {
	m := &PriceAlertMonitor{
		alerts: make(map[string]*PriceAlert),
		db:     db,
		alert:  alertService,
	}
	m.loadFromDB()
	return m
}

// CheckPrice checks all alerts for a symbol against the current price
func (m *PriceAlertMonitor) CheckPrice(symbol string, price float64) {
	m.mu.Lock()
	defer m.mu.Unlock()

	for _, a := range m.alerts {
		if a.Symbol != symbol || a.Triggered {
			continue
		}

		triggered := false
		if a.Direction == "ABOVE" && price >= a.TargetPrice {
			triggered = true
		} else if a.Direction == "BELOW" && price <= a.TargetPrice {
			triggered = true
		}

		if triggered {
			now := time.Now()
			a.Triggered = true
			a.TriggeredAt = &now

			logger.Info("Price alert triggered",
				"symbol", symbol,
				"target", a.TargetPrice,
				"direction", a.Direction,
				"current", price,
			)

			// Send notification via AlertService
			if m.alert != nil {
				ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
				direction := "above"
				if a.Direction == "BELOW" {
					direction = "below"
				}
				_ = m.alert.SendPriceAlert(ctx, symbol, price, direction)
				cancel()
			}

			// Persist trigger state
			m.persistTrigger(a.ID, now)
		}
	}
}

// AddAlert creates a new price alert
func (m *PriceAlertMonitor) AddAlert(symbol string, targetPrice float64, direction string) (*PriceAlert, error) {
	if direction != "ABOVE" && direction != "BELOW" {
		return nil, fmt.Errorf("direction must be ABOVE or BELOW")
	}
	if targetPrice <= 0 {
		return nil, fmt.Errorf("target_price must be greater than 0")
	}

	alert := &PriceAlert{
		ID:          uuid.New().String(),
		Symbol:      symbol,
		TargetPrice: targetPrice,
		Direction:   direction,
		Triggered:   false,
		CreatedAt:   time.Now(),
	}

	m.mu.Lock()
	m.alerts[alert.ID] = alert
	m.mu.Unlock()

	// Persist to DB
	if m.db != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_, err := m.db.Exec(ctx,
			`INSERT INTO price_alerts (id, symbol, target_price, direction, triggered) VALUES ($1, $2, $3, $4, $5)`,
			alert.ID, alert.Symbol, alert.TargetPrice, alert.Direction, alert.Triggered,
		)
		if err != nil {
			logger.Error("Failed to persist price alert", "id", alert.ID, "error", err)
		}
	}

	logger.Info("Price alert added", "symbol", symbol, "target", targetPrice, "direction", direction)
	return alert, nil
}

// RemoveAlert deletes a price alert
func (m *PriceAlertMonitor) RemoveAlert(id string) error {
	m.mu.Lock()
	delete(m.alerts, id)
	m.mu.Unlock()

	if m.db != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_, err := m.db.Exec(ctx, `DELETE FROM price_alerts WHERE id = $1`, id)
		if err != nil {
			return fmt.Errorf("failed to delete alert: %w", err)
		}
	}
	return nil
}

// GetAlerts returns all configured alerts
func (m *PriceAlertMonitor) GetAlerts() []*PriceAlert {
	m.mu.RLock()
	defer m.mu.RUnlock()

	result := make([]*PriceAlert, 0, len(m.alerts))
	for _, a := range m.alerts {
		result = append(result, a)
	}
	return result
}

// ResetTriggered resets all triggered alerts so they can fire again
func (m *PriceAlertMonitor) ResetTriggered() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for _, a := range m.alerts {
		if a.Triggered {
			a.Triggered = false
			a.TriggeredAt = nil
		}
	}

	if m.db != nil {
		ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_, _ = m.db.Exec(ctx, `UPDATE price_alerts SET triggered = FALSE, triggered_at = NULL WHERE triggered = TRUE`)
	}
}

// persistTrigger saves the triggered state to DB
func (m *PriceAlertMonitor) persistTrigger(id string, triggeredAt time.Time) {
	if m.db == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	_, _ = m.db.Exec(ctx,
		`UPDATE price_alerts SET triggered = TRUE, triggered_at = $1 WHERE id = $2`,
		triggeredAt, id,
	)
}

// loadFromDB restores alerts from the database
func (m *PriceAlertMonitor) loadFromDB() {
	if m.db == nil {
		return
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	rows, err := m.db.Query(ctx,
		`SELECT id, symbol, target_price, direction, triggered, triggered_at, created_at FROM price_alerts ORDER BY created_at DESC`,
	)
	if err != nil {
		logger.Error("Failed to load price alerts from DB", "error", err)
		return
	}
	defer rows.Close()

	count := 0
	for rows.Next() {
		var a PriceAlert
		if err := rows.Scan(&a.ID, &a.Symbol, &a.TargetPrice, &a.Direction, &a.Triggered, &a.TriggeredAt, &a.CreatedAt); err != nil {
			logger.Error("Failed to scan price alert", "error", err)
			continue
		}
		m.alerts[a.ID] = &a
		count++
	}
	logger.Info("Loaded price alerts from DB", "count", count)
}
