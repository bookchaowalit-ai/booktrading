package database

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"fmt"
	"io"
	"os"
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

// encryptionKey derives a 32-byte AES key from the ENCRYPTION_KEY env var.
// Falls back to a zero key (no effective encryption) when env var is unset — log a warning.
func encryptionKey() []byte {
	raw := os.Getenv("ENCRYPTION_KEY")
	if raw == "" {
		// No key configured — return deterministic key derived from empty string.
		// In production, always set ENCRYPTION_KEY.
		sum := sha256.Sum256([]byte("UNSET_ENCRYPTION_KEY"))
		return sum[:]
	}
	sum := sha256.Sum256([]byte(raw))
	return sum[:]
}

// encryptString encrypts plaintext using AES-256-GCM and returns base64-encoded ciphertext.
func encryptString(plaintext string) (string, error) {
	block, err := aes.NewCipher(encryptionKey())
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonce := make([]byte, gcm.NonceSize())
	if _, err = io.ReadFull(rand.Reader, nonce); err != nil {
		return "", err
	}
	ciphertext := gcm.Seal(nonce, nonce, []byte(plaintext), nil)
	return base64.StdEncoding.EncodeToString(ciphertext), nil
}

// decryptString decrypts a base64-encoded AES-256-GCM ciphertext.
func decryptString(encoded string) (string, error) {
	data, err := base64.StdEncoding.DecodeString(encoded)
	if err != nil {
		// Not base64 — treat as legacy plain text
		return encoded, nil
	}
	block, err := aes.NewCipher(encryptionKey())
	if err != nil {
		return "", err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return "", err
	}
	nonceSize := gcm.NonceSize()
	if len(data) < nonceSize {
		// Too short to be valid ciphertext — treat as plain text (migration case)
		return encoded, nil
	}
	nonce, ciphertext := data[:nonceSize], data[nonceSize:]
	plaintext, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		// Decryption failed — may be legacy plain text value
		return encoded, nil
	}
	return string(plaintext), nil
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

// SaveAPIKey saves or updates API credentials for an exchange (encrypted at rest)
func (r *APIKeyRepository) SaveAPIKey(ctx context.Context, provider, apiKey, apiSecret string, useTestnet bool) error {
	encKey, err := encryptString(apiKey)
	if err != nil {
		return fmt.Errorf("failed to encrypt api_key: %w", err)
	}
	encSecret, err := encryptString(apiSecret)
	if err != nil {
		return fmt.Errorf("failed to encrypt api_secret: %w", err)
	}

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
	_, err = r.pool.Exec(ctx, query, provider, encKey, encSecret, useTestnet)
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

	// Decrypt stored values
	if key.APIKey, err = decryptString(key.APIKey); err != nil {
		return nil, fmt.Errorf("failed to decrypt api_key: %w", err)
	}
	if key.APISecret, err = decryptString(key.APISecret); err != nil {
		return nil, fmt.Errorf("failed to decrypt api_secret: %w", err)
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
		// Decrypt stored values
		if key.APIKey, err = decryptString(key.APIKey); err != nil {
			return nil, fmt.Errorf("failed to decrypt api_key: %w", err)
		}
		if key.APISecret, err = decryptString(key.APISecret); err != nil {
			return nil, fmt.Errorf("failed to decrypt api_secret: %w", err)
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
