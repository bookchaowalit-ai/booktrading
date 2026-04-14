package model

import "time"

// DCABotStatus constants
const (
	DCABotStatusStopped   = "STOPPED"
	DCABotStatusRunning   = "RUNNING"
	DCABotStatusCompleted = "COMPLETED"
	DCABotStatusError     = "ERROR"
)

// DCAOrderType constants
const (
	DCAOrderTypeBase       = "BASE"
	DCAOrderTypeSafety     = "SAFETY"
	DCAOrderTypeTakeProfit = "TAKE_PROFIT"
)

// DCABot represents a Dollar Cost Averaging bot configuration
type DCABot struct {
	ID                    string     `json:"id"`
	UserID                string     `json:"user_id"`
	Symbol                string     `json:"symbol"`
	InvestmentAmount      float64    `json:"investment_amount"`
	IntervalMinutes       int        `json:"interval_minutes"`
	TakeProfitPercent     float64    `json:"take_profit_percent"`
	SafetyOrderMultiplier float64    `json:"safety_order_multiplier"`
	MaxSafetyOrders       int        `json:"max_safety_orders"`
	PriceDeviationPercent float64    `json:"price_deviation_percent"`
	Status                string     `json:"status"`
	TotalInvested         float64    `json:"total_invested"`
	TotalSold             float64    `json:"total_sold"`
	CurrentPositionQty    float64    `json:"current_position_qty"`
	AvgEntryPrice         float64    `json:"avg_entry_price"`
	CreatedAt             time.Time  `json:"created_at"`
	UpdatedAt             time.Time  `json:"updated_at"`
	StartedAt             *time.Time `json:"started_at,omitempty"`
	StoppedAt             *time.Time `json:"stopped_at,omitempty"`
}

// DCAOrder represents a DCA order (base, safety, or take-profit)
type DCAOrder struct {
	ID           string     `json:"id"`
	BotID        string     `json:"bot_id"`
	OrderType    string     `json:"order_type"`
	Side         string     `json:"side"`
	Quantity     float64    `json:"quantity"`
	Price        float64    `json:"price"`
	Total        float64    `json:"total"`
	Status       string     `json:"status"`
	OrderNumber  int        `json:"order_number"`
	ExecutedAt   *time.Time `json:"executed_at,omitempty"`
	CreatedAt    time.Time  `json:"created_at"`
}

// DCABotCreateRequest represents the request to create a new DCA bot
type DCABotCreateRequest struct {
	Symbol                string  `json:"symbol"`
	InvestmentAmount      float64 `json:"investment_amount"`
	IntervalMinutes       int     `json:"interval_minutes"`
	TakeProfitPercent     float64 `json:"take_profit_percent"`
	SafetyOrderMultiplier float64 `json:"safety_order_multiplier"`
	MaxSafetyOrders       int     `json:"max_safety_orders"`
	PriceDeviationPercent float64 `json:"price_deviation_percent"`
}
