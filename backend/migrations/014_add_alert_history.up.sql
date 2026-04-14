-- +migrate Up
-- Persist alert history
CREATE TABLE IF NOT EXISTS alert_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    channel VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    data JSONB,
    sent BOOLEAN DEFAULT FALSE,
    sent_at TIMESTAMPTZ,
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_alert_history_type ON alert_history(alert_type);
CREATE INDEX idx_alert_history_channel ON alert_history(channel);
CREATE INDEX idx_alert_history_created_at ON alert_history(created_at DESC);

-- +migrate Down
DROP TABLE IF EXISTS alert_history;
