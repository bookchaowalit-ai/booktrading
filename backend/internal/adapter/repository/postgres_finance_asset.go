package repository

import (
	"context"
	"time"

	"github.com/google/uuid"
	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresFinanceAssetRepository implements FinanceAssetRepository with PostgreSQL
type PostgresFinanceAssetRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresFinanceAssetRepository creates a new PostgreSQL finance asset repository
func NewPostgresFinanceAssetRepository(pool *pgxpool.Pool) repository.FinanceAssetRepository {
	return &PostgresFinanceAssetRepository{pool: pool}
}

func (r *PostgresFinanceAssetRepository) Create(ctx context.Context, asset *model.FinanceAsset) error {
	if asset.ID == "" {
		asset.ID = uuid.New().String()
	}
	now := time.Now()
	asset.CreatedAt = now
	asset.UpdatedAt = now

	query := `
		INSERT INTO finance_assets (
			id, user_id, name, type, description, purchase_price, current_value,
			currency, purchase_date, location, documents, is_active, created_at, updated_at
		) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
	`
	_, err := r.pool.Exec(ctx, query,
		asset.ID, asset.UserID, asset.Name, asset.Type, asset.Description,
		asset.PurchasePrice, asset.CurrentValue, asset.Currency, asset.PurchaseDate,
		asset.Location, asset.Documents, asset.IsActive, asset.CreatedAt, asset.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceAssetRepository) GetByID(ctx context.Context, id string) (*model.FinanceAsset, error) {
	query := `
		SELECT id, user_id, name, type, description, purchase_price, current_value,
			currency, purchase_date, location, documents, is_active, created_at, updated_at
		FROM finance_assets WHERE id = $1
	`
	asset := &model.FinanceAsset{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&asset.ID, &asset.UserID, &asset.Name, &asset.Type, &asset.Description,
		&asset.PurchasePrice, &asset.CurrentValue, &asset.Currency, &asset.PurchaseDate,
		&asset.Location, &asset.Documents, &asset.IsActive, &asset.CreatedAt, &asset.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return asset, nil
}

func (r *PostgresFinanceAssetRepository) GetByUserID(ctx context.Context, userID string) ([]*model.FinanceAsset, error) {
	query := `
		SELECT id, user_id, name, type, description, purchase_price, current_value,
			currency, purchase_date, location, documents, is_active, created_at, updated_at
		FROM finance_assets WHERE user_id = $1 AND is_active = true
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var assets []*model.FinanceAsset
	for rows.Next() {
		asset := &model.FinanceAsset{}
		err := rows.Scan(
			&asset.ID, &asset.UserID, &asset.Name, &asset.Type, &asset.Description,
			&asset.PurchasePrice, &asset.CurrentValue, &asset.Currency, &asset.PurchaseDate,
			&asset.Location, &asset.Documents, &asset.IsActive, &asset.CreatedAt, &asset.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		assets = append(assets, asset)
	}
	return assets, rows.Err()
}

func (r *PostgresFinanceAssetRepository) GetByType(ctx context.Context, userID string, assetType model.AssetType) ([]*model.FinanceAsset, error) {
	query := `
		SELECT id, user_id, name, type, description, purchase_price, current_value,
			currency, purchase_date, location, documents, is_active, created_at, updated_at
		FROM finance_assets WHERE user_id = $1 AND type = $2 AND is_active = true
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, userID, assetType)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var assets []*model.FinanceAsset
	for rows.Next() {
		asset := &model.FinanceAsset{}
		err := rows.Scan(
			&asset.ID, &asset.UserID, &asset.Name, &asset.Type, &asset.Description,
			&asset.PurchasePrice, &asset.CurrentValue, &asset.Currency, &asset.PurchaseDate,
			&asset.Location, &asset.Documents, &asset.IsActive, &asset.CreatedAt, &asset.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		assets = append(assets, asset)
	}
	return assets, rows.Err()
}

func (r *PostgresFinanceAssetRepository) Update(ctx context.Context, asset *model.FinanceAsset) error {
	asset.UpdatedAt = time.Now()
	query := `
		UPDATE finance_assets SET
			name = $2, type = $3, description = $4, purchase_price = $5, current_value = $6,
			currency = $7, purchase_date = $8, location = $9, documents = $10,
			is_active = $11, updated_at = $12
		WHERE id = $1
	`
	_, err := r.pool.Exec(ctx, query,
		asset.ID, asset.Name, asset.Type, asset.Description, asset.PurchasePrice,
		asset.CurrentValue, asset.Currency, asset.PurchaseDate, asset.Location,
		asset.Documents, asset.IsActive, asset.UpdatedAt,
	)
	return err
}

func (r *PostgresFinanceAssetRepository) Delete(ctx context.Context, id string) error {
	query := `DELETE FROM finance_assets WHERE id = $1`
	_, err := r.pool.Exec(ctx, query, id)
	return err
}

func (r *PostgresFinanceAssetRepository) GetTotalValue(ctx context.Context, userID string) (float64, error) {
	query := `
		SELECT COALESCE(SUM(current_value), 0) as total
		FROM finance_assets WHERE user_id = $1 AND is_active = true
	`
	var total float64
	err := r.pool.QueryRow(ctx, query, userID).Scan(&total)
	return total, err
}

func (r *PostgresFinanceAssetRepository) GetTotalValueByType(ctx context.Context, userID string) (map[model.AssetType]float64, error) {
	query := `
		SELECT type, SUM(current_value) as total
		FROM finance_assets WHERE user_id = $1 AND is_active = true
		GROUP BY type
	`
	rows, err := r.pool.Query(ctx, query, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	result := make(map[model.AssetType]float64)
	for rows.Next() {
		var assetType model.AssetType
		var total float64
		err := rows.Scan(&assetType, &total)
		if err != nil {
			return nil, err
		}
		result[assetType] = total
	}
	return result, rows.Err()
}