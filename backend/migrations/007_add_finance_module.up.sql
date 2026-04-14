-- Migration 007: Add Finance Module tables for personal finance management

-- ============================================
-- Accounts: Bank accounts, credit cards, cash, wallets
-- ============================================
CREATE TABLE IF NOT EXISTS finance_accounts (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'checking', 'savings', 'credit_card', 'cash', 'wallet', 'investment', 'loan'
    institution VARCHAR(200), -- Bank name or institution
    account_number VARCHAR(50), -- Last 4 digits or masked number
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    balance DOUBLE PRECISION NOT NULL DEFAULT 0,
    credit_limit DOUBLE PRECISION, -- For credit cards
    interest_rate DOUBLE PRECISION, -- For loans/savings
    color VARCHAR(20), -- UI color
    icon VARCHAR(50), -- Icon name
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    include_in_net_worth BOOLEAN NOT NULL DEFAULT TRUE,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_accounts_user_id ON finance_accounts (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_accounts_type ON finance_accounts (type);

DROP TRIGGER IF EXISTS update_finance_accounts_updated_at ON finance_accounts;
CREATE TRIGGER update_finance_accounts_updated_at BEFORE UPDATE ON finance_accounts
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Categories: Transaction categories
-- ============================================
CREATE TABLE IF NOT EXISTS finance_categories (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(100) NOT NULL,
    type VARCHAR(20) NOT NULL, -- 'income', 'expense', 'transfer'
    parent_id VARCHAR(100), -- For subcategories
    color VARCHAR(20),
    icon VARCHAR(50),
    budget_amount DOUBLE PRECISION DEFAULT 0,
    is_system BOOLEAN NOT NULL DEFAULT FALSE, -- System default categories
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (parent_id) REFERENCES finance_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_categories_user_id ON finance_categories (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_categories_type ON finance_categories (type);

DROP TRIGGER IF EXISTS update_finance_categories_updated_at ON finance_categories;
CREATE TRIGGER update_finance_categories_updated_at BEFORE UPDATE ON finance_categories
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Transactions: Income, expenses, transfers
-- ============================================
CREATE TABLE IF NOT EXISTS finance_transactions (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    account_id VARCHAR(100) NOT NULL,
    category_id VARCHAR(100),
    type VARCHAR(20) NOT NULL, -- 'income', 'expense', 'transfer'
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    description TEXT,
    payee VARCHAR(200), -- Who received/paid
    date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_recurring BOOLEAN NOT NULL DEFAULT FALSE,
    recurring_id VARCHAR(100), -- Link to recurring transaction
    tags TEXT[], -- Array of tags
    attachments TEXT[], -- File paths for receipts
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    location_name VARCHAR(200),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (account_id) REFERENCES finance_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES finance_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_transactions_user_id ON finance_transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_account_id ON finance_transactions (account_id);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_category_id ON finance_transactions (category_id);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_date ON finance_transactions (date DESC);
CREATE INDEX IF NOT EXISTS idx_finance_transactions_type ON finance_transactions (type);

DROP TRIGGER IF EXISTS update_finance_transactions_updated_at ON finance_transactions;
CREATE TRIGGER update_finance_transactions_updated_at BEFORE UPDATE ON finance_transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Budgets: Monthly/category budgets
-- ============================================
CREATE TABLE IF NOT EXISTS finance_budgets (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    category_id VARCHAR(100), -- NULL for overall budget
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    period VARCHAR(20) NOT NULL DEFAULT 'monthly', -- 'weekly', 'monthly', 'yearly'
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    alert_threshold DOUBLE PRECISION DEFAULT 80, -- Alert at 80% spent
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (category_id) REFERENCES finance_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_budgets_user_id ON finance_budgets (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_budgets_category_id ON finance_budgets (category_id);

DROP TRIGGER IF EXISTS update_finance_budgets_updated_at ON finance_budgets;
CREATE TRIGGER update_finance_budgets_updated_at BEFORE UPDATE ON finance_budgets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Goals: Financial goals (savings, debt payoff, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS finance_goals (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'savings', 'debt_payoff', 'investment', 'emergency_fund', 'custom'
    target_amount DOUBLE PRECISION NOT NULL,
    current_amount DOUBLE PRECISION NOT NULL DEFAULT 0,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    target_date TIMESTAMPTZ,
    monthly_contribution DOUBLE PRECISION DEFAULT 0,
    priority VARCHAR(20) NOT NULL DEFAULT 'medium', -- 'low', 'medium', 'high'
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'completed', 'paused', 'cancelled'
    color VARCHAR(20),
    icon VARCHAR(50),
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_goals_user_id ON finance_goals (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_goals_status ON finance_goals (status);

DROP TRIGGER IF EXISTS update_finance_goals_updated_at ON finance_goals;
CREATE TRIGGER update_finance_goals_updated_at BEFORE UPDATE ON finance_goals
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Assets: Non-trading assets (real estate, vehicles, etc.)
-- ============================================
CREATE TABLE IF NOT EXISTS finance_assets (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'real_estate', 'vehicle', 'jewelry', 'collectibles', 'business', 'other'
    description TEXT,
    purchase_price DOUBLE PRECISION NOT NULL,
    current_value DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    purchase_date TIMESTAMPTZ,
    location VARCHAR(200),
    documents TEXT[], -- File paths for documents
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_assets_user_id ON finance_assets (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_assets_type ON finance_assets (type);

DROP TRIGGER IF EXISTS update_finance_assets_updated_at ON finance_assets;
CREATE TRIGGER update_finance_assets_updated_at BEFORE UPDATE ON finance_assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Liabilities: Debts, loans, mortgages
-- ============================================
CREATE TABLE IF NOT EXISTS finance_liabilities (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    type VARCHAR(50) NOT NULL, -- 'mortgage', 'car_loan', 'student_loan', 'credit_card', 'personal_loan', 'other'
    lender VARCHAR(200),
    original_amount DOUBLE PRECISION NOT NULL,
    current_balance DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    interest_rate DOUBLE PRECISION,
    interest_type VARCHAR(20), -- 'fixed', 'variable'
    minimum_payment DOUBLE PRECISION,
    due_date INTEGER, -- Day of month for payment
    start_date TIMESTAMPTZ,
    end_date TIMESTAMPTZ, -- Expected payoff date
    status VARCHAR(20) NOT NULL DEFAULT 'active', -- 'active', 'paid_off', 'defaulted'
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_liabilities_user_id ON finance_liabilities (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_liabilities_type ON finance_liabilities (type);

DROP TRIGGER IF EXISTS update_finance_liabilities_updated_at ON finance_liabilities;
CREATE TRIGGER update_finance_liabilities_updated_at BEFORE UPDATE ON finance_liabilities
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Subscriptions: Recurring payments/subscriptions
-- ============================================
CREATE TABLE IF NOT EXISTS finance_subscriptions (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    name VARCHAR(200) NOT NULL,
    description TEXT,
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    billing_cycle VARCHAR(20) NOT NULL DEFAULT 'monthly', -- 'weekly', 'monthly', 'quarterly', 'yearly'
    next_billing_date TIMESTAMPTZ,
    last_billing_date TIMESTAMPTZ,
    account_id VARCHAR(100), -- Account to charge
    category_id VARCHAR(100),
    provider VARCHAR(200), -- Service provider
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    reminder_days INTEGER DEFAULT 3, -- Remind X days before
    color VARCHAR(20),
    icon VARCHAR(50),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (account_id) REFERENCES finance_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES finance_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_subscriptions_user_id ON finance_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_subscriptions_next_billing ON finance_subscriptions (next_billing_date);

DROP TRIGGER IF EXISTS update_finance_subscriptions_updated_at ON finance_subscriptions;
CREATE TRIGGER update_finance_subscriptions_updated_at BEFORE UPDATE ON finance_subscriptions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Financial Diary Entries: Daily financial journal
-- ============================================
CREATE TABLE IF NOT EXISTS finance_diary_entries (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    title VARCHAR(200),
    content TEXT,
    mood VARCHAR(50), -- 'great', 'good', 'neutral', 'bad', 'terrible'
    financial_mood VARCHAR(50), -- 'confident', 'anxious', 'stressed', 'hopeful', 'neutral'
    spending_reflection TEXT, -- Reflection on spending
    savings_wins TEXT, -- What went well with savings
    lessons_learned TEXT, -- Financial lessons
    tomorrow_goals TEXT, -- Goals for tomorrow
    gratitude TEXT, -- Financial gratitude
    total_spent DOUBLE PRECISION DEFAULT 0,
    total_earned DOUBLE PRECISION DEFAULT 0,
    tags TEXT[],
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_diary_user_id ON finance_diary_entries (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_diary_date ON finance_diary_entries (date DESC);

DROP TRIGGER IF EXISTS update_finance_diary_updated_at ON finance_diary_entries;
CREATE TRIGGER update_finance_diary_updated_at BEFORE UPDATE ON finance_diary_entries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Recurring Transactions: Templates for recurring income/expenses
-- ============================================
CREATE TABLE IF NOT EXISTS finance_recurring_transactions (
    id VARCHAR(100) PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    account_id VARCHAR(100),
    category_id VARCHAR(100),
    type VARCHAR(20) NOT NULL, -- 'income', 'expense'
    amount DOUBLE PRECISION NOT NULL,
    currency VARCHAR(10) NOT NULL DEFAULT 'THB',
    description TEXT,
    payee VARCHAR(200),
    frequency VARCHAR(20) NOT NULL, -- 'daily', 'weekly', 'biweekly', 'monthly', 'quarterly', 'yearly'
    start_date TIMESTAMPTZ NOT NULL,
    end_date TIMESTAMPTZ,
    next_occurrence TIMESTAMPTZ NOT NULL,
    last_occurrence TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    auto_create BOOLEAN NOT NULL DEFAULT FALSE, -- Auto-create transaction
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    FOREIGN KEY (account_id) REFERENCES finance_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (category_id) REFERENCES finance_categories(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_finance_recurring_user_id ON finance_recurring_transactions (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_recurring_next ON finance_recurring_transactions (next_occurrence);

DROP TRIGGER IF EXISTS update_finance_recurring_updated_at ON finance_recurring_transactions;
CREATE TRIGGER update_finance_recurring_updated_at BEFORE UPDATE ON finance_recurring_transactions
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- Net Worth History: Track net worth over time
-- ============================================
CREATE TABLE IF NOT EXISTS finance_net_worth_history (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL DEFAULT 'default',
    date TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    total_assets DOUBLE PRECISION NOT NULL DEFAULT 0,
    total_liabilities DOUBLE PRECISION NOT NULL DEFAULT 0,
    net_worth DOUBLE PRECISION NOT NULL DEFAULT 0,
    breakdown JSONB, -- JSON with breakdown by category
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_finance_net_worth_user_id ON finance_net_worth_history (user_id);
CREATE INDEX IF NOT EXISTS idx_finance_net_worth_date ON finance_net_worth_history (date DESC);

-- ============================================
-- Insert default categories
-- ============================================
INSERT INTO finance_categories (id, user_id, name, type, color, icon, is_system) VALUES
-- Expense categories
('cat-food', 'system', 'Food & Dining', 'expense', '#FF6B6B', 'utensils', true),
('cat-transport', 'system', 'Transportation', 'expense', '#4ECDC4', 'car', true),
('cat-shopping', 'system', 'Shopping', 'expense', '#45B7D1', 'shopping-bag', true),
('cat-entertainment', 'system', 'Entertainment', 'expense', '#96CEB4', 'film', true),
('cat-bills', 'system', 'Bills & Utilities', 'expense', '#FFEAA7', 'file-invoice-dollar', true),
('cat-health', 'system', 'Health & Medical', 'expense', '#DDA0DD', 'heart', true),
('cat-education', 'system', 'Education', 'expense', '#98D8C8', 'graduation-cap', true),
('cat-travel', 'system', 'Travel', 'expense', '#F7DC6F', 'plane', true),
('cat-gifts', 'system', 'Gifts & Donations', 'expense', '#BB8FCE', 'gift', true),
('cat-personal', 'system', 'Personal Care', 'expense', '#85C1E9', 'user', true),
('cat-home', 'system', 'Home & Living', 'expense', '#F8B500', 'home', true),
('cat-insurance', 'system', 'Insurance', 'expense', '#E74C3C', 'shield-alt', true),
('cat-debt', 'system', 'Debt Payments', 'expense', '#C0392B', 'credit-card', true),
('cat-savings', 'system', 'Savings & Investments', 'expense', '#27AE60', 'piggy-bank', true),
('cat-other-expense', 'system', 'Other Expense', 'expense', '#95A5A6', 'ellipsis-h', true),
-- Income categories
('cat-salary', 'system', 'Salary', 'income', '#2ECC71', 'briefcase', true),
('cat-freelance', 'system', 'Freelance', 'income', '#3498DB', 'laptop', true),
('cat-business', 'system', 'Business', 'income', '#9B59B6', 'building', true),
('cat-investments', 'system', 'Investments', 'income', '#F39C12', 'chart-line', true),
('cat-rental', 'system', 'Rental Income', 'income', '#1ABC9C', 'key', true),
('cat-dividends', 'system', 'Dividends', 'income', '#16A085', 'coins', true),
('cat-interest', 'system', 'Interest', 'income', '#27AE60', 'percent', true),
('cat-gifts-income', 'system', 'Gifts Received', 'income', '#E91E63', 'gift', true),
('cat-refund', 'system', 'Refunds', 'income', '#00BCD4', 'undo', true),
('cat-other-income', 'system', 'Other Income', 'income', '#95A5A6', 'ellipsis-h', true),
-- Transfer category
('cat-transfer', 'system', 'Transfer', 'transfer', '#7F8C8D', 'exchange-alt', true)
ON CONFLICT (id) DO NOTHING;