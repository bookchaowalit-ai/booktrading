-- TimescaleDB hypertable for efficient time-series storage of market data
CREATE TABLE IF NOT EXISTS klines (
    time TIMESTAMPTZ NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    interval_type VARCHAR(10) NOT NULL,
    open NUMERIC(20, 8) NOT NULL,
    high NUMERIC(20, 8) NOT NULL,
    low NUMERIC(20, 8) NOT NULL,
    close NUMERIC(20, 8) NOT NULL,
    volume NUMERIC(20, 8) NOT NULL,
    close_time TIMESTAMPTZ,
    quote_volume NUMERIC(20, 8),
    trades INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (time, symbol, interval_type)
);

-- Convert to TimescaleDB hypertable (only if extension exists)
SELECT create_hypertable('klines', 'time', if_not_exists => TRUE);

CREATE INDEX IF NOT EXISTS idx_klines_symbol_interval ON klines(symbol, interval_type, time DESC);
CREATE INDEX IF NOT EXISTS idx_klines_time_desc ON klines(time DESC);
