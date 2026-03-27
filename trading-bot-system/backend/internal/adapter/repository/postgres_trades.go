package repository

import (
	"context"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/domain/model"
	"trading-bot-system/backend/internal/domain/repository"
)

// PostgresTradeHistoryRepository implements TradeHistoryRepository with PostgreSQL
type PostgresTradeHistoryRepository struct {
	pool *pgxpool.Pool
}

// NewPostgresTradeHistoryRepository creates a new PostgreSQL trade history repository
func NewPostgresTradeHistoryRepository(pool *pgxpool.Pool) repository.TradeHistoryRepository {
	return &PostgresTradeHistoryRepository{
		pool: pool,
	}
}

// Add adds a new trade to history
func (r *PostgresTradeHistoryRepository) Add(ctx context.Context, trade *model.TradeHistory) error {
	query := `
		INSERT INTO trade_history (id, symbol, side, quantity, price, total, fee, executed_at, created_at)
		VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
	`
	_, err := r.pool.Exec(ctx, query,
		trade.ID,
		trade.Symbol,
		trade.Side,
		trade.Quantity,
		trade.Price,
		trade.Total,
		trade.Fee,
		trade.ExecutedAt,
		time.Now(),
	)
	return err
}

// GetAll retrieves all trades with limit
func (r *PostgresTradeHistoryRepository) GetAll(ctx context.Context, limit int) ([]*model.TradeHistory, error) {
	query := `
		SELECT id, symbol, side, quantity, price, total, fee, executed_at
		FROM trade_history ORDER BY executed_at DESC LIMIT $1
	`
	rows, err := r.pool.Query(ctx, query, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var trades []*model.TradeHistory
	for rows.Next() {
		trade := &model.TradeHistory{}
		err := rows.Scan(
			&trade.ID,
			&trade.Symbol,
			&trade.Side,
			&trade.Quantity,
			&trade.Price,
			&trade.Total,
			&trade.Fee,
			&trade.ExecutedAt,
		)
		if err != nil {
			return nil, err
		}
		trades = append(trades, trade)
	}
	return trades, rows.Err()
}

// GetBySymbol retrieves trades for a specific symbol with limit
func (r *PostgresTradeHistoryRepository) GetBySymbol(ctx context.Context, symbol model.TradeSymbol, limit int) ([]*model.TradeHistory, error) {
	query := `
		SELECT id, symbol, side, quantity, price, total, fee, executed_at
		FROM trade_history WHERE symbol = $1 ORDER BY executed_at DESC LIMIT $2
	`
	rows, err := r.pool.Query(ctx, query, symbol, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var trades []*model.TradeHistory
	for rows.Next() {
		trade := &model.TradeHistory{}
		err := rows.Scan(
			&trade.ID,
			&trade.Symbol,
			&trade.Side,
			&trade.Quantity,
			&trade.Price,
			&trade.Total,
			&trade.Fee,
			&trade.ExecutedAt,
		)
		if err != nil {
			return nil, err
		}
		trades = append(trades, trade)
	}
	return trades, rows.Err()
}
