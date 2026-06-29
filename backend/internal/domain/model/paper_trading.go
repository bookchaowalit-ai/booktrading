package model

import (
	"time"
)

// PaperOrderStatus represents the status of a simulated order
type PaperOrderStatus string

const (
	PaperOrderStatusPending  PaperOrderStatus = "PENDING"
	PaperOrderStatusFilled   PaperOrderStatus = "FILLED"
	PaperOrderStatusCancelled PaperOrderStatus = "CANCELLED"
)

// PaperOrder represents a simulated order for paper trading
type PaperOrder struct {
	ID            string           `json:"id"`
	Symbol        string           `json:"symbol"`
	Side          OrderSide        `json:"side"`
	Type          OrderType        `json:"type"`
	Quantity      float64          `json:"quantity"`
	Price         float64          `json:"price"`     // Execution price
	LimitPrice    float64          `json:"limit_price,omitempty"` // Requested price for limit orders
	StopLossPrice float64          `json:"stop_loss_price,omitempty"`
	TakeProfitPrice float64        `json:"take_profit_price,omitempty"`
	Status        PaperOrderStatus `json:"status"`
	Fee           float64          `json:"fee"`       // Simulated fee
	CreatedAt     time.Time        `json:"created_at"`
	FilledAt      *time.Time       `json:"filled_at,omitempty"`
}

// PaperPosition represents a simulated position for paper trading
type PaperPosition struct {
	Symbol        string    `json:"symbol"`
	Quantity      float64   `json:"quantity"`
	AvgEntryPrice float64   `json:"avg_entry_price"`
	CurrentPrice  float64   `json:"current_price"`
	UnrealizedPnL float64   `json:"unrealized_pnl"`
	RealizedPnL   float64   `json:"realized_pnl"`
	OpenedAt      time.Time `json:"opened_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// SymbolPnL tracks per-symbol PnL across the lifetime of the engine
type SymbolPnL struct {
	Symbol               string  `json:"symbol"`
	RealizedPnL          float64 `json:"realized_pnl"`
	UnrealizedPnL        float64 `json:"unrealized_pnl"`
	TotalPnL             float64 `json:"total_pnl"`               // Realized + Unrealized
	TotalTrades          int     `json:"total_trades"`            // Number of round-trip trades
	WinTrades            int     `json:"win_trades"`
	LossTrades           int     `json:"loss_trades"`
	TotalVolume          float64 `json:"total_volume"`            // Total traded volume in quote currency
	TotalHoldTimeSeconds float64 `json:"total_hold_time_seconds"` // Cumulative hold time for avg calculation
	AvgHoldTimeSeconds   float64 `json:"avg_hold_time_seconds"`   // Average hold time per trade
	UpdatedAt            time.Time `json:"updated_at"`
}

// PaperPortfolio represents a simulated portfolio for paper trading
type PaperPortfolio struct {
	InitialBalance float64         `json:"initial_balance"`
	CurrentBalance float64         `json:"current_balance"` // Cash available
	TotalValue     float64         `json:"total_value"`     // Cash + positions value
	Positions      []PaperPosition `json:"positions"`
	TotalPnL       float64         `json:"total_pnl"`
	TotalPnLPercent float64        `json:"total_pnl_percent"`
	TotalTrades    int             `json:"total_trades"`
	WinTrades      int             `json:"win_trades"`
	LossTrades     int             `json:"loss_trades"`
	MaxDrawdown    float64         `json:"max_drawdown"`
	SymbolPnL      map[string]*SymbolPnL `json:"symbol_pnl"` // Per-symbol PnL tracking
	UpdatedAt      time.Time       `json:"updated_at"`
}
