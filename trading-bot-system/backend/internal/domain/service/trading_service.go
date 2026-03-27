package service

import (
	"context"
	"fmt"
	"sync"
	"time"

	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
)

// TradingService manages real trading operations
type TradingService struct {
	mu            sync.RWMutex
	client        *bitkub.Client
	isRunning     bool
	symbol        string
	quantity      float64
	gridLevels    int
	lowerPrice    float64
	upperPrice    float64
	investment    float64
	botStatus     *BotStatus
}

// BotStatus represents the trading bot status
type BotStatus struct {
	IsActive    bool    `json:"is_active"`
	StartedAt   *string `json:"started_at,omitempty"`
	StoppedAt   *string `json:"stopped_at,omitempty"`
	TotalTrades int     `json:"total_trades"`
	TotalProfit float64 `json:"total_profit"`
}

// NewTradingService creates a new trading service
func NewTradingService() *TradingService {
	return &TradingService{
		botStatus: &BotStatus{
			IsActive:    false,
			TotalTrades: 0,
			TotalProfit: 0,
		},
	}
}

// ConfigureBot configures the trading bot with API credentials
func (s *TradingService) ConfigureBot(apiKey, apiSecret string, testnet bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.client = bitkub.NewClient(apiKey, apiSecret, testnet)
}

// StartBot starts the trading bot
func (s *TradingService) StartBot(ctx context.Context, symbol string, quantity float64, gridLevels int, lowerPrice, upperPrice, investment float64) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if s.client == nil {
		return fmt.Errorf("bot not configured - please add API keys first")
	}

	if s.isRunning {
		return fmt.Errorf("bot is already running")
	}

	// Test API connection first
	_, err := s.client.GetBalances()
	if err != nil {
		return fmt.Errorf("failed to connect to exchange: %v", err)
	}

	// Configure bot parameters
	s.symbol = symbol
	s.quantity = quantity
	s.gridLevels = gridLevels
	s.lowerPrice = lowerPrice
	s.upperPrice = upperPrice
	s.investment = investment
	s.isRunning = true

	// Update bot status
	now := time.Now().Format(time.RFC3339)
	s.botStatus.IsActive = true
	s.botStatus.StartedAt = &now

	// Start trading loop in background
	go s.tradingLoop(ctx)

	return nil
}

// StopBot stops the trading bot
func (s *TradingService) StopBot() error {
	s.mu.Lock()
	defer s.mu.Unlock()

	if !s.isRunning {
		return fmt.Errorf("bot is not running")
	}

	s.isRunning = false

	// Update bot status
	now := time.Now().Format(time.RFC3339)
	s.botStatus.IsActive = false
	s.botStatus.StoppedAt = &now

	return nil
}

// GetStatus returns the current bot status
func (s *TradingService) GetStatus() *BotStatus {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.botStatus
}

// GetBalance returns the current balance
func (s *TradingService) GetBalance() (map[string]float64, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.client == nil {
		return nil, fmt.Errorf("bot not configured")
	}

	balances, err := s.client.GetBalances()
	if err != nil {
		return nil, err
	}

	balanceMap := make(map[string]float64)
	for _, b := range balances {
		balanceMap[b.Currency] = b.Available
	}

	return balanceMap, nil
}

// tradingLoop is the main trading loop
func (s *TradingService) tradingLoop(ctx context.Context) {
	ticker := time.NewTicker(5 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			s.StopBot()
			return
		case <-ticker.C:
			if !s.isRunning {
				return
			}

			// Execute trading logic
			s.executeTradingLogic()
		}
	}
}

// executeTradingLogic contains the actual trading logic
func (s *TradingService) executeTradingLogic() {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if !s.isRunning || s.client == nil {
		return
	}

	// Get current price
	ticker, err := s.client.GetTicker(s.symbol)
	if err != nil {
		fmt.Printf("Error getting ticker: %v\n", err)
		return
	}

	currentPrice := ticker.LastPrice

	// Simple grid trading logic
	gridSize := (s.upperPrice - s.lowerPrice) / float64(s.gridLevels)

	// Check if we should buy or sell
	if currentPrice <= s.lowerPrice+gridSize {
		// Price is low - consider buying
		fmt.Printf("Price low: %.2f - Consider BUY\n", currentPrice)
		// In production: s.client.PlaceOrder(...)
		s.botStatus.TotalTrades++
	} else if currentPrice >= s.upperPrice-gridSize {
		// Price is high - consider selling
		fmt.Printf("Price high: %.2f - Consider SELL\n", currentPrice)
		// In production: s.client.PlaceOrder(...)
		s.botStatus.TotalTrades++
	}

	// Update profit (mock for now)
	s.botStatus.TotalProfit += 0.0 // Will be calculated from actual trades
}

// PlaceBuyOrder places a buy order
func (s *TradingService) PlaceBuyOrder(symbol string, quantity, price float64) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.client == nil {
		return "", fmt.Errorf("bot not configured")
	}

	order, err := s.client.PlaceOrder(symbol, "BUY", "LIMIT", quantity, price)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("%d", order.OrderID), nil
}

// PlaceSellOrder places a sell order
func (s *TradingService) PlaceSellOrder(symbol string, quantity, price float64) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.client == nil {
		return "", fmt.Errorf("bot not configured")
	}

	order, err := s.client.PlaceOrder(symbol, "SELL", "LIMIT", quantity, price)
	if err != nil {
		return "", err
	}

	return fmt.Sprintf("%d", order.OrderID), nil
}

// GetPortfolio returns the current portfolio
func (s *TradingService) GetPortfolio() (map[string]interface{}, error) {
	balances, err := s.GetBalance()
	if err != nil {
		return nil, err
	}

	portfolio := make([]map[string]interface{}, 0)
	for currency, amount := range balances {
		if amount > 0 {
			portfolio = append(portfolio, map[string]interface{}{
				"symbol":  currency,
				"balance": amount,
				"locked":  0.0,
			})
		}
	}

	return map[string]interface{}{
		"balances": portfolio,
		"total":    len(portfolio),
	}, nil
}
