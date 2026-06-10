-- Migration: Advanced Personal Finance System Upgrade
-- Target Database: SQLite

-- 1. Add tags column to transactions table if it doesn't exist (handled programmatically in init_db as SQLite doesn't support IF NOT EXISTS in ALTER TABLE)
-- ALTER TABLE transactions ADD COLUMN tags TEXT;

-- 2. Add current_amount and target_amount columns to provisions table if they don't exist
-- ALTER TABLE provisions ADD COLUMN current_amount REAL DEFAULT 0.0;
-- ALTER TABLE provisions ADD COLUMN target_amount REAL DEFAULT 0.0;

-- 3. Create category_rules table
CREATE TABLE IF NOT EXISTS category_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern TEXT NOT NULL,
    category TEXT NOT NULL,
    rule_type TEXT DEFAULT 'contains', -- 'contains' or 'regex'
    tags TEXT -- comma-separated tags
);

-- 4. Create purchase_simulations table
CREATE TABLE IF NOT EXISTS purchase_simulations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    amount REAL NOT NULL,
    installments INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    category TEXT DEFAULT 'Compras',
    status TEXT DEFAULT 'pending' -- 'pending' or 'confirmed'
);
