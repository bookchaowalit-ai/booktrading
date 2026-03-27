package exchange

import (
	"context"
	"fmt"
	"log"
	"sync"
	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/adapter/database"
	"trading-bot-system/backend/internal/adapter/exchange/bitkub"
)

// ExchangeManager manages multiple exchange connections
type ExchangeManager struct {
	mu               sync.RWMutex
	currentProvider  config.ExchangeProvider
	binanceAdapter   *BinanceAdapter
	binanceTHAdapter *BinanceTHAdapter
	bitkubClient     *bitkub.Client
	apiKeys          map[string]*config.ExchangeAPIKey
	dbRepo           *database.APIKeyRepository
}

// Balance represents exchange balance
type Balance struct {
	Currency  string  `json:"currency"`
	Free      float64 `json:"free"`
	Locked    float64 `json:"locked"`
	Total     float64 `json:"total"`
}

// ExchangeInfo represents exchange information
type ExchangeInfo struct {
	Provider    string     `json:"provider"`
	Name        string     `json:"name"`
	NameTH      string     `json:"name_th"`
	Connected   bool       `json:"connected"`
	Testnet     bool       `json:"testnet"`
	Balances    []Balance  `json:"balances,omitempty"`
}

// NewExchangeManager creates a new exchange manager
func NewExchangeManager(cfg *config.ExchangeConfig, dbRepo *database.APIKeyRepository) *ExchangeManager {
	manager := &ExchangeManager{
		currentProvider: cfg.Provider,
		apiKeys:         cfg.APIKeys,
		dbRepo:          dbRepo,
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
			
			// Initialize adapters based on loaded keys
			switch key.Provider {
			case string(config.ExchangeBinance):
				manager.binanceAdapter = NewBinanceAdapter(key.APIKey, key.APISecret, key.UseTestnet)
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
			log.Printf("Note: Could not delete from database: %v", err)
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

// GetBinanceTHBalances gets balances from Binance Thailand
func (m *ExchangeManager) getBinanceTHBalances(ctx context.Context) ([]Balance, error) {
	if m.binanceTHAdapter == nil {
		return nil, fmt.Errorf("Binance TH adapter not initialized")
	}
	return m.binanceTHAdapter.GetBalances(ctx)
}

// GetBinanceBalances gets balances from Binance
func (m *ExchangeManager) getBinanceBalances(ctx context.Context) ([]Balance, error) {
	// TODO: Implement actual Binance balance fetching
	// For now, return empty balances
	return []Balance{}, nil
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
