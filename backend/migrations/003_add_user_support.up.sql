-- Add user_id column to orders table for multi-user support

ALTER TABLE orders ADD COLUMN IF NOT EXISTS user_id VARCHAR(100) DEFAULT 'default';
ALTER TABLE orders ADD COLUMN IF NOT EXISTS notes TEXT;

-- Create index for user_id
CREATE INDEX IF NOT EXISTS idx_orders_user_id ON orders (user_id);

-- Add comment
COMMENT ON COLUMN orders.user_id IS 'Added in migration 003 - Multi-user support';
COMMENT ON COLUMN orders.notes IS 'Added in migration 003 - Order notes/comments';
