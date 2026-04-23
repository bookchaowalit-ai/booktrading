-- Migration: 017_add_dex_support.down.sql
-- Remove DEX/AMM support tables

DROP INDEX IF EXISTS idx_dex_liquidity_history_wallet_id;
DROP INDEX IF EXISTS idx_dex_liquidity_history_user_id;
DROP INDEX IF EXISTS idx_dex_swap_history_tx_hash;
DROP INDEX IF EXISTS idx_dex_swap_history_wallet_id;
DROP INDEX IF EXISTS idx_dex_swap_history_user_id;
DROP INDEX IF EXISTS idx_dex_liquidity_positions_wallet_id;
DROP INDEX IF EXISTS idx_dex_liquidity_positions_user_id;
DROP INDEX IF EXISTS idx_dex_wallets_address;
DROP INDEX IF EXISTS idx_dex_wallets_user_id;

DROP TABLE IF EXISTS dex_user_settings;
DROP TABLE IF EXISTS dex_liquidity_history;
DROP TABLE IF EXISTS dex_swap_history;
DROP TABLE IF EXISTS dex_liquidity_positions;
DROP TABLE IF EXISTS dex_tokens;
DROP TABLE IF EXISTS dex_wallets;
