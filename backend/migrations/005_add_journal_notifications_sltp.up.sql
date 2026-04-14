-- Migration 005: Add journal entries, notifications, and stop-loss/take-profit tables

-- Trading journal table
CREATE TABLE IF NOT EXISTS journal_entries (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    entry_price DOUBLE PRECISION NOT NULL,
    exit_price DOUBLE PRECISION,
    quantity DOUBLE PRECISION NOT NULL,
    pnl DOUBLE PRECISION NOT NULL DEFAULT 0,
    pnl_percent DOUBLE PRECISION NOT NULL DEFAULT 0,
    notes TEXT,
    rating INTEGER CHECK (rating >= 1 AND rating <= 5),
    strategy VARCHAR(100),
    emotions VARCHAR(100),
    lessons TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_journal_user_id ON journal_entries (user_id);
CREATE INDEX IF NOT EXISTS idx_journal_date ON journal_entries (date DESC);
CREATE INDEX IF NOT EXISTS idx_journal_symbol ON journal_entries (symbol);

DROP TRIGGER IF EXISTS update_journal_updated_at ON journal_entries;
CREATE TRIGGER update_journal_updated_at BEFORE UPDATE ON journal_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Notifications table
CREATE TABLE IF NOT EXISTS notifications (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    read BOOLEAN NOT NULL DEFAULT FALSE,
    priority VARCHAR(20) NOT NULL DEFAULT 'LOW'
);

CREATE INDEX IF NOT EXISTS idx_notifications_user_id ON notifications (user_id);
CREATE INDEX IF NOT EXISTS idx_notifications_timestamp ON notifications (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_read ON notifications (read);

-- Stop-loss / Take-profit config table
CREATE TABLE IF NOT EXISTS stop_loss_take_profit (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    symbol VARCHAR(20) NOT NULL,
    stop_loss_percent DOUBLE PRECISION,
    take_profit_percent DOUBLE PRECISION,
    stop_loss_price DOUBLE PRECISION,
    take_profit_price DOUBLE PRECISION,
    trailing_stop BOOLEAN NOT NULL DEFAULT FALSE,
    trailing_stop_percent DOUBLE PRECISION,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

CREATE INDEX IF NOT EXISTS idx_sltp_user_symbol ON stop_loss_take_profit (user_id, symbol);

DROP TRIGGER IF EXISTS update_sltp_updated_at ON stop_loss_take_profit;
CREATE TRIGGER update_sltp_updated_at BEFORE UPDATE ON stop_loss_take_profit
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
