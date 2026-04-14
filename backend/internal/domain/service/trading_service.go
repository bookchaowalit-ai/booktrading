package service

import (
	"fmt"
	"sync"

	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
)

// TradingService manages real trading operations (utility service, not bot lifecycle)
type TradingService struct {
	mu     sync.RWMutex
	client *bitkub.Client
}

// NewTradingService creates a new trading service
func NewTradingService() *TradingService {
	return &TradingService{}
}

// ConfigureClient configures the trading client with API credentials
func (s *TradingService) ConfigureClient(apiKey, apiSecret string, testnet bool) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.client = bitkub.NewClient(apiKey, apiSecret, testnet)
}

// GetClient returns the configured bitkub client (for use by bot service)
func (s *TradingService) GetClient() *bitkub.Client {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.client
}

// GetBalance returns the current balance
func (s *TradingService) GetBalance() (map[string]float64, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.client == nil {
		return nil, fmt.Errorf("trading client not configured")
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

// PlaceBuyOrder places a buy order
func (s *TradingService) PlaceBuyOrder(symbol string, quantity, price float64) (string, error) {
	s.mu.RLock()
	defer s.mu.RUnlock()

	if s.client == nil {
		return "", fmt.Errorf("trading client not configured")
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
		return "", fmt.Errorf("trading client not configured")
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
