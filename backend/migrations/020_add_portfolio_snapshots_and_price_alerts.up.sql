-- +migrate Up
-- Periodic portfolio value snapshots for sparkline charts
CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_value NUMERIC(20, 8) NOT NULL,
    current_balance NUMERIC(20, 8) NOT NULL,
    positions_value NUMERIC(20, 8) NOT NULL DEFAULT 0,
    total_pnl NUMERIC(20, 8) NOT NULL DEFAULT 0,
    total_trades INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_created_at ON portfolio_snapshots(created_at DESC);

-- Price alert levels
CREATE TABLE IF NOT EXISTS price_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol VARCHAR(20) NOT NULL,
    target_price NUMERIC(20, 8) NOT NULL,
    direction VARCHAR(10) NOT NULL DEFAULT 'ABOVE', -- ABOVE or BELOW
    triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_price_alerts_symbol ON price_alerts(symbol);
CREATE INDEX IF NOT EXISTS idx_price_alerts_triggered ON price_alerts(triggered);

-- +migrate Down
DROP TABLE IF EXISTS portfolio_snapshots;
DROP TABLE IF EXISTS price_alerts;
