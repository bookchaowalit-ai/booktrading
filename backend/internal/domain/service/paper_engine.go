package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// PaperEngine simulates trading without real money
type PaperEngine struct {
	mu sync.RWMutex

	// Portfolio state
	portfolio *model.PaperPortfolio

	// Open orders
	orders map[string]*model.PaperOrder

	// Trade history (filled orders)
	tradeHistory []*model.PaperOrder

	// Initial balance (constant reference)
	initialBalance float64

	// Fee rate (e.g., 0.001 = 0.1%)
	feeRate float64

	// Peak balance for drawdown calculation
	peakBalance float64

	// Last trade time for cooldown
	lastTradeAt time.Time

	// Last snapshot time for throttling
	lastSnapshotAt time.Time

	// Database pool for persistence
	db *pgxpool.Pool

	// Event bus for publishing trade events (optional, set via SetEventBus)
	eventBus *EventBus
}

// SetEventBus wires an event bus so the paper engine publishes events on fills
func (e *PaperEngine) SetEventBus(bus *EventBus) {
	e.mu.Lock()
	defer e.mu.Unlock()
	e.eventBus = bus
}

// NewPaperEngine creates a new paper trading engine
func NewPaperEngine(initialBalance float64, feeRate float64, db *pgxpool.Pool) *PaperEngine {
	pe := &PaperEngine{
		portfolio: &model.PaperPortfolio{
			InitialBalance: initialBalance,
			CurrentBalance: initialBalance,
			TotalValue:     initialBalance,
			Positions:      make([]model.PaperPosition, 0),
			TotalPnL:       0,
			TotalTrades:    0,
			WinTrades:      0,
			LossTrades:     0,
			SymbolPnL:      make(map[string]*model.SymbolPnL),
		},
		orders:         make(map[string]*model.PaperOrder),
		tradeHistory:   make([]*model.PaperOrder, 0),
		initialBalance: initialBalance,
		feeRate:        feeRate,
		peakBalance:    initialBalance,
		db:             db,
	}
	// Load persisted trades from DB
	pe.loadFromDB()
	return pe
}

// PlaceOrder creates a simulated order
// For LIMIT orders: order stays PENDING until price touches the limit level.
// For MARKET orders (limitPrice=0): fills immediately at currentPrice.
func (e *PaperEngine) PlaceOrder(ctx context.Context, symbol string, side model.OrderSide, quantity float64, limitPrice float64, currentPrice float64) (*model.PaperOrder, error) {
	e.mu.Lock()
	defer e.mu.Unlock()

	if quantity <= 0 {
		return nil, fmt.Errorf("quantity must be greater than 0")
	}

	// For buy orders, check sufficient balance (use limitPrice for cost estimate)
	costPrice := limitPrice
	if costPrice <= 0 {
		costPrice = currentPrice
	}
	if side == model.SideBuy {
		totalCost := quantity * costPrice
		fee := totalCost * e.feeRate
		if totalCost+fee > e.portfolio.CurrentBalance {
			return nil, fmt.Errorf("insufficient balance: need %.2f, have %.2f", totalCost+fee, e.portfolio.CurrentBalance)
		}
	}

	// For sell orders, check sufficient position
	if side == model.SideSell {
		pos := e.getPosition(symbol)
		if pos == nil || pos.Quantity < quantity {
			return nil, fmt.Errorf("insufficient position for %s", symbol)
		}
	}

	order := &model.PaperOrder{
		ID:         uuid.New().String(),
		Symbol:     symbol,
		Side:       side,
		Type:       model.OrderTypeLimit,
		Quantity:   quantity,
		LimitPrice: limitPrice,
		Price:      currentPrice, // Reference price at time of placement
		Status:     model.PaperOrderStatusPending,
		CreatedAt:  time.Now(),
	}

	// LIMIT ORDER: stay pending until price touches the level
	// Only auto-fill if limitPrice == 0 (market order) or if price already touches
	if limitPrice <= 0 {
		// Market order: fill immediately
		e.fillOrder(order, currentPrice)
	} else if side == model.SideBuy && limitPrice >= currentPrice {
		// Buy limit price >= market → would have filled
		e.fillOrder(order, currentPrice)
	} else if side == model.SideSell && limitPrice <= currentPrice {
		// Sell limit price <= market → would have filled
		e.fillOrder(order, currentPrice)
	} else {
		// Limit order stays PENDING — will fill when UpdatePrice is called
		logger.Info("Paper order placed (PENDING)",
			"symbol", symbol,
			"side", side,
			"quantity", quantity,
			"limitPrice", limitPrice,
			"currentPrice", currentPrice,
		)
	}

	e.orders[order.ID] = order
	return order, nil
}

// fillOrder simulates order execution
func (e *PaperEngine) fillOrder(order *model.PaperOrder, marketPrice float64) {
	// Fill at market price (or limit price if it would have filled)
	execPrice := marketPrice
	if order.LimitPrice > 0 {
		if order.Side == model.SideBuy && order.LimitPrice >= marketPrice {
			execPrice = order.LimitPrice
		} else if order.Side == model.SideSell && order.LimitPrice <= marketPrice {
			execPrice = order.LimitPrice
		} else if order.LimitPrice > 0 {
			// Limit order wouldn't fill at current price
			order.Status = model.PaperOrderStatusPending
			return
		}
	}

	order.Price = execPrice
	order.Fee = order.Quantity * execPrice * e.feeRate
	order.Status = model.PaperOrderStatusFilled
	now := time.Now()
	order.FilledAt = &now

	// Apply to portfolio
	if order.Side == model.SideBuy {
		e.applyBuy(order)
	} else {
		e.applySell(order)
	}

	e.lastTradeAt = now
	logger.Info("Paper order filled",
		"symbol", order.Symbol,
		"side", order.Side,
		"quantity", order.Quantity,
		"price", execPrice,
		"fee", order.Fee,
	)

	// Publish event to event bus (triggers alerts)
	if e.eventBus != nil {
		pnl := 0.0
		if order.Side == model.SideSell {
			pos := e.getPosition(order.Symbol)
			if pos != nil {
				pnl = (execPrice - pos.AvgEntryPrice) * order.Quantity
			}
		}
		e.eventBus.Publish(context.Background(), Event{
			Type: EventPaperTrade,
			Data: map[string]any{
				"symbol":   order.Symbol,
				"side":     string(order.Side),
				"quantity": order.Quantity,
				"price":    execPrice,
				"fee":      order.Fee,
				"pnl":      pnl,
				"order_id": order.ID,
			},
		})
	}

	// Persist trade to database
	e.persistTrade(order)
}

// applyBuy adds to or creates a position
func (e *PaperEngine) applyBuy(order *model.PaperOrder) {
	totalCost := order.Quantity * order.Price + order.Fee
	e.portfolio.CurrentBalance -= totalCost

	// Update per-symbol PnL volume tracking
	symbolPnL := e.getOrCreateSymbolPnL(order.Symbol)
	symbolPnL.TotalVolume += totalCost
	symbolPnL.UpdatedAt = time.Now()

	pos := e.getPosition(order.Symbol)
	if pos == nil {
		// New position
		now := time.Now()
		e.portfolio.Positions = append(e.portfolio.Positions, model.PaperPosition{
			Symbol:        order.Symbol,
			Quantity:      order.Quantity,
			AvgEntryPrice: order.Price,
			CurrentPrice:  order.Price,
			UnrealizedPnL: 0,
			RealizedPnL:   0,
			OpenedAt:      now,
			UpdatedAt:     now,
		})
	} else {
		// Average up
		totalQty := pos.Quantity + order.Quantity
		pos.AvgEntryPrice = (pos.AvgEntryPrice*pos.Quantity + order.Price*order.Quantity) / totalQty
		pos.Quantity = totalQty
		pos.UpdatedAt = time.Now()
	}
}

// applySell closes or reduces a position
func (e *PaperEngine) applySell(order *model.PaperOrder) {
	revenue := order.Quantity*order.Price - order.Fee
	e.portfolio.CurrentBalance += revenue

	pos := e.getPosition(order.Symbol)
	if pos == nil {
		return // Should have been validated before
	}

	// Calculate hold time for this trade
	holdTimeSeconds := time.Since(pos.OpenedAt).Seconds()

	// Calculate realized PnL
	pnl := (order.Price - pos.AvgEntryPrice) * order.Quantity
	pos.RealizedPnL += pnl
	pos.Quantity -= order.Quantity
	pos.UpdatedAt = time.Now()

	// Update per-symbol PnL tracking
	symbolPnL := e.getOrCreateSymbolPnL(order.Symbol)
	symbolPnL.RealizedPnL += pnl
	symbolPnL.TotalVolume += revenue
	symbolPnL.TotalTrades++
	symbolPnL.TotalHoldTimeSeconds += holdTimeSeconds
	if symbolPnL.TotalTrades > 0 {
		symbolPnL.AvgHoldTimeSeconds = symbolPnL.TotalHoldTimeSeconds / float64(symbolPnL.TotalTrades)
	}
	if pnl > 0 {
		symbolPnL.WinTrades++
	} else {
		symbolPnL.LossTrades++
	}
	symbolPnL.UpdatedAt = time.Now()

	// Update trade stats
	e.portfolio.TotalTrades++
	if pnl > 0 {
		e.portfolio.WinTrades++
	} else {
		e.portfolio.LossTrades++
	}

	// Remove position if fully closed
	if pos.Quantity <= 0.000001 {
		e.removePosition(order.Symbol)
	}

	// Add to trade history
	e.tradeHistory = append(e.tradeHistory, order)
}

// SeedPosition creates an initial position for a symbol without recording a trade.
// Used by grid bots to enable SELL orders before any BUY has filled.
func (e *PaperEngine) SeedPosition(symbol string, quantity float64, price float64) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	if quantity <= 0 || price <= 0 {
		return fmt.Errorf("quantity and price must be > 0")
	}

	// Check if position already exists — if so, skip (don't double-seed)
	pos := e.getPosition(symbol)
	if pos != nil && pos.Quantity > 0 {
		logger.Info("SeedPosition skipped — position already exists",
			"symbol", symbol, "qty", pos.Quantity, "entry", pos.AvgEntryPrice)
		return nil
	}

	totalCost := quantity * price
	if totalCost > e.portfolio.CurrentBalance {
		return fmt.Errorf("insufficient balance for seed: need %.2f, have %.2f", totalCost, e.portfolio.CurrentBalance)
	}

	// Deduct cost from balance (simulates having bought the position)
	e.portfolio.CurrentBalance -= totalCost

	now := time.Now()
	e.portfolio.Positions = append(e.portfolio.Positions, model.PaperPosition{
		Symbol:        symbol,
		Quantity:      quantity,
		AvgEntryPrice: price,
		CurrentPrice:  price,
		UnrealizedPnL: 0,
		RealizedPnL:   0,
		OpenedAt:      now,
		UpdatedAt:     now,
	})

	logger.Info("Position seeded",
		"symbol", symbol, "qty", quantity, "price", price, "cost", totalCost,
		"remaining_balance", e.portfolio.CurrentBalance)

	return nil
}

// UpdatePrice updates the current price for all positions and recalculates PnL.
// Also checks pending limit orders — fills them if price touches the limit level.
func (e *PaperEngine) UpdatePrice(symbol string, price float64) {
	e.mu.Lock()
	defer e.mu.Unlock()

	// Check pending orders for this symbol
	for _, order := range e.orders {
		if order.Symbol != symbol || order.Status != model.PaperOrderStatusPending {
			continue
		}
		// BUY fills when market price drops to or below limit price
		if order.Side == model.SideBuy && price <= order.LimitPrice {
			e.fillOrder(order, order.LimitPrice) // Fill at limit price (realistic)
			logger.Info("Paper PENDING order filled (price dropped to limit)",
				"symbol", symbol, "side", "BUY",
				"limitPrice", order.LimitPrice, "marketPrice", price,
			)
		}
		// SELL fills when market price rises to or above limit price
		if order.Side == model.SideSell && price >= order.LimitPrice {
			e.fillOrder(order, order.LimitPrice) // Fill at limit price (realistic)
			logger.Info("Paper PENDING order filled (price rose to limit)",
				"symbol", symbol, "side", "SELL",
				"limitPrice", order.LimitPrice, "marketPrice", price,
			)
		}
	}

	// Record snapshot (throttled to every 5 minutes) — runs regardless of open positions
	if time.Since(e.lastSnapshotAt) >= 5*time.Minute {
		e.recordSnapshot()
	}

	// Update position price
	pos := e.getPosition(symbol)
	if pos == nil {
		return
	}

	pos.CurrentPrice = price
	pos.UpdatedAt = time.Now()

	// Recalculate portfolio totals
	e.recalculatePortfolio()
}

// recalculatePortfolio updates portfolio totals
func (e *PaperEngine) recalculatePortfolio() {
	positionsValue := 0.0
	for i := range e.portfolio.Positions {
		pos := &e.portfolio.Positions[i]
		pos.UnrealizedPnL = (pos.CurrentPrice - pos.AvgEntryPrice) * pos.Quantity
		positionsValue += pos.Quantity * pos.CurrentPrice

		// Update per-symbol unrealized PnL for open positions
		symbolPnL := e.getOrCreateSymbolPnL(pos.Symbol)
		symbolPnL.UnrealizedPnL = pos.UnrealizedPnL
		symbolPnL.UpdatedAt = time.Now()
	}

	// Ensure TotalPnL is correct for ALL symbols (including those with no open position)
	for _, spnl := range e.portfolio.SymbolPnL {
		spnl.TotalPnL = spnl.RealizedPnL + spnl.UnrealizedPnL
	}

	e.portfolio.TotalValue = e.portfolio.CurrentBalance + positionsValue
	e.portfolio.TotalPnL = e.portfolio.TotalValue - e.initialBalance
	if e.initialBalance > 0 {
		e.portfolio.TotalPnLPercent = (e.portfolio.TotalPnL / e.initialBalance) * 100
	}

	// Track peak and drawdown
	if e.portfolio.TotalValue > e.peakBalance {
		e.peakBalance = e.portfolio.TotalValue
	}
	drawdown := 0.0
	if e.peakBalance > 0 {
		drawdown = (e.peakBalance - e.portfolio.TotalValue) / e.peakBalance * 100
	}
	e.portfolio.MaxDrawdown = drawdown

	e.portfolio.UpdatedAt = time.Now()
}

// GetPortfolio returns the current paper trading portfolio
func (e *PaperEngine) GetPortfolio() *model.PaperPortfolio {
	e.mu.RLock()
	defer e.mu.RUnlock()

	// Return a copy
	snapshot := *e.portfolio
	snapshot.Positions = make([]model.PaperPosition, len(e.portfolio.Positions))
	copy(snapshot.Positions, e.portfolio.Positions)
	return &snapshot
}

// GetOrders returns all paper orders
func (e *PaperEngine) GetOrders() []*model.PaperOrder {
	e.mu.RLock()
	defer e.mu.RUnlock()

	orders := make([]*model.PaperOrder, 0, len(e.orders))
	for _, o := range e.orders {
		orders = append(orders, o)
	}
	return orders
}

// GetOpenOrders returns only pending (unfilled) orders
func (e *PaperEngine) GetOpenOrders() []*model.PaperOrder {
	e.mu.RLock()
	defer e.mu.RUnlock()

	orders := make([]*model.PaperOrder, 0)
	for _, o := range e.orders {
		if o.Status == model.PaperOrderStatusPending {
			orders = append(orders, o)
		}
	}
	return orders
}

// GetTradeHistory returns filled orders
func (e *PaperEngine) GetTradeHistory() []*model.PaperOrder {
	e.mu.RLock()
	defer e.mu.RUnlock()

	snapshot := make([]*model.PaperOrder, len(e.tradeHistory))
	copy(snapshot, e.tradeHistory)
	return snapshot
}

// getPosition returns a position for a symbol
func (e *PaperEngine) getPosition(symbol string) *model.PaperPosition {
	for i := range e.portfolio.Positions {
		if e.portfolio.Positions[i].Symbol == symbol {
			return &e.portfolio.Positions[i]
		}
	}
	return nil
}

// getOrCreateSymbolPnL returns or creates a SymbolPnL entry for a symbol
func (e *PaperEngine) getOrCreateSymbolPnL(symbol string) *model.SymbolPnL {
	if spnl, ok := e.portfolio.SymbolPnL[symbol]; ok {
		return spnl
	}
	spnl := &model.SymbolPnL{
		Symbol:        symbol,
		RealizedPnL:   0,
		UnrealizedPnL: 0,
		TotalPnL:      0,
		TotalTrades:   0,
		WinTrades:     0,
		LossTrades:    0,
		TotalVolume:   0,
		UpdatedAt:     time.Now(),
	}
	e.portfolio.SymbolPnL[symbol] = spnl
	return spnl
}

// removePosition removes a position for a symbol
func (e *PaperEngine) removePosition(symbol string) {
	positions := make([]model.PaperPosition, 0)
	for _, pos := range e.portfolio.Positions {
		if pos.Symbol != symbol {
			positions = append(positions, pos)
		}
	}
	e.portfolio.Positions = positions
}

// CancelOrder cancels a pending order by ID
func (e *PaperEngine) CancelOrder(orderID string) error {
	e.mu.Lock()
	defer e.mu.Unlock()

	order, exists := e.orders[orderID]
	if !exists {
		return fmt.Errorf("order %s not found", orderID)
	}
	if order.Status != model.PaperOrderStatusPending {
		return fmt.Errorf("order %s is %s, cannot cancel", orderID, order.Status)
	}

	order.Status = model.PaperOrderStatusCancelled
	logger.Info("Paper order cancelled",
		"id", orderID,
		"symbol", order.Symbol,
		"side", order.Side,
		"limitPrice", order.LimitPrice,
	)
	return nil
}

// Reset resets the paper trading engine to initial state
func (e *PaperEngine) Reset() {
	e.mu.Lock()
	defer e.mu.Unlock()

	e.portfolio.CurrentBalance = e.initialBalance
	e.portfolio.TotalValue = e.initialBalance
	e.portfolio.Positions = make([]model.PaperPosition, 0)
	e.portfolio.TotalPnL = 0
	e.portfolio.TotalPnLPercent = 0
	e.portfolio.TotalTrades = 0
	e.portfolio.WinTrades = 0
	e.portfolio.LossTrades = 0
	e.portfolio.MaxDrawdown = 0
	e.portfolio.SymbolPnL = make(map[string]*model.SymbolPnL)
	e.orders = make(map[string]*model.PaperOrder)
	e.tradeHistory = make([]*model.PaperOrder, 0)
	e.peakBalance = e.initialBalance
}

// recordSnapshot saves current portfolio value to the database for sparkline charts
func (e *PaperEngine) recordSnapshot() {
	if e.db == nil {
		return
	}
	e.lastSnapshotAt = time.Now()

	positionsValue := 0.0
	for _, pos := range e.portfolio.Positions {
		positionsValue += pos.Quantity * pos.CurrentPrice
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := e.db.Exec(ctx,
		`INSERT INTO portfolio_snapshots (total_value, current_balance, positions_value, total_pnl, total_trades) VALUES ($1, $2, $3, $4, $5)`,
		e.portfolio.TotalValue, e.portfolio.CurrentBalance, positionsValue, e.portfolio.TotalPnL, e.portfolio.TotalTrades,
	)
	if err != nil {
		logger.Error("Failed to record portfolio snapshot", "error", err)
	} else {
		logger.Debug("Portfolio snapshot recorded", "total_value", e.portfolio.TotalValue)
	}
}

// PortfolioSnapshot represents a point-in-time portfolio value
type PortfolioSnapshot struct {
	TotalValue     float64   `json:"total_value"`
	CurrentBalance float64   `json:"current_balance"`
	PositionsValue float64   `json:"positions_value"`
	TotalPnL       float64   `json:"total_pnl"`
	TotalTrades    int       `json:"total_trades"`
	CreatedAt      time.Time `json:"created_at"`
}

// GetSnapshots returns portfolio value history
func (e *PaperEngine) GetSnapshots(limit int) []PortfolioSnapshot {
	if e.db == nil {
		return nil
	}
	if limit <= 0 || limit > 500 {
		limit = 500
	}

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	rows, err := e.db.Query(ctx,
		`SELECT total_value, current_balance, positions_value, total_pnl, total_trades, created_at FROM portfolio_snapshots ORDER BY created_at DESC LIMIT $1`, limit,
	)
	if err != nil {
		logger.Error("Failed to get portfolio snapshots", "error", err)
		return nil
	}
	defer rows.Close()

	snapshots := make([]PortfolioSnapshot, 0)
	for rows.Next() {
		var s PortfolioSnapshot
		if err := rows.Scan(&s.TotalValue, &s.CurrentBalance, &s.PositionsValue, &s.TotalPnL, &s.TotalTrades, &s.CreatedAt); err != nil {
			logger.Error("Failed to scan snapshot", "error", err)
			continue
		}
		snapshots = append(snapshots, s)
	}

	// Reverse to chronological order
	for i, j := 0, len(snapshots)-1; i < j; i, j = i+1, j-1 {
		snapshots[i], snapshots[j] = snapshots[j], snapshots[i]
	}
	return snapshots
}

// persistTrade saves a filled order to the database
func (e *PaperEngine) persistTrade(order *model.PaperOrder) {
	if e.db == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()

	_, err := e.db.Exec(ctx,
		`INSERT INTO paper_trades (id, symbol, side, type, quantity, price, limit_price, fee, status, created_at, filled_at)
		 VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
		 ON CONFLICT (id) DO NOTHING`,
		order.ID, order.Symbol, string(order.Side), string(order.Type),
		order.Quantity, order.Price, order.LimitPrice, order.Fee,
		string(order.Status), order.CreatedAt, order.FilledAt,
	)
	if err != nil {
		logger.Error("Failed to persist paper trade", "id", order.ID, "error", err)
	}
}

// loadFromDB restores trade history and portfolio state from the database
func (e *PaperEngine) loadFromDB() {
	if e.db == nil {
		return
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	rows, err := e.db.Query(ctx,
		`SELECT id, symbol, side, type, quantity, price, limit_price, fee, status, created_at, filled_at
		 FROM paper_trades ORDER BY created_at ASC`)
	if err != nil {
		logger.Error("Failed to load paper trades from DB", "error", err)
		return
	}
	defer rows.Close()

	balance := e.initialBalance
	positions := make(map[string]*model.PaperPosition)
	symbolPnLMap := make(map[string]*model.SymbolPnL)

	for rows.Next() {
		var order model.PaperOrder
		var sideStr, typeStr, statusStr string
		var filledAt *time.Time

		err := rows.Scan(
			&order.ID, &order.Symbol, &sideStr, &typeStr,
			&order.Quantity, &order.Price, &order.LimitPrice, &order.Fee,
			&statusStr, &order.CreatedAt, &filledAt,
		)
		if err != nil {
			logger.Error("Failed to scan paper trade row", "error", err)
			continue
		}
		order.Side = model.OrderSide(sideStr)
		order.Type = model.OrderType(typeStr)
		order.Status = model.PaperOrderStatus(statusStr)
		order.FilledAt = filledAt

		e.tradeHistory = append(e.tradeHistory, &order)
		e.orders[order.ID] = &order

		// Get or create SymbolPnL for this symbol
		spnl, ok := symbolPnLMap[order.Symbol]
		if !ok {
			spnl = &model.SymbolPnL{
				Symbol:               order.Symbol,
				RealizedPnL:          0,
				UnrealizedPnL:        0,
				TotalPnL:             0,
				TotalTrades:          0,
				WinTrades:            0,
				LossTrades:           0,
				TotalVolume:          0,
				TotalHoldTimeSeconds: 0,
				AvgHoldTimeSeconds:   0,
				UpdatedAt:            time.Now(),
			}
			symbolPnLMap[order.Symbol] = spnl
		}

		// Rebuild portfolio state
		if order.Side == model.SideBuy {
			cost := order.Quantity*order.Price + order.Fee
			balance -= cost
			spnl.TotalVolume += cost
			pos, ok := positions[order.Symbol]
			if !ok {
				openedAt := order.CreatedAt
				if order.FilledAt != nil {
					openedAt = *order.FilledAt
				}
				positions[order.Symbol] = &model.PaperPosition{
					Symbol:        order.Symbol,
					Quantity:      order.Quantity,
					AvgEntryPrice: order.Price,
					CurrentPrice:  order.Price,
					OpenedAt:      openedAt,
				}
			} else {
				totalQty := pos.Quantity + order.Quantity
				pos.AvgEntryPrice = (pos.AvgEntryPrice*pos.Quantity + order.Price*order.Quantity) / totalQty
				pos.Quantity = totalQty
			}
		} else if order.Side == model.SideSell {
			revenue := order.Quantity*order.Price - order.Fee
			balance += revenue
			spnl.TotalVolume += revenue
			pos, ok := positions[order.Symbol]
			if ok {
				pnl := (order.Price - pos.AvgEntryPrice) * order.Quantity
				pos.RealizedPnL += pnl
				pos.Quantity -= order.Quantity
				spnl.RealizedPnL += pnl
				spnl.TotalTrades++
				// Calculate hold time for this trade
				sellTime := order.CreatedAt
				if order.FilledAt != nil {
					sellTime = *order.FilledAt
				}
				holdTime := sellTime.Sub(pos.OpenedAt).Seconds()
				if holdTime > 0 {
					spnl.TotalHoldTimeSeconds += holdTime
				}
				if spnl.TotalTrades > 0 {
					spnl.AvgHoldTimeSeconds = spnl.TotalHoldTimeSeconds / float64(spnl.TotalTrades)
				}
				if pnl > 0 {
					spnl.WinTrades++
				} else {
					spnl.LossTrades++
				}
				e.portfolio.TotalTrades++
				if pnl > 0 {
					e.portfolio.WinTrades++
				} else {
					e.portfolio.LossTrades++
				}
				if pos.Quantity <= 0.000001 {
					delete(positions, order.Symbol)
				}
			}
		}
		spnl.UpdatedAt = time.Now()
	}

	e.portfolio.CurrentBalance = balance
	e.portfolio.Positions = make([]model.PaperPosition, 0, len(positions))
	for _, pos := range positions {
		e.portfolio.Positions = append(e.portfolio.Positions, *pos)
	}
	e.portfolio.SymbolPnL = symbolPnLMap
	e.recalculatePortfolio()

	loaded := len(e.tradeHistory)
	if loaded > 0 {
		logger.Info("Loaded paper trades from DB",
			"count", loaded,
			"balance", balance,
			"positions", len(e.portfolio.Positions),
		)
	}
}
