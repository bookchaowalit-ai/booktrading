package repository

import (
	"context"
	"encoding/json"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresNetWorthHistoryRepository implements NetWorthHistoryRepository with PostgreSQL
type PostgresNetWorthHistoryRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresNetWorthHistoryRepository creates a new PostgreSQL net worth history repository
func NewPostgresNetWorthHistoryRepository(pool *pgxpool.Pool) repository.NetWorthHistoryRepository {
	return &PostgresNetWorthHistoryRepository{pool: pool}
}

func (r *PostgresNetWorthHistoryRepository) Create(ctx context.Context, history *model.NetWorthHistory) error {
	now := time.Now()
	history.CreatedAt = now

	var breakdownJSON []byte
	if history.Breakdown != nil {
		breakdownJSON, _ = json.Marshal(history.Breakdown)
	}

	query := `
		INSERT INTO finance_net_worth_history (
			user_id, date, total_assets, total_liabilities, net_worth, breakdown, created_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7)
		RETURNING id
	`
	err := r.pool.QueryRow(ctx, query,
		history.UserID, history.Date, history.TotalAssets, history.TotalLiabilities,
		history.NetWorth, breakdownJSON, history.CreatedAt,
	).Scan(&history.ID)
	return err
}

func (r *PostgresNetWorthHistoryRepository) GetByUserID(ctx context.Context, userID string, limit int) ([]*model.NetWorthHistory, error) {
	query := `
		SELECT id, user_id, date, total_assets, total_liabilities, net_worth, breakdown, created_at
		FROM finance_net_worth_history WHERE user_id = $1
		ORDER BY date DESC
		LIMIT $2
	`
	rows, err := r.pool.Query(ctx, query, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanNetWorthHistory(rows)
}

func (r *PostgresNetWorthHistoryRepository) GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.NetWorthHistory, error) {
	query := `
		SELECT id, user_id, date, total_assets, total_liabilities, net_worth, breakdown, created_at
		FROM finance_net_worth_history WHERE user_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanNetWorthHistory(rows)
}

func (r *PostgresNetWorthHistoryRepository) GetLatest(ctx context.Context, userID string) (*model.NetWorthHistory, error) {
	query := `
		SELECT id, user_id, date, total_assets, total_liabilities, net_worth, breakdown, created_at
		FROM finance_net_worth_history WHERE user_id = $1
		ORDER BY date DESC LIMIT 1
	`
	history := &model.NetWorthHistory{}
	var breakdownJSON []byte
	err := r.pool.QueryRow(ctx, query, userID).Scan(
		&history.ID, &history.UserID, &history.Date, &history.TotalAssets,
		&history.TotalLiabilities, &history.NetWorth, &breakdownJSON, &history.CreatedAt,
	)
	if err != nil {
		return nil, err
	}

	if len(breakdownJSON) > 0 {
		var breakdown model.NetWorthBreakdown
		json.Unmarshal(breakdownJSON, &breakdown)
		history.Breakdown = &breakdown
	}

	return history, nil
}

func (r *PostgresNetWorthHistoryRepository) GetForMonth(ctx context.Context, userID string, month time.Time) (*model.NetWorthHistory, error) {
	startOfMonth := time.Date(month.Year(), month.Month(), 1, 0, 0, 0, 0, month.Location())
	endOfMonth := startOfMonth.AddDate(0, 1, 0)

	query := `
		SELECT id, user_id, date, total_assets, total_liabilities, net_worth, breakdown, created_at
		FROM finance_net_worth_history WHERE user_id = $1 AND date >= $2 AND date < $3
		ORDER BY date DESC LIMIT 1
	`
	history := &model.NetWorthHistory{}
	var breakdownJSON []byte
	err := r.pool.QueryRow(ctx, query, userID, startOfMonth, endOfMonth).Scan(
		&history.ID, &history.UserID, &history.Date, &history.TotalAssets,
		&history.TotalLiabilities, &history.NetWorth, &breakdownJSON, &history.CreatedAt,
	)
	if err != nil {
		return nil, err
	}

	if len(breakdownJSON) > 0 {
		var breakdown model.NetWorthBreakdown
		json.Unmarshal(breakdownJSON, &breakdown)
		history.Breakdown = &breakdown
	}

	return history, nil
}

func (r *PostgresNetWorthHistoryRepository) DeleteOlderThan(ctx context.Context, userID string, before time.Time) error {
	query := `DELETE FROM finance_net_worth_history WHERE user_id = $1 AND date < $2`
	_, err := r.pool.Exec(ctx, query, userID, before)
	return err
}

func (r *PostgresNetWorthHistoryRepository) scanNetWorthHistory(rows pgx.Rows) ([]*model.NetWorthHistory, error) {
	var histories []*model.NetWorthHistory
	for rows.Next() {
		history := &model.NetWorthHistory{}
		var breakdownJSON []byte
		err := rows.Scan(
			&history.ID, &history.UserID, &history.Date, &history.TotalAssets,
			&history.TotalLiabilities, &history.NetWorth, &breakdownJSON, &history.CreatedAt,
		)
		if err != nil {
			return nil, err
		}

		if len(breakdownJSON) > 0 {
			var breakdown model.NetWorthBreakdown
			json.Unmarshal(breakdownJSON, &breakdown)
			history.Breakdown = &breakdown
		}

		histories = append(histories, history)
	}
	return histories, rows.Err()
}

// PostgresRecurringTransactionRepository implements RecurringTransactionRepository with PostgreSQL
type PostgresRecurringTransactionRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresRecurringTransactionRepository creates a new PostgreSQL recurring transaction repository
func NewPostgresRecurringTransactionRepository(pool *pgxpool.Pool) repository.RecurringTransactionRepository {
	return &PostgresRecurringTransactionRepository{pool: pool}
}

func (r *PostgresRecurringTransactionRepository) Create(ctx context.Context, recurring *model.RecurringTransaction) error {
	if recurring.ID == "" {
		recurring.ID = uuid.New().String()
	}
	now := time.Now()
	recurring.CreatedAt = now
	recurring.UpdatedAt = now

	query := `
		INSERT INTO finance_recurring_transactions (
			id, user_id, account_id, category_id, type, amount, currency,
			description, payee, frequency, start_date, end_date, next_occurrence,
			last_occurrence, is_active, auto_create, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18)
	`
	_, err := r.pool.Exec(ctx, query,
		recurring.ID, recurring.UserID, recurring.AccountID, recurring.CategoryID,
		recurring.Type, recurring.Amount, recurring.Currency, recurring.Description,
		recurring.Payee, recurring.Frequency, recurring.StartDate, recurring.EndDate,
		recurring.NextOccurrence, recurring.LastOccurrence, recurring.IsActive,
		recurring.AutoCreate, recurring.CreatedAt, recurring.UpdatedAt,
	)
	return err
}

func (r *PostgresRecurringTransactionRepository) GetByID(ctx context.Context, id string) (*model.RecurringTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, frequency, start_date, end_date, next_occurrence,
			last_occurrence, is_active, auto_create, created_at, updated_at
		FROM finance_recurring_transactions WHERE id = $1
	`
	recurring := &model.RecurringTransaction{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&recurring.ID, &recurring.UserID, &recurring.AccountID, &recurring.CategoryID,
		&recurring.Type, &recurring.Amount, &recurring.Currency, &recurring.Description,
		&recurring.Payee, &recurring.Frequency, &recurring.StartDate, &recurring.EndDate,
		&recurring.NextOccurrence, &recurring.LastOccurrence, &recurring.IsActive,
		&recurring.AutoCreate, &recurring.CreatedAt, &recurring.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return recurring, nil
}

func (r *PostgresRecurringTransactionRepository) GetByUserID(ctx context.Context, userID string) ([]*model.RecurringTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, frequency, start_date, end_date, next_occurrence,
			last_occurrence, is_active, auto_create, created_at, updated_at
		FROM finance_recurring_transactions WHERE user_id = $1
		ORDER BY next_occurrence ASC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanRecurringTransactions(rows)
}

func (r *PostgresRecurringTransactionRepository) GetActive(ctx context.Context, userID string) ([]*model.RecurringTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, frequency, start_date, end_date, next_occurrence,
			last_occurrence, is_active, auto_create, created_at, updated_at
		FROM finance_recurring_transactions WHERE user_id = $1 AND is_active = true
		ORDER BY next_occurrence ASC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanRecurringTransactions(rows)
}

func (r *PostgresRecurringTransactionRepository) GetDueForProcessing(ctx context.Context, before time.Time) ([]*model.RecurringTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, frequency, start_date, end_date, next_occurrence,
			last_occurrence, is_active, auto_create, created_at, updated_at
		FROM finance_recurring_transactions
		WHERE is_active = true AND auto_create = true AND next_occurrence <= $1
		ORDER BY next_occurrence ASC
	`
	rows, err := r.pool.Query(ctx, query, before)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanRecurringTransactions(rows)
}

func (r *PostgresRecurringTransactionRepository) Update(ctx context.Context, recurring *model.RecurringTransaction) error {
	recurring.UpdatedAt = time.Now()
	query := `
		UPDATE finance_recurring_transactions SET
			account_id = $2, category_id = $3, type = $4, amount = $5, currency = $6,
			description = $7, payee = $8, frequency = $9, start_date = $10, end_date = $11,
			next_occurrence = $12, last_occurrence = $13, is_active = $14, auto_create = $15, updated_at = $16
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		recurring.ID, recurring.AccountID, recurring.CategoryID, recurring.Type,
		recurring.Amount, recurring.Currency, recurring.Description, recurring.Payee,
		recurring.Frequency, recurring.StartDate, recurring.EndDate,
		recurring.NextOccurrence, recurring.LastOccurrence, recurring.IsActive,
		recurring.AutoCreate, recurring.UpdatedAt,
	)
	return err
}

func (r *PostgresRecurringTransactionRepository) UpdateAfterProcessing(ctx context.Context, id string, lastOccurrence, nextOccurrence time.Time) error {
	query := `
		UPDATE finance_recurring_transactions SET
			last_occurrence = $1, next_occurrence = $2, updated_at = $3
		WHERE id = $4
	`
	_, err := r.pool.Exec(ctx, query, lastOccurrence, nextOccurrence, time.Now(), id)
	return err
}

func (r *PostgresRecurringTransactionRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_recurring_transactions WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

func (r *PostgresRecurringTransactionRepository) scanRecurringTransactions(rows pgx.Rows) ([]*model.RecurringTransaction, error) {
	var recurrings []*model.RecurringTransaction
	for rows.Next() {
		recurring := &model.RecurringTransaction{}
		err := rows.Scan(
			&recurring.ID, &recurring.UserID, &recurring.AccountID, &recurring.CategoryID,
			&recurring.Type, &recurring.Amount, &recurring.Currency, &recurring.Description,
			&recurring.Payee, &recurring.Frequency, &recurring.StartDate, &recurring.EndDate,
			&recurring.NextOccurrence, &recurring.LastOccurrence, &recurring.IsActive,
			&recurring.AutoCreate, &recurring.CreatedAt, &recurring.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		recurrings = append(recurrings, recurring)
	}
	return recurrings, rows.Err()
}
