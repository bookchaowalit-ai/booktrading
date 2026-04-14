package bitkub

import (
	"bytes"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"trading-bot-system/backend/internal/logger"
	"net/http"
	"net/url"
	"sort"
	"strconv"
	"time"
)

// Client represents a Bitkub API client
type Client struct {
	APIKey    string
	APISecret string
	Testnet   bool
	BaseURL   string
	client    *http.Client
}

// Balance represents a user's balance
type Balance struct {
	Currency string  `json:"currency"`
	Amount   float64 `json:"amount"`
	Available float64 `json:"available"`
}

// Order represents a trading order
type Order struct {
	OrderID    int64   `json:"orderId"`
	Symbol     string  `json:"symbol"`
	Side       string  `json:"side"`
	Type       string  `json:"type"`
	Price      float64 `json:"price"`
	Quantity   float64 `json:"quantity"`
	Filled     float64 `json:"filled"`
	Remaining  float64 `json:"remaining"`
	Status     string  `json:"status"`
	CreatedAt  int64   `json:"createdAt"`
}

// Ticker represents market ticker data
type Ticker struct {
	Symbol       string  `json:"symbol"`
	LastPrice    float64 `json:"last"`
	High24h      float64 `json:"high"`
	Low24h       float64 `json:"low"`
	Volume24h    float64 `json:"volume"`
	Change24h    float64 `json:"change"`
	ChangePercent float64 `json:"changePercent"`
}

// NewClient creates a new Bitkub client
func NewClient(apiKey, apiSecret string, testnet bool) *Client {
	baseURL := "https://api.bitkub.com"
	if testnet {
		baseURL = "https://api.bitkub.cloud" // Testnet URL
	}

	return &Client{
		APIKey:    apiKey,
		APISecret: apiSecret,
		Testnet:   testnet,
		BaseURL:   baseURL,
		client:    &http.Client{Timeout: 30 * time.Second},
	}
}

// generateSignature creates HMAC-SHA256 signature
func (c *Client) generateSignature(payload string) string {
	mac := hmac.New(sha256.New, []byte(c.APISecret))
	mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

// signRequest signs and adds authentication headers
func (c *Client) signRequest(method, path string, params url.Values) (string, error) {
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)
	
	// Sort parameters
	keys := make([]string, 0, len(params))
	for k := range params {
		keys = append(keys, k)
	}
	sort.Strings(keys)

	// Build query string
	queryString := ""
	for _, k := range keys {
		queryString += fmt.Sprintf("%s=%s&", k, params.Get(k))
	}
	queryString += fmt.Sprintf("ts=%s", timestamp)

	// Create signature payload
	payload := fmt.Sprintf("%s\n%s\n%s", method, path, queryString)
	signature := c.generateSignature(payload)

	return signature, nil
}

// GetBalances retrieves user's balances
func (c *Client) GetBalances() ([]Balance, error) {
	// Bitkub wallet endpoint - uses POST method
	path := "/api/market/wallet"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	// Create signature for POST request
	signature := c.generateSignature(fmt.Sprintf("POST\n%s\n%s", path, timestamp))

	// Prepare request body
	body := map[string]interface{}{}
	jsonBody, _ := json.Marshal(body)

	req, err := http.NewRequest("POST", c.BaseURL+path, bytes.NewBuffer(jsonBody))
	if err != nil {
		return nil, err
	}

	// Set Bitkub API headers
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-BTK-APIKEY", c.APIKey)
	req.Header.Set("X-BTK-TIMESTAMP", timestamp)
	req.Header.Set("X-BTK-SIGN", signature)

	logger.Info("Bitkub balance request", "url", c.BaseURL+path, "api_key_prefix", c.APIKey[:8], "timestamp", timestamp)

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	logger.Info("Bitkub balances response received", "body_length", len(respBody))

	// Parse response
	var rawData map[string]interface{}
	if err := json.Unmarshal(respBody, &rawData); err != nil {
		return nil, fmt.Errorf("failed to parse response: %w", err)
	}

	// Check for error first (Bitkub returns {"error": 404, "message": "..."})
	if errVal, ok := rawData["error"]; ok {
		errorMsg := "Unknown error"
		if msg, ok := rawData["message"].(string); ok {
			errorMsg = msg
		} else if errNum, ok := errVal.(float64); ok {
			errorMsg = fmt.Sprintf("HTTP Error %d", int(errNum))
		} else if errMsg, ok := errVal.(string); ok {
			errorMsg = errMsg
		}
		return nil, fmt.Errorf("Bitkub API error: %s", errorMsg)
	}

	// Check for status field
	if status, ok := rawData["status"].(float64); ok && status != 1 {
		errorMsg := "Unknown error"
		if msg, ok := rawData["message"].(string); ok {
			errorMsg = msg
		} else if err, ok := rawData["error"].(string); ok {
			errorMsg = err
		}
		return nil, fmt.Errorf("API error (status %.0f): %s", status, errorMsg)
	}

	// Parse successful response
	var result struct {
		Status int `json:"status"`
		Data   []struct {
			Currency        string  `json:"currency"`
			Name            string  `json:"name"`
			NameEN          string  `json:"name_en"`
			Amount          float64 `json:"amount"`
			Available       float64 `json:"available"`
			Frozen          float64 `json:"frozen"`
			OnOrder         float64 `json:"on_order"`
			PendingWithdraw float64 `json:"pending_withdraw"`
		} `json:"data"`
	}

	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, err
	}

	// Convert to Balance array
	balances := make([]Balance, len(result.Data))
	for i, b := range result.Data {
		balances[i] = Balance{
			Currency:  b.Currency,
			Amount:    b.Amount,
			Available: b.Available,
		}
	}

	return balances, nil
}

// GetTicker gets ticker data for a symbol
func (c *Client) GetTicker(symbol string) (*Ticker, error) {
	path := "/api/v1/ticker"
	params := url.Values{}
	params.Add("sym", symbol)

	resp, err := c.client.Get(c.BaseURL + path + "?" + params.Encode())
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result map[string]struct {
		Last       string `json:"last"`
		High24h    string `json:"high24"`
		Low24h     string `json:"low24"`
		Volume24h  string `json:"vol24"`
		Change24h  string `json:"change24"`
		ChangePct  string `json:"changepct24"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	tickerData, ok := result[symbol]
	if !ok {
		return nil, fmt.Errorf("symbol not found: %s", symbol)
	}

	last, _ := strconv.ParseFloat(tickerData.Last, 64)
	high, _ := strconv.ParseFloat(tickerData.High24h, 64)
	low, _ := strconv.ParseFloat(tickerData.Low24h, 64)
	volume, _ := strconv.ParseFloat(tickerData.Volume24h, 64)
	change, _ := strconv.ParseFloat(tickerData.Change24h, 64)
	changePct, _ := strconv.ParseFloat(tickerData.ChangePct, 64)

	return &Ticker{
		Symbol:       symbol,
		LastPrice:    last,
		High24h:      high,
		Low24h:       low,
		Volume24h:    volume,
		Change24h:    change,
		ChangePercent: changePct,
	}, nil
}

// PlaceOrder places a new order
func (c *Client) PlaceOrder(symbol, side, orderType string, quantity, price float64) (*Order, error) {
	path := "/api/v3/order"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	params := url.Values{}
	params.Add("sym", symbol)
	params.Add("sd", side)  // sd = side (BUY/SELL)
	params.Add("ty", orderType) // ty = type (LIMIT/MARKET)
	params.Add("amt", fmt.Sprintf("%f", quantity))
	params.Add("ts", timestamp)

	if orderType == "LIMIT" {
		params.Add("prc", fmt.Sprintf("%f", price))
	}

	signature := c.generateSignature(fmt.Sprintf("POST\n%s\n%s", path, params.Encode()))

	// Prepare request body
	body := map[string]interface{}{
		"sym": symbol,
		"sd":  side,
		"ty":  orderType,
		"amt": quantity,
	}
	if orderType == "LIMIT" {
		body["prc"] = price
	}

	jsonBody, _ := json.Marshal(body)
	_ = jsonBody // Mark as used (sent via query params for Bitkub)

	req, err := http.NewRequest("POST", c.BaseURL+path+"?"+params.Encode(), nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("X-JFIN-API-Key", c.APIKey)
	req.Header.Set("X-JFIN-API-Signature", signature)
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	respBody, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result struct {
		Result  int    `json:"result"`
		OrderID int64  `json:"order_id"`
		Error   string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(respBody, &result); err != nil {
		return nil, err
	}

	if result.Result != 0 {
		return nil, fmt.Errorf("API error: %s", result.Error)
	}

	return &Order{
		OrderID: result.OrderID,
		Symbol:  symbol,
		Side:    side,
		Type:    orderType,
		Status:  "PENDING",
	}, nil
}

// CancelOrder cancels an existing order
func (c *Client) CancelOrder(symbol string, orderID int64) error {
	path := "/api/v3/order"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	params := url.Values{}
	params.Add("sym", symbol)
	params.Add("oid", strconv.FormatInt(orderID, 10))
	params.Add("ts", timestamp)

	signature := c.generateSignature(fmt.Sprintf("DELETE\n%s\n%s", path, params.Encode()))

	req, err := http.NewRequest("DELETE", c.BaseURL+path+"?"+params.Encode(), nil)
	if err != nil {
		return err
	}

	req.Header.Set("X-JFIN-API-Key", c.APIKey)
	req.Header.Set("X-JFIN-API-Signature", signature)

	resp, err := c.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return err
	}

	var result struct {
		Result int    `json:"result"`
		Error  string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return err
	}

	if result.Result != 0 {
		return fmt.Errorf("API error: %s", result.Error)
	}

	return nil
}

// GetOpenOrders gets all open orders
func (c *Client) GetOpenOrders(symbol string) ([]Order, error) {
	path := "/api/v3/order/open"
	timestamp := strconv.FormatInt(time.Now().UnixMilli(), 10)

	params := url.Values{}
	params.Add("sym", symbol)
	params.Add("ts", timestamp)

	signature := c.generateSignature(fmt.Sprintf("GET\n%s\n%s", path, params.Encode()))

	req, err := http.NewRequest("GET", c.BaseURL+path+"?"+params.Encode(), nil)
	if err != nil {
		return nil, err
	}

	req.Header.Set("X-JFIN-API-Key", c.APIKey)
	req.Header.Set("X-JFIN-API-Signature", signature)

	resp, err := c.client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}

	var result struct {
		Result int `json:"result"`
		Orders []struct {
			OrderID   int64   `json:"id"`
			Symbol    string  `json:"symbol"`
			Side      string  `json:"side"`
			Type      string  `json:"type"`
			Price     float64 `json:"price"`
			Quantity  float64 `json:"quantity"`
			Filled    float64 `json:"filled"`
			Remaining float64 `json:"remaining"`
			Status    string  `json:"status"`
		} `json:"orders"`
		Error string `json:"error,omitempty"`
	}

	if err := json.Unmarshal(body, &result); err != nil {
		return nil, err
	}

	if result.Result != 0 {
		return nil, fmt.Errorf("API error: %s", result.Error)
	}

	orders := make([]Order, len(result.Orders))
	for i, o := range result.Orders {
		orders[i] = Order{
			OrderID:   o.OrderID,
			Symbol:    o.Symbol,
			Side:      o.Side,
			Type:      o.Type,
			Price:     o.Price,
			Quantity:  o.Quantity,
			Filled:    o.Filled,
			Remaining: o.Remaining,
			Status:    o.Status,
		}
	}

	return orders, nil
}
