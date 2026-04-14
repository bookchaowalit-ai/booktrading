package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
)

// UserPreferences represents user settings stored in database
type UserPreferences struct {
	ID                          int       `json:"id"`
	UserID                      string    `json:"user_id"`
	Language                    string    `json:"language"`
	Theme                       string    `json:"theme"`
	NotificationsTradeExecutions bool     `json:"notifications_trade_executions"`
	NotificationsPriceAlerts    bool     `json:"notifications_price_alerts"`
	NotificationsBotStatus      bool     `json:"notifications_bot_status"`
	NotificationsErrors         bool     `json:"notifications_errors"`
	CreatedAt                   time.Time `json:"created_at"`
	UpdatedAt                   time.Time `json:"updated_at"`
}

// UserPreferencesRepository handles user preferences storage
type UserPreferencesRepository struct {
	pool *pgxpool.Pool
}

// NewUserPreferencesRepository creates a new preferences repository
func NewUserPreferencesRepository(pool *pgxpool.Pool) *UserPreferencesRepository {
	return &UserPreferencesRepository{
		pool: pool,
	}
}

// GetPreferences retrieves user preferences
func (r *UserPreferencesRepository) GetPreferences(ctx context.Context, userID string) (*UserPreferences, error) {
	query := `
		SELECT id, user_id, language, theme, 
		       notifications_trade_executions, notifications_price_alerts,
		       notifications_bot_status, notifications_errors,
		       created_at, updated_at
		FROM user_preferences
		WHERE user_id = $1
		LIMIT 1
	`
	
	var prefs UserPreferences
	err := r.pool.QueryRow(ctx, query, userID).Scan(
		&prefs.ID,
		&prefs.UserID,
		&prefs.Language,
		&prefs.Theme,
		&prefs.NotificationsTradeExecutions,
		&prefs.NotificationsPriceAlerts,
		&prefs.NotificationsBotStatus,
		&prefs.NotificationsErrors,
		&prefs.CreatedAt,
		&prefs.UpdatedAt,
	)
	
	if err != nil {
		return nil, fmt.Errorf("failed to get preferences: %w", err)
	}
	
	return &prefs, nil
}

// UpdatePreferences updates user preferences
func (r *UserPreferencesRepository) UpdatePreferences(ctx context.Context, prefs *UserPreferences) error {
	query := `
		INSERT INTO user_preferences 
			(user_id, language, theme, 
			 notifications_trade_executions, notifications_price_alerts,
			 notifications_bot_status, notifications_errors,
			 updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
		ON CONFLICT (user_id) 
		DO UPDATE SET
			language = $2,
			theme = $3,
			notifications_trade_executions = $4,
			notifications_price_alerts = $5,
			notifications_bot_status = $6,
			notifications_errors = $7,
			updated_at = NOW()
	`
	
	_, err := r.pool.Exec(ctx, query,
		prefs.UserID,
		prefs.Language,
		prefs.Theme,
		prefs.NotificationsTradeExecutions,
		prefs.NotificationsPriceAlerts,
		prefs.NotificationsBotStatus,
		prefs.NotificationsErrors,
	)
	
	if err != nil {
		return fmt.Errorf("failed to update preferences: %w", err)
	}
	
	return nil
}

// ResetPreferences resets preferences to defaults
func (r *UserPreferencesRepository) ResetPreferences(ctx context.Context, userID string) error {
	query := `
		UPDATE user_preferences
		SET 
			language = 'en',
			theme = 'system',
			notifications_trade_executions = true,
			notifications_price_alerts = false,
			notifications_bot_status = true,
			notifications_errors = true,
			updated_at = NOW()
		WHERE user_id = $1
	`
	
	_, err := r.pool.Exec(ctx, query, userID)
	if err != nil {
		return fmt.Errorf("failed to reset preferences: %w", err)
	}
	
	return nil
}
