package exchange

import (
	"context"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"strconv"
	"sync"
	"time"
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

	log.Printf("Binance TH balance request: GET %s", reqURL)
	log.Printf("Binance TH balance headers: API-Key=%s...", b.apiKey[:8])

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

	log.Printf("Binance TH balances response: %s", string(body))

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
		MakerCommission  int `json:"makerCommission"`
		TakerCommission  int `json:"takerCommission"`
		BuyerCommission  int `json:"buyerCommission"`
		SellerCommission int `json:"sellerCommission"`
		CanTrade         bool `json:"canTrade"`
		CanWithdraw      bool `json:"canWithdraw"`
		CanDeposit       bool `json:"canDeposit"`
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
		}
	}

	return balances, nil
}

// Connect establishes connection (Binance TH doesn't use WebSocket for account data)
func (b *BinanceTHAdapter) Connect(ctx context.Context) error {
	log.Println("Binance TH adapter initialized (REST API only)")
	return nil
}

// Disconnect closes the connection
func (b *BinanceTHAdapter) Disconnect(ctx context.Context) error {
	return nil
}
