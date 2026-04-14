-- Remove indexes added in migration 002

DROP INDEX IF EXISTS idx_orders_status_symbol;
DROP INDEX IF EXISTS idx_trade_history_symbol_executed;
