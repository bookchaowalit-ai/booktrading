-- +migrate Up
-- Real trading order persistence
CREATE TABLE IF NOT EXISTS real_trades (
    id VARCHAR(64) PRIMARY KEY,
    exchange_order_id VARCHAR(64),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    type VARCHAR(20) DEFAULT 'MARKET',
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) DEFAULT 0,
    executed_qty NUMERIC(20, 8) DEFAULT 0,
    executed_price NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'PENDING',
    fee NUMERIC(20, 8) DEFAULT 0,
    exchange VARCHAR(20) DEFAULT 'binance',
    testnet BOOLEAN DEFAULT true,
    strategy VARCHAR(40),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    filled_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_real_trades_symbol ON real_trades(symbol);
CREATE INDEX IF NOT EXISTS idx_real_trades_status ON real_trades(status);
CREATE INDEX IF NOT EXISTS idx_real_trades_created_at ON real_trades(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_real_trades_strategy ON real_trades(strategy);

-- Real trade daily P&L summary
CREATE TABLE IF NOT EXISTS real_trade_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trade_date DATE NOT NULL UNIQUE,
    total_trades INTEGER DEFAULT 0,
    win_trades INTEGER DEFAULT 0,
    loss_trades INTEGER DEFAULT 0,
    total_pnl NUMERIC(20, 8) DEFAULT 0,
    total_volume NUMERIC(20, 8) DEFAULT 0,
    max_drawdown NUMERIC(20, 8) DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- +migrate Down
DROP TABLE IF EXISTS real_trades;
DROP TABLE IF EXISTS real_trade_summaries;
