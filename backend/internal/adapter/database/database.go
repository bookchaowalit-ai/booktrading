package database

import (
	"context"
	"fmt"
	"time"

	"github.com/jackc/pgx/v5/pgxpool"
	"trading-bot-system/backend/internal/logger"
)

// Database represents a PostgreSQL database connection pool
type Database struct {
	pool *pgxpool.Pool
}

// NewDatabase creates a new database connection
func NewDatabase(ctx context.Context, connStr string) (*Database, error) {
	pool, err := pgxpool.New(ctx, connStr)
	if err != nil {
		return nil, fmt.Errorf("failed to create connection pool: %w", err)
	}

	// Test the connection
	if err := pool.Ping(ctx); err != nil {
		return nil, fmt.Errorf("failed to ping database: %w", err)
	}

	// Configure pool settings
	pool.Config().MaxConns = 25
	pool.Config().MinConns = 5
	pool.Config().MaxConnLifetime = time.Hour
	pool.Config().MaxConnIdleTime = 30 * time.Minute

	db := &Database{pool: pool}

	// Log pool stats periodically
	go db.logPoolStats(ctx)

	return db, nil
}

// Close closes the database connection pool
func (db *Database) Close() {
	if db.pool != nil {
		db.pool.Close()
		logger.Info("Database connection pool closed")
	}
}

// Pool returns the underlying connection pool
func (db *Database) Pool() *pgxpool.Pool {
	return db.pool
}

// Health checks if the database is healthy
func (db *Database) Health(ctx context.Context) error {
	return db.pool.Ping(ctx)
}

// Stats returns database pool statistics
func (db *Database) Stats() map[string]interface{} {
	if db.pool == nil {
		return nil
	}
	stats := db.pool.Stat()
	return map[string]interface{}{
		"acquire_count":            stats.AcquireCount(),
		"acquired_conns":           stats.AcquiredConns(),
		"canceled_acquire_count":   stats.CanceledAcquireCount(),
		"constructing_conns":       stats.ConstructingConns(),
		"acquire_duration":         stats.AcquireDuration().String(),
		"empty_acquire_count":      stats.EmptyAcquireCount(),
		"idle_conns":               stats.IdleConns(),
		"max_conns":                stats.MaxConns(),
		"total_conns":              stats.TotalConns(),
		"new_conns_count":          stats.NewConnsCount(),
	}
}

// logPoolStats logs pool statistics every 30 seconds
func (db *Database) logPoolStats(ctx context.Context) {
	ticker := time.NewTicker(30 * time.Second)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			stats := db.Stats()
			logger.Debug("Database pool stats",
				"total_conns", stats["total_conns"],
				"acquired_conns", stats["acquired_conns"],
				"idle_conns", stats["idle_conns"],
				"max_conns", stats["max_conns"],
			)
		}
	}
}

// WithTransaction executes a function within a database transaction
func (db *Database) WithTransaction(ctx context.Context, fn func(ctx context.Context) error) error {
	tx, err := db.pool.Begin(ctx)
	if err != nil {
		return fmt.Errorf("failed to begin transaction: %w", err)
	}

	defer func() {
		if p := recover(); p != nil {
			tx.Rollback(ctx)
			panic(p)
		} else if err != nil {
			tx.Rollback(ctx)
		} else {
			err = tx.Commit(ctx)
		}
	}()

	err = fn(ctx)
	return err
}

// Execute executes a query and returns the number of rows affected
func (db *Database) Execute(ctx context.Context, query string, args ...interface{}) (int64, error) {
	result, err := db.pool.Exec(ctx, query, args...)
	if err != nil {
		logger.Error("Database execute failed",
			"query", query,
			"error", err,
		)
		return 0, fmt.Errorf("failed to execute query: %w", err)
	}
	return result.RowsAffected(), nil
}

// Query executes a query and returns rows
func (db *Database) Query(ctx context.Context, query string, args ...interface{}) (interface{}, error) {
	rows, err := db.pool.Query(ctx, query, args...)
	if err != nil {
		logger.Error("Database query failed",
			"query", query,
			"error", err,
		)
		return nil, fmt.Errorf("failed to execute query: %w", err)
	}
	return rows, nil
}

// QueryRow executes a query that returns a single row
func (db *Database) QueryRow(ctx context.Context, query string, args ...interface{}) interface{} {
	return db.pool.QueryRow(ctx, query, args...)
}
