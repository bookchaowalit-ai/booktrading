-- PaperEngine persistence table.
-- Migration 013 creates the API-facing paper_orders/positions/portfolios tables,
-- while the Go engine persists its filled-order history in paper_trades.
CREATE TABLE IF NOT EXISTS paper_trades (
    id UUID PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    type VARCHAR(20) NOT NULL DEFAULT 'LIMIT',
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    limit_price NUMERIC(20, 8) DEFAULT 0,
    fee NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) NOT NULL DEFAULT 'FILLED',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_paper_trades_symbol ON paper_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_paper_trades_created_at ON paper_trades(created_at DESC);
