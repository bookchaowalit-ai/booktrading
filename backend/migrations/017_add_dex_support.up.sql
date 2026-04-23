-- Migration: 017_add_dex_support.up.sql
-- Add DEX/AMM support tables

-- DEX wallets table (stores encrypted private keys)
CREATE TABLE IF NOT EXISTS dex_wallets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    address VARCHAR(42) NOT NULL UNIQUE,
    chain_id BIGINT NOT NULL,
    private_key_encrypted TEXT NOT NULL,
    public_key TEXT,
    label VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- DEX token list (tracked tokens)
CREATE TABLE IF NOT EXISTS dex_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chain_id BIGINT NOT NULL,
    address VARCHAR(42) NOT NULL,
    symbol VARCHAR(20) NOT NULL,
    name VARCHAR(100),
    decimals SMALLINT NOT NULL DEFAULT 18,
    logo_uri TEXT,
    is_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(chain_id, address)
);

-- DEX liquidity positions
CREATE TABLE IF NOT EXISTS dex_liquidity_positions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL REFERENCES dex_wallets(id) ON DELETE CASCADE,
    pool_address VARCHAR(42) NOT NULL,
    dex_provider VARCHAR(50) NOT NULL,
    chain_id BIGINT NOT NULL,
    token0_address VARCHAR(42) NOT NULL,
    token1_address VARCHAR(42) NOT NULL,
    token0_amount NUMERIC(78, 0),
    token1_amount NUMERIC(78, 0),
    lp_token_amount NUMERIC(78, 0),
    initial_deposit_usd NUMERIC(20, 2),
    current_value_usd NUMERIC(20, 2),
    fees_earned_usd NUMERIC(20, 2) DEFAULT 0,
    impermanent_loss_pct NUMERIC(10, 4),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- DEX swap history
CREATE TABLE IF NOT EXISTS dex_swap_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL REFERENCES dex_wallets(id) ON DELETE CASCADE,
    tx_hash VARCHAR(66) NOT NULL UNIQUE,
    dex_provider VARCHAR(50) NOT NULL,
    chain_id BIGINT NOT NULL,
    token_in_address VARCHAR(42) NOT NULL,
    token_out_address VARCHAR(42) NOT NULL,
    token_in_amount NUMERIC(78, 0) NOT NULL,
    token_out_amount NUMERIC(78, 0),
    token_out_amount_expected NUMERIC(78, 0),
    price_impact_pct NUMERIC(10, 4),
    gas_used BIGINT,
    gas_price_gwei NUMERIC(20, 2),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE
);

-- DEX add/remove liquidity history
CREATE TABLE IF NOT EXISTS dex_liquidity_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    wallet_id UUID NOT NULL REFERENCES dex_wallets(id) ON DELETE CASCADE,
    tx_hash VARCHAR(66) NOT NULL UNIQUE,
    dex_provider VARCHAR(50) NOT NULL,
    chain_id BIGINT NOT NULL,
    action VARCHAR(20) NOT NULL, -- 'add' or 'remove'
    pool_address VARCHAR(42) NOT NULL,
    token0_address VARCHAR(42),
    token1_address VARCHAR(42),
    token0_amount NUMERIC(78, 0),
    token1_amount NUMERIC(78, 0),
    lp_token_amount NUMERIC(78, 0),
    gas_used BIGINT,
    gas_price_gwei NUMERIC(20, 2),
    status VARCHAR(20) DEFAULT 'pending',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    confirmed_at TIMESTAMP WITH TIME ZONE
);

-- DEX settings per user
CREATE TABLE IF NOT EXISTS dex_user_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    default_dex_provider VARCHAR(50) DEFAULT 'uniswap_v3',
    slippage_tolerance NUMERIC(5, 2) DEFAULT 0.5,
    max_price_impact NUMERIC(5, 2) DEFAULT 3.0,
    auto_route BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes
CREATE INDEX idx_dex_wallets_user_id ON dex_wallets(user_id);
CREATE INDEX idx_dex_wallets_address ON dex_wallets(address);
CREATE INDEX idx_dex_liquidity_positions_user_id ON dex_liquidity_positions(user_id);
CREATE INDEX idx_dex_liquidity_positions_wallet_id ON dex_liquidity_positions(wallet_id);
CREATE INDEX idx_dex_swap_history_user_id ON dex_swap_history(user_id);
CREATE INDEX idx_dex_swap_history_wallet_id ON dex_swap_history(wallet_id);
CREATE INDEX idx_dex_swap_history_tx_hash ON dex_swap_history(tx_hash);
CREATE INDEX idx_dex_liquidity_history_user_id ON dex_liquidity_history(user_id);
CREATE INDEX idx_dex_liquidity_history_wallet_id ON dex_liquidity_history(wallet_id);
