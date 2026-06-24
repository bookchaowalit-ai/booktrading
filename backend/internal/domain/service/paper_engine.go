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

	// Database pool for persistence
	db *pgxpool.Pool
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

	// Persist trade to database
	e.persistTrade(order)
}

// applyBuy adds to or creates a position
func (e *PaperEngine) applyBuy(order *model.PaperOrder) {
	totalCost := order.Quantity * order.Price + order.Fee
	e.portfolio.CurrentBalance -= totalCost

	pos := e.getPosition(order.Symbol)
	if pos == nil {
		// New position
		e.portfolio.Positions = append(e.portfolio.Positions, model.PaperPosition{
			Symbol:       order.Symbol,
			Quantity:     order.Quantity,
			AvgEntryPrice: order.Price,
			CurrentPrice: order.Price,
			UnrealizedPnL: 0,
			RealizedPnL:  0,
			UpdatedAt:    time.Now(),
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

	// Calculate realized PnL
	pnl := (order.Price - pos.AvgEntryPrice) * order.Quantity
	pos.RealizedPnL += pnl
	pos.Quantity -= order.Quantity
	pos.UpdatedAt = time.Now()

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

// GetPosition returns a position for a symbol
func (e *PaperEngine) getPosition(symbol string) *model.PaperPosition {
	for i := range e.portfolio.Positions {
		if e.portfolio.Positions[i].Symbol == symbol {
			return &e.portfolio.Positions[i]
		}
	}
	return nil
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
	e.orders = make(map[string]*model.PaperOrder)
	e.tradeHistory = make([]*model.PaperOrder, 0)
	e.peakBalance = e.initialBalance
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

		// Rebuild portfolio state
		if order.Side == model.SideBuy {
			balance -= order.Quantity*order.Price + order.Fee
			pos, ok := positions[order.Symbol]
			if !ok {
				positions[order.Symbol] = &model.PaperPosition{
					Symbol:        order.Symbol,
					Quantity:      order.Quantity,
					AvgEntryPrice: order.Price,
					CurrentPrice:  order.Price,
				}
			} else {
				totalQty := pos.Quantity + order.Quantity
				pos.AvgEntryPrice = (pos.AvgEntryPrice*pos.Quantity + order.Price*order.Quantity) / totalQty
				pos.Quantity = totalQty
			}
		} else if order.Side == model.SideSell {
			balance += order.Quantity*order.Price - order.Fee
			pos, ok := positions[order.Symbol]
			if ok {
				pnl := (order.Price - pos.AvgEntryPrice) * order.Quantity
				pos.RealizedPnL += pnl
				pos.Quantity -= order.Quantity
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
	}

	e.portfolio.CurrentBalance = balance
	e.portfolio.Positions = make([]model.PaperPosition, 0, len(positions))
	for _, pos := range positions {
		e.portfolio.Positions = append(e.portfolio.Positions, *pos)
	}
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
