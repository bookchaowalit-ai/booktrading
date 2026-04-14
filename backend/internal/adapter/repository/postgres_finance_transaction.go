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

// PostgresFinanceTransactionRepository implements FinanceTransactionRepository with PostgreSQL
type PostgresFinanceTransactionRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceTransactionRepository creates a new PostgreSQL finance transaction repository
func NewPostgresFinanceTransactionRepository(pool *pgxpool.Pool) repository.FinanceTransactionRepository {
	return &PostgresFinanceTransactionRepository{pool: pool}
}

// Create stores a new finance transaction
func (r *PostgresFinanceTransactionRepository) Create(ctx context.Context, transaction *model.FinanceTransaction) error {
	if transaction.ID == "" {
		transaction.ID = uuid.New().String()
	}
	now := time.Now()
	transaction.CreatedAt = now
	transaction.UpdatedAt = now

	query := `
		INSERT INTO finance_transactions (
			id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17, $18, $19)
	`
	_, err := r.pool.Exec(ctx, query,
		transaction.ID, transaction.UserID, transaction.AccountID, transaction.CategoryID,
		transaction.Type, transaction.Amount, transaction.Currency, transaction.Description,
		transaction.Payee, transaction.Date, transaction.IsRecurring, transaction.RecurringID,
		transaction.Tags, transaction.Attachments, transaction.Latitude, transaction.Longitude,
		transaction.LocationName, transaction.CreatedAt, transaction.UpdatedAt,
	)
	return err
}

// GetByID retrieves a finance transaction by ID
func (r *PostgresFinanceTransactionRepository) GetByID(ctx context.Context, id string) (*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE id = $1
	`
	transaction := &model.FinanceTransaction{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&transaction.ID, &transaction.UserID, &transaction.AccountID, &transaction.CategoryID,
		&transaction.Type, &transaction.Amount, &transaction.Currency, &transaction.Description,
		&transaction.Payee, &transaction.Date, &transaction.IsRecurring, &transaction.RecurringID,
		&transaction.Tags, &transaction.Attachments, &transaction.Latitude, &transaction.Longitude,
		&transaction.LocationName, &transaction.CreatedAt, &transaction.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return transaction, nil
}

// GetByUserID retrieves all finance transactions for a user with pagination
func (r *PostgresFinanceTransactionRepository) GetByUserID(ctx context.Context, userID string, limit, offset int) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE user_id = $1
		ORDER BY date DESC
		LIMIT $2 OFFSET $3
	`
	rows, err := r.pool.Query(ctx, query, userID, limit, offset)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetByAccountID retrieves transactions for an account
func (r *PostgresFinanceTransactionRepository) GetByAccountID(ctx context.Context, accountID string, limit int) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE account_id = $1
		ORDER BY date DESC
		LIMIT $2
	`
	rows, err := r.pool.Query(ctx, query, accountID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetByCategoryID retrieves transactions by category within a date range
func (r *PostgresFinanceTransactionRepository) GetByCategoryID(ctx context.Context, categoryID string, startDate, endDate time.Time) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE category_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date DESC
	`
	rows, err := r.pool.Query(ctx, query, categoryID, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetByDateRange retrieves transactions within a date range
func (r *PostgresFinanceTransactionRepository) GetByDateRange(ctx context.Context, userID string, startDate, endDate time.Time) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE user_id = $1 AND date >= $2 AND date <= $3
		ORDER BY date DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// GetByType retrieves transactions by type within a date range
func (r *PostgresFinanceTransactionRepository) GetByType(ctx context.Context, userID string, transactionType model.TransactionType, startDate, endDate time.Time) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE user_id = $1 AND type = $2 AND date >= $3 AND date <= $4
		ORDER BY date DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, transactionType, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// Update updates a finance transaction
func (r *PostgresFinanceTransactionRepository) Update(ctx context.Context, transaction *model.FinanceTransaction) error {
	transaction.UpdatedAt = time.Now()
	query := `
		UPDATE finance_transactions SET
			account_id = $2, category_id = $3, type = $4, amount = $5,
			currency = $6, description = $7, payee = $8, date = $9,
			is_recurring = $10, recurring_id = $11, tags = $12, attachments = $13,
			latitude = $14, longitude = $15, location_name = $16, updated_at = $17
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		transaction.ID, transaction.AccountID, transaction.CategoryID, transaction.Type,
		transaction.Amount, transaction.Currency, transaction.Description, transaction.Payee,
		transaction.Date, transaction.IsRecurring, transaction.RecurringID, transaction.Tags,
		transaction.Attachments, transaction.Latitude, transaction.Longitude,
		transaction.LocationName, transaction.UpdatedAt,
	)
	return err
}

// Delete deletes a finance transaction
func (r *PostgresFinanceTransactionRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_transactions WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

// GetTotalByType gets total amount by transaction type in a date range
func (r *PostgresFinanceTransactionRepository) GetTotalByType(ctx context.Context, userID string, transactionType model.TransactionType, startDate, endDate time.Time) (float64, error) {
	query := `
		SELECT COALESCE(SUM(amount), 0) as total
		FROM finance_transactions
		WHERE user_id = $1 AND type = $2 AND date >= $3 AND date <= $4
	`
	var total float64
	err := r.pool.QueryRow(ctx, query, userID, transactionType, startDate, endDate).Scan(&total)
	return total, err
}

// GetTotalByCategory gets total amount grouped by category in a date range
func (r *PostgresFinanceTransactionRepository) GetTotalByCategory(ctx context.Context, userID string, startDate, endDate time.Time) (map[string]float64, error) {
	query := `
		SELECT COALESCE(category_id, 'uncategorized') as category_id, SUM(amount) as total
		FROM finance_transactions
		WHERE user_id = $1 AND type = 'expense' AND date >= $2 AND date <= $3
		GROUP BY category_id
	`
	rows, err := r.pool.Query(ctx, query, userID, startDate, endDate)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[string]float64)
	for rows.Next() {
		var categoryID string
		var total float64
		err := rows.Scan(&categoryID, &total)
		if err != nil {
			return nil, err
		}
		result[categoryID] = total
	}
	return result, rows.Err()
}

// GetRecent retrieves recent transactions for a user
func (r *PostgresFinanceTransactionRepository) GetRecent(ctx context.Context, userID string, limit int) ([]*model.FinanceTransaction, error) {
	query := `
		SELECT id, user_id, account_id, category_id, type, amount, currency,
			description, payee, date, is_recurring, recurring_id, tags,
			attachments, latitude, longitude, location_name, created_at, updated_at
		FROM finance_transactions WHERE user_id = $1
		ORDER BY date DESC
		LIMIT $2
	`
	rows, err := r.pool.Query(ctx, query, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	return r.scanTransactions(rows)
}

// scanTransactions helper function to scan multiple transactions
func (r *PostgresFinanceTransactionRepository) scanTransactions(rows pgx.Rows) ([]*model.FinanceTransaction, error) {
	var transactions []*model.FinanceTransaction
	for rows.Next() {
		transaction := &model.FinanceTransaction{}
		err := rows.Scan(
			&transaction.ID, &transaction.UserID, &transaction.AccountID, &transaction.CategoryID,
			&transaction.Type, &transaction.Amount, &transaction.Currency, &transaction.Description,
			&transaction.Payee, &transaction.Date, &transaction.IsRecurring, &transaction.RecurringID,
			&transaction.Tags, &transaction.Attachments, &transaction.Latitude, &transaction.Longitude,
			&transaction.LocationName, &transaction.CreatedAt, &transaction.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		transactions = append(transactions, transaction)
	}
	return transactions, rows.Err()
}
