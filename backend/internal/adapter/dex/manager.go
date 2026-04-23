package dex

import (
	"context"
	"fmt"
	"math/big"
	"sync"

	"github.com/ethereum/go-ethereum/common"
	"github.com/ethereum/go-ethereum/core/types"
	"github.com/ethereum/go-ethereum/ethclient"
	"github.com/jackc/pgx/v5/pgxpool"

	"trading-bot-system/backend/internal/config"
	"trading-bot-system/backend/internal/logger"
)

// Signer defines the interface for transaction signing
type Signer interface {
	GetAddress() common.Address
	GetClient() *ethclient.Client
	GetChainID() *big.Int
	SignTransaction(ctx context.Context, tx *types.Transaction) (*types.Transaction, error)
	SendTransaction(ctx context.Context, signedTx *types.Transaction) error
}

// DEXManager manages multiple DEX connections
type DEXManager struct {
	mu              sync.RWMutex
	pool            *pgxpool.Pool
	cfg             *config.DexConfig
	client          *ethclient.Client
	chainID         *big.Int
	providers       map[config.DEXProvider]Provider
	currentProvider config.DEXProvider
	chainConfig     *config.ChainConfig
	signer          Signer
}

// NewDEXManager creates a new DEX manager
func NewDEXManager(pool *pgxpool.Pool, cfg *config.DexConfig) *DEXManager {
	return &DEXManager{
		pool:            pool,
		cfg:             cfg,
		providers:       make(map[config.DEXProvider]Provider),
		currentProvider: cfg.DefaultDEX,
	}
}

// Initialize connects to the blockchain and initializes DEX providers
func (m *DEXManager) Initialize(ctx context.Context) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if !m.cfg.Enabled {
		logger.Info("DEX trading is disabled, skipping initialization")
		return nil
	}

	chainCfg, ok := m.cfg.Chains[m.cfg.DefaultChain]
	if !ok {
		return fmt.Errorf("chain configuration not found for chain ID %d", m.cfg.DefaultChain)
	}
	m.chainConfig = chainCfg

	client, err := ethclient.DialContext(ctx, chainCfg.RPCURL)
	if err != nil {
		return fmt.Errorf("failed to connect to blockchain RPC: %w", err)
	}
	m.client = client
	m.chainID = big.NewInt(int64(chainCfg.ChainID))

	m.initProviders()

	logger.Info("DEX manager initialized",
		"chain", chainCfg.Name,
		"chain_id", chainCfg.ChainID,
		"default_dex", m.cfg.DefaultDEX,
		"providers", len(m.providers),
	)

	return nil
}

func (m *DEXManager) initProviders() {
	for providerName, routerCfg := range m.cfg.DEXRouters {
		var provider Provider

		switch providerName {
		case config.DEXUniswapV2:
			provider = NewUniswapV2Provider(m.client, routerCfg, m.chainID)
		case config.DEXUniswapV3:
			provider = NewUniswapV3Provider(m.client, routerCfg, m.chainID)
		case config.DEXPancakeSwap:
			provider = NewPancakeSwapProvider(m.client, routerCfg, m.chainID)
		default:
			logger.Warn("unsupported DEX provider", "provider", providerName)
			continue
		}

		m.providers[providerName] = provider
		logger.Info("Initialized DEX provider", "provider", providerName)
	}
}

// GetProvider returns a specific DEX provider
func (m *DEXManager) GetProvider(name config.DEXProvider) (Provider, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	provider, ok := m.providers[name]
	if !ok {
		return nil, fmt.Errorf("DEX provider not found: %s", name)
	}
	return provider, nil
}

// GetCurrentProvider returns the current active DEX provider
func (m *DEXManager) GetCurrentProvider() (Provider, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	provider, ok := m.providers[m.currentProvider]
	if !ok {
		return nil, fmt.Errorf("current DEX provider not found: %s", m.currentProvider)
	}
	return provider, nil
}

// SetCurrentProvider sets the current active DEX provider
func (m *DEXManager) SetCurrentProvider(name config.DEXProvider) error {
	m.mu.Lock()
	defer m.mu.Unlock()

	if _, ok := m.providers[name]; !ok {
		return fmt.Errorf("DEX provider not available: %s", name)
	}

	m.currentProvider = name
	logger.Info("Switched DEX provider", "provider", name)
	return nil
}

// GetQuote returns a quote for a token swap using the current provider
func (m *DEXManager) GetQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.GetQuote(ctx, tokenIn, tokenOut, amountIn, slippagePct)
}

// GetBestQuote queries all providers and returns the best quote
func (m *DEXManager) GetBestQuote(ctx context.Context, tokenIn, tokenOut string, amountIn *big.Int, slippagePct float64) (*Quote, error) {
	m.mu.RLock()
	defer m.mu.RUnlock()

	var bestQuote *Quote

	for name, provider := range m.providers {
		quote, err := provider.GetQuote(ctx, tokenIn, tokenOut, amountIn, slippagePct)
		if err != nil {
			logger.Debug("Provider returned error", "provider", name, "error", err)
			continue
		}

		if bestQuote == nil || quote.AmountOut.Cmp(bestQuote.AmountOut) > 0 {
			bestQuote = quote
			bestQuote.DEXProvider = string(name)
		}
	}

	if bestQuote == nil {
		return nil, fmt.Errorf("no provider could return a valid quote")
	}

	return bestQuote, nil
}

// Swap executes a token swap
func (m *DEXManager) Swap(ctx context.Context, params *SwapParams) (*SwapResult, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.Swap(ctx, params)
}

// GetLiquidityPools returns all LP positions
func (m *DEXManager) GetLiquidityPools(ctx context.Context, userAddress string) ([]LiquidityPosition, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.GetLiquidityPools(ctx, userAddress)
}

// AddLiquidity adds liquidity
func (m *DEXManager) AddLiquidity(ctx context.Context, params *AddLiquidityParams) (*SwapResult, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.AddLiquidity(ctx, params)
}

// RemoveLiquidity removes liquidity
func (m *DEXManager) RemoveLiquidity(ctx context.Context, params *RemoveLiquidityParams) (*SwapResult, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.RemoveLiquidity(ctx, params)
}

// GetPoolReserves returns reserves for a pool
func (m *DEXManager) GetPoolReserves(ctx context.Context, poolAddress string) (*big.Int, *big.Int, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, nil, err
	}
	return provider.GetPoolReserves(ctx, poolAddress)
}

// EstimateGas estimates gas
func (m *DEXManager) EstimateGas(ctx context.Context, to string, data []byte) (*GasEstimate, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.EstimateGas(ctx, to, data)
}

// GetTokenBalance returns ERC20 token balance
func (m *DEXManager) GetTokenBalance(ctx context.Context, tokenAddress, userAddress string) (*big.Int, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.GetTokenBalance(ctx, tokenAddress, userAddress)
}

// GetNativeBalance returns native token balance
func (m *DEXManager) GetNativeBalance(ctx context.Context, userAddress string) (*big.Int, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.GetNativeBalance(ctx, userAddress)
}

// GetTokenInfo returns token info
func (m *DEXManager) GetTokenInfo(ctx context.Context, tokenAddress string) (*Token, error) {
	provider, err := m.GetCurrentProvider()
	if err != nil {
		return nil, err
	}
	return provider.GetTokenInfo(ctx, tokenAddress)
}

// GetClient returns the Ethereum client
func (m *DEXManager) GetClient() *ethclient.Client {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.client
}

// GetChainID returns the chain ID
func (m *DEXManager) GetChainID() *big.Int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.chainID
}

// GetChainConfig returns the chain config
func (m *DEXManager) GetChainConfig() *config.ChainConfig {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.chainConfig
}

// SetSigner sets the transaction signer and propagates to all providers
func (m *DEXManager) SetSigner(s Signer) {
	m.mu.Lock()
	defer m.mu.Unlock()
	m.signer = s
	for _, provider := range m.providers {
		provider.SetSigner(s)
	}
}

// GetSigner returns the transaction signer
func (m *DEXManager) GetSigner() Signer {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.signer
}

// GetConfig returns DEX config
func (m *DEXManager) GetConfig() *config.DexConfig {
	return m.cfg
}

// ListProviders returns available providers
func (m *DEXManager) ListProviders() []config.DEXProvider {
	m.mu.RLock()
	defer m.mu.RUnlock()

	providers := make([]config.DEXProvider, 0, len(m.providers))
	for name := range m.providers {
		providers = append(providers, name)
	}
	return providers
}

// IsEnabled returns whether DEX is enabled
func (m *DEXManager) IsEnabled() bool {
	return m.cfg.Enabled
}

// Close closes the client
func (m *DEXManager) Close() {
	if m.client != nil {
		m.client.Close()
	}
}
