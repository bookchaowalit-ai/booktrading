-- +migrate Up
-- Persist paper trading orders and positions
CREATE TABLE IF NOT EXISTS paper_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    type VARCHAR(20) DEFAULT 'LIMIT',
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    limit_price NUMERIC(20, 8),
    stop_loss_price NUMERIC(20, 8),
    take_profit_price NUMERIC(20, 8),
    status VARCHAR(20) DEFAULT 'FILLED',
    fee NUMERIC(20, 8) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);
CREATE INDEX idx_paper_orders_user_id ON paper_orders(user_id);
CREATE INDEX idx_paper_orders_symbol ON paper_orders(symbol);
CREATE INDEX idx_paper_orders_created_at ON paper_orders(created_at DESC);

CREATE TABLE IF NOT EXISTS paper_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36),
    symbol VARCHAR(20) NOT NULL UNIQUE,
    quantity NUMERIC(20, 8) DEFAULT 0,
    avg_entry_price NUMERIC(20, 8) DEFAULT 0,
    current_price NUMERIC(20, 8) DEFAULT 0,
    unrealized_pnl NUMERIC(20, 8) DEFAULT 0,
    realized_pnl NUMERIC(20, 8) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_paper_positions_user_id ON paper_positions(user_id);

CREATE TABLE IF NOT EXISTS paper_portfolios (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) UNIQUE,
    initial_balance NUMERIC(20, 8) DEFAULT 10000,
    current_balance NUMERIC(20, 8) DEFAULT 10000,
    total_value NUMERIC(20, 8) DEFAULT 10000,
    total_pnl NUMERIC(20, 8) DEFAULT 0,
    total_pnl_percent NUMERIC(10, 4) DEFAULT 0,
    total_trades INTEGER DEFAULT 0,
    win_trades INTEGER DEFAULT 0,
    loss_trades INTEGER DEFAULT 0,
    max_drawdown NUMERIC(10, 4) DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_paper_portfolios_user_id ON paper_portfolios(user_id);

-- +migrate Down
DROP TABLE IF EXISTS paper_orders;
DROP TABLE IF EXISTS paper_positions;
DROP TABLE IF EXISTS paper_portfolios;
