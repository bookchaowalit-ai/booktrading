package repository

import (
	"context"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
)

// APIKeyRepository handles API key database operations
type APIKeyRepository struct {
	pool *pgxpool.Pool
}

// NewAPIKeyRepository creates a new API key repository
func NewAPIKeyRepository(pool *pgxpool.Pool) *APIKeyRepository {
	return &APIKeyRepository{
		pool: pool,
	}
}

// Save saves or updates an API key
func (r *APIKeyRepository) Save(ctx context.Context, apiKey *model.APIKey) error {
	query := `
		INSERT INTO api_keys (id, user_id, exchange, api_key, api_secret, passphrase, testnet, is_active)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
		ON CONFLICT (id) DO UPDATE SET
			api_key = EXCLUDED.api_key,
			api_secret = EXCLUDED.api_secret,
			passphrase = EXCLUDED.passphrase,
			testnet = EXCLUDED.testnet,
			is_active = EXCLUDED.is_active,
			updated_at = NOW()
	`

	_, err := r.pool.Exec(ctx, query,
		apiKey.ID,
		apiKey.UserID,
		apiKey.Exchange,
		apiKey.APIKey,
		apiKey.APISecret,
		apiKey.Passphrase,
		apiKey.Testnet,
		apiKey.IsActive,
	)

	return err
}

// GetByUser returns all API keys for a user
func (r *APIKeyRepository) GetByUser(ctx context.Context, userID string) ([]model.APIKey, error) {
	query := `
		SELECT id, user_id, exchange, api_key, api_secret, passphrase, testnet, is_active, 
		       created_at, updated_at, last_used_at
		FROM api_keys
		WHERE user_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`

	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var apiKeys []model.APIKey
	for rows.Next() {
		var key model.APIKey
		err := rows.Scan(
			&key.ID, &key.UserID, &key.Exchange, &key.APIKey, &key.APISecret,
			&key.Passphrase, &key.Testnet, &key.IsActive, &key.CreatedAt,
			&key.UpdatedAt, &key.LastUsedAt,
		)
		if err != nil {
			return nil, err
		}
		apiKeys = append(apiKeys, key)
	}

	return apiKeys, nil
}

// GetByExchange returns API key for a specific exchange
func (r *APIKeyRepository) GetByExchange(ctx context.Context, userID, exchange string) (*model.APIKey, error) {
	query := `
		SELECT id, user_id, exchange, api_key, api_secret, passphrase, testnet, is_active, 
		       created_at, updated_at, last_used_at
		FROM api_keys
		WHERE user_id = $1 AND exchange = $2 AND is_active = true
		LIMIT 1
	`

	var key model.APIKey
	err := r.pool.QueryRow(ctx, query, userID, exchange).Scan(
		&key.ID, &key.UserID, &key.Exchange, &key.APIKey, &key.APISecret,
		&key.Passphrase, &key.Testnet, &key.IsActive, &key.CreatedAt,
		&key.UpdatedAt, &key.LastUsedAt,
	)

	if err != nil {
		return nil, err
	}

	return &key, nil
}

// UpdateLastUsed updates the last used timestamp
func (r *APIKeyRepository) UpdateLastUsed(ctx context.Context, id string) error {
	query := `UPDATE api_keys SET last_used_at = NOW() WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

// Delete soft-deletes an API key
func (r *APIKeyRepository) Delete(ctx context.Context, id string) error {
	query := `UPDATE api_keys SET is_active = false WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}
