package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceBudgetRepository implements FinanceBudgetRepository with PostgreSQL
type PostgresFinanceBudgetRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceBudgetRepository creates a new PostgreSQL finance budget repository
func NewPostgresFinanceBudgetRepository(pool *pgxpool.Pool) repository.FinanceBudgetRepository {
	return &PostgresFinanceBudgetRepository{pool: pool}
}

func (r *PostgresFinanceBudgetRepository) Create(ctx context.Context, budget *model.FinanceBudget) error {
	if budget.ID == "" {
		budget.ID = uuid.New().String()
	}
	now := time.Now()
	budget.CreatedAt = now
	budget.UpdatedAt = now

	query := `
		INSERT INTO finance_budgets (
			id, user_id, name, category_id, amount, currency, period,
			start_date, end_date, is_active, alert_threshold, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
	`
	_, err := r.pool.Exec(ctx, query,
		budget.ID, budget.UserID, budget.Name, budget.CategoryID, budget.Amount,
		budget.Currency, budget.Period, budget.StartDate, budget.EndDate,
		budget.IsActive, budget.AlertThreshold, budget.CreatedAt, budget.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceBudgetRepository) GetByID(ctx context.Context, id string) (*model.FinanceBudget, error) {
	query := `
		SELECT id, user_id, name, category_id, amount, currency, period,
			start_date, end_date, is_active, alert_threshold, created_at, updated_at
		FROM finance_budgets WHERE id = $1
	`
	budget := &model.FinanceBudget{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&budget.ID, &budget.UserID, &budget.Name, &budget.CategoryID, &budget.Amount,
		&budget.Currency, &budget.Period, &budget.StartDate, &budget.EndDate,
		&budget.IsActive, &budget.AlertThreshold, &budget.CreatedAt, &budget.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return budget, nil
}

func (r *PostgresFinanceBudgetRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceBudget, error) {
	query := `
		SELECT id, user_id, name, category_id, amount, currency, period,
			start_date, end_date, is_active, alert_threshold, created_at, updated_at
		FROM finance_budgets WHERE user_id = $1
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var budgets []*model.FinanceBudget
	for rows.Next() {
		budget := &model.FinanceBudget{}
		err := rows.Scan(
			&budget.ID, &budget.UserID, &budget.Name, &budget.CategoryID, &budget.Amount,
			&budget.Currency, &budget.Period, &budget.StartDate, &budget.EndDate,
			&budget.IsActive, &budget.AlertThreshold, &budget.CreatedAt, &budget.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		budgets = append(budgets, budget)
	}
	return budgets, rows.Err()
}

func (r *PostgresFinanceBudgetRepository) GetActive(ctx context.Context, userID string) ([]*model.FinanceBudget, error) {
	query := `
		SELECT id, user_id, name, category_id, amount, currency, period,
			start_date, end_date, is_active, alert_threshold, created_at, updated_at
		FROM finance_budgets WHERE user_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var budgets []*model.FinanceBudget
	for rows.Next() {
		budget := &model.FinanceBudget{}
		err := rows.Scan(
			&budget.ID, &budget.UserID, &budget.Name, &budget.CategoryID, &budget.Amount,
			&budget.Currency, &budget.Period, &budget.StartDate, &budget.EndDate,
			&budget.IsActive, &budget.AlertThreshold, &budget.CreatedAt, &budget.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		budgets = append(budgets, budget)
	}
	return budgets, rows.Err()
}

func (r *PostgresFinanceBudgetRepository) GetByCategoryID(ctx context.Context, categoryID string) (*model.FinanceBudget, error) {
	query := `
		SELECT id, user_id, name, category_id, amount, currency, period,
			start_date, end_date, is_active, alert_threshold, created_at, updated_at
		FROM finance_budgets WHERE category_id = $1 AND is_active = true
		LIMIT 1
	`
	budget := &model.FinanceBudget{}
	err := r.pool.QueryRow(ctx, query, categoryID).Scan(
		&budget.ID, &budget.UserID, &budget.Name, &budget.CategoryID, &budget.Amount,
		&budget.Currency, &budget.Period, &budget.StartDate, &budget.EndDate,
		&budget.IsActive, &budget.AlertThreshold, &budget.CreatedAt, &budget.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return budget, nil
}

func (r *PostgresFinanceBudgetRepository) Update(ctx context.Context, budget *model.FinanceBudget) error {
	budget.UpdatedAt = time.Now()
	query := `
		UPDATE finance_budgets SET
			name = $2, category_id = $3, amount = $4, currency = $5, period = $6,
			start_date = $7, end_date = $8, is_active = $9, alert_threshold = $10, updated_at = $11
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		budget.ID, budget.Name, budget.CategoryID, budget.Amount, budget.Currency,
		budget.Period, budget.StartDate, budget.EndDate, budget.IsActive,
		budget.AlertThreshold, budget.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceBudgetRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_budgets WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}