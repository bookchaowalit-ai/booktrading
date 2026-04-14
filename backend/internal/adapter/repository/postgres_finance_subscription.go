package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceSubscriptionRepository implements FinanceSubscriptionRepository with PostgreSQL
type PostgresFinanceSubscriptionRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceSubscriptionRepository creates a new PostgreSQL finance subscription repository
func NewPostgresFinanceSubscriptionRepository(pool *pgxpool.Pool) repository.FinanceSubscriptionRepository {
	return &PostgresFinanceSubscriptionRepository{pool: pool}
}

func (r *PostgresFinanceSubscriptionRepository) Create(ctx context.Context, subscription *model.FinanceSubscription) error {
	if subscription.ID == "" {
		subscription.ID = uuid.New().String()
	}
	now := time.Now()
	subscription.CreatedAt = now
	subscription.UpdatedAt = now

	query := `
		INSERT INTO finance_subscriptions (
			id, user_id, name, description, amount, currency, billing_cycle,
			next_billing_date, last_billing_date, account_id, category_id,
			provider, is_active, reminder_days, color, icon, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
	`
	_, err := r.pool.Exec(ctx, query,
		subscription.ID, subscription.UserID, subscription.Name, subscription.Description,
		subscription.Amount, subscription.Currency, subscription.BillingCycle,
		subscription.NextBillingDate, subscription.LastBillingDate, subscription.AccountID,
		subscription.CategoryID, subscription.Provider, subscription.IsActive,
		subscription.ReminderDays, subscription.Color, subscription.Icon,
		subscription.CreatedAt, subscription.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceSubscriptionRepository) GetByID(ctx context.Context, id string) (*model.FinanceSubscription, error) {
	query := `
		SELECT id, user_id, name, description, amount, currency, billing_cycle,
			next_billing_date, last_billing_date, account_id, category_id,
			provider, is_active, reminder_days, color, icon, created_at, updated_at
		FROM finance_subscriptions WHERE id = $1
	`
	subscription := &model.FinanceSubscription{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&subscription.ID, &subscription.UserID, &subscription.Name, &subscription.Description,
		&subscription.Amount, &subscription.Currency, &subscription.BillingCycle,
		&subscription.NextBillingDate, &subscription.LastBillingDate, &subscription.AccountID,
		&subscription.CategoryID, &subscription.Provider, &subscription.IsActive,
		&subscription.ReminderDays, &subscription.Color, &subscription.Icon,
		&subscription.CreatedAt, &subscription.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return subscription, nil
}

func (r *PostgresFinanceSubscriptionRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceSubscription, error) {
	query := `
		SELECT id, user_id, name, description, amount, currency, billing_cycle,
			next_billing_date, last_billing_date, account_id, category_id,
			provider, is_active, reminder_days, color, icon, created_at, updated_at
		FROM finance_subscriptions WHERE user_id = $1
		ORDER BY next_billing_date ASC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanSubscriptions(rows)
}

func (r *PostgresFinanceSubscriptionRepository) GetActive(ctx context.Context, userID string) ([]*model.FinanceSubscription, error) {
	query := `
		SELECT id, user_id, name, description, amount, currency, billing_cycle,
			next_billing_date, last_billing_date, account_id, category_id,
			provider, is_active, reminder_days, color, icon, created_at, updated_at
		FROM finance_subscriptions WHERE user_id = $1 AND is_active = true
		ORDER BY next_billing_date ASC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanSubscriptions(rows)
}

func (r *PostgresFinanceSubscriptionRepository) GetUpcoming(ctx context.Context, userID string, days int) ([]*model.FinanceSubscription, error) {
	query := `
		SELECT id, user_id, name, description, amount, currency, billing_cycle,
			next_billing_date, last_billing_date, account_id, category_id,
			provider, is_active, reminder_days, color, icon, created_at, updated_at
		FROM finance_subscriptions
		WHERE user_id = $1 AND is_active = true
			AND next_billing_date IS NOT NULL
			AND next_billing_date <= $2
		ORDER BY next_billing_date ASC
	`
	rows, err := r.pool.Query(ctx, query, userID, time.Now().AddDate(0, 0, days))
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanSubscriptions(rows)
}

func (r *PostgresFinanceSubscriptionRepository) Update(ctx context.Context, subscription *model.FinanceSubscription) error {
	subscription.UpdatedAt = time.Now()
	query := `
		UPDATE finance_subscriptions SET
			name = $2, description = $3, amount = $4, currency = $5, billing_cycle = $6,
			next_billing_date = $7, last_billing_date = $8, account_id = $9, category_id = $10,
			provider = $11, is_active = $12, reminder_days = $13, color = $14, icon = $15, updated_at = $16
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		subscription.ID, subscription.Name, subscription.Description, subscription.Amount,
		subscription.Currency, subscription.BillingCycle, subscription.NextBillingDate,
		subscription.LastBillingDate, subscription.AccountID, subscription.CategoryID,
		subscription.Provider, subscription.IsActive, subscription.ReminderDays,
		subscription.Color, subscription.Icon, subscription.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceSubscriptionRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_subscriptions WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

func (r *PostgresFinanceSubscriptionRepository) GetTotalMonthly(ctx context.Context, userID string) (float64, error) {
	query := `
		SELECT COALESCE(SUM(
			CASE
				WHEN billing_cycle = 'weekly' THEN amount * 4
				WHEN billing_cycle = 'monthly' THEN amount
				WHEN billing_cycle = 'quarterly' THEN amount / 3
				WHEN billing_cycle = 'yearly' THEN amount / 12
				ELSE amount
			END
		), 0) as total
		FROM finance_subscriptions WHERE user_id = $1 AND is_active = true
	`
	var total float64
	err := r.pool.QueryRow(ctx, query, userID).Scan(&total)
	return total, err
}

func (r *PostgresFinanceSubscriptionRepository) scanSubscriptions(rows pgx.Rows) ([]*model.FinanceSubscription, error) {
	var subscriptions []*model.FinanceSubscription
	for rows.Next() {
		subscription := &model.FinanceSubscription{}
		err := rows.Scan(
			&subscription.ID, &subscription.UserID, &subscription.Name, &subscription.Description,
			&subscription.Amount, &subscription.Currency, &subscription.BillingCycle,
			&subscription.NextBillingDate, &subscription.LastBillingDate, &subscription.AccountID,
			&subscription.CategoryID, &subscription.Provider, &subscription.IsActive,
			&subscription.ReminderDays, &subscription.Color, &subscription.Icon,
			&subscription.CreatedAt, &subscription.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		subscriptions = append(subscriptions, subscription)
	}
	return subscriptions, rows.Err()
}
