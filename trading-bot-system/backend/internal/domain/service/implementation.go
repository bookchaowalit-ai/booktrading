package service

import (
	"context"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/google/uuid"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
	"trading-bot-system/backend/internal/port/input"
	"trading-bot-system/backend/internal/port/output"
)

// OrderServiceImpl implements the OrderService interface
type OrderServiceImpl struct {
	orderRepo      repository.OrderRepository
	tradeHistoryRepo repository.TradeHistoryRepository
	orderExecutor  output.OrderExecutor
	broadcaster    output.WebSocketBroadcaster
	mu             sync.Mutex
}

// NewOrderService creates a new order service
func NewOrderService(
	orderRepo repository.OrderRepository,
	tradeHistoryRepo repository.TradeHistoryRepository,
	orderExecutor output.OrderExecutor,
	broadcaster output.WebSocketBroadcaster,
) input.OrderHandler {
	return &OrderServiceImpl{
		orderRepo:      orderRepo,
		tradeHistoryRepo: tradeHistoryRepo,
		orderExecutor:  orderExecutor,
		broadcaster:    broadcaster,
	}
}

// CreateOrder creates a new order
func (s *OrderServiceImpl) CreateOrder(ctx context.Context, req *model.OrderRequest) (*model.OrderResponse, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	order := &model.Order{
		ID:        uuid.New().String(),
		Symbol:    req.Symbol,
		Side:      req.Side,
		Type:      model.OrderTypeMarket,
		Quantity:  req.Quantity,
		Price:     req.Price,
		Status:    model.OrderStatusPending,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	// Save order to repository
	if err := s.orderRepo.Create(ctx, order); err != nil {
		return nil, fmt.Errorf("failed to create order: %w", err)
	}

	// Execute order on exchange
	executedOrder, err := s.orderExecutor.PlaceOrder(ctx, order)
	if err != nil {
		order.Status = model.OrderStatusRejected
		s.orderRepo.UpdateStatus(ctx, order.ID, model.OrderStatusRejected)
		return nil, fmt.Errorf("failed to execute order: %w", err)
	}

	// Update order status
	executedOrder.UpdatedAt = time.Now()
	if err := s.orderRepo.UpdateStatus(ctx, executedOrder.ID, executedOrder.Status); err != nil {
		log.Printf("Failed to update order status: %v", err)
	}

	// Create trade history if filled
	if executedOrder.Status == model.OrderStatusFilled {
		trade := &model.TradeHistory{
			ID:         uuid.New().String(),
			Symbol:     executedOrder.Symbol,
			Side:       executedOrder.Side,
			Quantity:   executedOrder.Quantity,
			Price:      executedOrder.Price,
			Total:      executedOrder.Quantity * executedOrder.Price,
			Fee:        executedOrder.Quantity * executedOrder.Price * 0.001, // 0.1% fee
			ExecutedAt: time.Now(),
		}
		s.tradeHistoryRepo.Add(ctx, trade)
	}

	// Broadcast order update
	s.broadcaster.BroadcastOrderUpdate(executedOrder)

	return &model.OrderResponse{
		OrderID:   executedOrder.ID,
		Symbol:    executedOrder.Symbol,
		Side:      executedOrder.Side,
		Quantity:  executedOrder.Quantity,
		Status:    executedOrder.Status,
		CreatedAt: executedOrder.CreatedAt,
	}, nil
}

// CancelOrder cancels an existing order
func (s *OrderServiceImpl) CancelOrder(ctx context.Context, orderID string) error {
	order, err := s.orderRepo.GetByID(ctx, orderID)
	if err != nil {
		return fmt.Errorf("failed to get order: %w", err)
	}

	if order.Status != model.OrderStatusPending {
		return fmt.Errorf("cannot cancel order with status %s", order.Status)
	}

	if err := s.orderExecutor.CancelOrder(ctx, orderID, order.Symbol); err != nil {
		return fmt.Errorf("failed to cancel order on exchange: %w", err)
	}

	if err := s.orderRepo.UpdateStatus(ctx, orderID, model.OrderStatusCancelled); err != nil {
		return fmt.Errorf("failed to update order status: %w", err)
	}

	// Broadcast order update
	s.broadcaster.BroadcastOrderUpdate(&model.Order{
		ID:     orderID,
		Status: model.OrderStatusCancelled,
	})

	return nil
}

// GetOrder retrieves an order by ID
func (s *OrderServiceImpl) GetOrder(ctx context.Context, orderID string) (*model.Order, error) {
	return s.orderRepo.GetByID(ctx, orderID)
}

// GetAllOrders retrieves all orders
func (s *OrderServiceImpl) GetAllOrders(ctx context.Context) ([]*model.Order, error) {
	return s.orderRepo.GetAll(ctx)
}

// MarketDataServiceImpl implements the MarketDataService interface
type MarketDataServiceImpl struct {
	exchangeStream output.ExchangeDataStream
	marketDataRepo repository.MarketDataRepository
	publisher      output.MarketDataPublisher
	broadcaster    output.WebSocketBroadcaster
	streaming      map[model.TradeSymbol]bool
	streamingMu    sync.RWMutex
	ctx            context.Context
	cancel         context.CancelFunc
}

// NewMarketDataService creates a new market data service
func NewMarketDataService(
	exchangeStream output.ExchangeDataStream,
	marketDataRepo repository.MarketDataRepository,
	publisher output.MarketDataPublisher,
	broadcaster output.WebSocketBroadcaster,
) input.MarketDataHandler {
	ctx, cancel := context.WithCancel(context.Background())
	return &MarketDataServiceImpl{
		exchangeStream: exchangeStream,
		marketDataRepo: marketDataRepo,
		publisher:      publisher,
		broadcaster:    broadcaster,
		streaming:      make(map[model.TradeSymbol]bool),
		ctx:            ctx,
		cancel:         cancel,
	}
}

// GetLatestPrice retrieves the latest price for a symbol
func (s *MarketDataServiceImpl) GetLatestPrice(ctx context.Context, symbol model.TradeSymbol) (*model.MarketData, error) {
	return s.marketDataRepo.GetLatest(ctx, symbol)
}

// GetPriceHistory retrieves price history for a symbol
func (s *MarketDataServiceImpl) GetPriceHistory(ctx context.Context, symbol model.TradeSymbol) ([]*model.MarketData, error) {
	return s.marketDataRepo.GetPriceHistory(ctx, symbol, 24*time.Hour)
}

// Subscribe subscribes to market data for a symbol
func (s *MarketDataServiceImpl) Subscribe(ctx context.Context, symbol model.TradeSymbol) (<-chan *model.MarketData, error) {
	// Simple implementation - return the exchange stream channel
	// In production, implement proper subscription management
	ch := make(chan *model.MarketData, 100)
	
	// Start forwarding messages
	go func() {
		streamCh := s.exchangeStream.GetStreamChannel()
		for {
			select {
			case <-ctx.Done():
				close(ch)
				return
			case data, ok := <-streamCh:
				if !ok {
					close(ch)
					return
				}
				if data.Symbol == symbol {
					select {
					case ch <- data:
					default:
						// Channel full, skip
					}
				}
			}
		}
	}()
	
	return ch, nil
}

// Unsubscribe unsubscribes from market data for a symbol
func (s *MarketDataServiceImpl) Unsubscribe(ctx context.Context, symbol model.TradeSymbol) error {
	// Simple implementation - just log
	log.Printf("Unsubscribed from %s", symbol)
	return nil
}

// StartStreaming starts streaming market data for a symbol
func (s *MarketDataServiceImpl) StartStreaming(ctx context.Context, symbol model.TradeSymbol) error {
	s.streamingMu.Lock()
	defer s.streamingMu.Unlock()

	if s.streaming[symbol] {
		return nil
	}

	if err := s.exchangeStream.Subscribe(ctx, symbol); err != nil {
		return fmt.Errorf("failed to subscribe to exchange: %w", err)
	}

	s.streaming[symbol] = true

	// Start processing stream
	go s.processStream(symbol)

	log.Printf("Started streaming for %s", symbol)
	return nil
}

// StopStreaming stops streaming market data for a symbol
func (s *MarketDataServiceImpl) StopStreaming(ctx context.Context, symbol model.TradeSymbol) error {
	s.streamingMu.Lock()
	defer s.streamingMu.Unlock()

	if !s.streaming[symbol] {
		return nil
	}

	if err := s.exchangeStream.Unsubscribe(ctx, symbol); err != nil {
		return fmt.Errorf("failed to unsubscribe from exchange: %w", err)
	}

	s.streaming[symbol] = false

	log.Printf("Stopped streaming for %s", symbol)
	return nil
}

func (s *MarketDataServiceImpl) processStream(symbol model.TradeSymbol) {
	streamCh := s.exchangeStream.GetStreamChannel()

	for {
		select {
		case <-s.ctx.Done():
			return
		case data, ok := <-streamCh:
			if !ok {
				return
			}

			// Filter by symbol if needed
			if data.Symbol != symbol {
				continue
			}

			// Save to cache
			s.marketDataRepo.Save(s.ctx, data)

			// Publish to Redis
			if err := s.publisher.PublishMarketData(s.ctx, data); err != nil {
				log.Printf("Failed to publish market data: %v", err)
			}

			// Broadcast to WebSocket clients
			s.broadcaster.BroadcastMarketData(data)
		}
	}
}

// Shutdown stops all streaming
func (s *MarketDataServiceImpl) Shutdown() {
	s.cancel()
}

// BotServiceImpl implements the BotService interface
type BotServiceImpl struct {
	botStatusRepo    repository.BotStatusRepository
	orderSignalSub   output.RedisPublisher
	broadcaster      output.WebSocketBroadcaster
	isRunning        bool
	runningMu        sync.RWMutex
	startedAt        time.Time
	ctx              context.Context
	cancel           context.CancelFunc
}

// NewBotService creates a new bot service
func NewBotService(
	botStatusRepo repository.BotStatusRepository,
	orderSignalSub output.RedisPublisher,
	broadcaster output.WebSocketBroadcaster,
) input.BotHandler {
	return &BotServiceImpl{
		botStatusRepo:  botStatusRepo,
		orderSignalSub: orderSignalSub,
		broadcaster:    broadcaster,
	}
}

// Start starts the trading bot
func (s *BotServiceImpl) Start(ctx context.Context) error {
	s.runningMu.Lock()
	defer s.runningMu.Unlock()

	if s.isRunning {
		return fmt.Errorf("bot is already running")
	}

	s.ctx, s.cancel = context.WithCancel(context.Background())
	s.isRunning = true
	s.startedAt = time.Now()

	if err := s.botStatusRepo.SetActive(ctx, true); err != nil {
		return fmt.Errorf("failed to update bot status: %w", err)
	}

	// Start listening for order signals from strategy service
	go s.listenForOrderSignals()

	// Broadcast status update
	s.broadcaster.BroadcastBotStatus(&model.BotStatus{
		IsActive:  true,
		StartedAt: &s.startedAt,
	})

	log.Println("Trading bot started")
	return nil
}

// Stop stops the trading bot
func (s *BotServiceImpl) Stop(ctx context.Context) error {
	s.runningMu.Lock()
	defer s.runningMu.Unlock()

	if !s.isRunning {
		return fmt.Errorf("bot is not running")
	}

	s.cancel()
	s.isRunning = false

	if err := s.botStatusRepo.SetActive(ctx, false); err != nil {
		return fmt.Errorf("failed to update bot status: %w", err)
	}

	// Broadcast status update
	stoppedAt := time.Now()
	s.broadcaster.BroadcastBotStatus(&model.BotStatus{
		IsActive:  false,
		StoppedAt: &stoppedAt,
	})

	log.Println("Trading bot stopped")
	return nil
}

// GetStatus retrieves the current bot status
func (s *BotServiceImpl) GetStatus(ctx context.Context) (*model.BotStatus, error) {
	status, err := s.botStatusRepo.Get(ctx)
	if err != nil {
		return nil, err
	}

	s.runningMu.RLock()
	status.IsActive = s.isRunning
	s.runningMu.RUnlock()

	return status, nil
}

// IsRunning checks if the bot is currently running
func (s *BotServiceImpl) IsRunning(ctx context.Context) bool {
	s.runningMu.RLock()
	defer s.runningMu.RUnlock()
	return s.isRunning
}

func (s *BotServiceImpl) listenForOrderSignals() {
	// This would subscribe to Redis and process order signals
	// For now, it's a placeholder for the actual implementation
	log.Println("Listening for order signals from strategy service...")
}

// PortfolioServiceImpl implements the PortfolioService interface
type PortfolioServiceImpl struct {
	portfolioRepo repository.PortfolioRepository
}

// NewPortfolioService creates a new portfolio service
func NewPortfolioService(portfolioRepo repository.PortfolioRepository) input.PortfolioHandler {
	return &PortfolioServiceImpl{
		portfolioRepo: portfolioRepo,
	}
}

// GetPortfolio retrieves the entire portfolio
func (s *PortfolioServiceImpl) GetPortfolio(ctx context.Context) ([]*model.Portfolio, error) {
	return s.portfolioRepo.GetAll(ctx)
}

// GetPortfolioBySymbol retrieves portfolio for a specific symbol
func (s *PortfolioServiceImpl) GetPortfolioBySymbol(ctx context.Context, symbol model.TradeSymbol) (*model.Portfolio, error) {
	return s.portfolioRepo.Get(ctx, symbol)
}

// UpdatePortfolioAfterTrade updates portfolio after a trade is executed
func (s *PortfolioServiceImpl) UpdatePortfolioAfterTrade(ctx context.Context, trade *model.TradeHistory) error {
	portfolio, err := s.portfolioRepo.Get(ctx, trade.Symbol)
	if err != nil {
		// Create new portfolio if not exists
		portfolio = &model.Portfolio{
			Symbol: trade.Symbol,
		}
	}

	if trade.Side == model.SideBuy {
		// Update balance and average buy price
		totalCost := portfolio.Balance*portfolio.AvgBuyPrice + trade.Total
		portfolio.Balance += trade.Quantity
		if portfolio.Balance > 0 {
			portfolio.AvgBuyPrice = totalCost / portfolio.Balance
		}
	} else {
		// Sell
		portfolio.Balance -= trade.Quantity
	}

	portfolio.UpdatedAt = time.Now()
	return s.portfolioRepo.Update(ctx, portfolio)
}

// TradeHistoryServiceImpl implements the TradeHistoryService interface
type TradeHistoryServiceImpl struct {
	tradeHistoryRepo repository.TradeHistoryRepository
}

// NewTradeHistoryService creates a new trade history service
func NewTradeHistoryService(tradeHistoryRepo repository.TradeHistoryRepository) input.TradeHistoryHandler {
	return &TradeHistoryServiceImpl{
		tradeHistoryRepo: tradeHistoryRepo,
	}
}

// GetTradeHistory retrieves trade history
func (s *TradeHistoryServiceImpl) GetTradeHistory(ctx context.Context, limit int) ([]*model.TradeHistory, error) {
	return s.tradeHistoryRepo.GetAll(ctx, limit)
}

// GetTradeHistoryBySymbol retrieves trade history for a specific symbol
func (s *TradeHistoryServiceImpl) GetTradeHistoryBySymbol(ctx context.Context, symbol model.TradeSymbol, limit int) ([]*model.TradeHistory, error) {
	return s.tradeHistoryRepo.GetBySymbol(ctx, symbol, limit)
}
