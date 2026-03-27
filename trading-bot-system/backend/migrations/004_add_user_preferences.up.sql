-- User Preferences Table
-- Stores user-specific settings and preferences
CREATE TABLE IF NOT EXISTS user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),  -- For multi-user support (currently single user)
    language VARCHAR(10) NOT NULL DEFAULT 'en',
    theme VARCHAR(20) NOT NULL DEFAULT 'system',
    notifications_trade_executions BOOLEAN NOT NULL DEFAULT true,
    notifications_price_alerts BOOLEAN NOT NULL DEFAULT false,
    notifications_bot_status BOOLEAN NOT NULL DEFAULT true,
    notifications_errors BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id);

-- Insert default preferences for single user
INSERT INTO user_preferences (user_id, language, theme, notifications_trade_executions, notifications_price_alerts, notifications_bot_status, notifications_errors)
VALUES ('default', 'en', 'system', true, false, true, true)
ON CONFLICT DO NOTHING;

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_user_preferences_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to auto-update updated_at
DROP TRIGGER IF EXISTS update_user_preferences_updated_at ON user_preferences;
CREATE TRIGGER update_user_preferences_updated_at
    BEFORE UPDATE ON user_preferences
    FOR EACH ROW
    EXECUTE FUNCTION update_user_preferences_updated_at();
