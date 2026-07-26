package exchange

import (
	"context"
	"fmt"
	"sync"
	"time"
	"trading-bot-system/backend/internal/adapter/database"
	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/logger"
)

// ExchangeManager manages multiple exchange connections
type ExchangeManager struct {
	mu               sync.RWMutex
	currentProvider  config.ExchangeProvider
	binanceAdapter   *BinanceAdapter
	binanceExecutor  *BinanceOrderExecutor
	binanceTHAdapter *BinanceTHAdapter
	bitkubClient     *bitkub.Client
	apiKeys          map[string]*config.ExchangeAPIKey
	dbRepo           *database.APIKeyRepository
}

// Balance represents exchange balance
type Balance struct {
	Currency string  `json:"currency"`
	Free     float64 `json:"free"`
	Locked   float64 `json:"locked"`
	Total    float64 `json:"total"`
}

// TickerInfo represents ticker data
type TickerInfo struct {
	Symbol    string  `json:"symbol"`
	LastPrice float64 `json:"lastPrice"`
	HighPrice float64 `json:"highPrice,omitempty"`
	LowPrice  float64 `json:"lowPrice,omitempty"`
	Volume    float64 `json:"volume,omitempty"`
}

// ExchangeInfo represents exchange information
type ExchangeInfo struct {
	Provider  string    `json:"provider"`
	Name      string    `json:"name"`
	NameTH    string    `json:"name_th"`
	Connected bool      `json:"connected"`
	Testnet   bool      `json:"testnet"`
	Balances  []Balance `json:"balances,omitempty"`
}

// NewExchangeManager creates a new exchange manager
func NewExchangeManager(cfg *config.ExchangeConfig, dbRepo *database.APIKeyRepository) *ExchangeManager {
	manager := &ExchangeManager{
		currentProvider: cfg.Provider,
		apiKeys:         cfg.APIKeys,
		dbRepo:          dbRepo,
	}

	// Initialize adapters from env config keys first
	for provider, key := range cfg.APIKeys {
		if key.Enabled && key.APIKey != "" {
			switch provider {
			case string(config.ExchangeBinance):
				manager.binanceAdapter = NewBinanceAdapter(key.APIKey, key.APISecret, key.UseTestnet)
				manager.binanceExecutor = NewBinanceOrderExecutor(key.APIKey, key.APISecret, key.UseTestnet)
			case string(config.ExchangeBinanceTH):
				manager.binanceTHAdapter = NewBinanceTHAdapter(key.APIKey, key.APISecret)
			case string(config.ExchangeBitkub):
				manager.bitkubClient = bitkub.NewClient(key.APIKey, key.APISecret, key.UseTestnet)
			}
		}
	}

	// Load API keys from database and override config
	ctx := context.Background()
	dbKeys, err := dbRepo.GetAllAPIKeys(ctx)
	if err == nil && len(dbKeys) > 0 {
		for _, key := range dbKeys {
			manager.apiKeys[key.Provider] = &config.ExchangeAPIKey{
				APIKey:     key.APIKey,
				APISecret:  key.APISecret,
				UseTestnet: key.UseTestnet,
				Enabled:    true,
			}

			// Initialize adapters based on loaded keys (override env config)
			switch key.Provider {
			case string(config.ExchangeBinance):
				manager.binanceAdapter = NewBinanceAdapter(key.APIKey, key.APISecret, key.UseTestnet)
				manager.binanceExecutor = NewBinanceOrderExecutor(key.APIKey, key.APISecret, key.UseTestnet)
			case string(config.ExchangeBinanceTH):
				manager.binanceTHAdapter = NewBinanceTHAdapter(key.APIKey, key.APISecret)
			case string(config.ExchangeBitkub):
				manager.bitkubClient = bitkub.NewClient(key.APIKey, key.APISecret, key.UseTestnet)
			}
		}
	}

	return manager
}

// GetCurrentProvider returns the current exchange provider
func (m *ExchangeManager) GetCurrentProvider() config.ExchangeProvider {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.currentProvider
}

// SetCurrentProvider sets the current exchange provider
func (m *ExchangeManager) SetCurrentProvider(provider config.ExchangeProvider) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Check if we have credentials for this provider
	if _, ok := m.apiKeys[string(provider)]; !ok {
		return fmt.Errorf("no API credentials configured for provider: %s", provider)
	}

	m.currentProvider = provider
	return nil
}

// ConfigureExchange configures API keys for an exchange provider
func (m *ExchangeManager) ConfigureExchange(provider, apiKey, apiSecret string, useTestnet bool) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Save to database
	if m.dbRepo != nil {
		if err := m.dbRepo.SaveAPIKey(context.Background(), provider, apiKey, apiSecret, useTestnet); err != nil {
			return fmt.Errorf("failed to save to database: %w", err)
		}
	}

	// Create or update API key configuration in memory
	m.apiKeys[provider] = &config.ExchangeAPIKey{
		APIKey:     apiKey,
		APISecret:  apiSecret,
		UseTestnet: useTestnet,
		Enabled:    true,
	}

	// Re-initialize the appropriate adapter based on provider
	switch config.ExchangeProvider(provider) {
	case config.ExchangeBinance:
		m.binanceAdapter = NewBinanceAdapter(apiKey, apiSecret, useTestnet)
		m.binanceExecutor = NewBinanceOrderExecutor(apiKey, apiSecret, useTestnet)
	case config.ExchangeBinanceTH:
		m.binanceTHAdapter = NewBinanceTHAdapter(apiKey, apiSecret)
	case config.ExchangeBitkub:
		m.bitkubClient = bitkub.NewClient(apiKey, apiSecret, useTestnet)
	}

	return nil
}

// DeleteExchange deletes API keys for an exchange provider
func (m *ExchangeManager) DeleteExchange(provider string) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	// Delete from database
	if m.dbRepo != nil {
		if err := m.dbRepo.DeleteAPIKey(context.Background(), provider); err != nil {
			// Don't fail if key doesn't exist in database
			logger.Info("Could not delete API key from database", "provider", provider, "error", err)
		}
	}

	// Remove from memory
	delete(m.apiKeys, provider)

	// Reset the appropriate adapter based on provider
	switch config.ExchangeProvider(provider) {
	case config.ExchangeBinance:
		m.binanceAdapter = nil
	case config.ExchangeBitkub:
		m.bitkubClient = nil
	}

	return nil
}

// StoredAPIKeyInfo represents masked API key info for display
type StoredAPIKeyInfo struct {
	ID        string `json:"id"`
	Exchange  string `json:"exchange"`
	APIKey    string `json:"apiKey"`
	APISecret string `json:"apiSecret"`
	Testnet   bool   `json:"testnet"`
	IsActive  bool   `json:"isActive"`
	CreatedAt string `json:"createdAt"`
}

// maskSecret returns first 4 chars + "****" for display
func maskSecret(s string) string {
	if len(s) <= 4 {
		return "****"
	}
	return s[:4] + "****"
}

// GetStoredAPIKeyInfos returns masked API key info from the database
func (m *ExchangeManager) GetStoredAPIKeyInfos(ctx context.Context) ([]StoredAPIKeyInfo, error) {
	if m.dbRepo == nil {
		return []StoredAPIKeyInfo{}, nil
	}
	keys, err := m.dbRepo.GetAllAPIKeys(ctx)
	if err != nil {
		return []StoredAPIKeyInfo{}, nil
	}
	result := make([]StoredAPIKeyInfo, 0, len(keys))
	for _, k := range keys {
		result = append(result, StoredAPIKeyInfo{
			ID:        k.Provider,
			Exchange:  k.Provider,
			APIKey:    maskSecret(k.APIKey),
			APISecret: maskSecret(k.APISecret),
			Testnet:   k.UseTestnet,
			IsActive:  true,
			CreatedAt: k.CreatedAt.Format("2006-01-02T15:04:05Z"),
		})
	}
	return result, nil
}

// GetSupportedExchanges returns list of supported exchanges with their status
func (m *ExchangeManager) GetSupportedExchanges() []ExchangeInfo {
	m.mu.RLock()
	defer m.mu.RUnlock()

	// Check if Binance credentials exist
	binanceKey, hasBinance := m.apiKeys[string(config.ExchangeBinance)]
	binanceConnected := m.binanceAdapter != nil && hasBinance && binanceKey.Enabled
	binanceTestnet := false
	if hasBinance {
		binanceTestnet = binanceKey.UseTestnet
	}

	// Check if Binance TH credentials exist
	binanceTHKey, hasBinanceTH := m.apiKeys[string(config.ExchangeBinanceTH)]
	binanceTHConnected := m.binanceTHAdapter != nil && hasBinanceTH && binanceTHKey.Enabled
	binanceTHTestnet := false
	if hasBinanceTH {
		binanceTHTestnet = false // Binance TH doesn't have testnet
	}

	// Check if Bitkub credentials exist
	bitkubKey, hasBitkub := m.apiKeys[string(config.ExchangeBitkub)]
	bitkubConnected := m.bitkubClient != nil && hasBitkub && bitkubKey.Enabled
	bitkubTestnet := false
	if hasBitkub {
		bitkubTestnet = bitkubKey.UseTestnet
	}

	exchanges := []ExchangeInfo{
		{
			Provider:  string(config.ExchangeBinance),
			Name:      "Binance (Global)",
			NameTH:    "ไบแนนซ์ (ทั่วโลก)",
			Connected: binanceConnected,
			Testnet:   binanceTestnet,
		},
		{
			Provider:  string(config.ExchangeBinanceTH),
			Name:      "Binance TH (Thailand)",
			NameTH:    "ไบแนนซ์ ไทยแลนด์",
			Connected: binanceTHConnected,
			Testnet:   binanceTHTestnet,
		},
		{
			Provider:  string(config.ExchangeBitkub),
			Name:      "Bitkub",
			NameTH:    "บิทคับ",
			Connected: bitkubConnected,
			Testnet:   bitkubTestnet,
		},
	}

	return exchanges
}

// GetBalances returns balances for the current exchange
func (m *ExchangeManager) GetBalances(ctx context.Context) ([]Balance, error) {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinance:
		return m.getBinanceBalances(ctx)
	case config.ExchangeBinanceTH:
		return m.getBinanceTHBalances(ctx)
	case config.ExchangeBitkub:
		return m.getBitkubBalances()
	default:
		return nil, fmt.Errorf("unsupported exchange: %s", provider)
	}
}

// PlaceOrder places an order on the current exchange
func (m *ExchangeManager) PlaceOrder(ctx context.Context, symbol string, side string, quantity float64, price float64) (interface{}, error) {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinance:
		return m.placeBinanceOrder(ctx, symbol, side, quantity, price)
	case config.ExchangeBinanceTH:
		return m.placeBinanceTHOrder(ctx, symbol, side, quantity, price)
	case config.ExchangeBitkub:
		return m.placeBitkubOrder(symbol, side, quantity, price)
	default:
		return nil, fmt.Errorf("unsupported exchange: %s", provider)
	}
}

// GetTicker returns ticker info for a symbol from the current exchange
func (m *ExchangeManager) GetTicker(ctx context.Context, symbol string) (*TickerInfo, error) {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinance:
		return m.getBinanceTicker(ctx, symbol)
	case config.ExchangeBinanceTH:
		return m.getBinanceTHTicker(ctx, symbol)
	case config.ExchangeBitkub:
		return m.getBitkubTicker(symbol)
	default:
		return nil, fmt.Errorf("unsupported exchange: %s", provider)
	}
}

// GetBinanceTHBalances gets balances from Binance Thailand
func (m *ExchangeManager) getBinanceTHBalances(ctx context.Context) ([]Balance, error) {
	if m.binanceTHAdapter == nil {
		return nil, fmt.Errorf("Binance TH adapter not initialized")
	}
	return m.binanceTHAdapter.GetBalances(ctx)
}

// GetBinanceTHTicker gets ticker from Binance Thailand
func (m *ExchangeManager) getBinanceTHTicker(ctx context.Context, symbol string) (*TickerInfo, error) {
	if m.binanceTHAdapter == nil {
		return nil, fmt.Errorf("Binance TH adapter not initialized")
	}
	return m.binanceTHAdapter.GetTicker(ctx, symbol)
}

// GetBinanceBalances gets balances from Binance
func (m *ExchangeManager) getBinanceBalances(ctx context.Context) ([]Balance, error) {
	if m.binanceAdapter == nil {
		return nil, fmt.Errorf("Binance adapter not initialized")
	}
	return m.binanceAdapter.GetBalances(ctx)
}

// GetBinanceTicker gets ticker from Binance
func (m *ExchangeManager) getBinanceTicker(ctx context.Context, symbol string) (*TickerInfo, error) {
	if m.binanceAdapter == nil {
		return nil, fmt.Errorf("Binance adapter not initialized")
	}
	return m.binanceAdapter.GetTicker(ctx, symbol)
}

// GetBitkubBalances gets balances from Bitkub
func (m *ExchangeManager) getBitkubBalances() ([]Balance, error) {
	if m.bitkubClient == nil {
		return nil, fmt.Errorf("Bitkub client not initialized")
	}

	// Get balances from Bitkub API
	balances, err := m.bitkubClient.GetBalances()
	if err != nil {
		return nil, fmt.Errorf("failed to get Bitkub balances: %w", err)
	}

	result := make([]Balance, 0, len(balances))
	for _, b := range balances {
		result = append(result, Balance{
			Currency: b.Currency,
			Free:     b.Available,
			Locked:   b.Amount - b.Available,
			Total:    b.Amount,
		})
	}

	return result, nil
}

// GetBitkubTicker gets ticker from Bitkub
func (m *ExchangeManager) getBitkubTicker(symbol string) (*TickerInfo, error) {
	if m.bitkubClient == nil {
		return nil, fmt.Errorf("Bitkub client not initialized")
	}
	ticker, err := m.bitkubClient.GetTicker(symbol)
	if err != nil {
		return nil, err
	}
	return &TickerInfo{
		Symbol:    symbol,
		LastPrice: ticker.LastPrice,
		HighPrice: ticker.High24h,
		LowPrice:  ticker.Low24h,
		Volume:    ticker.Volume24h,
	}, nil
}

// placeBinanceOrder places a REAL order on Binance Global via the order executor
func (m *ExchangeManager) placeBinanceOrder(ctx context.Context, symbol string, side string, quantity float64, price float64) (interface{}, error) {
	if m.binanceExecutor == nil {
		return nil, fmt.Errorf("Binance order executor not initialized — configure API keys first")
	}

	// Determine order type
	orderType := model.OrderTypeMarket
	if price > 0 {
		orderType = model.OrderTypeLimit
	}

	order := &model.Order{
		ID:       fmt.Sprintf("real_%d", time.Now().UnixNano()),
		Symbol:   model.TradeSymbol(symbol),
		Side:     model.OrderSide(side),
		Type:     orderType,
		Quantity: quantity,
		Price:    price,
	}

	result, err := m.binanceExecutor.PlaceOrder(ctx, order)
	if err != nil {
		return nil, fmt.Errorf("Binance order failed: %w", err)
	}

	return result, nil
}

// placeBinanceTHOrder places an order on Binance Thailand
func (m *ExchangeManager) placeBinanceTHOrder(ctx context.Context, symbol string, side string, quantity float64, price float64) (interface{}, error) {
	if m.binanceTHAdapter == nil {
		return nil, fmt.Errorf("Binance TH adapter not initialized")
	}

	// Determine order type
	orderType := "MARKET"
	timeInForce := ""

	if price > 0 {
		orderType = "LIMIT"
		timeInForce = "GTC" // Good Til Canceled
	}

	return m.binanceTHAdapter.PlaceOrder(ctx, symbol, side, orderType, quantity, price, timeInForce)
}

// GetOpenOrders gets all open orders for the current exchange
func (m *ExchangeManager) GetOpenOrders(ctx context.Context, symbol string) (interface{}, error) {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinance:
		return nil, fmt.Errorf("Binance open orders not yet implemented")
	case config.ExchangeBinanceTH:
		if m.binanceTHAdapter == nil {
			return nil, fmt.Errorf("Binance TH adapter not initialized")
		}
		return m.binanceTHAdapter.GetOpenOrders(ctx, symbol)
	case config.ExchangeBitkub:
		return nil, fmt.Errorf("Bitkub open orders not yet implemented")
	default:
		return nil, fmt.Errorf("unsupported exchange: %s", provider)
	}
}

// CancelOrder cancels an order on the current exchange
func (m *ExchangeManager) CancelOrder(ctx context.Context, symbol string, orderID int64) error {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinanceTH:
		if m.binanceTHAdapter == nil {
			return fmt.Errorf("Binance TH adapter not initialized")
		}
		return m.binanceTHAdapter.CancelOrder(ctx, symbol, orderID)
	default:
		return fmt.Errorf("cancel order not supported for exchange: %s", provider)
	}
}

// GetOrderStatus queries a single order's current status on the current exchange
func (m *ExchangeManager) GetOrderStatus(ctx context.Context, symbol string, orderID int64) (*Order, error) {
	m.mu.RLock()
	provider := m.currentProvider
	m.mu.RUnlock()

	switch provider {
	case config.ExchangeBinanceTH:
		if m.binanceTHAdapter == nil {
			return nil, fmt.Errorf("Binance TH adapter not initialized")
		}
		return m.binanceTHAdapter.GetOrderStatus(ctx, symbol, orderID)
	default:
		return nil, fmt.Errorf("order status not supported for exchange: %s", provider)
	}
}

// placeBitkubOrder places an order on Bitkub
func (m *ExchangeManager) placeBitkubOrder(symbol string, side string, quantity float64, price float64) (interface{}, error) {
	if m.bitkubClient == nil {
		return nil, fmt.Errorf("Bitkub client not initialized")
	}
	return m.bitkubClient.PlaceOrder(symbol, side, "LIMIT", quantity, price)
}

// Connect connects to the current exchange WebSocket
func (m *ExchangeManager) Connect(ctx context.Context) error {
	m.mu.RLock()
	provider := m.currentProvider
	adapter := m.binanceAdapter
	m.mu.RUnlock()

	if provider == config.ExchangeBinance && adapter != nil {
		return adapter.Connect(ctx)
	}

	return nil
}

// Disconnect disconnects from the current exchange WebSocket
func (m *ExchangeManager) Disconnect(ctx context.Context) error {
	m.mu.RLock()
	provider := m.currentProvider
	adapter := m.binanceAdapter
	m.mu.RUnlock()

	if provider == config.ExchangeBinance && adapter != nil {
		return adapter.Disconnect(ctx)
	}

	return nil
}
