// Migration CLI tool
// Usage:
//   go run cmd/migrate/main.go up       - Run all pending migrations
//   go run cmd/migrate/main.go down     - Rollback last migration
//   go run cmd/migrate/main.go version  - Show current version
//   go run cmd/migrate/main.go create NAME - Create new migration

package main

import (
	"flag"
	"fmt"
	"log/slog"
	"os"

	"github.com/golang-migrate/migrate/v4"
	_ "github.com/golang-migrate/migrate/v4/database/pgx/v5"
	_ "github.com/golang-migrate/migrate/v4/source/file"
)

func main() {
	databaseURL := flag.String("db", "", "Database URL (e.g., postgres://user:pass@host:port/db?sslmode=disable)")
	flag.Parse()

	if *databaseURL == "" {
		// Try to get from environment
		*databaseURL = os.Getenv("DATABASE_URL")
	}

	if *databaseURL == "" {
		slog.Error("Database URL is required. Use -db flag or DATABASE_URL environment variable")
		os.Exit(1)
	}

	args := flag.Args()
	if len(args) == 0 {
		printUsage()
		os.Exit(1)
	}

	command := args[0]

	switch command {
	case "up":
		migrateUp(*databaseURL)
	case "down":
		migrateDown(*databaseURL)
	case "version":
		showVersion(*databaseURL)
	case "create":
		if len(args) < 2 {
			slog.Error("Migration name required. Usage: migrate create NAME")
			os.Exit(1)
		}
		createMigration(args[1])
	default:
		printUsage()
		os.Exit(1)
	}
}

func printUsage() {
	fmt.Println(`Database Migration Tool

Usage:
  migrate [options] command [arguments]

Commands:
  up       Run all pending migrations
  down     Rollback last migration
  version  Show current migration version
  create   Create a new migration (generates up and down files)

Options:
  -db      Database URL (or use DATABASE_URL environment variable)

Examples:
  go run cmd/migrate/main.go up
  go run cmd/migrate/main.go down
  go run cmd/migrate/main.go version
  go run cmd/migrate/main.go create add_new_column
  DATABASE_URL=postgres://... go run cmd/migrate/main.go up`)
}

func migrateUp(databaseURL string) {
	m, err := migrate.New("file://migrations", databaseURL)
	if err != nil {
		slog.Error("Failed to create migrate instance: %v", err)
	}
	defer m.Close()

	if err := m.Up(); err != nil {
		if err == migrate.ErrNoChange {
			slog.Info("No new migrations to apply")
			return
		}
		slog.Error("Failed to run migrations: %v", err)
	}

	slog.Info("✓ Migrations applied successfully")
}

func migrateDown(databaseURL string) {
	m, err := migrate.New("file://migrations", databaseURL)
	if err != nil {
		slog.Error("Failed to create migrate instance: %v", err)
	}
	defer m.Close()

	if err := m.Steps(-1); err != nil {
		slog.Error("Failed to rollback migration: %v", err)
	}

	slog.Info("✓ Migration rolled back successfully")
}

func showVersion(databaseURL string) {
	m, err := migrate.New("file://migrations", databaseURL)
	if err != nil {
		slog.Error("Failed to create migrate instance: %v", err)
	}
	defer m.Close()

	version, dirty, err := m.Version()
	if err != nil {
		slog.Error("Failed to get migration version: %v", err)
	}

	if dirty {
		slog.Info("⚠️  Warning: Database is in a dirty state")
	}

	fmt.Printf("Current migration version: %d\n", version)
}

func createMigration(name string) {
	// Create migration files in migrations directory
	upFile := fmt.Sprintf("migrations/%04d_%s.up.sql", getNextMigrationNumber(), name)
	downFile := fmt.Sprintf("migrations/%04d_%s.down.sql", getNextMigrationNumber(), name)

	// Create files
	if err := os.WriteFile(upFile, []byte("-- Migration up\n"), 0644); err != nil {
		slog.Error("Failed to create up migration: %v", err)
	}

	if err := os.WriteFile(downFile, []byte("-- Migration down\n"), 0644); err != nil {
		slog.Error("Failed to create down migration: %v", err)
	}

	fmt.Printf("✓ Created migration files:\n  - %s\n  - %s\n", upFile, downFile)
}

func getNextMigrationNumber() int {
	// Simple implementation - count existing files
	files, err := os.ReadDir("migrations")
	if err != nil {
		return 1
	}
	return len(files)/2 + 1
}
