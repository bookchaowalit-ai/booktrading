CREATE TABLE IF NOT EXISTS dca_bots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(36),
    symbol VARCHAR(20) NOT NULL,
    investment_amount NUMERIC(20, 8) NOT NULL,
    interval_minutes INTEGER NOT NULL,
    take_profit_percent NUMERIC(5, 2) DEFAULT 0,
    safety_order_multiplier NUMERIC(5, 2) DEFAULT 1.5,
    max_safety_orders INTEGER DEFAULT 3,
    price_deviation_percent NUMERIC(5, 2) DEFAULT 2.0,
    status VARCHAR(20) DEFAULT 'STOPPED',
    total_invested NUMERIC(20, 8) DEFAULT 0,
    total_sold NUMERIC(20, 8) DEFAULT 0,
    current_position_qty NUMERIC(20, 8) DEFAULT 0,
    avg_entry_price NUMERIC(20, 8) DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    stopped_at TIMESTAMP WITH TIME ZONE
);
CREATE INDEX idx_dca_bots_user_id ON dca_bots(user_id);
CREATE INDEX idx_dca_bots_status ON dca_bots(status);

CREATE TABLE IF NOT EXISTS dca_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bot_id UUID NOT NULL REFERENCES dca_bots(id),
    order_type VARCHAR(20) NOT NULL, -- 'BASE', 'SAFETY', 'TAKE_PROFIT'
    side VARCHAR(10) NOT NULL,
    quantity NUMERIC(20, 8) NOT NULL,
    price NUMERIC(20, 8) NOT NULL,
    total NUMERIC(20, 8) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    order_number INTEGER DEFAULT 1,
    executed_at TIMESTAMP WITH TIME ZONE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);
CREATE INDEX idx_dca_orders_bot_id ON dca_orders(bot_id);
