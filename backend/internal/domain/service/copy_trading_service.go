package service

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// CopyTradingService manages copy trading operations
type CopyTradingService struct {
	pool *pgxpool.Pool
}

// NewCopyTradingService creates a new copy trading service
func NewCopyTradingService(pool *pgxpool.Pool) *CopyTradingService {
	return &CopyTradingService{
		pool: pool,
	}
}

// CreateStrategy creates a shareable trading strategy from current bot performance
func (s *CopyTradingService) CreateStrategy(ctx context.Context, ownerID string, req model.CreateStrategyRequest) (*model.StrategyProfile, error) {
	if req.Name == "" {
		return nil, fmt.Errorf("strategy name is required")
	}
	if req.StrategyType == "" {
		return nil, fmt.Errorf("strategy type is required")
	}
	if len(req.Name) > 100 {
		return nil, fmt.Errorf("strategy name must be 100 characters or less")
	}

	// Validate strategy type
	validTypes := map[string]bool{"rsi": true, "ema_cross": true, "macd": true, "dca": true}
	if !validTypes[req.StrategyType] {
		return nil, fmt.Errorf("invalid strategy type: %s (must be one of: rsi, ema_cross, macd, dca)", req.StrategyType)
	}

	profileID := uuid.New().String()
	now := time.Now()

	// Serialize parameters to JSON
	paramsJSON, err := json.Marshal(req.Parameters)
	if err != nil {
		return nil, fmt.Errorf("failed to serialize parameters: %w", err)
	}

	var descPtr *string
	if req.Description != nil {
		descPtr = req.Description
	}

	query := `INSERT INTO strategy_profiles (id, owner_id, name, description, strategy_type, is_public, parameters, performance, total_copiers, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		RETURNING id, owner_id, name, description, strategy_type, is_public, parameters, performance, total_copiers, created_at, updated_at`

	profile := &model.StrategyProfile{}
	var paramsJSONBytes []byte
	var perfJSONBytes []byte
	var descVal *string

	err = s.pool.QueryRow(ctx, query,
		profileID, ownerID, req.Name, descPtr, req.StrategyType, req.IsPublic,
		paramsJSON, nil, 0, now, now,
	).Scan(
		&profile.ID, &profile.OwnerID, &profile.Name, &descVal,
		&profile.StrategyType, &profile.IsPublic, &paramsJSONBytes, &perfJSONBytes,
		&profile.TotalCopiers, &profile.CreatedAt, &profile.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create strategy profile: %w", err)
	}

	if descVal != nil {
		profile.Description = descVal
	}

	// Parse parameters JSON
	if len(paramsJSONBytes) > 0 {
		if err := json.Unmarshal(paramsJSONBytes, &profile.Parameters); err != nil {
			logger.Error("Failed to unmarshal strategy parameters", "strategy_id", profile.ID, "error", err)
			profile.Parameters = make(map[string]any)
		}
	} else {
		profile.Parameters = make(map[string]any)
	}

	// Parse performance JSON
	if len(perfJSONBytes) > 0 {
		if err := json.Unmarshal(perfJSONBytes, &profile.Performance); err != nil {
			logger.Error("Failed to unmarshal strategy performance", "strategy_id", profile.ID, "error", err)
		}
	}

	logger.Info("Created strategy profile", "strategy_id", profile.ID, "owner_id", ownerID, "name", req.Name)
	return profile, nil
}

// GetPublicLeaderboard returns top public strategies sorted by sharpe ratio or total copiers
func (s *CopyTradingService) GetPublicLeaderboard(ctx context.Context, limit, offset int) ([]model.LeaderboardEntry, error) {
	if limit <= 0 || limit > 100 {
		limit = 50
	}
	if offset < 0 {
		offset = 0
	}

	query := `SELECT id, name, description, strategy_type, total_copiers, performance
		FROM strategy_profiles
		WHERE is_public = true
		ORDER BY total_copiers DESC, created_at DESC
		LIMIT $1 OFFSET $2`

	rows, err := s.pool.Query(ctx, query, limit, offset)
	if err != nil {
		return nil, fmt.Errorf("failed to query leaderboard: %w", err)
	}
	defer rows.Close()

	var entries []model.LeaderboardEntry
	for rows.Next() {
		var entry model.LeaderboardEntry
		var perfJSON []byte
		var descVal *string

		err := rows.Scan(&entry.StrategyID, &entry.Name, &descVal, &entry.StrategyType, &entry.TotalCopiers, &perfJSON)
		if err != nil {
			logger.Error("Failed to scan leaderboard row", "error", err)
			continue
		}

		if descVal != nil {
			entry.Description = descVal
		}

		// Parse performance metrics
		if len(perfJSON) > 0 {
			var perf map[string]any
			if err := json.Unmarshal(perfJSON, &perf); err == nil {
				entry.WinRate = toFloat64(perf["win_rate"])
				entry.TotalReturn = toFloat64(perf["total_return_percent"])
				entry.ProfitFactor = toFloat64(perf["profit_factor"])
				entry.MaxDrawdown = toFloat64(perf["max_drawdown_percent"])
				entry.SharpeRatio = toFloat64(perf["sharpe_ratio"])
			}
		}

		entries = append(entries, entry)
	}

	if entries == nil {
		entries = []model.LeaderboardEntry{}
	}

	return entries, nil
}

// GetMyStrategies returns all strategies owned by a user
func (s *CopyTradingService) GetMyStrategies(ctx context.Context, userID string) ([]model.StrategyProfile, error) {
	query := `SELECT id, owner_id, name, description, strategy_type, is_public, parameters, performance, total_copiers, created_at, updated_at
		FROM strategy_profiles
		WHERE owner_id = $1
		ORDER BY created_at DESC`

	rows, err := s.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query user strategies: %w", err)
	}
	defer rows.Close()

	var profiles []model.StrategyProfile
	for rows.Next() {
		profile, err := scanStrategyProfile(rows)
		if err != nil {
			logger.Error("Failed to scan strategy profile", "error", err)
			continue
		}
		profiles = append(profiles, *profile)
	}

	if profiles == nil {
		profiles = []model.StrategyProfile{}
	}

	return profiles, nil
}

// StartCopying creates a new copy relationship
func (s *CopyTradingService) StartCopying(ctx context.Context, copierID string, req model.CopyStrategyRequest) (*model.CopyRelationship, error) {
	if req.StrategyID == "" {
		return nil, fmt.Errorf("strategy_id is required")
	}
	if req.AllocationPct < 0 || req.AllocationPct > 100 {
		return nil, fmt.Errorf("allocation_percent must be between 0 and 100")
	}

	// Verify strategy exists and is public
	var strategyIsPublic bool
	var strategyOwnerID string
	err := s.pool.QueryRow(ctx,
		"SELECT is_public, owner_id FROM strategy_profiles WHERE id = $1",
		req.StrategyID,
	).Scan(&strategyIsPublic, &strategyOwnerID)
	if err != nil {
		return nil, fmt.Errorf("strategy not found: %w", err)
	}
	if !strategyIsPublic {
		return nil, fmt.Errorf("strategy is not public and cannot be copied")
	}
	if strategyOwnerID == copierID {
		return nil, fmt.Errorf("cannot copy your own strategy")
	}

	// Check if already copying this strategy
	var existingCount int
	err = s.pool.QueryRow(ctx,
		"SELECT COUNT(*) FROM copy_relationships WHERE copier_id = $1 AND strategy_id = $2 AND is_active = true",
		copierID, req.StrategyID,
	).Scan(&existingCount)
	if err != nil {
		return nil, fmt.Errorf("failed to check existing copy relationship: %w", err)
	}
	if existingCount > 0 {
		return nil, fmt.Errorf("already copying this strategy")
	}

	relID := uuid.New().String()
	now := time.Now()
	allocPct := req.AllocationPct
	if allocPct == 0 {
		allocPct = 100.0
	}

	query := `INSERT INTO copy_relationships (id, copier_id, strategy_id, allocation_percent, is_active, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id, copier_id, strategy_id, allocation_percent, is_active, created_at, updated_at`

	rel := &model.CopyRelationship{}
	err = s.pool.QueryRow(ctx, query,
		relID, copierID, req.StrategyID, allocPct, true, now, now,
	).Scan(
		&rel.ID, &rel.CopierID, &rel.StrategyID, &rel.AllocationPct,
		&rel.IsActive, &rel.CreatedAt, &rel.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create copy relationship: %w", err)
	}

	// Increment total_copiers on the strategy
	_, err = s.pool.Exec(ctx,
		"UPDATE strategy_profiles SET total_copiers = total_copiers + 1, updated_at = $1 WHERE id = $2",
		now, req.StrategyID,
	)
	if err != nil {
		logger.Error("Failed to increment strategy copiers count", "strategy_id", req.StrategyID, "error", err)
	}

	logger.Info("Started copying strategy", "copier_id", copierID, "strategy_id", req.StrategyID, "allocation_pct", allocPct)
	return rel, nil
}

// StopCopying deactivates a copy relationship
func (s *CopyTradingService) StopCopying(ctx context.Context, copierID, relationshipID string) error {
	// Verify ownership
	var relStrategyID string
	var relIsActive bool
	err := s.pool.QueryRow(ctx,
		"SELECT strategy_id, is_active FROM copy_relationships WHERE id = $1 AND copier_id = $2",
		relationshipID, copierID,
	).Scan(&relStrategyID, &relIsActive)
	if err != nil {
		return fmt.Errorf("copy relationship not found or access denied")
	}
	if !relIsActive {
		return fmt.Errorf("copy relationship is already inactive")
	}

	now := time.Now()
	_, err = s.pool.Exec(ctx,
		"UPDATE copy_relationships SET is_active = false, updated_at = $1 WHERE id = $2",
		now, relationshipID,
	)
	if err != nil {
		return fmt.Errorf("failed to stop copying: %w", err)
	}

	// Decrement total_copiers on the strategy
	_, err = s.pool.Exec(ctx,
		"UPDATE strategy_profiles SET total_copiers = GREATEST(total_copiers - 1, 0), updated_at = $1 WHERE id = $2",
		now, relStrategyID,
	)
	if err != nil {
		logger.Error("Failed to decrement strategy copiers count", "strategy_id", relStrategyID, "error", err)
	}

	logger.Info("Stopped copying strategy", "copier_id", copierID, "relationship_id", relationshipID)
	return nil
}

// GetMyCopiedStrategies returns all strategies a user is currently copying
func (s *CopyTradingService) GetMyCopiedStrategies(ctx context.Context, copierID string) ([]model.CopyRelationship, error) {
	query := `SELECT cr.id, cr.copier_id, cr.strategy_id, cr.allocation_percent, cr.is_active, cr.created_at, cr.updated_at,
		sp.name, sp.strategy_type, sp.performance
		FROM copy_relationships cr
		JOIN strategy_profiles sp ON cr.strategy_id = sp.id
		WHERE cr.copier_id = $1
		ORDER BY cr.created_at DESC`

	rows, err := s.pool.Query(ctx, query, copierID)
	if err != nil {
		return nil, fmt.Errorf("failed to query copied strategies: %w", err)
	}
	defer rows.Close()

	var relationships []model.CopyRelationship
	for rows.Next() {
		rel, err := scanCopyRelationshipWithStrategy(rows)
		if err != nil {
			logger.Error("Failed to scan copy relationship", "error", err)
			continue
		}
		relationships = append(relationships, *rel)
	}

	if relationships == nil {
		relationships = []model.CopyRelationship{}
	}

	return relationships, nil
}

// GetCopyTradeHistory returns trades for a specific copy relationship
func (s *CopyTradingService) GetCopyTradeHistory(ctx context.Context, relationshipID string, limit int) ([]model.CopyTrade, error) {
	if limit <= 0 {
		limit = 50
	}
	if limit > 200 {
		limit = 200
	}

	// Verify the relationship exists
	var relExists bool
	err := s.pool.QueryRow(ctx,
		"SELECT EXISTS(SELECT 1 FROM copy_relationships WHERE id = $1)",
		relationshipID,
	).Scan(&relExists)
	if err != nil || !relExists {
		return nil, fmt.Errorf("copy relationship not found")
	}

	query := `SELECT id, copy_relationship_id, original_trade_id, symbol, side, quantity, entry_price,
		exit_price, pnl, status, opened_at, closed_at
		FROM copy_trades
		WHERE copy_relationship_id = $1
		ORDER BY opened_at DESC
		LIMIT $2`

	rows, err := s.pool.Query(ctx, query, relationshipID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query copy trades: %w", err)
	}
	defer rows.Close()

	var trades []model.CopyTrade
	for rows.Next() {
		trade, err := scanCopyTrade(rows)
		if err != nil {
			logger.Error("Failed to scan copy trade", "error", err)
			continue
		}
		trades = append(trades, *trade)
	}

	if trades == nil {
		trades = []model.CopyTrade{}
	}

	return trades, nil
}

// PublishTrade is called when the original bot places a trade.
// It propagates the trade to all active copiers, scaled by their allocation percentage.
func (s *CopyTradingService) PublishTrade(ctx context.Context, strategyID, symbol, side string, quantity, price float64, originalTradeID *string) error {
	if quantity <= 0 || price <= 0 {
		return fmt.Errorf("quantity and price must be positive")
	}
	if side != "BUY" && side != "SELL" {
		return fmt.Errorf("side must be BUY or SELL")
	}

	// Find all active copy relationships for this strategy
	query := `SELECT id, copier_id, allocation_percent
		FROM copy_relationships
		WHERE strategy_id = $1 AND is_active = true`

	rows, err := s.pool.Query(ctx, query, strategyID)
	if err != nil {
		return fmt.Errorf("failed to query copy relationships: %w", err)
	}
	defer rows.Close()

	type copyTarget struct {
		relID         string
		copierID      string
		allocationPct float64
	}

	var targets []copyTarget
	for rows.Next() {
		var t copyTarget
		if err := rows.Scan(&t.relID, &t.copierID, &t.allocationPct); err != nil {
			logger.Error("Failed to scan copy relationship for trade publishing", "error", err)
			continue
		}
		targets = append(targets, t)
	}

	if len(targets) == 0 {
		logger.Debug("No active copiers for strategy", "strategy_id", strategyID)
		return nil
	}

	// Insert copy_trade records for each copier
	now := time.Now()
	insertQuery := `INSERT INTO copy_trades (id, copy_relationship_id, original_trade_id, symbol, side, quantity, entry_price, status, opened_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)`

	copiedCount := 0
	for _, target := range targets {
		// Scale quantity by allocation percentage
		scaledQty := quantity * (target.allocationPct / 100.0)
		// Round to 8 decimal places
		scaledQty = math.Round(scaledQty*1e8) / 1e8

		if scaledQty <= 0 {
			logger.Debug("Skipping copy trade: scaled quantity is zero",
				"copier_id", target.copierID, "allocation_pct", target.allocationPct)
			continue
		}

		tradeID := uuid.New().String()
		var origTradeIDPtr *string
		if originalTradeID != nil {
			origTradeIDPtr = originalTradeID
		}

		_, err := s.pool.Exec(ctx, insertQuery,
			tradeID, target.relID, origTradeIDPtr, symbol, side,
			scaledQty, price, "OPEN", now,
		)
		if err != nil {
			logger.Error("Failed to insert copy trade",
				"copier_id", target.copierID, "strategy_id", strategyID, "error", err)
			continue
		}

		copiedCount++
		logger.Info("Published copy trade",
			"trade_id", tradeID, "copier_id", target.copierID,
			"symbol", symbol, "side", side, "quantity", scaledQty, "price", price)
	}

	logger.Info("Published trades to copiers",
		"strategy_id", strategyID, "total_copiers", len(targets), "successful_copies", copiedCount)

	return nil
}

// CloseTrade closes an open copy trade with exit price and PnL
func (s *CopyTradingService) CloseTrade(ctx context.Context, relationshipID, symbol string, exitPrice, pnl float64) error {
	now := time.Now()

	query := `UPDATE copy_trades
		SET exit_price = $1, pnl = $2, status = 'CLOSED', closed_at = $3
		WHERE copy_relationship_id = $4 AND symbol = $5 AND status = 'OPEN'`

	result, err := s.pool.Exec(ctx, query, exitPrice, pnl, now, relationshipID, symbol)
	if err != nil {
		return fmt.Errorf("failed to close copy trade: %w", err)
	}

	rowsAffected := result.RowsAffected()
	if rowsAffected == 0 {
		return fmt.Errorf("no open trade found for symbol %s in relationship %s", symbol, relationshipID)
	}

	logger.Info("Closed copy trade",
		"relationship_id", relationshipID, "symbol", symbol,
		"exit_price", exitPrice, "pnl", pnl, "trades_closed", rowsAffected)

	return nil
}

// ── Helper functions ──

type scannable interface {
	Scan(dest ...any) error
}

func scanStrategyProfile(row scannable) (*model.StrategyProfile, error) {
	profile := &model.StrategyProfile{}
	var descVal *string
	var paramsJSON []byte
	var perfJSON []byte

	err := row.Scan(
		&profile.ID, &profile.OwnerID, &profile.Name, &descVal,
		&profile.StrategyType, &profile.IsPublic, &paramsJSON, &perfJSON,
		&profile.TotalCopiers, &profile.CreatedAt, &profile.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}

	if descVal != nil {
		profile.Description = descVal
	}

	if len(paramsJSON) > 0 {
		if err := json.Unmarshal(paramsJSON, &profile.Parameters); err != nil {
			logger.Error("Failed to unmarshal strategy parameters", "strategy_id", profile.ID, "error", err)
			profile.Parameters = make(map[string]any)
		}
	} else {
		profile.Parameters = make(map[string]any)
	}

	if len(perfJSON) > 0 {
		if err := json.Unmarshal(perfJSON, &profile.Performance); err != nil {
			logger.Error("Failed to unmarshal strategy performance", "strategy_id", profile.ID, "error", err)
		}
	}

	return profile, nil
}

func scanCopyRelationshipWithStrategy(row scannable) (*model.CopyRelationship, error) {
	rel := &model.CopyRelationship{}
	var perfJSON []byte

	err := row.Scan(
		&rel.ID, &rel.CopierID, &rel.StrategyID, &rel.AllocationPct,
		&rel.IsActive, &rel.CreatedAt, &rel.UpdatedAt,
		&rel.StrategyName, &rel.StrategyType, &perfJSON,
	)
	if err != nil {
		return nil, err
	}

	if len(perfJSON) > 0 {
		if err := json.Unmarshal(perfJSON, &rel.StrategyPerf); err != nil {
			logger.Error("Failed to unmarshal strategy performance for relationship", "relationship_id", rel.ID, "error", err)
		}
	}

	return rel, nil
}

func scanCopyTrade(row scannable) (*model.CopyTrade, error) {
	trade := &model.CopyTrade{}
	var origTradeID *string
	var exitPrice *float64
	var pnl *float64
	var closedAt *time.Time

	err := row.Scan(
		&trade.ID, &trade.CopyRelationshipID, &origTradeID,
		&trade.Symbol, &trade.Side, &trade.Quantity, &trade.EntryPrice,
		&exitPrice, &pnl, &trade.Status, &trade.OpenedAt, &closedAt,
	)
	if err != nil {
		return nil, err
	}

	trade.OriginalTradeID = origTradeID
	trade.ExitPrice = exitPrice
	trade.PnL = pnl
	trade.ClosedAt = closedAt

	return trade, nil
}
