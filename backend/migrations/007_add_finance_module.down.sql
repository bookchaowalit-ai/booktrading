-- Migration 007: Rollback Finance Module tables

DROP TRIGGER IF EXISTS update_finance_recurring_updated_at ON finance_recurring_transactions;
DROP TRIGGER IF EXISTS update_finance_diary_updated_at ON finance_diary_entries;
DROP TRIGGER IF EXISTS update_finance_subscriptions_updated_at ON finance_subscriptions;
DROP TRIGGER IF EXISTS update_finance_liabilities_updated_at ON finance_liabilities;
DROP TRIGGER IF EXISTS update_finance_assets_updated_at ON finance_assets;
DROP TRIGGER IF EXISTS update_finance_goals_updated_at ON finance_goals;
DROP TRIGGER IF EXISTS update_finance_budgets_updated_at ON finance_budgets;
DROP TRIGGER IF EXISTS update_finance_transactions_updated_at ON finance_transactions;
DROP TRIGGER IF EXISTS update_finance_categories_updated_at ON finance_categories;
DROP TRIGGER IF EXISTS update_finance_accounts_updated_at ON finance_accounts;

DROP TABLE IF EXISTS finance_net_worth_history;
DROP TABLE IF EXISTS finance_recurring_transactions;
DROP TABLE IF EXISTS finance_diary_entries;
DROP TABLE IF EXISTS finance_subscriptions;
DROP TABLE IF EXISTS finance_liabilities;
DROP TABLE IF EXISTS finance_assets;
DROP TABLE IF EXISTS finance_goals;
DROP TABLE IF EXISTS finance_budgets;
DROP TABLE IF EXISTS finance_transactions;
DROP TABLE IF EXISTS finance_categories;
DROP TABLE IF EXISTS finance_accounts;