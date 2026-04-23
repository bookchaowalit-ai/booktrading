package config

import (
	"fmt"
	"os"
	"strconv"
	"time"
)

// ExchangeProvider represents supported exchange providers
type ExchangeProvider string

const (
	ExchangeBinance   ExchangeProvider = "binance"
	ExchangeBinanceTH ExchangeProvider = "binance_th"
	ExchangeBitkub    ExchangeProvider = "bitkub"
	ExchangeSatangPro ExchangeProvider = "satangpro"
)

// DEXProvider represents supported DEX providers
type DEXProvider string

const (
	DEXUniswapV2   DEXProvider = "uniswap_v2"
	DEXUniswapV3   DEXProvider = "uniswap_v3"
	DEXPancakeSwap DEXProvider = "pancakeswap"
	DEXSushiSwap   DEXProvider = "sushiswap"
)

// ChainID represents supported EVM chains
type ChainID int64

const (
	ChainEthereum ChainID = 1
	ChainArbitrum ChainID = 42161
	ChainBase     ChainID = 8453
	ChainOptimism ChainID = 10
	ChainBSC      ChainID = 56
	ChainPolygon  ChainID = 137
)

// ChainConfig holds chain-specific configuration
type ChainConfig struct {
	ChainID        ChainID `json:"chain_id"`
	Name           string  `json:"name"`
	NativeCurrency string  `json:"native_currency"`
	RPCURL         string  `json:"rpc_url"`
	ExplorerURL    string  `json:"explorer_url"`
	IsTestnet      bool    `json:"is_testnet"`
}

// DEXRouterConfig holds DEX router contract addresses
type DEXRouterConfig struct {
	Provider        DEXProvider `json:"provider"`
	RouterAddress   string      `json:"router_address"`
	FactoryAddress  string      `json:"factory_address"`
	QuoterAddress   string      `json:"quoter_address"`   // V3 only
	PositionManager string      `json:"position_manager"` // V3 only
}

// WalletConfig holds wallet configuration
type WalletConfig struct {
	PrivateKeyEncrypted string `json:"private_key_encrypted"`
	Address             string `json:"address"`
	CreatedAt           string `json:"created_at"`
}

// DexConfig holds DEX/AMM configuration
type DexConfig struct {
	Enabled        bool                             `json:"enabled"`
	DefaultChain   ChainID                          `json:"default_chain"`
	DefaultDEX     DEXProvider                      `json:"default_dex"`
	Chains         map[ChainID]*ChainConfig         `json:"chains"`
	DEXRouters     map[DEXProvider]*DEXRouterConfig `json:"dex_routers"`
	SlippagePct    float64                          `json:"slippage_pct"`     // Default slippage tolerance (e.g., 0.5 = 0.5%)
	GasLimit       uint64                           `json:"gas_limit"`        // Max gas limit per transaction
	MaxPriceImpact float64                          `json:"max_price_impact"` // Max price impact warning threshold (e.g., 3.0 = 3%)
}

// ExchangeAPIKey represents API credentials for an exchange
type ExchangeAPIKey struct {
	APIKey     string `json:"api_key"`
	APISecret  string `json:"api_secret"`
	UseTestnet bool   `json:"use_testnet"`
	Enabled    bool   `json:"enabled"`
}

// Config holds all configuration for the application
type Config struct {
	Server    ServerConfig
	Redis     RedisConfig
	Exchange  ExchangeConfig
	Dex       DexConfig
	WebSocket WebSocketConfig
	GRPC      GRPCConfig
	Database  DatabaseConfig
}

// ServerConfig holds HTTP server configuration
type ServerConfig struct {
	Port         string
	ReadTimeout  time.Duration
	WriteTimeout time.Duration
	// TLS configuration (optional — if both are set, server uses HTTPS)
	TLSCertFile string
	TLSKeyFile  string
}

// RedisConfig holds Redis configuration
type RedisConfig struct {
	Host     string
	Port     string
	Password string
	DB       int
}

// ExchangeConfig holds exchange API configuration
type ExchangeConfig struct {
	Provider ExchangeProvider           `json:"provider"`
	APIKeys  map[string]*ExchangeAPIKey `json:"api_keys"` // Map by provider
}

// WebSocketConfig holds WebSocket server configuration
type WebSocketConfig struct {
	Port           string
	MaxClients     int
	BroadcastQueue int
}

// GRPCConfig holds gRPC server configuration
type GRPCConfig struct {
	Port string
}

// DatabaseConfig holds database configuration
type DatabaseConfig struct {
	Host     string
	Port     string
	User     string
	Password string
	DBName   string
	SSLMode  string
}

// LoadConfig loads configuration from environment variables
func LoadConfig() *Config {
	// Initialize API keys map
	apiKeys := make(map[string]*ExchangeAPIKey)

	// Load Binance credentials
	binanceKey := getEnv("BINANCE_API_KEY", "")
	binanceSecret := getEnv("BINANCE_API_SECRET", "")
	if binanceKey != "" {
		apiKeys[string(ExchangeBinance)] = &ExchangeAPIKey{
			APIKey:     binanceKey,
			APISecret:  binanceSecret,
			UseTestnet: getEnv("BINANCE_USE_TESTNET", "true") == "true",
			Enabled:    true,
		}
	}

	// Load Binance TH credentials
	binanceTHKey := getEnv("BINANCE_TH_API_KEY", "")
	binanceTHSecret := getEnv("BINANCE_TH_API_SECRET", "")
	if binanceTHKey != "" {
		apiKeys[string(ExchangeBinanceTH)] = &ExchangeAPIKey{
			APIKey:     binanceTHKey,
			APISecret:  binanceTHSecret,
			UseTestnet: false,
			Enabled:    true,
		}
	}

	// Load Bitkub credentials
	bitkubKey := getEnv("BITKUB_API_KEY", "")
	bitkubSecret := getEnv("BITKUB_API_SECRET", "")
	if bitkubKey != "" {
		apiKeys[string(ExchangeBitkub)] = &ExchangeAPIKey{
			APIKey:     bitkubKey,
			APISecret:  bitkubSecret,
			UseTestnet: getEnv("BITKUB_USE_TESTNET", "false") == "true",
			Enabled:    true,
		}
	}

	// Determine default provider (use first available)
	defaultProvider := ExchangeBinance
	if binanceKey == "" && binanceTHKey != "" {
		defaultProvider = ExchangeBinanceTH
	} else if binanceKey == "" && bitkubKey != "" {
		defaultProvider = ExchangeBitkub
	}

	return &Config{
		Server: ServerConfig{
			Port:         getEnv("SERVER_PORT", "8080"),
			ReadTimeout:  getEnvDuration("SERVER_READ_TIMEOUT", 30*time.Second),
			WriteTimeout: getEnvDuration("SERVER_WRITE_TIMEOUT", 30*time.Second),
			TLSCertFile:  getEnv("TLS_CERT_FILE", ""),
			TLSKeyFile:   getEnv("TLS_KEY_FILE", ""),
		},
		Redis: RedisConfig{
			Host:     getEnv("REDIS_HOST", "localhost"),
			Port:     getEnv("REDIS_PORT", "6379"),
			Password: getEnv("REDIS_PASSWORD", ""),
			DB:       getEnvInt("REDIS_DB", 0),
		},
		Exchange: ExchangeConfig{
			Provider: ExchangeProvider(getEnv("EXCHANGE_PROVIDER", string(defaultProvider))),
			APIKeys:  apiKeys,
		},
		Dex: DexConfig{
			Enabled:        getEnv("DEX_ENABLED", "false") == "true",
			DefaultChain:   ChainID(getEnvInt("DEX_CHAIN_ID", 42161)), // Arbitrum default
			DefaultDEX:     DEXProvider(getEnv("DEX_PROVIDER", "uniswap_v3")),
			SlippagePct:    getEnvFloat("DEX_SLIPPAGE_PCT", 0.5),
			GasLimit:       uint64(getEnvInt("DEX_GAS_LIMIT", 500000)),
			MaxPriceImpact: getEnvFloat("DEX_MAX_PRICE_IMPACT", 3.0),
			Chains: map[ChainID]*ChainConfig{
				ChainEthereum: {
					ChainID:        ChainEthereum,
					Name:           "Ethereum",
					NativeCurrency: "ETH",
					RPCURL:         getEnv("ETH_RPC_URL", "https://eth.llamarpc.com"),
					ExplorerURL:    "https://etherscan.io",
					IsTestnet:      false,
				},
				ChainArbitrum: {
					ChainID:        ChainArbitrum,
					Name:           "Arbitrum One",
					NativeCurrency: "ETH",
					RPCURL:         getEnv("ARBITRUM_RPC_URL", "https://arb1.arbitrum.io/rpc"),
					ExplorerURL:    "https://arbiscan.io",
					IsTestnet:      false,
				},
				ChainBase: {
					ChainID:        ChainBase,
					Name:           "Base",
					NativeCurrency: "ETH",
					RPCURL:         getEnv("BASE_RPC_URL", "https://mainnet.base.org"),
					ExplorerURL:    "https://basescan.org",
					IsTestnet:      false,
				},
				ChainBSC: {
					ChainID:        ChainBSC,
					Name:           "BNB Smart Chain",
					NativeCurrency: "BNB",
					RPCURL:         getEnv("BSC_RPC_URL", "https://bsc-dataseed.binance.org"),
					ExplorerURL:    "https://bscscan.com",
					IsTestnet:      false,
				},
			},
			DEXRouters: map[DEXProvider]*DEXRouterConfig{
				DEXUniswapV2: {
					Provider:       DEXUniswapV2,
					RouterAddress:  "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D",
					FactoryAddress: "0x5C69bEe701ef814a2B6a3EDD4B1652CB9cc5aA6f",
				},
				DEXUniswapV3: {
					Provider:        DEXUniswapV3,
					RouterAddress:   "0xE592427A0AEce92De3Edee1F18E0157C05861564", // SwapRouter
					FactoryAddress:  "0x1F98431c8aD98523631AE4a59f267346ea31F984",
					QuoterAddress:   "0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6",
					PositionManager: "0xC36442b4a4522E871399CD717aBDD847Ab11FE88",
				},
				DEXPancakeSwap: {
					Provider:       DEXPancakeSwap,
					RouterAddress:  "0x10ED43C718714eb63d5aA57B78B54704E256024E",
					FactoryAddress: "0xcA143Ce32Fe78f1f7019d7d551a6402fC5350c73",
				},
				DEXSushiSwap: {
					Provider:       DEXSushiSwap,
					RouterAddress:  "0xd9e1cE17f2641f24aE83637ab66a2cca9C378B9F",
					FactoryAddress: "0xC0AEe478e3658e2610c5F7A4A2E1777cE9e4f2Ac",
				},
			},
		},
		WebSocket: WebSocketConfig{
			Port:           getEnv("WS_PORT", "8081"),
			MaxClients:     getEnvInt("WS_MAX_CLIENTS", 100),
			BroadcastQueue: getEnvInt("WS_BROADCAST_QUEUE", 100),
		},
		GRPC: GRPCConfig{
			Port: getEnv("GRPC_PORT", "9000"),
		},
		Database: DatabaseConfig{
			Host:     getEnv("DATABASE_HOST", "localhost"),
			Port:     getEnv("DATABASE_PORT", "5432"),
			User:     getEnv("DATABASE_USER", "trading"),
			Password: getEnv("DATABASE_PASSWORD", ""),
			DBName:   getEnv("DATABASE_NAME", "trading_bot"),
			SSLMode:  getEnv("DATABASE_SSLMODE", "disable"),
		},
	}
}

// Validate checks that all required configuration values are set.
// Returns an error if any required value is missing.
func (c *Config) Validate() error {
	if c.Database.Password == "" {
		return fmt.Errorf("DATABASE_PASSWORD is required — set a secure password before starting the application")
	}
	if c.Redis.Password == "" {
		return fmt.Errorf("REDIS_PASSWORD is required — set a secure password before starting the application")
	}
	return nil
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvInt(key string, defaultValue int) int {
	if value := os.Getenv(key); value != "" {
		if intValue, err := strconv.Atoi(value); err == nil {
			return intValue
		}
	}
	return defaultValue
}

func getEnvFloat(key string, defaultValue float64) float64 {
	if value := os.Getenv(key); value != "" {
		if floatValue, err := strconv.ParseFloat(value, 64); err == nil {
			return floatValue
		}
	}
	return defaultValue
}

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}
