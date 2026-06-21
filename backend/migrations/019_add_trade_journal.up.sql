-- +migrate Up
-- Trade journal: records every trade signal with full context
CREATE TABLE IF NOT EXISTS trade_journal (
    id BIGSERIAL PRIMARY KEY,
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    strategy VARCHAR(40) DEFAULT 'grid_bot_v2',
    entry_reason TEXT DEFAULT '',
    entry_price NUMERIC(20, 8) NOT NULL DEFAULT 0,
    quantity NUMERIC(20, 8) NOT NULL DEFAULT 0,
    expected_risk_thb NUMERIC(20, 8) DEFAULT 0,
    expected_reward_thb NUMERIC(20, 8) DEFAULT 0,
    stop_loss_price NUMERIC(20, 8) DEFAULT 0,
    take_profit_price NUMERIC(20, 8) DEFAULT 0,
    exit_price NUMERIC(20, 8) DEFAULT 0,
    exit_reason TEXT DEFAULT '',
    actual_pnl NUMERIC(20, 8) DEFAULT 0,
    fee NUMERIC(20, 8) DEFAULT 0,
    drawdown_impact_pct NUMERIC(10, 4) DEFAULT 0,
    exchange_order_id VARCHAR(64),
    status VARCHAR(20) DEFAULT 'OPEN',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_journal_symbol ON trade_journal(symbol);
CREATE INDEX IF NOT EXISTS idx_journal_status ON trade_journal(status);
CREATE INDEX IF NOT EXISTS idx_journal_strategy ON trade_journal(strategy);
CREATE INDEX IF NOT EXISTS idx_journal_created_at ON trade_journal(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_journal_exchange_oid ON trade_journal(exchange_order_id);

-- +migrate Down
DROP TABLE IF EXISTS trade_journal;
