-- Add indexes for better query performance

-- Index for order lookup by status and symbol
CREATE INDEX IF NOT EXISTS idx_orders_status_symbol ON orders (status, symbol);

-- Index for trade history by executed_at and symbol
CREATE INDEX IF NOT EXISTS idx_trade_history_symbol_executed ON trade_history (symbol, executed_at DESC);

-- Add comment
COMMENT ON INDEX idx_orders_status_symbol IS 'Added in migration 002 - Performance improvement for order queries';
COMMENT ON INDEX idx_trade_history_symbol_executed IS 'Added in migration 002 - Performance improvement for trade history queries';
