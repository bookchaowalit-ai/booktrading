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

// ExchangeAPIKey represents API credentials for an exchange
type ExchangeAPIKey struct {
	APIKey    string `json:"api_key"`
	APISecret string `json:"api_secret"`
	UseTestnet bool  `json:"use_testnet"`
	Enabled   bool   `json:"enabled"`
}

// Config holds all configuration for the application
type Config struct {
	Server    ServerConfig
	Redis     RedisConfig
	Exchange  ExchangeConfig
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
	Provider      ExchangeProvider     `json:"provider"`
	APIKeys       map[string]*ExchangeAPIKey `json:"api_keys"` // Map by provider
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

func getEnvDuration(key string, defaultValue time.Duration) time.Duration {
	if value := os.Getenv(key); value != "" {
		if duration, err := time.ParseDuration(value); err == nil {
			return duration
		}
	}
	return defaultValue
}
