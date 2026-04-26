CREATE TABLE IF NOT EXISTS rebalance_targets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    target_percent NUMERIC(5, 2) NOT NULL,  -- 0-100
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, symbol)
);
CREATE INDEX IF NOT EXISTS idx_rebalance_targets_user ON rebalance_targets(user_id);

CREATE TABLE IF NOT EXISTS rebalance_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36) NOT NULL,
    triggered_by VARCHAR(50) DEFAULT 'manual',  -- manual, scheduled, threshold
    allocations_before JSONB,  -- snapshot before rebalance
    allocations_after JSONB,   -- snapshot after rebalance
    trades_executed INTEGER DEFAULT 0,
    total_fees NUMERIC(20, 8) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'COMPLETED',
    executed_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_rebalance_history_user ON rebalance_history(user_id);
