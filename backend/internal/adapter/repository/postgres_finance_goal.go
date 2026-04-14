package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceGoalRepository implements FinanceGoalRepository with PostgreSQL
type PostgresFinanceGoalRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceGoalRepository creates a new PostgreSQL finance goal repository
func NewPostgresFinanceGoalRepository(pool *pgxpool.Pool) repository.FinanceGoalRepository {
	return &PostgresFinanceGoalRepository{pool: pool}
}

func (r *PostgresFinanceGoalRepository) Create(ctx context.Context, goal *model.FinanceGoal) error {
	if goal.ID == "" {
		goal.ID = uuid.New().String()
	}
	now := time.Now()
	goal.CreatedAt = now
	goal.UpdatedAt = now

	query := `
		INSERT INTO finance_goals (
			id, user_id, name, type, target_amount, current_amount, currency,
			target_date, monthly_contribution, priority, status, color, icon, notes, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
	`
	_, err := r.pool.Exec(ctx, query,
		goal.ID, goal.UserID, goal.Name, goal.Type, goal.TargetAmount, goal.CurrentAmount,
		goal.Currency, goal.TargetDate, goal.MonthlyContribution, goal.Priority, goal.Status,
		goal.Color, goal.Icon, goal.Notes, goal.CreatedAt, goal.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceGoalRepository) GetByID(ctx context.Context, id string) (*model.FinanceGoal, error) {
	query := `
		SELECT id, user_id, name, type, target_amount, current_amount, currency,
			target_date, monthly_contribution, priority, status, color, icon, notes, created_at, updated_at
		FROM finance_goals WHERE id = $1
	`
	goal := &model.FinanceGoal{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&goal.ID, &goal.UserID, &goal.Name, &goal.Type, &goal.TargetAmount, &goal.CurrentAmount,
		&goal.Currency, &goal.TargetDate, &goal.MonthlyContribution, &goal.Priority, &goal.Status,
		&goal.Color, &goal.Icon, &goal.Notes, &goal.CreatedAt, &goal.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return goal, nil
}

func (r *PostgresFinanceGoalRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceGoal, error) {
	query := `
		SELECT id, user_id, name, type, target_amount, current_amount, currency,
			target_date, monthly_contribution, priority, status, color, icon, notes, created_at, updated_at
		FROM finance_goals WHERE user_id = $1
		ORDER BY priority DESC, created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var goals []*model.FinanceGoal
	for rows.Next() {
		goal := &model.FinanceGoal{}
		err := rows.Scan(
			&goal.ID, &goal.UserID, &goal.Name, &goal.Type, &goal.TargetAmount, &goal.CurrentAmount,
			&goal.Currency, &goal.TargetDate, &goal.MonthlyContribution, &goal.Priority, &goal.Status,
			&goal.Color, &goal.Icon, &goal.Notes, &goal.CreatedAt, &goal.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		goals = append(goals, goal)
	}
	return goals, rows.Err()
}

func (r *PostgresFinanceGoalRepository) GetActive(ctx context.Context, userID string) ([]*model.FinanceGoal, error) {
	query := `
		SELECT id, user_id, name, type, target_amount, current_amount, currency,
			target_date, monthly_contribution, priority, status, color, icon, notes, created_at, updated_at
		FROM finance_goals WHERE user_id = $1 AND status = 'active'
		ORDER BY priority DESC, created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var goals []*model.FinanceGoal
	for rows.Next() {
		goal := &model.FinanceGoal{}
		err := rows.Scan(
			&goal.ID, &goal.UserID, &goal.Name, &goal.Type, &goal.TargetAmount, &goal.CurrentAmount,
			&goal.Currency, &goal.TargetDate, &goal.MonthlyContribution, &goal.Priority, &goal.Status,
			&goal.Color, &goal.Icon, &goal.Notes, &goal.CreatedAt, &goal.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		goals = append(goals, goal)
	}
	return goals, rows.Err()
}

func (r *PostgresFinanceGoalRepository) GetByStatus(ctx context.Context, userID string, status model.GoalStatus) ([]*model.FinanceGoal, error) {
	query := `
		SELECT id, user_id, name, type, target_amount, current_amount, currency,
			target_date, monthly_contribution, priority, status, color, icon, notes, created_at, updated_at
		FROM finance_goals WHERE user_id = $1 AND status = $2
		ORDER BY priority DESC, created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, status)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var goals []*model.FinanceGoal
	for rows.Next() {
		goal := &model.FinanceGoal{}
		err := rows.Scan(
			&goal.ID, &goal.UserID, &goal.Name, &goal.Type, &goal.TargetAmount, &goal.CurrentAmount,
			&goal.Currency, &goal.TargetDate, &goal.MonthlyContribution, &goal.Priority, &goal.Status,
			&goal.Color, &goal.Icon, &goal.Notes, &goal.CreatedAt, &goal.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		goals = append(goals, goal)
	}
	return goals, rows.Err()
}

func (r *PostgresFinanceGoalRepository) Update(ctx context.Context, goal *model.FinanceGoal) error {
	goal.UpdatedAt = time.Now()
	query := `
		UPDATE finance_goals SET
			name = $2, type = $3, target_amount = $4, current_amount = $5, currency = $6,
			target_date = $7, monthly_contribution = $8, priority = $9, status = $10,
			color = $11, icon = $12, notes = $13, updated_at = $14
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		goal.ID, goal.Name, goal.Type, goal.TargetAmount, goal.CurrentAmount, goal.Currency,
		goal.TargetDate, goal.MonthlyContribution, goal.Priority, goal.Status,
		goal.Color, goal.Icon, goal.Notes, goal.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceGoalRepository) UpdateProgress(ctx context.Context, id string, amount float64, isAdd bool) error {
	var query string
	if isAdd {
		query = `UPDATE finance_goals SET current_amount = current_amount + $1, updated_at = $2 WHERE id = $3`
	} else {
		query = `UPDATE finance_goals SET current_amount = current_amount - $1, updated_at = $2 WHERE id = $3`
	}
	_, err := r.pool.Exec(ctx, query, amount, time.Now(), id)
	return err
}

func (r *PostgresFinanceGoalRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_goals WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}