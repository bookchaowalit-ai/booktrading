package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceLiabilityRepository implements FinanceLiabilityRepository with PostgreSQL
type PostgresFinanceLiabilityRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceLiabilityRepository creates a new PostgreSQL finance liability repository
func NewPostgresFinanceLiabilityRepository(pool *pgxpool.Pool) repository.FinanceLiabilityRepository {
	return &PostgresFinanceLiabilityRepository{pool: pool}
}

func (r *PostgresFinanceLiabilityRepository) Create(ctx context.Context, liability *model.FinanceLiability) error {
	if liability.ID == "" {
		liability.ID = uuid.New().String()
	}
	now := time.Now()
	liability.CreatedAt = now
	liability.UpdatedAt = now

	query := `
		INSERT INTO finance_liabilities (
			id, user_id, name, type, lender, original_amount, current_balance,
			currency, interest_rate, interest_type, minimum_payment, due_date,
			start_date, end_date, status, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16, $17)
	`
	_, err := r.pool.Exec(ctx, query,
		liability.ID, liability.UserID, liability.Name, liability.Type, liability.Lender,
		liability.OriginalAmount, liability.CurrentBalance, liability.Currency,
		liability.InterestRate, liability.InterestType, liability.MinimumPayment,
		liability.DueDate, liability.StartDate, liability.EndDate, liability.Status,
		liability.CreatedAt, liability.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceLiabilityRepository) GetByID(ctx context.Context, id string) (*model.FinanceLiability, error) {
	query := `
		SELECT id, user_id, name, type, lender, original_amount, current_balance,
			currency, interest_rate, interest_type, minimum_payment, due_date,
			start_date, end_date, status, created_at, updated_at
		FROM finance_liabilities WHERE id = $1
	`
	liability := &model.FinanceLiability{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&liability.ID, &liability.UserID, &liability.Name, &liability.Type, &liability.Lender,
		&liability.OriginalAmount, &liability.CurrentBalance, &liability.Currency,
		&liability.InterestRate, &liability.InterestType, &liability.MinimumPayment,
		&liability.DueDate, &liability.StartDate, &liability.EndDate, &liability.Status,
		&liability.CreatedAt, &liability.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return liability, nil
}

func (r *PostgresFinanceLiabilityRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceLiability, error) {
	query := `
		SELECT id, user_id, name, type, lender, original_amount, current_balance,
			currency, interest_rate, interest_type, minimum_payment, due_date,
			start_date, end_date, status, created_at, updated_at
		FROM finance_liabilities WHERE user_id = $1 AND status = 'active'
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var liabilities []*model.FinanceLiability
	for rows.Next() {
		liability := &model.FinanceLiability{}
		err := rows.Scan(
			&liability.ID, &liability.UserID, &liability.Name, &liability.Type, &liability.Lender,
			&liability.OriginalAmount, &liability.CurrentBalance, &liability.Currency,
			&liability.InterestRate, &liability.InterestType, &liability.MinimumPayment,
			&liability.DueDate, &liability.StartDate, &liability.EndDate, &liability.Status,
			&liability.CreatedAt, &liability.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		liabilities = append(liabilities, liability)
	}
	return liabilities, rows.Err()
}

func (r *PostgresFinanceLiabilityRepository) GetByType(ctx context.Context, userID string, liabilityType model.LiabilityType) ([]*model.FinanceLiability, error) {
	query := `
		SELECT id, user_id, name, type, lender, original_amount, current_balance,
			currency, interest_rate, interest_type, minimum_payment, due_date,
			start_date, end_date, status, created_at, updated_at
		FROM finance_liabilities WHERE user_id = $1 AND type = $2 AND status = 'active'
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, liabilityType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var liabilities []*model.FinanceLiability
	for rows.Next() {
		liability := &model.FinanceLiability{}
		err := rows.Scan(
			&liability.ID, &liability.UserID, &liability.Name, &liability.Type, &liability.Lender,
			&liability.OriginalAmount, &liability.CurrentBalance, &liability.Currency,
			&liability.InterestRate, &liability.InterestType, &liability.MinimumPayment,
			&liability.DueDate, &liability.StartDate, &liability.EndDate, &liability.Status,
			&liability.CreatedAt, &liability.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		liabilities = append(liabilities, liability)
	}
	return liabilities, rows.Err()
}

func (r *PostgresFinanceLiabilityRepository) GetByStatus(ctx context.Context, userID string, status model.LiabilityStatus) ([]*model.FinanceLiability, error) {
	query := `
		SELECT id, user_id, name, type, lender, original_amount, current_balance,
			currency, interest_rate, interest_type, minimum_payment, due_date,
			start_date, end_date, status, created_at, updated_at
		FROM finance_liabilities WHERE user_id = $1 AND status = $2
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, status)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var liabilities []*model.FinanceLiability
	for rows.Next() {
		liability := &model.FinanceLiability{}
		err := rows.Scan(
			&liability.ID, &liability.UserID, &liability.Name, &liability.Type, &liability.Lender,
			&liability.OriginalAmount, &liability.CurrentBalance, &liability.Currency,
			&liability.InterestRate, &liability.InterestType, &liability.MinimumPayment,
			&liability.DueDate, &liability.StartDate, &liability.EndDate, &liability.Status,
			&liability.CreatedAt, &liability.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		liabilities = append(liabilities, liability)
	}
	return liabilities, rows.Err()
}

func (r *PostgresFinanceLiabilityRepository) Update(ctx context.Context, liability *model.FinanceLiability) error {
	liability.UpdatedAt = time.Now()
	query := `
		UPDATE finance_liabilities SET
			name = $2, type = $3, lender = $4, original_amount = $5, current_balance = $6,
			currency = $7, interest_rate = $8, interest_type = $9, minimum_payment = $10,
			due_date = $11, start_date = $12, end_date = $13, status = $14, updated_at = $15
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		liability.ID, liability.Name, liability.Type, liability.Lender,
		liability.OriginalAmount, liability.CurrentBalance, liability.Currency,
		liability.InterestRate, liability.InterestType, liability.MinimumPayment,
		liability.DueDate, liability.StartDate, liability.EndDate, liability.Status,
		liability.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceLiabilityRepository) UpdateBalance(ctx context.Context, id string, amount float64, isReduce bool) error {
	var query string
	if isReduce {
		query = `UPDATE finance_liabilities SET current_balance = current_balance - $1, updated_at = $2 WHERE id = $3`
	} else {
		query = `UPDATE finance_liabilities SET current_balance = current_balance + $1, updated_at = $2 WHERE id = $3`
	}
	_, err := r.pool.Exec(ctx, query, amount, time.Now(), id)
	return err
}

func (r *PostgresFinanceLiabilityRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_liabilities WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

func (r *PostgresFinanceLiabilityRepository) GetTotalBalance(ctx context.Context, userID string) (float64, error) {
	query := `
		SELECT COALESCE(SUM(current_balance), 0) as total
		FROM finance_liabilities WHERE user_id = $1 AND status = 'active'
	`
	var total float64
	err := r.pool.QueryRow(ctx, query, userID).Scan(&total)
	return total, err
}

func (r *PostgresFinanceLiabilityRepository) GetTotalBalanceByType(ctx context.Context, userID string) (map[model.LiabilityType]float64, error) {
	query := `
		SELECT type, SUM(current_balance) as total
		FROM finance_liabilities WHERE user_id = $1 AND status = 'active'
		GROUP BY type
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[model.LiabilityType]float64)
	for rows.Next() {
		var liabilityType model.LiabilityType
		var total float64
		err := rows.Scan(&liabilityType, &total)
		if err != nil {
			return nil, err
		}
		result[liabilityType] = total
	}
	return result, rows.Err()
}