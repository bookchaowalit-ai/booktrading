-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE;

-- Create hypertable for market data (time-series data)
CREATE TABLE IF NOT EXISTS market_data (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    volume DOUBLE PRECISION NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Convert to hypertable for time-series optimization
SELECT create_hypertable('market_data', 'time', if_not_exists => TRUE);

-- Create indexes for faster queries
CREATE INDEX IF NOT EXISTS idx_market_data_symbol_time ON market_data (symbol, time DESC);
CREATE INDEX IF NOT EXISTS idx_market_data_time ON market_data (time DESC);

-- Orders table
CREATE TABLE IF NOT EXISTS orders (
    id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    type VARCHAR(20) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION,
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_orders_symbol ON orders (symbol);
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders (status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON orders (created_at DESC);

-- Trade history table
CREATE TABLE IF NOT EXISTS trade_history (
    id VARCHAR(100) PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity DOUBLE PRECISION NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    total DOUBLE PRECISION NOT NULL,
    fee DOUBLE PRECISION NOT NULL,
    executed_at TIMESTAMPTZ DEFAULT NOW(),
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trade_history_symbol ON trade_history (symbol);
CREATE INDEX IF NOT EXISTS idx_trade_history_executed_at ON trade_history (executed_at DESC);

-- Portfolio table
CREATE TABLE IF NOT EXISTS portfolio (
    symbol VARCHAR(20) PRIMARY KEY,
    balance DOUBLE PRECISION NOT NULL DEFAULT 0,
    locked DOUBLE PRECISION NOT NULL DEFAULT 0,
    avg_buy_price DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Bot status table
CREATE TABLE IF NOT EXISTS bot_status (
    id SERIAL PRIMARY KEY,
    is_active BOOLEAN NOT NULL DEFAULT FALSE,
    started_at TIMESTAMPTZ,
    stopped_at TIMESTAMPTZ,
    total_trades INTEGER NOT NULL DEFAULT 0,
    total_profit DOUBLE PRECISION NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert initial bot status
INSERT INTO bot_status (is_active, total_trades, total_profit) 
VALUES (FALSE, 0, 0)
ON CONFLICT (id) DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at (drop first if exists to avoid conflicts)
DROP TRIGGER IF EXISTS update_orders_updated_at ON orders;
CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON orders
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_portfolio_updated_at ON portfolio;
CREATE TRIGGER update_portfolio_updated_at BEFORE UPDATE ON portfolio
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

DROP TRIGGER IF EXISTS update_bot_status_updated_at ON bot_status;
CREATE TRIGGER update_bot_status_updated_at BEFORE UPDATE ON bot_status
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create continuous aggregate for market data (1-minute candles)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM timescaledb_information.continuous_aggregates WHERE view_name = 'market_data_1m'
    ) THEN
        CREATE MATERIALIZED VIEW market_data_1m
        WITH (timescaledb.continuous) AS
        SELECT
            time_bucket('1 minute', time) AS bucket,
            symbol,
            first(price, time) AS open,
            max(price) AS high,
            min(price) AS low,
            last(price, time) AS close,
            sum(volume) AS volume
        FROM market_data
        GROUP BY bucket, symbol
        WITH NO DATA;
    END IF;
END
$$;

-- Add compression to market_data after 7 days (if not exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'market_data'
    ) AND NOT EXISTS (
        SELECT 1 FROM timescaledb_information.compression_policies WHERE hypertable_name = 'market_data'
    ) THEN
        PERFORM add_compression_policy('market_data', INTERVAL '7 days');
    END IF;
END
$$;

-- Add retention policy to drop data older than 90 days (if not exists)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM timescaledb_information.hypertables WHERE hypertable_name = 'market_data'
    ) AND NOT EXISTS (
        SELECT 1 FROM timescaledb_information.retention_policies WHERE hypertable_name = 'market_data'
    ) THEN
        PERFORM add_retention_policy('market_data', INTERVAL '90 days');
    END IF;
END
$$;
