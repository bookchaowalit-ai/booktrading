-- Drop all tables (in reverse order of creation)

-- Drop continuous aggregate
DROP MATERIALIZED VIEW IF EXISTS market_data_1m;

-- Drop tables
DROP TABLE IF EXISTS bot_status;
DROP TABLE IF EXISTS portfolio;
DROP TABLE IF EXISTS trade_history;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS market_data;

-- Drop TimescaleDB extension (optional - will remove all hypertables)
-- DROP EXTENSION IF EXISTS timescaledb CASCADE;
