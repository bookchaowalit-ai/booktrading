package model

import "time"

// StrategyProfile represents a shareable trading strategy
type StrategyProfile struct {
	ID           string         `json:"id"`
	OwnerID      string         `json:"owner_id"`
	Name         string         `json:"name"`
	Description  *string        `json:"description,omitempty"`
	StrategyType string         `json:"strategy_type"` // rsi, ema_cross, macd, dca
	IsPublic     bool           `json:"is_public"`
	Parameters   map[string]any `json:"parameters"`
	Performance  map[string]any `json:"performance,omitempty"` // cached metrics
	TotalCopiers int            `json:"total_copiers"`
	CreatedAt    time.Time      `json:"created_at"`
	UpdatedAt    time.Time      `json:"updated_at"`
}

// CopyRelationship represents a user copying a strategy
type CopyRelationship struct {
	ID            string         `json:"id"`
	CopierID      string         `json:"copier_id"`
	StrategyID    string         `json:"strategy_id"`
	AllocationPct float64        `json:"allocation_percent"`
	IsActive      bool           `json:"is_active"`
	CreatedAt     time.Time      `json:"created_at"`
	UpdatedAt     time.Time      `json:"updated_at"`
	// Joined fields for API responses
	StrategyName   *string        `json:"strategy_name,omitempty"`
	StrategyType   *string        `json:"strategy_type,omitempty"`
	StrategyPerf   map[string]any `json:"strategy_performance,omitempty"`
}

// CopyTrade represents an individual copied trade
type CopyTrade struct {
	ID                 string     `json:"id"`
	CopyRelationshipID string     `json:"copy_relationship_id"`
	OriginalTradeID    *string    `json:"original_trade_id,omitempty"`
	Symbol             string     `json:"symbol"`
	Side               string     `json:"side"`
	Quantity           float64    `json:"quantity"`
	EntryPrice         float64    `json:"entry_price"`
	ExitPrice          *float64   `json:"exit_price,omitempty"`
	PnL                *float64   `json:"pnl,omitempty"`
	Status             string     `json:"status"` // OPEN, CLOSED, STOPPED
	OpenedAt           time.Time  `json:"opened_at"`
	ClosedAt           *time.Time `json:"closed_at,omitempty"`
}

// LeaderboardEntry represents a strategy in the public leaderboard
type LeaderboardEntry struct {
	StrategyID   string   `json:"strategy_id"`
	Name         string   `json:"name"`
	StrategyType string   `json:"strategy_type"`
	TotalCopiers int      `json:"total_copiers"`
	WinRate      float64  `json:"win_rate"`
	TotalReturn  float64  `json:"total_return_percent"`
	ProfitFactor float64  `json:"profit_factor"`
	MaxDrawdown  float64  `json:"max_drawdown_percent"`
	SharpeRatio  float64  `json:"sharpe_ratio"`
	Description  *string  `json:"description,omitempty"`
}

// CreateStrategyRequest for creating a new shareable strategy
type CreateStrategyRequest struct {
	Name         string         `json:"name"`
	Description  *string        `json:"description,omitempty"`
	StrategyType string         `json:"strategy_type"`
	IsPublic     bool           `json:"is_public"`
	Parameters   map[string]any `json:"parameters"`
}

// CopyStrategyRequest for starting to copy a strategy
type CopyStrategyRequest struct {
	StrategyID    string  `json:"strategy_id"`
	AllocationPct float64 `json:"allocation_percent"` // 0-100
}
