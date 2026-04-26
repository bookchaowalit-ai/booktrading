-- +migrate Up
-- Create users table for authentication/authorization
-- This table was missing despite user_id being referenced in orders (migration 003)
CREATE TABLE IF NOT EXISTS users (
    id VARCHAR(36) PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    name VARCHAR(255) NOT NULL DEFAULT '',
    role VARCHAR(50) NOT NULL DEFAULT 'trader',
    password_hash VARCHAR(255) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Add foreign key constraint to orders table (was missing)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'fk_orders_user_id'
    ) THEN
        ALTER TABLE orders ADD CONSTRAINT fk_orders_user_id
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL;
    END IF;
END $$;

-- +migrate Down
DO $$
BEGIN
    ALTER TABLE orders DROP CONSTRAINT IF EXISTS fk_orders_user_id;
EXCEPTION
    WHEN undefined_table THEN NULL;
END $$;
DROP TABLE IF EXISTS users;
