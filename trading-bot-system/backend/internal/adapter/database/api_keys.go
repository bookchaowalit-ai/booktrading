package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// ExchangeAPIKey represents stored API credentials
type ExchangeAPIKey struct {
	Provider   string
	APIKey     string
	APISecret  string
	UseTestnet bool
	CreatedAt  time.Time
	UpdatedAt  time.Time
}

// APIKeyRepository handles API key storage
type APIKeyRepository struct {
	pool *pgxpool.Pool
}

// NewAPIKeyRepository creates a new API key repository
func NewAPIKeyRepository(pool *pgxpool.Pool) *APIKeyRepository {
	return &APIKeyRepository{
		pool: pool,
	}
}

// SaveAPIKey saves or updates API credentials for an exchange
func (r *APIKeyRepository) SaveAPIKey(ctx context.Context, provider, apiKey, apiSecret string, useTestnet bool) error {
	query := `
		INSERT INTO exchange_api_keys (provider, api_key, api_secret, use_testnet, updated_at)
		VALUES ($1, $2, $3, $4, NOW())
		ON CONFLICT (provider) 
		DO UPDATE SET 
			api_key = $2,
			api_secret = $3,
			use_testnet = $4,
			updated_at = NOW()
	`
	_, err := r.pool.Exec(ctx, query, provider, apiKey, apiSecret, useTestnet)
	if err != nil {
		return fmt.Errorf("failed to save API key: %w", err)
	}
	return nil
}

// GetAPIKey retrieves API credentials for an exchange
func (r *APIKeyRepository) GetAPIKey(ctx context.Context, provider string) (*ExchangeAPIKey, error) {
	query := `
		SELECT provider, api_key, api_secret, use_testnet, created_at, updated_at
		FROM exchange_api_keys
		WHERE provider = $1
	`
	
	var key ExchangeAPIKey
	err := r.pool.QueryRow(ctx, query, provider).Scan(
		&key.Provider,
		&key.APIKey,
		&key.APISecret,
		&key.UseTestnet,
		&key.CreatedAt,
		&key.UpdatedAt,
	)
	if err != nil {
		return nil, fmt.Errorf("failed to get API key: %w", err)
	}
	
	return &key, nil
}

// GetAllAPIKeys retrieves all stored API credentials
func (r *APIKeyRepository) GetAllAPIKeys(ctx context.Context) ([]ExchangeAPIKey, error) {
	query := `
		SELECT provider, api_key, api_secret, use_testnet, created_at, updated_at
		FROM exchange_api_keys
		ORDER BY provider
	`
	
	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, fmt.Errorf("failed to get API keys: %w", err)
	}
	defer rows.Close()
	
	var keys []ExchangeAPIKey
	for rows.Next() {
		var key ExchangeAPIKey
		err := rows.Scan(
			&key.Provider,
			&key.APIKey,
			&key.APISecret,
			&key.UseTestnet,
			&key.CreatedAt,
			&key.UpdatedAt,
		)
		if err != nil {
			return nil, fmt.Errorf("failed to scan API key: %w", err)
		}
		keys = append(keys, key)
	}
	
	return keys, nil
}

// DeleteAPIKey deletes API credentials for an exchange
func (r *APIKeyRepository) DeleteAPIKey(ctx context.Context, provider string) error {
	query := `DELETE FROM exchange_api_keys WHERE provider = $1`
	_, err := r.pool.Exec(ctx, query, provider)
	if err != nil {
		return fmt.Errorf("failed to delete API key: %w", err)
	}
	return nil
}
