package exchange

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"sync"
	"time"
	"trading-bot-system/backend/internal/logger"
)

// BinanceTHAdapter implements the ExchangeDataStream interface for Binance Thailand
type BinanceTHAdapter struct {
	apiKey     string
	apiSecret  string
	baseURL    string
	httpClient *http.Client
	mu         sync.RWMutex
}

// NewBinanceTHAdapter creates a new Binance Thailand adapter
func NewBinanceTHAdapter(apiKey, apiSecret string) *BinanceTHAdapter {
	return &BinanceTHAdapter{
		apiKey:    apiKey,
		apiSecret: apiSecret,
		baseURL:   "https://api.binance.th",
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// generateSignature creates HMAC SHA256 signature
func (b *BinanceTHAdapter) generateSignature(queryString string) string {
	mac := hmac.New(sha256.New, []byte(b.apiSecret))
	mac.Write([]byte(queryString))
	return hex.EncodeToString(mac.Sum(nil))
}

// GetBalances retrieves account balances from Binance TH
func (b *BinanceTHAdapter) GetBalances(ctx context.Context) ([]Balance, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	// Account endpoint
	path := "/api/v1/accountV2"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	// Build query string (timestamp only, signature appended at the end)
	queryString := fmt.Sprintf("timestamp=%s", timestamp)

	// Generate signature
	signature := b.generateSignature(queryString)

	// Create request with signature at the end
	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, path, queryString, signature)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	logger.Info("Binance TH balance request", "url", reqURL, "api_key_prefix", b.apiKey[:8])

	// Execute request
	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	logger.Info("Binance TH balances response received", "body_length", len(body))

	// Check for error response
	var errorResult struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &errorResult); err == nil && errorResult.Code != 0 {
		return nil, fmt.Errorf("Binance TH API error (code %d): %s", errorResult.Code, errorResult.Msg)
	}

	// Parse successful response
	var result struct {
		MakerCommission  json.Number `json:"makerCommission"`
		TakerCommission  json.Number `json:"takerCommission"`
		BuyerCommission  json.Number `json:"buyerCommission"`
		SellerCommission json.Number `json:"sellerCommission"`
		CanTrade         bool        `json:"canTrade"`
		CanWithdraw      bool        `json:"canWithdraw"`
		CanDeposit       bool        `json:"canDeposit"`
		Balances         []struct {
			Asset  string `json:"asset"`
			Free   string `json:"free"`
			Locked string `json:"locked"`
		} `json:"balances"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Convert to Balance array
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
			logger.Debug("Binance TH balance found", "asset", b.Asset, "free", free, "locked", locked)
		}
	}

	logger.Info("Binance TH balances parsed", "count", len(balances))
	for _, bal := range balances {
		logger.Info("Binance TH balance", "asset", bal.Currency, "free", bal.Free, "total", bal.Total)
	}

	return balances, nil
}

// GetTicker retrieves the latest ticker for a symbol
func (b *BinanceTHAdapter) GetTicker(ctx context.Context, symbol string) (*TickerInfo, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	// Ticker endpoint - Binance TH uses /api/v1/ticker/price (not v3)
	path := "/api/v1/ticker/price"
	queryString := fmt.Sprintf("symbol=%s", symbol)

	// Create request
	reqURL := fmt.Sprintf("%s%s?%s", b.baseURL, path, queryString)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	logger.Info("Binance TH ticker request", "url", reqURL)

	// Execute request
	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	logger.Info("Binance TH ticker response", "status", resp.StatusCode, "body", string(body))

	// Check HTTP status code first
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance TH API returned HTTP %d for %s, body: %s", resp.StatusCode, reqURL, string(body))
	}

	// Check if we got HTML instead of JSON
	if len(body) > 0 && body[0] == '<' {
		return nil, fmt.Errorf("Binance TH returned HTML instead of JSON (status: %d)", resp.StatusCode)
	}

	// Check for error response
	var errorResult struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &errorResult); err == nil && errorResult.Code != 0 {
		return nil, fmt.Errorf("Binance TH API error (code %d): %s", errorResult.Code, errorResult.Msg)
	}

	// Parse response
	var result struct {
		Symbol string `json:"symbol"`
		Price  string `json:"price"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w, body: %s", err, string(body))
	}

	price, _ := strconv.ParseFloat(result.Price, 64)

	logger.Info("Binance TH ticker parsed", "symbol", result.Symbol, "price", price)

	return &TickerInfo{
		Symbol:    result.Symbol,
		LastPrice: price,
	}, nil
}

// Order represents a Binance TH order
type Order struct {
	Symbol        string `json:"symbol"`
	OrderID       int64  `json:"orderId"`
	ClientOrderID string `json:"clientOrderId"`
	Price         string `json:"price"`
	OrigQty       string `json:"origQty"`
	ExecutedQty   string `json:"executedQty"`
	Status        string `json:"status"`
	TimeInForce   string `json:"timeInForce"`
	Type          string `json:"type"`
	Side          string `json:"side"`
	TransactTime  int64  `json:"transactTime"`
	CumQuote      string `json:"cummulativeQuoteQty"`
}

// PlaceOrder creates a new order on Binance TH
func (b *BinanceTHAdapter) PlaceOrder(ctx context.Context, symbol, side, orderType string, quantity, price float64, timeInForce string) (*Order, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	// Order endpoint
	path := "/api/v1/order"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	// Build query string for signing
	params := fmt.Sprintf("symbol=%s&side=%s&type=%s&quantity=%s&timestamp=%s",
		symbol, side, orderType,
		strconv.FormatFloat(quantity, 'f', -1, 64),
		timestamp)

	// Add price and timeInForce for LIMIT orders
	if orderType == "LIMIT" {
		params += fmt.Sprintf("&price=%s&timeInForce=%s",
			strconv.FormatFloat(price, 'f', -1, 64),
			timeInForce)
	}

	// Add price for STOP_LOSS_LIMIT, TAKE_PROFIT_LIMIT, etc.
	if orderType != "MARKET" && orderType != "LIMIT" && price > 0 {
		params += fmt.Sprintf("&price=%s",
			strconv.FormatFloat(price, 'f', -1, 64))
	}

	// Generate signature
	signature := b.generateSignature(params)

	// Create request
	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, path, params, signature)
	req, err := http.NewRequestWithContext(ctx, "POST", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	// Set headers
	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	req.Header.Set("Accept", "application/json")

	logger.Info("Binance TH order request", "url", path, "symbol", symbol, "side", side, "type", orderType, "quantity", quantity, "price", price)

	// Execute request
	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	logger.Info("Binance TH order response", "status", resp.StatusCode, "body", string(body))

	// Check HTTP status code
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance TH API returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	// Check for error response
	var errorResult struct {
		Code int    `json:"code"`
		Msg  string `json:"msg"`
	}
	if err := json.Unmarshal(body, &errorResult); err == nil && errorResult.Code != 0 {
		return nil, fmt.Errorf("Binance TH API error (code %d): %s", errorResult.Code, errorResult.Msg)
	}

	// Parse successful response
	var order Order
	if err := json.Unmarshal(body, &order); err != nil {
		return nil, fmt.Errorf("failed to parse order response: %w, body: %s", err, string(body))
	}

	logger.Info("Binance TH order placed", "orderId", order.OrderID, "symbol", order.Symbol, "status", order.Status)

	return &order, nil
}

// GetOpenOrders retrieves all open orders for a symbol
func (b *BinanceTHAdapter) GetOpenOrders(ctx context.Context, symbol string) ([]Order, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	path := "/api/v1/openOrders"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	queryString := fmt.Sprintf("symbol=%s&timestamp=%s", symbol, timestamp)
	signature := b.generateSignature(queryString)

	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, path, queryString, signature)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance TH API returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	var orders []Order
	if err := json.Unmarshal(body, &orders); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w, body: %s", err, string(body))
	}

	return orders, nil
}

// CancelOrder cancels an existing order
func (b *BinanceTHAdapter) CancelOrder(ctx context.Context, symbol string, orderID int64) error {
	b.mu.RLock()
	defer b.mu.RUnlock()

	path := "/api/v1/order"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	queryString := fmt.Sprintf("symbol=%s&orderId=%d&timestamp=%s", symbol, orderID, timestamp)
	signature := b.generateSignature(queryString)

	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, path, queryString, signature)
	req, err := http.NewRequestWithContext(ctx, "DELETE", reqURL, nil)
	if err != nil {
		return fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return fmt.Errorf("Binance TH API returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	logger.Info("Binance TH order cancelled", "orderId", orderID, "symbol", symbol)

	return nil
}

// GetTradeHistory retrieves user trade history for a symbol
func (b *BinanceTHAdapter) GetTradeHistory(ctx context.Context, symbol string, limit int) ([]interface{}, error) {
	b.mu.RLock()
	defer b.mu.RUnlock()

	path := "/api/v1/userTrades"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	queryString := fmt.Sprintf("symbol=%s&limit=%d&timestamp=%s", symbol, limit, timestamp)
	signature := b.generateSignature(queryString)

	reqURL := fmt.Sprintf("%s%s?%s&signature=%s", b.baseURL, path, queryString, signature)
	req, err := http.NewRequestWithContext(ctx, "GET", reqURL, nil)
	if err != nil {
		return nil, fmt.Errorf("failed to create request: %w", err)
	}

	req.Header.Set("X-MBX-APIKEY", b.apiKey)
	req.Header.Set("Accept", "application/json")

	resp, err := b.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("request failed: %w", err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, fmt.Errorf("failed to read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("Binance TH API returned HTTP %d: %s", resp.StatusCode, string(body))
	}

	var trades []interface{}
	if err := json.Unmarshal(body, &trades); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	return trades, nil
}

// Connect establishes connection (Binance TH doesn't use WebSocket for account data)
func (b *BinanceTHAdapter) Connect(ctx context.Context) error {
	logger.Info("Binance TH adapter initialized (REST API only)")
	return nil
}

// Disconnect closes the connection
func (b *BinanceTHAdapter) Disconnect(ctx context.Context) error {
	return nil
}
