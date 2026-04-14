package service

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"sort"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

const defaultFeeRate = 0.001 // 0.1%

// RebalancingService handles portfolio rebalancing operations
type RebalancingService struct {
	pool *pgxpool.Pool
}

// NewRebalancingService creates a new rebalancing service
func NewRebalancingService(pool *pgxpool.Pool) *RebalancingService {
	return &RebalancingService{pool: pool}
}

// SetTargets upserts rebalance targets for a user. Targets must sum to 100%.
func (s *RebalancingService) SetTargets(ctx context.Context, userID string, targets []model.RebalanceTarget) error {
	// Validate targets sum to 100%
	var total float64
	for _, t := range targets {
		if t.TargetPercent < 0 || t.TargetPercent > 100 {
			return fmt.Errorf("target percent for %s must be between 0 and 100", t.Symbol)
		}
		total += t.TargetPercent
	}
	if math.Abs(total-100.0) > 0.01 {
		return fmt.Errorf("target percentages must sum to 100, got %.2f", total)
	}

	tx, err := s.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}
	defer tx.Rollback(ctx)

	// Deactivate all existing targets for this user
	_, err = tx.Exec(ctx, `UPDATE rebalance_targets SET is_active = FALSE, updated_at = NOW() WHERE user_id = $1`, userID)
	if err != nil {
		return fmt.Errorf("failed to deactivate existing targets: %w", err)
	}

	// Insert or update new targets
	for _, t := range targets {
		_, err = tx.Exec(ctx, `
			INSERT INTO rebalance_targets (id, user_id, symbol, target_percent, is_active, created_at, updated_at)
			VALUES ($1, $2, $3, $4, TRUE, NOW(), NOW())
			ON CONFLICT (user_id, symbol) DO UPDATE SET
				target_percent = EXCLUDED.target_percent,
				is_active = TRUE,
				updated_at = NOW()
		`, uuid.New().String(), userID, t.Symbol, t.TargetPercent)
		if err != nil {
			return fmt.Errorf("failed to upsert target for %s: %w", t.Symbol, err)
		}
	}

	if err := tx.Commit(ctx); err != nil {
		return fmt.Errorf("failed to commit transaction: %w", err)
	}

	logger.Info("Rebalance targets updated", "user_id", userID, "count", len(targets))
	return nil
}

// GetTargets returns all active rebalance targets for a user
func (s *RebalancingService) GetTargets(ctx context.Context, userID string) ([]model.RebalanceTarget, error) {
	rows, err := s.pool.Query(ctx, `
		SELECT id, user_id, symbol, target_percent, is_active, created_at, updated_at
		FROM rebalance_targets
		WHERE user_id = $1 AND is_active = TRUE
		ORDER BY symbol
	`, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query rebalance targets: %w", err)
	}
	defer rows.Close()

	var targets []model.RebalanceTarget
	for rows.Next() {
		var t model.RebalanceTarget
		if err := rows.Scan(&t.ID, &t.UserID, &t.Symbol, &t.TargetPercent, &t.IsActive, &t.CreatedAt, &t.UpdatedAt); err != nil {
			return nil, fmt.Errorf("failed to scan rebalance target: %w", err)
		}
		targets = append(targets, t)
	}

	return targets, nil
}

// AnalyzePortfolio compares current allocation vs targets and returns required trades
func (s *RebalancingService) AnalyzePortfolio(ctx context.Context, userID string) (*model.RebalancePlan, error) {
	// Get current portfolio balances
	balances, totalValue, err := s.getPortfolioBalances(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get portfolio balances: %w", err)
	}

	// Get target allocations
	targets, err := s.GetTargets(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get targets: %w", err)
	}

	if len(targets) == 0 {
		return nil, fmt.Errorf("no rebalance targets configured")
	}

	plan := &model.RebalancePlan{
		TotalValue: totalValue,
	}

	targetMap := make(map[string]float64)
	for _, t := range targets {
		targetMap[t.Symbol] = t.TargetPercent
	}

	// Build current allocation with deviations
	allSymbols := make(map[string]bool)
	for sym := range balances {
		allSymbols[sym] = true
	}
	for sym := range targetMap {
		allSymbols[sym] = true
	}

	thresholdBreached := false
	for sym := range allSymbols {
		currentValue := balances[sym]
		var currentPercent float64
		if totalValue > 0 {
			currentPercent = (currentValue / totalValue) * 100
		}
		targetPercent := targetMap[sym]
		deviation := currentPercent - targetPercent

		action := "HOLD"
		if deviation > 0 {
			action = "SELL"
		} else if deviation < 0 {
			action = "BUY"
		}

		// Check threshold breach (default 5%)
		if math.Abs(deviation) > 5.0 {
			thresholdBreached = true
		}

		alloc := model.PortfolioAllocation{
			Symbol:         sym,
			CurrentValue:   currentValue,
			CurrentPercent: math.Round(currentPercent*100) / 100,
			TargetPercent:  targetPercent,
			Deviation:      math.Round(deviation*100) / 100,
			ActionNeeded:   action,
		}
		plan.CurrentAlloc = append(plan.CurrentAlloc, alloc)
	}

	// Sort allocations by symbol for consistent output
	sort.Slice(plan.CurrentAlloc, func(i, j int) bool {
		return plan.CurrentAlloc[i].Symbol < plan.CurrentAlloc[j].Symbol
	})

	plan.ThresholdBreached = thresholdBreached

	// Calculate required trades
	var totalFees float64
	for _, alloc := range plan.CurrentAlloc {
		targetMapVal := targetMap[alloc.Symbol]
		targetValue := (targetMapVal / 100) * totalValue
		diffValue := alloc.CurrentValue - targetValue

		if math.Abs(diffValue) < 0.01 {
			continue // Negligible difference
		}

		var action string
		var quantity, value float64

		if diffValue > 0 {
			// Over-allocated: SELL
			action = "SELL"
			value = diffValue
			// For SELL, quantity = value / approximate price
			if alloc.CurrentPercent > 0 {
				approxPrice := alloc.CurrentValue / (alloc.CurrentPercent * totalValue / 100)
				if approxPrice > 0 {
					quantity = value / approxPrice
				}
			}
		} else {
			// Under-allocated: BUY
			action = "BUY"
			value = -diffValue
			if targetMapVal > 0 {
				targetValueForPrice := (targetMapVal / 100) * totalValue
				approxPrice := targetValueForPrice / (targetMapVal * totalValue / 100)
				if approxPrice > 0 {
					quantity = value / approxPrice
				}
			}
		}

		quantity = math.Round(quantity*1e8) / 1e8
		value = math.Round(value*1e8) / 1e8

		trade := model.RequiredTrade{
			Symbol:         alloc.Symbol,
			Action:         action,
			Quantity:       quantity,
			Value:          value,
			CurrentPercent: alloc.CurrentPercent,
			TargetPercent:  alloc.TargetPercent,
		}
		plan.RequiredTrades = append(plan.RequiredTrades, trade)

		totalFees += value * defaultFeeRate
	}

	plan.EstimatedFees = math.Round(totalFees*1e8) / 1e8

	logger.Info("Portfolio analyzed",
		"user_id", userID,
		"total_value", totalValue,
		"trades_required", len(plan.RequiredTrades),
		"threshold_breached", thresholdBreached,
	)

	return plan, nil
}

// ExecuteRebalance executes the rebalance plan
func (s *RebalancingService) ExecuteRebalance(ctx context.Context, userID, triggeredBy string) (*model.RebalanceHistory, error) {
	// Get current allocation snapshot before rebalance
	beforeAlloc, err := s.getAllocationSnapshot(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to get allocation snapshot: %w", err)
	}

	// Analyze portfolio to get required trades
	plan, err := s.AnalyzePortfolio(ctx, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to analyze portfolio: %w", err)
	}

	if len(plan.RequiredTrades) == 0 {
		logger.Info("No trades required for rebalance", "user_id", userID)
		return &model.RebalanceHistory{
			UserID:            userID,
			TriggeredBy:       triggeredBy,
			AllocationsBefore: beforeAlloc,
			AllocationsAfter:  beforeAlloc,
			TradesExecuted:    0,
			TotalFees:         0,
			Status:            "COMPLETED",
			ExecutedAt:        nowFunc(),
		}, nil
	}

	// Execute trades (simulated for now — in production, integrate with exchange)
	var totalFees float64
	tradesExecuted := 0

	for _, trade := range plan.RequiredTrades {
		logger.Info("Executing rebalance trade",
			"user_id", userID,
			"symbol", trade.Symbol,
			"action", trade.Action,
			"quantity", trade.Quantity,
			"value", trade.Value,
		)

		// Record trade in trade_history table
		approxPrice := trade.Value / 0.000001
		if trade.Quantity > 0 {
			approxPrice = trade.Value / trade.Quantity
		}
		_, err := s.pool.Exec(ctx, `
			INSERT INTO trade_history (id, symbol, side, quantity, price, total, fee, executed_at)
			VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
		`, uuid.New().String(), trade.Symbol, trade.Action, trade.Quantity,
			approxPrice, trade.Value, trade.Value*defaultFeeRate)
		if err != nil {
			logger.Error("Failed to record rebalance trade",
				"user_id", userID,
				"symbol", trade.Symbol,
				"error", err,
			)
			// Continue with other trades — partial execution
			continue
		}

		totalFees += trade.Value * defaultFeeRate
		tradesExecuted++
	}

	// Get allocation snapshot after rebalance
	afterAlloc, err := s.getAllocationSnapshot(ctx, userID)
	if err != nil {
		logger.Error("Failed to get post-rebalance snapshot", "user_id", userID, "error", err)
		afterAlloc = beforeAlloc // Fallback
	}

	// Record rebalance history
	historyID := uuid.New().String()
	beforeJSON, _ := json.Marshal(beforeAlloc)
	afterJSON, _ := json.Marshal(afterAlloc)

	_, err = s.pool.Exec(ctx, `
		INSERT INTO rebalance_history (id, user_id, triggered_by, allocations_before, allocations_after, trades_executed, total_fees, status, executed_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, 'COMPLETED', NOW())
	`, historyID, userID, triggeredBy, beforeJSON, afterJSON, tradesExecuted, totalFees)
	if err != nil {
		return nil, fmt.Errorf("failed to record rebalance history: %w", err)
	}

	logger.Info("Rebalance executed",
		"user_id", userID,
		"trades_executed", tradesExecuted,
		"total_fees", totalFees,
	)

	return &model.RebalanceHistory{
		ID:                historyID,
		UserID:            userID,
		TriggeredBy:       triggeredBy,
		AllocationsBefore: beforeAlloc,
		AllocationsAfter:  afterAlloc,
		TradesExecuted:    tradesExecuted,
		TotalFees:         math.Round(totalFees*1e8) / 1e8,
		Status:            "COMPLETED",
		ExecutedAt:        nowFunc(),
	}, nil
}

// GetRebalanceHistory returns the rebalance history for a user
func (s *RebalancingService) GetRebalanceHistory(ctx context.Context, userID string, limit int) ([]model.RebalanceHistory, error) {
	if limit <= 0 {
		limit = 20
	}

	rows, err := s.pool.Query(ctx, `
		SELECT id, user_id, triggered_by, allocations_before, allocations_after,
		       trades_executed, total_fees, status, executed_at
		FROM rebalance_history
		WHERE user_id = $1
		ORDER BY executed_at DESC
		LIMIT $2
	`, userID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query rebalance history: %w", err)
	}
	defer rows.Close()

	var history []model.RebalanceHistory
	for rows.Next() {
		var h model.RebalanceHistory
		var beforeJSON, afterJSON []byte
		if err := rows.Scan(&h.ID, &h.UserID, &h.TriggeredBy, &beforeJSON, &afterJSON,
			&h.TradesExecuted, &h.TotalFees, &h.Status, &h.ExecutedAt); err != nil {
			return nil, fmt.Errorf("failed to scan rebalance history: %w", err)
		}

		// Parse JSONB allocations
		h.AllocationsBefore = make(map[string]float64)
		h.AllocationsAfter = make(map[string]float64)
		_ = json.Unmarshal(beforeJSON, &h.AllocationsBefore)
		_ = json.Unmarshal(afterJSON, &h.AllocationsAfter)

		history = append(history, h)
	}

	return history, nil
}

// CheckThresholdBreach checks if any allocation deviates from target by more than thresholdPercent
func (s *RebalancingService) CheckThresholdBreach(ctx context.Context, userID string, thresholdPercent float64) (bool, error) {
	plan, err := s.AnalyzePortfolio(ctx, userID)
	if err != nil {
		return false, fmt.Errorf("failed to analyze portfolio: %w", err)
	}

	for _, alloc := range plan.CurrentAlloc {
		if math.Abs(alloc.Deviation) > thresholdPercent {
			logger.Warn("Threshold breach detected",
				"user_id", userID,
				"symbol", alloc.Symbol,
				"deviation", alloc.Deviation,
				"threshold", thresholdPercent,
			)
			return true, nil
		}
	}

	return false, nil
}

// getPortfolioBalances returns current portfolio balances and total value
func (s *RebalancingService) getPortfolioBalances(ctx context.Context, userID string) (map[string]float64, float64, error) {
	// Query from portfolio table or exchange balances
	// Using a generic approach — assumes balances are stored in a portfolio-like table
	rows, err := s.pool.Query(ctx, `
		SELECT symbol, balance
		FROM portfolio
		WHERE user_id = $1 AND balance > 0
	`, userID)
	if err != nil {
		// Fallback: try to get from trade_history or return empty
		logger.Info("No portfolio table found, using fallback", "error", err)
		return s.getBalancesFromHistory(ctx, userID)
	}
	defer rows.Close()

	balances := make(map[string]float64)
	var totalValue float64
	for rows.Next() {
		var symbol string
		var balance float64
		if err := rows.Scan(&symbol, &balance); err != nil {
			continue
		}
		balances[symbol] = balance
		// For non-stablecoin assets, we'd need current price
		// For simplicity, assume balance represents USD value
		if symbol == "USDT" || symbol == "USD" {
			totalValue += balance
		} else {
			// Approximate: in production, fetch real-time prices
			totalValue += balance
		}
	}

	return balances, totalValue, nil
}

// getBalancesFromHistory is a fallback to estimate balances from recent trades
func (s *RebalancingService) getBalancesFromHistory(ctx context.Context, userID string) (map[string]float64, float64, error) {
	// Simplified — return empty balances
	logger.Warn("Using fallback balance calculation", "user_id", userID)
	return make(map[string]float64), 0, nil
}

// getAllocationSnapshot returns a map of symbol -> current allocation percent
func (s *RebalancingService) getAllocationSnapshot(ctx context.Context, userID string) (map[string]float64, error) {
	balances, totalValue, err := s.getPortfolioBalances(ctx, userID)
	if err != nil {
		return nil, err
	}

	snapshot := make(map[string]float64)
	for sym, balance := range balances {
		if totalValue > 0 {
			snapshot[sym] = math.Round((balance/totalValue)*10000) / 100
		}
	}

	return snapshot, nil
}

// nowFunc is a variable for testability
var nowFunc = func() time.Time {
	return time.Now()
}
