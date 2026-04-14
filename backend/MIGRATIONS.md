# Database Migration Guide

## Overview

This project uses [golang-migrate](https://github.com/golang-migrate/migrate) for database schema versioning and migrations.

## Migration Files

Migration files are located in `backend/migrations/` and follow this naming convention:

```
NNNN_description.up.sql   # Upgrade migration
NNNN_description.down.sql # Downgrade migration
```

Example:
```
migrations/
├── 001_init_schema.up.sql
├── 001_init_schema.down.sql
├── 002_add_indexes.up.sql
├── 002_add_indexes.down.sql
└── 003_add_user_support.up.sql
└── 003_add_user_support.down.sql
```

## Running Migrations

### Option 1: Automatic (on application startup)

Migrations run automatically when the backend starts. Check the logs for:
```
Running database migrations...
Database migrations completed successfully
```

### Option 2: Manual CLI

```bash
cd backend

# Run all pending migrations
go run cmd/migrate/main.go up

# Rollback last migration
go run cmd/migrate/main.go down

# Check current version
go run cmd/migrate/main.go version

# Create new migration
go run cmd/migrate/main.go create add_new_column
```

### Option 3: Using DATABASE_URL

```bash
export DATABASE_URL="postgres://trading:trading123@localhost:5434/trading_bot?sslmode=disable"

go run cmd/migrate/main.go up
```

## Creating a New Migration

### 1. Generate Migration Files

```bash
cd backend
go run cmd/migrate/main.go create add_email_column
```

This creates:
- `migrations/004_add_email_column.up.sql`
- `migrations/004_add_email_column.down.sql`

### 2. Edit the Up Migration

Edit `004_add_email_column.up.sql`:

```sql
-- Add email column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255);
CREATE INDEX idx_users_email ON users (email);
```

### 3. Edit the Down Migration

Edit `004_add_email_column.down.sql`:

```sql
-- Remove email column from users table
DROP INDEX IF EXISTS idx_users_email;
ALTER TABLE users DROP COLUMN IF EXISTS email;
```

### 4. Test the Migration

```bash
# Apply migration
go run cmd/migrate/main.go up

# Verify changes
docker exec -it trading-bot-postgres psql -U trading -d trading_bot -c "\d users"

# Rollback to test
go run cmd/migrate/main.go down

# Re-apply
go run cmd/migrate/main.go up
```

## Migration Best Practices

### ✅ DO

1. **Always create both up and down migrations**
   ```sql
   -- 005_feature.up.sql
   ALTER TABLE orders ADD COLUMN priority INTEGER;
   
   -- 005_feature.down.sql
   ALTER TABLE orders DROP COLUMN priority;
   ```

2. **Make migrations idempotent when possible**
   ```sql
   CREATE TABLE IF NOT EXISTS ...
   ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...
   ```

3. **Use descriptive names**
   ```
   ✅ 006_add_trailing_stop_support.sql
   ❌ 006_add_column.sql
   ```

4. **Test migrations on a clean database**
   ```bash
   # Drop and recreate database
   docker compose down -v
   docker compose up postgres
   
   # Run migrations
   go run cmd/migrate/main.go up
   ```

5. **Add comments for complex changes**
   ```sql
   -- Add index for faster order lookup
   -- Added: 2024-01-15
   -- Reason: Issue #123 - Slow order history queries
   CREATE INDEX idx_orders_created ON orders (created_at DESC);
   ```

### ❌ DON'T

1. **Don't modify existing migration files**
   - Once committed, migrations are immutable
   - Create a new migration to fix issues

2. **Don't skip down migrations**
   - Always provide rollback capability
   - Test rollback before deploying

3. **Don't use database-specific features**
   - Keep migrations portable
   - Avoid TimescaleDB-specific features in core schema

## Troubleshooting

### Migration Error: "Dirty Database"

If a migration fails halfway, the database is marked as "dirty":

```bash
# Force migration to a specific version
go run cmd/migrate/main.go force 1

# Or fix manually and clear dirty flag
docker exec -it trading-bot-postgres psql -U trading -d trading_bot -c "DELETE FROM schema_migrations WHERE dirty=true;"
```

### Check Migration Status

```sql
-- View migration history
SELECT * FROM schema_migrations ORDER BY version;

-- Current version
SELECT version, dirty FROM schema_migrations ORDER BY version DESC LIMIT 1;
```

### Rollback Multiple Migrations

```bash
# Rollback 3 migrations
go run cmd/migrate/main.go down
go run cmd/migrate/main.go down
go run cmd/migrate/main.go down

# Or use force to go to specific version
go run cmd/migrate/main.go force 1
```

## Example Migration Scenarios

### Add a Column

```sql
-- 007_add_stop_loss.up.sql
ALTER TABLE orders ADD COLUMN stop_loss DECIMAL(10,2);
ALTER TABLE orders ADD COLUMN take_profit DECIMAL(10,2);

-- 007_add_stop_loss.down.sql
ALTER TABLE orders DROP COLUMN stop_loss;
ALTER TABLE orders DROP COLUMN take_profit;
```

### Create a New Table

```sql
-- 008_create_strategies.up.sql
CREATE TABLE strategies (
    id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    config JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 008_create_strategies.down.sql
DROP TABLE IF EXISTS strategies;
```

### Add Index for Performance

```sql
-- 009_add_performance_indexes.up.sql
CREATE INDEX CONCURRENTLY idx_market_data_symbol_time 
ON market_data (symbol, time DESC);

-- 009_add_performance_indexes.down.sql
DROP INDEX IF EXISTS idx_market_data_symbol_time;
```

### Update Data

```sql
-- 010_migrate_old_orders.up.sql
UPDATE orders 
SET status = 'ARCHIVED' 
WHERE status = 'PENDING' 
  AND created_at < NOW() - INTERVAL '30 days';

-- 010_migrate_old_orders.down.sql
-- No rollback needed for data updates
```

## Version History

| Version | Date | Description |
|---------|------|-------------|
| 001 | 2024-01-01 | Initial schema with TimescaleDB |
| 002 | 2024-01-02 | Performance indexes |
| 003 | 2024-01-03 | Multi-user support |

## More Information

- [golang-migrate Documentation](https://github.com/golang-migrate/migrate/blob/master/GETTING_STARTED.md)
- [PostgreSQL Migration Best Practices](https://www.postgresql.org/docs/current/sql-altertable.html)
- [TimescaleDB Hypertables](https://docs.timescale.com/use-timescale/latest/hypertables/)
