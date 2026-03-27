package exchange

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"sync"
	"time"

	"github.com/gorilla/websocket"
	"trading-bot-system/backend/internal/domain/model"
)

// BinanceAdapter implements the ExchangeDataStream interface for Binance
type BinanceAdapter struct {
	apiKey       string
	apiSecret    string
	useTestnet   bool
	wsURL        string
	conn         *websocket.Conn
	mu           sync.RWMutex
	streamCh     chan *model.MarketData
	subscribed   map[model.TradeSymbol]bool
	subscribedMu sync.RWMutex
}

// NewBinanceAdapter creates a new Binance adapter
func NewBinanceAdapter(apiKey, apiSecret string, useTestnet bool) *BinanceAdapter {
	wsURL := "wss://stream.binance.com:9443/ws"
	if useTestnet {
		wsURL = "wss://testnet.binance.vision/ws"
	}

	return &BinanceAdapter{
		apiKey:     apiKey,
		apiSecret:  apiSecret,
		useTestnet: useTestnet,
		wsURL:      wsURL,
		streamCh:   make(chan *model.MarketData, 1000),
		subscribed: make(map[model.TradeSymbol]bool),
	}
}

// Connect establishes WebSocket connection to Binance
func (b *BinanceAdapter) Connect(ctx context.Context) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	var dialer websocket.Dialer
	conn, _, err := dialer.Dial(b.wsURL, nil)
	if err != nil {
		return fmt.Errorf("failed to connect to Binance WebSocket: %w", err)
	}

	b.conn = conn

	// Start reading messages
	go b.readMessages(ctx)

	log.Println("Connected to Binance WebSocket")
	return nil
}

// Disconnect closes the WebSocket connection
func (b *BinanceAdapter) Disconnect(ctx context.Context) error {
	b.mu.Lock()
	defer b.mu.Unlock()

	if b.conn != nil {
		if err := b.conn.Close(); err != nil {
			return fmt.Errorf("failed to close connection: %w", err)
		}
	}

	log.Println("Disconnected from Binance WebSocket")
	return nil
}

// Subscribe subscribes to market data for a symbol
func (b *BinanceAdapter) Subscribe(ctx context.Context, symbol model.TradeSymbol) error {
	b.subscribedMu.Lock()
	defer b.subscribedMu.Unlock()

	if b.subscribed[symbol] {
		return nil
	}

	symbolLower := fmt.Sprintf("%s@trade", toLower(string(symbol)))
	subscribeMsg := map[string]interface{}{
		"method": "SUBSCRIBE",
		"params": []string{symbolLower},
		"id":     time.Now().UnixNano(),
	}

	if err := b.conn.WriteJSON(subscribeMsg); err != nil {
		return fmt.Errorf("failed to subscribe: %w", err)
	}

	b.subscribed[symbol] = true
	log.Printf("Subscribed to %s", symbol)
	return nil
}

// Unsubscribe unsubscribes from market data for a symbol
func (b *BinanceAdapter) Unsubscribe(ctx context.Context, symbol model.TradeSymbol) error {
	b.subscribedMu.Lock()
	defer b.subscribedMu.Unlock()

	if !b.subscribed[symbol] {
		return nil
	}

	symbolLower := fmt.Sprintf("%s@trade", toLower(string(symbol)))
	unsubscribeMsg := map[string]interface{}{
		"method": "UNSUBSCRIBE",
		"params": []string{symbolLower},
		"id":     time.Now().UnixNano(),
	}

	if err := b.conn.WriteJSON(unsubscribeMsg); err != nil {
		return fmt.Errorf("failed to unsubscribe: %w", err)
	}

	b.subscribed[symbol] = false
	log.Printf("Unsubscribed from %s", symbol)
	return nil
}

// GetStreamChannel returns the channel for receiving market data
func (b *BinanceAdapter) GetStreamChannel() <-chan *model.MarketData {
	return b.streamCh
}

func (b *BinanceAdapter) readMessages(ctx context.Context) {
	for {
		select {
		case <-ctx.Done():
			return
		default:
			b.mu.RLock()
			if b.conn == nil {
				b.mu.RUnlock()
				return
			}
			b.mu.RUnlock()

			_, message, err := b.conn.ReadMessage()
			if err != nil {
				if websocket.IsUnexpectedCloseError(err, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
					log.Printf("WebSocket error: %v", err)
				}
				return
			}

			b.processMessage(message)
		}
	}
}

func (b *BinanceAdapter) processMessage(message []byte) {
	var tradeMsg map[string]interface{}
	if err := json.Unmarshal(message, &tradeMsg); err != nil {
		return
	}

	// Check if it's a trade message
	if tradeMsg["e"] != "trade" {
		return
	}

	symbol, ok := tradeMsg["s"].(string)
	if !ok {
		return
	}

	price, ok := tradeMsg["p"].(string)
	if !ok {
		return
	}

	volume, ok := tradeMsg["q"].(string)
	if !ok {
		return
	}

	timestamp := time.Now()
	if ts, ok := tradeMsg["T"].(float64); ok {
		timestamp = time.UnixMilli(int64(ts))
	}

	marketData := &model.MarketData{
		Symbol:    model.TradeSymbol(symbol),
		Timestamp: timestamp,
	}

	// Parse price
	if _, err := fmt.Sscanf(price, "%f", &marketData.Price); err != nil {
		return
	}

	// Parse volume
	if _, err := fmt.Sscanf(volume, "%f", &marketData.Volume); err != nil {
		return
	}

	select {
	case b.streamCh <- marketData:
	default:
		log.Println("Warning: stream channel full, dropping message")
	}
}

func toLower(s string) string {
	result := ""
	for _, r := range s {
		if r >= 'A' && r <= 'Z' {
			result += string(r + 32)
		} else {
			result += string(r)
		}
	}
	return result
}

// BinanceOrderExecutor implements OrderExecutor for Binance
type BinanceOrderExecutor struct {
	apiKey     string
	apiSecret  string
	baseURL    string
	httpClient *httpClient
}

type httpClient struct{}

// NewBinanceOrderExecutor creates a new Binance order executor
func NewBinanceOrderExecutor(apiKey, apiSecret string, useTestnet bool) *BinanceOrderExecutor {
	baseURL := "https://api.binance.com"
	if useTestnet {
		baseURL = "https://testnet.binance.vision"
	}

	return &BinanceOrderExecutor{
		apiKey:     apiKey,
		apiSecret:  apiSecret,
		baseURL:    baseURL,
		httpClient: &httpClient{},
	}
}

// PlaceOrder places an order on Binance
func (b *BinanceOrderExecutor) PlaceOrder(ctx context.Context, order *model.Order) (*model.Order, error) {
	// For demo purposes, we'll simulate order execution
	// In production, this would call Binance API
	log.Printf("Placing order: %+v", order)

	// Simulate order execution
	executedOrder := &model.Order{
		ID:        order.ID,
		Symbol:    order.Symbol,
		Side:      order.Side,
		Type:      order.Type,
		Quantity:  order.Quantity,
		Price:     order.Price,
		Status:    model.OrderStatusFilled,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	return executedOrder, nil
}

// CancelOrder cancels an order on Binance
func (b *BinanceOrderExecutor) CancelOrder(ctx context.Context, orderID string, symbol model.TradeSymbol) error {
	log.Printf("Cancelling order %s for %s", orderID, symbol)
	return nil
}

// GetOrderStatus gets the status of an order from Binance
func (b *BinanceOrderExecutor) GetOrderStatus(ctx context.Context, orderID string, symbol model.TradeSymbol) (*model.Order, error) {
	return &model.Order{
		ID:     orderID,
		Symbol: symbol,
		Status: model.OrderStatusFilled,
	}, nil
}
