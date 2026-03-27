#!/bin/bash
# Migration helper script
# Usage: ./scripts/migrate.sh [up|down|version|create NAME]

set -e

# Database configuration
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5434}"
DB_USER="${DB_USER:-trading}"
DB_PASSWORD="${DB_PASSWORD:-trading123}"
DB_NAME="${DB_NAME:-trading_bot}"
DB_SSLMODE="${DB_SSLMODE:-disable}"

DATABASE_URL="postgres://${DB_USER}:${DB_PASSWORD}@${DB_HOST}:${DB_PORT}/${DB_NAME}?sslmode=${DB_SSLMODE}"

# Check if running in Docker
if command -v docker &> /dev/null; then
    # Run migration in Docker container
    docker run --rm \
        -v $(pwd)/backend/migrations:/app/migrations \
        -w /app \
        golang:1.21-alpine \
        sh -c "
            apk add --no-cache git && \
            cd /app && \
            go mod download && \
            go run cmd/migrate/main.go $@ -db '${DATABASE_URL}'
        "
else
    # Run locally if Go is installed
    cd backend
    DATABASE_URL="${DATABASE_URL}" go run cmd/migrate/main.go "$@"
fi
