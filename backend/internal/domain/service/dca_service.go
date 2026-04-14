package service

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// runningBot holds the runtime state of an active DCA bot
type runningBot struct {
	config       *model.DCABot
	ctx          context.Context
	cancel       context.CancelFunc
	ticker       *time.Ticker
	lastBuyPrice float64
	lastBuyTime  time.Time
	buyCount     int
	safetyCount  int
}

// DCABotService manages DCA bot lifecycle and execution
type DCABotService struct {
	pool       *pgxpool.Pool
	mu         sync.RWMutex
	activeBots map[string]*runningBot
	httpClient *http.Client
}

// NewDCABotService creates a new DCA bot service and loads existing running bots
func NewDCABotService(pool *pgxpool.Pool) *DCABotService {
	s := &DCABotService{
		pool:       pool,
		activeBots: make(map[string]*runningBot),
		httpClient: &http.Client{Timeout: 10 * time.Second},
	}

	// Load and restart any bots that were RUNNING
	s.loadActiveBots(context.Background())
	return s
}

// loadActiveBots finds bots with RUNNING status and restarts them
func (s *DCABotService) loadActiveBots(ctx context.Context) {
	query := `SELECT id, user_id, symbol, investment_amount, interval_minutes,
		take_profit_percent, safety_order_multiplier, max_safety_orders,
		price_deviation_percent, status, total_invested, total_sold,
		current_position_qty, avg_entry_price
		FROM dca_bots WHERE status = $1`

	rows, err := s.pool.Query(ctx, query, model.DCABotStatusRunning)
	if err != nil {
		logger.Error("Failed to query active DCA bots", "error", err)
		return
	}
	defer rows.Close()

	for rows.Next() {
		var bot model.DCABot
		err := rows.Scan(
			&bot.ID, &bot.UserID, &bot.Symbol, &bot.InvestmentAmount,
			&bot.IntervalMinutes, &bot.TakeProfitPercent,
			&bot.SafetyOrderMultiplier, &bot.MaxSafetyOrders,
			&bot.PriceDeviationPercent, &bot.Status,
			&bot.TotalInvested, &bot.TotalSold,
			&bot.CurrentPositionQty, &bot.AvgEntryPrice,
		)
		if err != nil {
			logger.Error("Failed to scan DCA bot", "error", err, "bot_id", bot.ID)
			continue
		}
		go s.startBotLoop(&bot)
		logger.Info("Restarted DCA bot", "bot_id", bot.ID, "symbol", bot.Symbol)
	}
}

// CreateBot creates a new DCA bot in the database
func (s *DCABotService) CreateBot(ctx context.Context, req *model.DCABotCreateRequest, userID string) (*model.DCABot, error) {
	if req.Symbol == "" {
		return nil, fmt.Errorf("symbol is required")
	}
	if req.InvestmentAmount <= 0 {
		return nil, fmt.Errorf("investment_amount must be greater than 0")
	}
	if req.IntervalMinutes <= 0 {
		return nil, fmt.Errorf("interval_minutes must be greater than 0")
	}

	bot := &model.DCABot{
		ID:                    uuid.New().String(),
		UserID:                userID,
		Symbol:                req.Symbol,
		InvestmentAmount:      req.InvestmentAmount,
		IntervalMinutes:       req.IntervalMinutes,
		TakeProfitPercent:     req.TakeProfitPercent,
		SafetyOrderMultiplier: req.SafetyOrderMultiplier,
		MaxSafetyOrders:       req.MaxSafetyOrders,
		PriceDeviationPercent: req.PriceDeviationPercent,
		Status:                model.DCABotStatusStopped,
		CreatedAt:             time.Now(),
		UpdatedAt:             time.Now(),
	}

	// Set defaults
	if bot.SafetyOrderMultiplier == 0 {
		bot.SafetyOrderMultiplier = 1.5
	}
	if bot.MaxSafetyOrders == 0 {
		bot.MaxSafetyOrders = 3
	}
	if bot.PriceDeviationPercent == 0 {
		bot.PriceDeviationPercent = 2.0
	}

	query := `INSERT INTO dca_bots (id, user_id, symbol, investment_amount, interval_minutes,
		take_profit_percent, safety_order_multiplier, max_safety_orders,
		price_deviation_percent, status, total_invested, total_sold,
		current_position_qty, avg_entry_price, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)`

	_, err := s.pool.Exec(ctx, query,
		bot.ID, bot.UserID, bot.Symbol, bot.InvestmentAmount,
		bot.IntervalMinutes, bot.TakeProfitPercent,
		bot.SafetyOrderMultiplier, bot.MaxSafetyOrders,
		bot.PriceDeviationPercent, bot.Status,
		bot.TotalInvested, bot.TotalSold,
		bot.CurrentPositionQty, bot.AvgEntryPrice,
		bot.CreatedAt, bot.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to create DCA bot: %w", err)
	}

	logger.Info("Created DCA bot", "bot_id", bot.ID, "symbol", bot.Symbol, "user_id", userID)
	return bot, nil
}

// StartBot starts the DCA loop for a bot
func (s *DCABotService) StartBot(ctx context.Context, botID string) error {
	s.mu.Lock()
	if _, exists := s.activeBots[botID]; exists {
		s.mu.Unlock()
		return fmt.Errorf("bot %s is already running", botID)
	}
	s.mu.Unlock()

	bot, err := s.GetBot(ctx, botID)
	if err != nil {
		return fmt.Errorf("failed to get bot: %w", err)
	}

	if bot.Status == model.DCABotStatusCompleted {
		return fmt.Errorf("bot %s is completed and cannot be restarted", botID)
	}

	now := time.Now()
	query := `UPDATE dca_bots SET status = $1, started_at = $2, updated_at = $3 WHERE id = $4`
	_, err = s.pool.Exec(ctx, query, model.DCABotStatusRunning, now, now, botID)
	if err != nil {
		return fmt.Errorf("failed to update bot status: %w", err)
	}
	bot.Status = model.DCABotStatusRunning
	bot.StartedAt = &now

	go s.startBotLoop(bot)
	logger.Info("Started DCA bot", "bot_id", botID, "symbol", bot.Symbol)
	return nil
}

// startBotLoop runs the DCA strategy loop for a bot
func (s *DCABotService) startBotLoop(bot *model.DCABot) {
	ctx, cancel := context.WithCancel(context.Background())
	ticker := time.NewTicker(time.Duration(bot.IntervalMinutes) * time.Minute)

	s.mu.Lock()
	s.activeBots[bot.ID] = &runningBot{
		config: bot,
		ctx:    ctx,
		cancel: cancel,
		ticker: ticker,
	}
	s.mu.Unlock()

	defer func() {
		ticker.Stop()
		cancel()
		s.mu.Lock()
		delete(s.activeBots, bot.ID)
		s.mu.Unlock()
		logger.Info("DCA bot loop stopped", "bot_id", bot.ID)
	}()

	logger.Info("DCA bot loop started", "bot_id", bot.ID, "symbol", bot.Symbol,
		"interval_min", bot.IntervalMinutes)

	// Run first tick immediately
	s.executeTick(ctx, bot)

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			s.executeTick(ctx, bot)
		}
	}
}

// executeTick performs one DCA cycle: fetch price, decide action, execute
func (s *DCABotService) executeTick(ctx context.Context, bot *model.DCABot) {
	price, err := s.fetchPrice(bot.Symbol)
	if err != nil {
		logger.Error("Failed to fetch price for DCA bot", "bot_id", bot.ID, "symbol", bot.Symbol, "error", err)
		return
	}

	s.mu.RLock()
	rb := s.activeBots[bot.ID]
	s.mu.RUnlock()
	if rb == nil {
		return
	}

	// Check take-profit condition
	if bot.CurrentPositionQty > 0 && bot.TakeProfitPercent > 0 {
		tpReached := s.checkTakeProfit(ctx, bot, price)
		if tpReached {
			return
		}
	}

	// If no position, place base order
	if bot.CurrentPositionQty <= 0 {
		s.executeBaseOrder(ctx, bot, price)
		return
	}

	// If position exists, check for safety order condition
	priceDrop := 0.0
	if rb.lastBuyPrice > 0 {
		priceDrop = ((rb.lastBuyPrice - price) / rb.lastBuyPrice) * 100
	}

	if priceDrop >= bot.PriceDeviationPercent && rb.safetyCount < bot.MaxSafetyOrders {
		s.executeSafetyOrder(ctx, bot, price)
	}
}

// checkTakeProfit checks if take-profit is reached and executes sell
func (s *DCABotService) checkTakeProfit(ctx context.Context, bot *model.DCABot, currentPrice float64) bool {
	if bot.AvgEntryPrice <= 0 || bot.CurrentPositionQty <= 0 {
		return false
	}

	profitPercent := ((currentPrice - bot.AvgEntryPrice) / bot.AvgEntryPrice) * 100
	if profitPercent < bot.TakeProfitPercent {
		return false
	}

	logger.Info("Take-profit reached, selling position",
		"bot_id", bot.ID, "symbol", bot.Symbol,
		"avg_entry", bot.AvgEntryPrice, "current", currentPrice,
		"profit_pct", profitPercent)

	// Execute sell
	total := bot.CurrentPositionQty * currentPrice
	now := time.Now()

	// Record take-profit order
	orderQuery := `INSERT INTO dca_orders (id, bot_id, order_type, side, quantity, price, total, status, executed_at, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)`
	orderID := uuid.New().String()
	_, err := s.pool.Exec(ctx, orderQuery,
		orderID, bot.ID, model.DCAOrderTypeTakeProfit, model.SideSell,
		bot.CurrentPositionQty, currentPrice, total, "FILLED", now, now,
	)
	if err != nil {
		logger.Error("Failed to record take-profit order", "bot_id", bot.ID, "error", err)
		return false
	}

	// Update bot stats
	updateQuery := `UPDATE dca_bots SET
		total_sold = total_sold + $1,
		current_position_qty = 0,
		avg_entry_price = 0,
		updated_at = $2
		WHERE id = $3`
	_, err = s.pool.Exec(ctx, updateQuery, total, now, bot.ID)
	if err != nil {
		logger.Error("Failed to update bot after take-profit", "bot_id", bot.ID, "error", err)
	}

	s.mu.RLock()
	rb := s.activeBots[bot.ID]
	s.mu.RUnlock()
	if rb != nil {
		rb.lastBuyPrice = 0
		rb.buyCount = 0
		rb.safetyCount = 0
	}

	logger.Info("Take-profit order executed",
		"bot_id", bot.ID, "quantity", bot.CurrentPositionQty,
		"price", currentPrice, "total", total)
	return true
}

// executeBaseOrder places a base buy order
func (s *DCABotService) executeBaseOrder(ctx context.Context, bot *model.DCABot, price float64) {
	if price <= 0 {
		logger.Warn("Invalid price for base order", "bot_id", bot.ID, "price", price)
		return
	}

	quantity := bot.InvestmentAmount / price
	total := bot.InvestmentAmount
	now := time.Now()

	logger.Info("Executing DCA base order",
		"bot_id", bot.ID, "symbol", bot.Symbol,
		"quantity", quantity, "price", price, "total", total)

	// Record order
	orderQuery := `INSERT INTO dca_orders (id, bot_id, order_type, side, quantity, price, total, status, order_number, executed_at, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`
	orderID := uuid.New().String()
	_, err := s.pool.Exec(ctx, orderQuery,
		orderID, bot.ID, model.DCAOrderTypeBase, model.SideBuy,
		quantity, price, total, "FILLED", 1, now, now,
	)
	if err != nil {
		logger.Error("Failed to record base order", "bot_id", bot.ID, "error", err)
		return
	}

	// Update bot stats: recalculate average entry price
	newAvgPrice := price
	if bot.TotalInvested > 0 && bot.CurrentPositionQty > 0 {
		totalCost := bot.TotalInvested + total
		totalQty := bot.CurrentPositionQty + quantity
		if totalQty > 0 {
			newAvgPrice = totalCost / totalQty
		}
	}

	updateQuery := `UPDATE dca_bots SET
		total_invested = total_invested + $1,
		current_position_qty = current_position_qty + $2,
		avg_entry_price = $3,
		updated_at = $4
		WHERE id = $5`
	_, err = s.pool.Exec(ctx, updateQuery, total, quantity, newAvgPrice, now, bot.ID)
	if err != nil {
		logger.Error("Failed to update bot after base order", "bot_id", bot.ID, "error", err)
	}

	s.mu.Lock()
	if rb, ok := s.activeBots[bot.ID]; ok {
		rb.lastBuyPrice = price
		rb.lastBuyTime = now
		rb.buyCount++
	}
	s.mu.Unlock()

	logger.Info("DCA base order completed", "bot_id", bot.ID, "qty", quantity, "price", price)
}

// executeSafetyOrder places a safety buy order
func (s *DCABotService) executeSafetyOrder(ctx context.Context, bot *model.DCABot, price float64) {
	s.mu.RLock()
	rb := s.activeBots[bot.ID]
	s.mu.RUnlock()
	if rb == nil {
		return
	}

	safetyOrderNum := rb.safetyCount + 1
	multiplier := math.Pow(bot.SafetyOrderMultiplier, float64(safetyOrderNum))
	investmentAmount := bot.InvestmentAmount * multiplier

	if price <= 0 {
		logger.Warn("Invalid price for safety order", "bot_id", bot.ID, "price", price)
		return
	}

	quantity := investmentAmount / price
	total := investmentAmount
	now := time.Now()

	logger.Info("Executing DCA safety order",
		"bot_id", bot.ID, "symbol", bot.Symbol,
		"order_num", safetyOrderNum, "multiplier", multiplier,
		"quantity", quantity, "price", price, "total", total)

	// Record order
	orderQuery := `INSERT INTO dca_orders (id, bot_id, order_type, side, quantity, price, total, status, order_number, executed_at, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)`
	orderID := uuid.New().String()
	_, err := s.pool.Exec(ctx, orderQuery,
		orderID, bot.ID, model.DCAOrderTypeSafety, model.SideBuy,
		quantity, price, total, "FILLED", safetyOrderNum, now, now,
	)
	if err != nil {
		logger.Error("Failed to record safety order", "bot_id", bot.ID, "error", err)
		return
	}

	// Update bot stats: recalculate average entry price
	totalCost := bot.TotalInvested + total
	totalQty := bot.CurrentPositionQty + quantity
	newAvgPrice := price
	if totalQty > 0 {
		newAvgPrice = totalCost / totalQty
	}

	updateQuery := `UPDATE dca_bots SET
		total_invested = total_invested + $1,
		current_position_qty = current_position_qty + $2,
		avg_entry_price = $3,
		updated_at = $4
		WHERE id = $5`
	_, err = s.pool.Exec(ctx, updateQuery, total, quantity, newAvgPrice, now, bot.ID)
	if err != nil {
		logger.Error("Failed to update bot after safety order", "bot_id", bot.ID, "error", err)
	}

	s.mu.Lock()
	if rb, ok := s.activeBots[bot.ID]; ok {
		rb.lastBuyPrice = price
		rb.lastBuyTime = now
		rb.safetyCount++
	}
	s.mu.Unlock()

	logger.Info("DCA safety order completed", "bot_id", bot.ID, "order_num", safetyOrderNum, "qty", quantity, "price", price)
}

// fetchPrice fetches the current price from Binance public API
func (s *DCABotService) fetchPrice(symbol string) (float64, error) {
	url := fmt.Sprintf("https://api.binance.com/api/v3/ticker/price?symbol=%s", symbol)

	resp, err := s.httpClient.Get(url)
	if err != nil {
		return 0, fmt.Errorf("failed to fetch price from Binance: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return 0, fmt.Errorf("Binance API error: status=%d, body=%s", resp.StatusCode, string(body))
	}

	var result struct {
		Symbol string `json:"symbol"`
		Price  string `json:"price"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
		return 0, fmt.Errorf("failed to decode Binance response: %w", err)
	}

	var price float64
	if _, err := fmt.Sscanf(result.Price, "%f", &price); err != nil {
		return 0, fmt.Errorf("invalid price format: %s", result.Price)
	}

	return price, nil
}

// StopBot stops the DCA loop for a bot
func (s *DCABotService) StopBot(ctx context.Context, botID string) error {
	s.mu.Lock()
	rb, exists := s.activeBots[botID]
	if !exists {
		s.mu.Unlock()
		return fmt.Errorf("bot %s is not running", botID)
	}
	rb.cancel()
	delete(s.activeBots, botID)
	s.mu.Unlock()

	now := time.Now()
	query := `UPDATE dca_bots SET status = $1, stopped_at = $2, updated_at = $3 WHERE id = $4`
	_, err := s.pool.Exec(ctx, query, model.DCABotStatusStopped, now, now, botID)
	if err != nil {
		logger.Error("Failed to update bot status on stop", "bot_id", botID, "error", err)
		return fmt.Errorf("failed to update bot status: %w", err)
	}

	logger.Info("Stopped DCA bot", "bot_id", botID)
	return nil
}

// GetBot retrieves a single DCA bot by ID
func (s *DCABotService) GetBot(ctx context.Context, botID string) (*model.DCABot, error) {
	query := `SELECT id, user_id, symbol, investment_amount, interval_minutes,
		take_profit_percent, safety_order_multiplier, max_safety_orders,
		price_deviation_percent, status, total_invested, total_sold,
		current_position_qty, avg_entry_price, created_at, updated_at,
		started_at, stopped_at
		FROM dca_bots WHERE id = $1`

	bot := &model.DCABot{}
	err := s.pool.QueryRow(ctx, query, botID).Scan(
		&bot.ID, &bot.UserID, &bot.Symbol, &bot.InvestmentAmount,
		&bot.IntervalMinutes, &bot.TakeProfitPercent,
		&bot.SafetyOrderMultiplier, &bot.MaxSafetyOrders,
		&bot.PriceDeviationPercent, &bot.Status,
		&bot.TotalInvested, &bot.TotalSold,
		&bot.CurrentPositionQty, &bot.AvgEntryPrice,
		&bot.CreatedAt, &bot.UpdatedAt,
		&bot.StartedAt, &bot.StoppedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get DCA bot: %w", err)
	}
	return bot, nil
}

// GetUserBots retrieves all DCA bots for a user
func (s *DCABotService) GetUserBots(ctx context.Context, userID string) ([]model.DCABot, error) {
	query := `SELECT id, user_id, symbol, investment_amount, interval_minutes,
		take_profit_percent, safety_order_multiplier, max_safety_orders,
		price_deviation_percent, status, total_invested, total_sold,
		current_position_qty, avg_entry_price, created_at, updated_at,
		started_at, stopped_at
		FROM dca_bots WHERE user_id = $1 ORDER BY created_at DESC`

	rows, err := s.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, fmt.Errorf("failed to query user bots: %w", err)
	}
	defer rows.Close()

	var bots []model.DCABot
	for rows.Next() {
		var bot model.DCABot
		err := rows.Scan(
			&bot.ID, &bot.UserID, &bot.Symbol, &bot.InvestmentAmount,
			&bot.IntervalMinutes, &bot.TakeProfitPercent,
			&bot.SafetyOrderMultiplier, &bot.MaxSafetyOrders,
			&bot.PriceDeviationPercent, &bot.Status,
			&bot.TotalInvested, &bot.TotalSold,
			&bot.CurrentPositionQty, &bot.AvgEntryPrice,
			&bot.CreatedAt, &bot.UpdatedAt,
			&bot.StartedAt, &bot.StoppedAt,
		)
		if err != nil {
			logger.Error("Failed to scan DCA bot row", "error", err)
			continue
		}
		bots = append(bots, bot)
	}
	return bots, nil
}

// DeleteBot deletes a DCA bot and its orders
func (s *DCABotService) DeleteBot(ctx context.Context, botID string) error {
	// Stop the bot first if running
	s.StopBot(ctx, botID)

	// Delete orders first (foreign key constraint)
	_, err := s.pool.Exec(ctx, "DELETE FROM dca_orders WHERE bot_id = $1", botID)
	if err != nil {
		return fmt.Errorf("failed to delete bot orders: %w", err)
	}

	_, err = s.pool.Exec(ctx, "DELETE FROM dca_bots WHERE id = $1", botID)
	if err != nil {
		return fmt.Errorf("failed to delete bot: %w", err)
	}

	logger.Info("Deleted DCA bot", "bot_id", botID)
	return nil
}

// GetBotOrders retrieves orders for a specific bot
func (s *DCABotService) GetBotOrders(ctx context.Context, botID string, limit int) ([]model.DCAOrder, error) {
	if limit <= 0 {
		limit = 50
	}

	query := `SELECT id, bot_id, order_type, side, quantity, price, total,
		status, order_number, executed_at, created_at
		FROM dca_orders WHERE bot_id = $1
		ORDER BY created_at DESC LIMIT $2`

	rows, err := s.pool.Query(ctx, query, botID, limit)
	if err != nil {
		return nil, fmt.Errorf("failed to query bot orders: %w", err)
	}
	defer rows.Close()

	var orders []model.DCAOrder
	for rows.Next() {
		var order model.DCAOrder
		err := rows.Scan(
			&order.ID, &order.BotID, &order.OrderType, &order.Side,
			&order.Quantity, &order.Price, &order.Total,
			&order.Status, &order.OrderNumber, &order.ExecutedAt,
			&order.CreatedAt,
		)
		if err != nil {
			logger.Error("Failed to scan DCA order row", "error", err)
			continue
		}
		orders = append(orders, order)
	}
	return orders, nil
}

// GetAllBots returns all DCA bots (for admin/debug purposes)
func (s *DCABotService) GetAllBots() []model.DCABot {
	s.mu.RLock()
	defer s.mu.RUnlock()

	var bots []model.DCABot
	for _, rb := range s.activeBots {
		if rb.config != nil {
			bots = append(bots, *rb.config)
		}
	}
	return bots
}
