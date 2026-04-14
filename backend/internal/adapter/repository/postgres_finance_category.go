package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceCategoryRepository implements FinanceCategoryRepository with PostgreSQL
type PostgresFinanceCategoryRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceCategoryRepository creates a new PostgreSQL finance category repository
func NewPostgresFinanceCategoryRepository(pool *pgxpool.Pool) repository.FinanceCategoryRepository {
	return &PostgresFinanceCategoryRepository{pool: pool}
}

// Create stores a new finance category
func (r *PostgresFinanceCategoryRepository) Create(ctx context.Context, category *model.FinanceCategory) error {
	if category.ID == "" {
		category.ID = uuid.New().String()
	}
	now := time.Now()
	category.CreatedAt = now
	category.UpdatedAt = now

	query := `
		INSERT INTO finance_categories (
			id, user_id, name, type, parent_id, color, icon, budget_amount, is_system, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
	`
	_, err := r.pool.Exec(ctx, query,
		category.ID, category.UserID, category.Name, category.Type, category.ParentID,
		category.Color, category.Icon, category.BudgetAmount, category.IsSystem,
		category.CreatedAt, category.UpdatedAt,
	)
	return err
}

// GetByID retrieves a finance category by ID
func (r *PostgresFinanceCategoryRepository) GetByID(ctx context.Context, id string) (*model.FinanceCategory, error) {
	query := `
		SELECT id, user_id, name, type, parent_id, color, icon, budget_amount, is_system, created_at, updated_at
		FROM finance_categories WHERE id = $1
	`
	category := &model.FinanceCategory{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&category.ID, &category.UserID, &category.Name, &category.Type, &category.ParentID,
		&category.Color, &category.Icon, &category.BudgetAmount, &category.IsSystem,
		&category.CreatedAt, &category.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return category, nil
}

// GetByUserID retrieves all finance categories for a user (including system categories)
func (r *PostgresFinanceCategoryRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceCategory, error) {
	query := `
		SELECT id, user_id, name, type, parent_id, color, icon, budget_amount, is_system, created_at, updated_at
		FROM finance_categories WHERE user_id = $1 OR user_id = 'system'
		ORDER BY type, name
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var categories []*model.FinanceCategory
	for rows.Next() {
		category := &model.FinanceCategory{}
		err := rows.Scan(
			&category.ID, &category.UserID, &category.Name, &category.Type, &category.ParentID,
			&category.Color, &category.Icon, &category.BudgetAmount, &category.IsSystem,
			&category.CreatedAt, &category.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		categories = append(categories, category)
	}
	return categories, rows.Err()
}

// GetByType retrieves finance categories by type
func (r *PostgresFinanceCategoryRepository) GetByType(ctx context.Context, userID string, categoryType model.CategoryType) ([]*model.FinanceCategory, error) {
	query := `
		SELECT id, user_id, name, type, parent_id, color, icon, budget_amount, is_system, created_at, updated_at
		FROM finance_categories WHERE (user_id = $1 OR user_id = 'system') AND type = $2
		ORDER BY name
	`
	rows, err := r.pool.Query(ctx, query, userID, categoryType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var categories []*model.FinanceCategory
	for rows.Next() {
		category := &model.FinanceCategory{}
		err := rows.Scan(
			&category.ID, &category.UserID, &category.Name, &category.Type, &category.ParentID,
			&category.Color, &category.Icon, &category.BudgetAmount, &category.IsSystem,
			&category.CreatedAt, &category.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		categories = append(categories, category)
	}
	return categories, rows.Err()
}

// GetSystemCategories retrieves all system default categories
func (r *PostgresFinanceCategoryRepository) GetSystemCategories(ctx context.Context) ([]*model.FinanceCategory, error) {
	query := `
		SELECT id, user_id, name, type, parent_id, color, icon, budget_amount, is_system, created_at, updated_at
		FROM finance_categories WHERE user_id = 'system'
		ORDER BY type, name
	`
	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var categories []*model.FinanceCategory
	for rows.Next() {
		category := &model.FinanceCategory{}
		err := rows.Scan(
			&category.ID, &category.UserID, &category.Name, &category.Type, &category.ParentID,
			&category.Color, &category.Icon, &category.BudgetAmount, &category.IsSystem,
			&category.CreatedAt, &category.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		categories = append(categories, category)
	}
	return categories, rows.Err()
}

// Update updates a finance category
func (r *PostgresFinanceCategoryRepository) Update(ctx context.Context, category *model.FinanceCategory) error {
	category.UpdatedAt = time.Now()
	query := `
		UPDATE finance_categories SET
			name = $2, type = $3, parent_id = $4, color = $5, icon = $6,
			budget_amount = $7, updated_at = $8
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		category.ID, category.Name, category.Type, category.ParentID,
		category.Color, category.Icon, category.BudgetAmount, category.UpdatedAt,
	)
	return err
}

// Delete deletes a finance category (only if not system)
func (r *PostgresFinanceCategoryRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_categories WHERE id = $1 AND is_system = false`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}