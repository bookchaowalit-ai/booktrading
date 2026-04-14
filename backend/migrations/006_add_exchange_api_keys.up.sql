-- Migration 006: Add exchange_api_keys table for storing encrypted API credentials

CREATE TABLE IF NOT EXISTS exchange_api_keys (
    provider VARCHAR(50) PRIMARY KEY,
    api_key TEXT NOT NULL,
    api_secret TEXT NOT NULL,
    use_testnet BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

DROP TRIGGER IF EXISTS update_exchange_api_keys_updated_at ON exchange_api_keys;
CREATE TRIGGER update_exchange_api_keys_updated_at BEFORE UPDATE ON exchange_api_keys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
