package database

import (
	"fmt"
	"log"
	"os"
	"path/filepath"
	"strings"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/postgres"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

// RunMigrations runs all pending database migrations
func RunMigrations(databaseURL string) error {
	// Get the directory where migrations are stored
	// In production (Docker), migrations are in /root/migrations
	// In development, they are in the local migrations folder
	migrationsPath := "file://migrations"

	// Check if we're running in Docker (migrations in /root/migrations)
	if _, err := os.Stat("/root/migrations"); err == nil {
		migrationsPath = "file:///root/migrations"
	} else if wd, err := os.Getwd(); err == nil {
		// Try to find migrations relative to current working directory
		migrationsDir := filepath.Join(wd, "migrations")
		if _, err := os.Stat(migrationsDir); err == nil {
			migrationsPath = fmt.Sprintf("file://%s", migrationsDir)
		}
	}

	m, err := migrate.New(
		migrationsPath,
		databaseURL,
	)
	if err != nil {
		return fmt.Errorf("failed to create migrate instance: %w", err)
	}
	defer m.Close()

	// Run all up migrations
	if err := m.Up(); err != nil {
		if err == migrate.ErrNoChange {
			log.Println("No new migrations to apply")
			return nil
		}
		// Check if it's a dirty database error
		if strings.Contains(err.Error(), "Dirty database") {
			log.Println("Database is in a dirty state - migrations may have already run partially")
			log.Println("To fix: Run 'docker exec trading-bot-postgres psql -U trading -d trading_bot -c \"DELETE FROM schema_migrations WHERE dirty = true;\"'")
			return fmt.Errorf("dirty database: %w", err)
		}
		// Ignore "already exists" errors - they mean migrations already ran
		if strings.Contains(err.Error(), "already exists") {
			log.Println("Database objects already exist - migrations already applied")
			return nil
		}
		return fmt.Errorf("failed to run migrations: %w", err)
	}

	log.Println("Database migrations completed successfully")
	return nil
}

// RollbackMigrations rolls back the last migration
func RollbackMigrations(databaseURL string) error {
	m, err := migrate.New(
		"file://migrations",
		databaseURL,
	)
	if err != nil {
		return fmt.Errorf("failed to create migrate instance: %w", err)
	}
	defer m.Close()

	if err := m.Steps(-1); err != nil {
		return fmt.Errorf("failed to rollback migration: %w", err)
	}

	log.Println("Migration rollback completed successfully")
	return nil
}

// GetMigrationVersion returns the current database version
func GetMigrationVersion(databaseURL string) (uint, error) {
	m, err := migrate.New(
		"file://migrations",
		databaseURL,
	)
	if err != nil {
		return 0, fmt.Errorf("failed to create migrate instance: %w", err)
	}
	defer m.Close()

	version, dirty, err := m.Version()
	if err != nil {
		return 0, fmt.Errorf("failed to get migration version: %w", err)
	}

	if dirty {
		log.Println("Warning: Database is in a dirty state")
	}

	return version, nil
}
