-- Strategy profiles that users can share (anonymized)
CREATE TABLE IF NOT EXISTS strategy_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    owner_id VARCHAR(36) NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    strategy_type VARCHAR(50) NOT NULL,  -- rsi, ema_cross, macd, dca
    is_public BOOLEAN DEFAULT FALSE,
    parameters JSONB,
    performance JSONB,  -- cached performance metrics
    total_copiers INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_strategy_profiles_owner ON strategy_profiles(owner_id);
CREATE INDEX IF NOT EXISTS idx_strategy_profiles_public ON strategy_profiles(is_public) WHERE is_public = true;
CREATE INDEX IF NOT EXISTS idx_strategy_profiles_copiers ON strategy_profiles(total_copiers DESC);

-- Active copy relationships
CREATE TABLE IF NOT EXISTS copy_relationships (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    copier_id VARCHAR(36) NOT NULL,
    strategy_id UUID NOT NULL REFERENCES strategy_profiles(id),
    allocation_percent NUMERIC(5, 2) DEFAULT 100.0,  -- what % of copier's capital to use
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_copy_relationships_copier ON copy_relationships(copier_id);
CREATE INDEX IF NOT EXISTS idx_copy_relationships_strategy ON copy_relationships(strategy_id);
CREATE INDEX IF NOT EXISTS idx_copy_relationships_active ON copy_relationships(is_active) WHERE is_active = true;

-- Copy trade log (tracks copied trades)
CREATE TABLE IF NOT EXISTS copy_trades (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    copy_relationship_id UUID NOT NULL REFERENCES copy_relationships(id),
    original_trade_id VARCHAR(255),
    symbol VARCHAR(20) NOT NULL,
    side VARCHAR(10) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    entry_price NUMERIC(20, 8) NOT NULL,
    exit_price NUMERIC(20, 8),
    pnl NUMERIC(20, 8),
    status VARCHAR(20) DEFAULT 'OPEN',
    opened_at TIMESTAMPTZ DEFAULT NOW(),
    closed_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_copy_trades_relationship ON copy_trades(copy_relationship_id);
CREATE INDEX IF NOT EXISTS idx_copy_trades_status ON copy_trades(status);
