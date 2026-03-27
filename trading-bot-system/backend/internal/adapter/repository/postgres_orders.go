package repository

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresOrderRepository implements OrderRepository with PostgreSQL
type PostgresOrderRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresOrderRepository creates a new PostgreSQL order repository
func NewPostgresOrderRepository(pool *pgxpool.Pool) repository.OrderRepository {
	return &PostgresOrderRepository{
		pool: pool,
	}
}

// Create stores a new order
func (r *PostgresOrderRepository) Create(ctx context.Context, order *model.Order) error {
	query := `
		INSERT INTO orders (id, symbol, side, type, quantity, price, status, created_at, updated_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`
	_, err := r.pool.Exec(ctx, query,
		order.ID,
		order.Symbol,
		order.Side,
		order.Type,
		order.Quantity,
		order.Price,
		order.Status,
		order.CreatedAt,
		order.UpdatedAt,
	)
	return err
}

// GetByID retrieves an order by ID
func (r *PostgresOrderRepository) GetByID(ctx context.Context, id string) (*model.Order, error) {
	query := `
		SELECT id, symbol, side, type, quantity, price, status, created_at, updated_at
		FROM orders WHERE id = $1
	`
	order := &model.Order{}
	err := r.pool.QueryRow(ctx, query, id).Scan(
		&order.ID,
		&order.Symbol,
		&order.Side,
		&order.Type,
		&order.Quantity,
		&order.Price,
		&order.Status,
		&order.CreatedAt,
		&order.UpdatedAt,
	)
	if err != nil {
		return nil, err
	}
	return order, nil
}

// GetBySymbol retrieves all orders for a symbol
func (r *PostgresOrderRepository) GetBySymbol(ctx context.Context, symbol model.TradeSymbol) ([]*model.Order, error) {
	query := `
		SELECT id, symbol, side, type, quantity, price, status, created_at, updated_at
		FROM orders WHERE symbol = $1
		ORDER BY created_at DESC
	`
	rows, err := r.pool.Query(ctx, query, symbol)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var orders []*model.Order
	for rows.Next() {
		order := &model.Order{}
		err := rows.Scan(
			&order.ID,
			&order.Symbol,
			&order.Side,
			&order.Type,
			&order.Quantity,
			&order.Price,
			&order.Status,
			&order.CreatedAt,
			&order.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		orders = append(orders, order)
	}
	return orders, rows.Err()
}

// UpdateStatus updates the status of an order
func (r *PostgresOrderRepository) UpdateStatus(ctx context.Context, id string, status model.OrderStatus) error {
	query := `UPDATE orders SET status = $1, updated_at = $2 WHERE id = $3`
	_, err := r.pool.Exec(ctx, query, status, time.Now(), id)
	return err
}

// GetAll retrieves all orders
func (r *PostgresOrderRepository) GetAll(ctx context.Context) ([]*model.Order, error) {
	query := `
		SELECT id, symbol, side, type, quantity, price, status, created_at, updated_at
		FROM orders ORDER BY created_at DESC LIMIT 100
	`
	rows, err := r.pool.Query(ctx, query)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var orders []*model.Order
	for rows.Next() {
		order := &model.Order{}
		err := rows.Scan(
			&order.ID,
			&order.Symbol,
			&order.Side,
			&order.Type,
			&order.Quantity,
			&order.Price,
			&order.Status,
			&order.CreatedAt,
			&order.UpdatedAt,
		)
		if err != nil {
			return nil, err
		}
		orders = append(orders, order)
	}
	return orders, rows.Err()
}
