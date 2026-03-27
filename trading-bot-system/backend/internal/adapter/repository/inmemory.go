package repository

import (
	"context"
	"fmt"
	"sync"
	"time"

	"trading-bot-system/backend/internal/domain/model"
)

// InMemoryOrderRepository implements OrderRepository with in-memory storage
type InMemoryOrderRepository struct {
	orders map[string]*model.Order
	mu     sync.RWMutex
}

// NewInMemoryOrderRepository creates a new in-memory order repository
func NewInMemoryOrderRepository() *InMemoryOrderRepository {
	return &InMemoryOrderRepository{
		orders: make(map[string]*model.Order),
	}
}

// Create stores a new order
func (r *InMemoryOrderRepository) Create(ctx context.Context, order *model.Order) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	if order.ID == "" {
		return fmt.Errorf("order ID is required")
	}

	r.orders[order.ID] = order
	return nil
}

// GetByID retrieves an order by ID
func (r *InMemoryOrderRepository) GetByID(ctx context.Context, id string) (*model.Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	order, exists := r.orders[id]
	if !exists {
		return nil, fmt.Errorf("order not found: %s", id)
	}

	return order, nil
}

// GetBySymbol retrieves all orders for a symbol
func (r *InMemoryOrderRepository) GetBySymbol(ctx context.Context, symbol model.TradeSymbol) ([]*model.Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var result []*model.Order
	for _, order := range r.orders {
		if order.Symbol == symbol {
			result = append(result, order)
		}
	}

	return result, nil
}

// UpdateStatus updates the status of an order
func (r *InMemoryOrderRepository) UpdateStatus(ctx context.Context, id string, status model.OrderStatus) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	order, exists := r.orders[id]
	if !exists {
		return fmt.Errorf("order not found: %s", id)
	}

	order.Status = status
	order.UpdatedAt = time.Now()
	return nil
}

// GetAll retrieves all orders
func (r *InMemoryOrderRepository) GetAll(ctx context.Context) ([]*model.Order, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*model.Order, 0, len(r.orders))
	for _, order := range r.orders {
		result = append(result, order)
	}

	return result, nil
}

// InMemoryPortfolioRepository implements PortfolioRepository with in-memory storage
type InMemoryPortfolioRepository struct {
	portfolios map[model.TradeSymbol]*model.Portfolio
	mu         sync.RWMutex
}

// NewInMemoryPortfolioRepository creates a new in-memory portfolio repository
func NewInMemoryPortfolioRepository() *InMemoryPortfolioRepository {
	return &InMemoryPortfolioRepository{
		portfolios: make(map[model.TradeSymbol]*model.Portfolio),
	}
}

// Get retrieves a portfolio by symbol
func (r *InMemoryPortfolioRepository) Get(ctx context.Context, symbol model.TradeSymbol) (*model.Portfolio, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	portfolio, exists := r.portfolios[symbol]
	if !exists {
		return nil, fmt.Errorf("portfolio not found for symbol: %s", symbol)
	}

	return portfolio, nil
}

// Update updates a portfolio
func (r *InMemoryPortfolioRepository) Update(ctx context.Context, portfolio *model.Portfolio) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.portfolios[portfolio.Symbol] = portfolio
	return nil
}

// GetAll retrieves all portfolios
func (r *InMemoryPortfolioRepository) GetAll(ctx context.Context) ([]*model.Portfolio, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	result := make([]*model.Portfolio, 0, len(r.portfolios))
	for _, portfolio := range r.portfolios {
		result = append(result, portfolio)
	}

	return result, nil
}

// InMemoryTradeHistoryRepository implements TradeHistoryRepository with in-memory storage
type InMemoryTradeHistoryRepository struct {
	trades []*model.TradeHistory
	mu     sync.RWMutex
}

// NewInMemoryTradeHistoryRepository creates a new in-memory trade history repository
func NewInMemoryTradeHistoryRepository() *InMemoryTradeHistoryRepository {
	return &InMemoryTradeHistoryRepository{
		trades: make([]*model.TradeHistory, 0),
	}
}

// Add adds a new trade to history
func (r *InMemoryTradeHistoryRepository) Add(ctx context.Context, trade *model.TradeHistory) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.trades = append(r.trades, trade)
	return nil
}

// GetAll retrieves all trades with limit
func (r *InMemoryTradeHistoryRepository) GetAll(ctx context.Context, limit int) ([]*model.TradeHistory, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	start := 0
	if len(r.trades) > limit {
		start = len(r.trades) - limit
	}

	result := make([]*model.TradeHistory, 0, limit)
	for i := start; i < len(r.trades); i++ {
		result = append(result, r.trades[i])
	}

	return result, nil
}

// GetBySymbol retrieves trades for a specific symbol with limit
func (r *InMemoryTradeHistoryRepository) GetBySymbol(ctx context.Context, symbol model.TradeSymbol, limit int) ([]*model.TradeHistory, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	var filtered []*model.TradeHistory
	for _, trade := range r.trades {
		if trade.Symbol == symbol {
			filtered = append(filtered, trade)
		}
	}

	start := 0
	if len(filtered) > limit {
		start = len(filtered) - limit
	}

	return filtered[start:], nil
}

// InMemoryBotStatusRepository implements BotStatusRepository with in-memory storage
type InMemoryBotStatusRepository struct {
	status *model.BotStatus
	mu     sync.RWMutex
}

// NewInMemoryBotStatusRepository creates a new in-memory bot status repository
func NewInMemoryBotStatusRepository() *InMemoryBotStatusRepository {
	return &InMemoryBotStatusRepository{
		status: &model.BotStatus{
			IsActive:    false,
			TotalTrades: 0,
			TotalProfit: 0,
		},
	}
}

// Get retrieves the current bot status
func (r *InMemoryBotStatusRepository) Get(ctx context.Context) (*model.BotStatus, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	return r.status, nil
}

// SetActive sets the bot active status
func (r *InMemoryBotStatusRepository) SetActive(ctx context.Context, active bool) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.status.IsActive = active
	now := time.Now()
	if active {
		r.status.StartedAt = &now
	} else {
		r.status.StoppedAt = &now
	}

	return nil
}

// IncrementTrades increments the total trades count
func (r *InMemoryBotStatusRepository) IncrementTrades(ctx context.Context) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.status.TotalTrades++
	return nil
}

// UpdateProfit updates the total profit
func (r *InMemoryBotStatusRepository) UpdateProfit(ctx context.Context, profit float64) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.status.TotalProfit += profit
	return nil
}

// InMemoryMarketDataRepository implements MarketDataRepository with in-memory storage
type InMemoryMarketDataRepository struct {
	latest  map[model.TradeSymbol]*model.MarketData
	history map[model.TradeSymbol][]*model.MarketData
	mu      sync.RWMutex
}

// NewInMemoryMarketDataRepository creates a new in-memory market data repository
func NewInMemoryMarketDataRepository() *InMemoryMarketDataRepository {
	return &InMemoryMarketDataRepository{
		latest:  make(map[model.TradeSymbol]*model.MarketData),
		history: make(map[model.TradeSymbol][]*model.MarketData),
	}
}

// GetLatest retrieves the latest market data for a symbol
func (r *InMemoryMarketDataRepository) GetLatest(ctx context.Context, symbol model.TradeSymbol) (*model.MarketData, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	data, exists := r.latest[symbol]
	if !exists {
		return nil, nil
	}

	return data, nil
}

// Save saves market data
func (r *InMemoryMarketDataRepository) Save(ctx context.Context, data *model.MarketData) error {
	r.mu.Lock()
	defer r.mu.Unlock()

	r.latest[data.Symbol] = data

	// Also save to history
	r.history[data.Symbol] = append(r.history[data.Symbol], data)

	// Keep only last 1000 records per symbol
	if len(r.history[data.Symbol]) > 1000 {
		r.history[data.Symbol] = r.history[data.Symbol][len(r.history[data.Symbol])-1000:]
	}

	return nil
}

// GetPriceHistory retrieves price history for a duration
func (r *InMemoryMarketDataRepository) GetPriceHistory(ctx context.Context, symbol model.TradeSymbol, duration time.Duration) ([]*model.MarketData, error) {
	r.mu.RLock()
	defer r.mu.RUnlock()

	history, exists := r.history[symbol]
	if !exists {
		return []*model.MarketData{}, nil
	}

	cutoff := time.Now().Add(-duration)
	var result []*model.MarketData

	for _, data := range history {
		if data.Timestamp.After(cutoff) {
			result = append(result, data)
		}
	}

	return result, nil
}
