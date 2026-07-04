package exchange

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"trading-bot-system/backend/internal/logger"
	"net/http"
	"strconv"
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

// GetBalances retrieves account balances from Binance global
func (b *BinanceAdapter) GetBalances(ctx context.Context) ([]Balance, error) {
	b.mu.RLock()
	apiKey := b.apiKey
	apiSecret := b.apiSecret
	useTestnet := b.useTestnet
	b.mu.RUnlock()

	baseURL := "https://api.binance.com"
	if useTestnet {
		baseURL = "https://testnet.binance.vision"
	}

	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
	queryString := fmt.Sprintf("timestamp=%s", timestamp)

	mac := hmac.New(sha256.New, []byte(apiSecret))
	mac.Write([]byte(queryString))
	signature := hex.EncodeToString(mac.Sum(nil))

	reqURL := fmt.Sprintf("%s/api/v3/account?%s&signature=%s", baseURL, queryString, signature)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("X-MBX-APIKEY", apiKey)
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var errResp struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &errResp); err == nil && errResp.Code != 0 {
		return nil, fmt.Errorf("Binance API error (code %d): %s", errResp.Code, errResp.Msg)
	}

	var result struct {
		Balances []struct {
			Asset  string `json:"asset"`
			Free   string `json:"free"`
			Locked string `json:"locked"`
		} `json:"balances"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	balances := make([]Balance, 0)
	for _, b := range result.Balances {
		free, _ := strconv.ParseFloat(b.Free, 64)
		locked, _ := strconv.ParseFloat(b.Locked, 64)
		if free > 0 || locked > 0 {
			balances = append(balances, Balance{
				Currency: b.Asset,
				Free:     free,
				Locked:   locked,
				Total:    free + locked,
			})
		}
	}
	return balances, nil
}

// GetTicker retrieves ticker data for a symbol from Binance
func (b *BinanceAdapter) GetTicker(ctx context.Context, symbol string) (*TickerInfo, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	baseURL := "https://api.binance.com"
	if b.useTestnet {
		baseURL = "https://testnet.binance.vision"
	}

	url := fmt.Sprintf("%s/api/v3/ticker/price?symbol=%s", baseURL, symbol)
	req, err := http.NewRequestWithContext(ctx, "GET", url, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("Accept", "application/json")

	client := &http.Client{Timeout: 30 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	var result struct {
		Symbol string `json:"symbol"`
		Price  string `json:"price"`
	}
	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	price, _ := strconv.ParseFloat(result.Price, 64)
	return &TickerInfo{
		Symbol:    result.Symbol,
		LastPrice: price,
	}, nil
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

	logger.Info("Connected to Binance WebSocket")
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

	logger.Info("Disconnected from Binance WebSocket")
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
	logger.Info("Subscribed to Binance market data", "symbol", symbol)
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
	logger.Info("Unsubscribed from Binance market data", "symbol", symbol)
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
					logger.Error("Binance WebSocket error", "error", err)
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
		logger.Info("Warning: stream channel full, dropping message")
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

// BinanceOrderExecutor implements OrderExecutor for Binance (REAL order placement)
type BinanceOrderExecutor struct {
	apiKey     string
	apiSecret  string
	baseURL    string
	orderPath  string // /api/v3/order for Global, /api/v1/order for TH
	httpClient *http.Client
	useTestnet bool
}

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
		httpClient: &http.Client{Timeout: 30 * time.Second},
		useTestnet: useTestnet,
	}
}

// NewBinanceOrderExecutorWithBaseURL creates a new Binance order executor with a custom base URL
func NewBinanceOrderExecutorWithBaseURL(apiKey, apiSecret, baseURL string) *BinanceOrderExecutor {
	return &BinanceOrderExecutor{
		apiKey:     apiKey,
		apiSecret:  apiSecret,
		baseURL:    baseURL,
		orderPath:  "/api/v1/order", // Binance TH uses v1
		httpClient: &http.Client{Timeout: 30 * time.Second},
		useTestnet: false,
	}
}

// generateSignature creates HMAC SHA256 signature for Binance API
func (b *BinanceOrderExecutor) generateSignature(queryString string) string {
	mac := hmac.New(sha256.New, []byte(b.apiSecret))
	mac.Write([]byte(queryString))
	return hex.EncodeToString(mac.Sum(nil))
}

// BinanceOrderResponse represents the response from Binance order API
type BinanceOrderResponse struct {
	Symbol            string  `json:"symbol"`
	OrderID           int64   `json:"orderId"`
	ClientOrderID     string  `json:"clientOrderId"`
	Price             string  `json:"price"`
	OrigQty           string  `json:"origQty"`
	ExecutedQty       string  `json:"executedQty"`
	Status            string  `json:"status"`
	TimeInForce       string  `json:"timeInForce"`
	Type              string  `json:"type"`
	Side              string  `json:"side"`
	TransactTime      int64   `json:"transactTime"`
	CumQuoteQty       string  `json:"cummulativeQuoteQty"`
}

// PlaceOrder places a REAL order on Binance via REST API
func (b *BinanceOrderExecutor) PlaceOrder(ctx context.Context, order *model.Order) (*model.Order, error) {
	if b.apiKey == "" || b.apiSecret == "" {
		return nil, fmt.Errorf("Binance API credentials not configured — cannot place real order")
	}

	logger.Info("Placing REAL order on Binance",
		"symbol", order.Symbol, "side", order.Side,
		"quantity", order.Quantity, "price", order.Price,
		"baseURL", b.baseURL,
	)

	// Determine order type
	orderType := "MARKET"
	params := fmt.Sprintf("symbol=%s&side=%s&type=%s&quantity=%s&timestamp=%d",
		order.Symbol,
		order.Side,
		orderType,
		strconv.FormatFloat(order.Quantity, 'f', -1, 64),
		time.Now().UnixMilli(),
	)

	// For LIMIT orders, add price and timeInForce
	if order.Type == model.OrderTypeLimit && order.Price > 0 {
		orderType = "LIMIT"
		params = fmt.Sprintf("symbol=%s&side=%s&type=%s&quantity=%s&price=%s&timeInForce=GTC&timestamp=%d",
			order.Symbol,
			order.Side,
			orderType,
			strconv.FormatFloat(order.Quantity, 'f', -1, 64),
			strconv.FormatFloat(order.Price, 'f', -1, 64),
			time.Now().UnixMilli(),
		)
	}

	// Generate signature
	signature := b.generateSignature(params)

	// Determine order path: Binance TH uses /api/v1, Global uses /api/v3
	orderPath := b.orderPath
	if orderPath == "" {
		orderPath = "/api/v3/order"
	}

	// Create request
	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, orderPath, params, signature)
	req, err := http.NewRequestWithContext(ctx, "POST", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	// Execute request
	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Binance API request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	// Check HTTP status
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance API returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	// Check for API error
	var errResp struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &errResp); err == nil && errResp.Code != 0 {
		return nil, fmt.Errorf("Binance API error (code %d): %s", errResp.Code, errResp.Msg)
	}

	// Parse successful response
	var binanceResp BinanceOrderResponse
	if err := json.Unmarshal(body, &binanceResp); err != nil {
		return nil, fmt.Errorf("failed to parse Binance order response: %w, body: %s", err, string(body))
	}

	// Map Binance status to our model status
	status := model.OrderStatusPending
	switch binanceResp.Status {
	case "FILLED":
		status = model.OrderStatusFilled
	case "CANCELED", "EXPIRED", "REJECTED":
		status = model.OrderStatusRejected
	case "NEW", "PARTIALLY_FILLED":
		status = model.OrderStatusPending
	}

	executedQty, _ := strconv.ParseFloat(binanceResp.ExecutedQty, 64)
	price, _ := strconv.ParseFloat(binanceResp.Price, 64)
	if price == 0 {
		price = order.Price
	}

	result := &model.Order{
		ID:        order.ID,
		Symbol:    order.Symbol,
		Side:      order.Side,
		Type:      order.Type,
		Quantity:  executedQty,
		Price:     price,
		Status:    status,
		CreatedAt: time.Now(),
		UpdatedAt: time.Now(),
	}

	logger.Info("REAL order placed on Binance",
		"orderId", binanceResp.OrderID,
		"symbol", binanceResp.Symbol,
		"status", binanceResp.Status,
		"executedQty", binanceResp.ExecutedQty,
		"cumQuote", binanceResp.CumQuoteQty,
	)

	return result, nil
}

// CancelOrder cancels an order on Binance
func (b *BinanceOrderExecutor) CancelOrder(ctx context.Context, orderID string, symbol model.TradeSymbol) error {
	if b.apiKey == "" || b.apiSecret == "" {
		return fmt.Errorf("Binance API credentials not configured")
	}

	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
	params := fmt.Sprintf("symbol=%s&orderId=%s&timestamp=%s", symbol, orderID, timestamp)
	signature := b.generateSignature(params)

	reqURL := fmt.Sprintf("%s/api/v3/order?%s&signature=%s", b.baseURL, params, signature)
	req, err := http.NewRequestWithContext(ctx, "DELETE", reqURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("Binance cancel request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Binance cancel returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	logger.Info("Order cancelled on Binance", "orderId", orderID, "symbol", symbol)
	return nil
}

// GetOrderStatus gets the status of an order from Binance
func (b *BinanceOrderExecutor) GetOrderStatus(ctx context.Context, orderID string, symbol model.TradeSymbol) (*model.Order, error) {
	if b.apiKey == "" || b.apiSecret == "" {
		return nil, fmt.Errorf("Binance API credentials not configured")
	}

	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
	params := fmt.Sprintf("symbol=%s&orderId=%s&timestamp=%s", symbol, orderID, timestamp)
	signature := b.generateSignature(params)

	reqURL := fmt.Sprintf("%s/api/v3/order?%s&signature=%s", b.baseURL, params, signature)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("Binance request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	var binanceResp BinanceOrderResponse
	if err := json.Unmarshal(body, &binanceResp); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w, body: %s", err, string(body))
	}

	status := model.OrderStatusPending
	switch binanceResp.Status {
	case "FILLED":
		status = model.OrderStatusFilled
	case "CANCELED", "EXPIRED", "REJECTED":
		status = model.OrderStatusRejected
	}

	return &model.Order{
		ID:     orderID,
		Symbol: symbol,
		Status: status,
	}, nil
}
