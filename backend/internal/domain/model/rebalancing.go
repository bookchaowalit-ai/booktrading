package model

import "time"

// RebalanceTarget represents a target allocation for a symbol
type RebalanceTarget struct {
	ID            string    `json:"id"`
	UserID        string    `json:"user_id"`
	Symbol        string    `json:"symbol"`
	TargetPercent float64   `json:"target_percent"` // 0-100
	IsActive      bool      `json:"is_active"`
	CreatedAt     time.Time `json:"created_at"`
	UpdatedAt     time.Time `json:"updated_at"`
}

// RebalanceHistory represents a completed rebalance operation
type RebalanceHistory struct {
	ID                string             `json:"id"`
	UserID            string             `json:"user_id"`
	TriggeredBy       string             `json:"triggered_by"` // manual, scheduled, threshold
	AllocationsBefore map[string]float64 `json:"allocations_before"`
	AllocationsAfter  map[string]float64 `json:"allocations_after"`
	TradesExecuted    int                `json:"trades_executed"`
	TotalFees         float64            `json:"total_fees"`
	Status            string             `json:"status"`
	ExecutedAt        time.Time          `json:"executed_at"`
}

// PortfolioAllocation represents current allocation percentages
type PortfolioAllocation struct {
	Symbol         string  `json:"symbol"`
	CurrentValue   float64 `json:"current_value"`
	CurrentPercent float64 `json:"current_percent"`
	TargetPercent  float64 `json:"target_percent"`
	Deviation      float64 `json:"deviation"`       // current - target
	ActionNeeded   string  `json:"action_needed"`   // BUY, SELL, HOLD
}

// RebalancePlan is the output of analysis showing required trades
type RebalancePlan struct {
	TotalValue        float64               `json:"total_value"`
	CurrentAlloc      []PortfolioAllocation `json:"current_allocation"`
	RequiredTrades    []RequiredTrade       `json:"required_trades"`
	EstimatedFees     float64               `json:"estimated_fees"`
	ThresholdBreached bool                  `json:"threshold_breached"`
}

// RequiredTrade represents a single trade needed for rebalancing
type RequiredTrade struct {
	Symbol         string  `json:"symbol"`
	Action         string  `json:"action"` // BUY or SELL
	Quantity       float64 `json:"quantity"`
	Value          float64 `json:"value"`
	CurrentPercent float64 `json:"current_percent"`
	TargetPercent  float64 `json:"target_percent"`
}

// SetRebalanceTargetsRequest for setting allocation targets
type SetRebalanceTargetsRequest struct {
	Targets []struct {
		Symbol        string  `json:"symbol"`
		TargetPercent float64 `json:"target_percent"`
	} `json:"targets"`
}
