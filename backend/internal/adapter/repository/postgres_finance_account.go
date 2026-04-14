package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceAccountRepository implements FinanceAccountRepository with PostgreSQL
type PostgresFinanceAccountRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceAccountRepository creates a new PostgreSQL finance account repository
func NewPostgresFinanceAccountRepository(pool *pgxpool.Pool) repository.FinanceAccountRepository {
	return &PostgresFinanceAccountRepository{pool: pool}
}

// Create stores a new finance account
func (r *PostgresFinanceAccountRepository) Create(ctx context.Context, account *model.FinanceAccount) error {
	if account.ID == "" {
		account.ID = uuid.New().String()
	}
	now := time.Now()
	account.CreatedAt = now
	account.UpdatedAt = now

	query := `
		INSERT INTO finance_accounts (
			id, user_id, name, type, institution, account_number, currency,
			balance, credit_limit, interest_rate, color, icon, is_active,
			include_in_net_worth, notes, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
	`
	_, err := r.pool.Exec(ctx, query,
		account.ID, account.UserID, account.Name, account.Type, account.Institution,
		account.AccountNumber, account.Currency, account.Balance, account.CreditLimit,
		account.InterestRate, account.Color, account.Icon, account.IsActive,
		account.IncludeInNetWorth, account.Notes, account.CreatedAt, account.UpdatedAt,
	)
	return err
}

// GetByID retrieves a finance account by ID
func (r *PostgresFinanceAccountRepository) GetByID(ctx context.Context, id string) (*model.FinanceAccount, error) {
	query := `
		SELECT id, user_id, name, type, institution, account_number, currency,
			balance, credit_limit, interest_rate, color, icon, is_active,
			include_in_net_worth, notes, created_at, updated_at
		FROM finance_accounts WHERE id = $1
	`
	account := &model.FinanceAccount{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&account.ID, &account.UserID, &account.Name, &account.Type, &account.Institution,
		&account.AccountNumber, &account.Currency, &account.Balance, &account.CreditLimit,
		&account.InterestRate, &account.Color, &account.Icon, &account.IsActive,
		&account.IncludeInNetWorth, &account.Notes, &account.CreatedAt, &account.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return account, nil
}

// GetByUserID retrieves all finance accounts for a user
func (r *PostgresFinanceAccountRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceAccount, error) {
	query := `
		SELECT id, user_id, name, type, institution, account_number, currency,
			balance, credit_limit, interest_rate, color, icon, is_active,
			include_in_net_worth, notes, created_at, updated_at
		FROM finance_accounts WHERE user_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var accounts []*model.FinanceAccount
	for rows.Next() {
		account := &model.FinanceAccount{}
		err := rows.Scan(
			&account.ID, &account.UserID, &account.Name, &account.Type, &account.Institution,
			&account.AccountNumber, &account.Currency, &account.Balance, &account.CreditLimit,
			&account.InterestRate, &account.Color, &account.Icon, &account.IsActive,
			&account.IncludeInNetWorth, &account.Notes, &account.CreatedAt, &account.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		accounts = append(accounts, account)
	}
	return accounts, rows.Err()
}

// GetByType retrieves finance accounts by type for a user
func (r *PostgresFinanceAccountRepository) GetByType(ctx context.Context, userID string, accountType model.AccountType) ([]*model.FinanceAccount, error) {
	query := `
		SELECT id, user_id, name, type, institution, account_number, currency,
			balance, credit_limit, interest_rate, color, icon, is_active,
			include_in_net_worth, notes, created_at, updated_at
		FROM finance_accounts WHERE user_id = $1 AND type = $2 AND is_active = true
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, accountType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var accounts []*model.FinanceAccount
	for rows.Next() {
		account := &model.FinanceAccount{}
		err := rows.Scan(
			&account.ID, &account.UserID, &account.Name, &account.Type, &account.Institution,
			&account.AccountNumber, &account.Currency, &account.Balance, &account.CreditLimit,
			&account.InterestRate, &account.Color, &account.Icon, &account.IsActive,
			&account.IncludeInNetWorth, &account.Notes, &account.CreatedAt, &account.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		accounts = append(accounts, account)
	}
	return accounts, rows.Err()
}

// Update updates a finance account
func (r *PostgresFinanceAccountRepository) Update(ctx context.Context, account *model.FinanceAccount) error {
	account.UpdatedAt = time.Now()
	query := `
		UPDATE finance_accounts SET
			name = $2, type = $3, institution = $4, account_number = $5,
			currency = $6, balance = $7, credit_limit = $8, interest_rate = $9,
			color = $10, icon = $11, is_active = $12, include_in_net_worth = $13,
			notes = $14, updated_at = $15
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		account.ID, account.Name, account.Type, account.Institution, account.AccountNumber,
		account.Currency, account.Balance, account.CreditLimit, account.InterestRate,
		account.Color, account.Icon, account.IsActive, account.IncludeInNetWorth,
		account.Notes, account.UpdatedAt,
	)
	return err
}

// Delete deletes a finance account
func (r *PostgresFinanceAccountRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_accounts WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

// UpdateBalance updates the balance of an account
func (r *PostgresFinanceAccountRepository) UpdateBalance(ctx context.Context, id string, amount float64, isAdd bool) error {
	var query string
	if isAdd {
		query = `UPDATE finance_accounts SET balance = balance + $1, updated_at = $2 WHERE id = $3`
	} else {
		query = `UPDATE finance_accounts SET balance = balance - $1, updated_at = $2 WHERE id = $3`
	}
	_, err := r.pool.Exec(ctx, query, amount, time.Now(), id)
	return err
}

// GetTotalBalanceByType gets total balance grouped by account type
func (r *PostgresFinanceAccountRepository) GetTotalBalanceByType(ctx context.Context, userID string) (map[model.AccountType]float64, error) {
	query := `
		SELECT type, SUM(balance) as total
		FROM finance_accounts
		WHERE user_id = $1 AND is_active = true AND include_in_net_worth = true
		GROUP BY type
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[model.AccountType]float64)
	for rows.Next() {
		var accountType model.AccountType
		var total float64
		err := rows.Scan(&accountType, &total)
		if err != nil {
			return nil, err
		}
		result[accountType] = total
	}
	return result, rows.Err()
}