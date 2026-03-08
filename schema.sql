-- Finance Tracker — Database Schema
-- Run: psql -U ubuntu -d finance_tracker -f schema.sql

-- Create database (run separately as superuser):
-- CREATE DATABASE finance_tracker OWNER ubuntu;

-- Categories
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Category keywords for auto-categorization
CREATE TABLE IF NOT EXISTS category_keywords (
    id SERIAL PRIMARY KEY,
    category_id INTEGER NOT NULL REFERENCES categories(id) ON DELETE CASCADE,
    keyword VARCHAR(200) NOT NULL,
    UNIQUE(category_id, keyword)
);

CREATE INDEX IF NOT EXISTS idx_category_keywords_category ON category_keywords(category_id);

-- Uploads (each file upload)
CREATE TABLE IF NOT EXISTS uploads (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    source VARCHAR(50) NOT NULL,  -- hdfc_bank, icici_bank, icici_cc, hdfc_cc, amex_cc
    txn_count INTEGER DEFAULT 0,
    uploaded_at TIMESTAMP DEFAULT NOW()
);

-- Transactions
CREATE TABLE IF NOT EXISTS transactions (
    id SERIAL PRIMARY KEY,
    upload_id INTEGER REFERENCES uploads(id) ON DELETE CASCADE,
    date DATE NOT NULL,
    description TEXT NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    txn_type VARCHAR(10) NOT NULL CHECK (txn_type IN ('debit', 'credit')),
    source VARCHAR(50) NOT NULL,
    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    is_coupon BOOLEAN DEFAULT FALSE,
    coupon_platform VARCHAR(100),
    cashback_amount NUMERIC(10, 2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_upload ON transactions(upload_id);
CREATE INDEX IF NOT EXISTS idx_transactions_coupon ON transactions(is_coupon) WHERE is_coupon = TRUE;
CREATE INDEX IF NOT EXISTS idx_transactions_month ON transactions(EXTRACT(YEAR FROM date), EXTRACT(MONTH FROM date));

-- Seed categories and keywords
INSERT INTO categories (name) VALUES
    ('Food & Dining'),
    ('Groceries'),
    ('Transport'),
    ('Shopping'),
    ('Entertainment'),
    ('Subscriptions'),
    ('Utilities'),
    ('Rent & Housing'),
    ('Health & Fitness'),
    ('Education'),
    ('Travel'),
    ('Insurance'),
    ('Investments'),
    ('EMI & Loans'),
    ('Cash Withdrawal'),
    ('UPI Transfer'),
    ('Salary'),
    ('Refund'),
    ('Other')
ON CONFLICT (name) DO NOTHING;

-- Seed keywords (Indian spending patterns)
-- Food & Dining
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'swiggy', 'zomato', 'dominos', 'pizza hut', 'mcdonalds', 'kfc',
    'burger king', 'starbucks', 'cafe coffee day', 'ccd', 'chaayos',
    'haldiram', 'barbeque nation', 'restaurant', 'food', 'dining',
    'eatery', 'biryani', 'chai', 'uber eats', 'eatsure', 'box8',
    'faasos', 'behrouz', 'oven story', 'magicpin'
]) AS kw WHERE c.name = 'Food & Dining'
ON CONFLICT DO NOTHING;

-- Groceries
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'blinkit', 'bigbasket', 'zepto', 'dunzo', 'jiomart', 'grofers',
    'nature basket', 'dmart', 'reliance fresh', 'more supermarket',
    'spencer', 'star bazaar', 'grocery', 'supermarket', 'instamart',
    'swiggy instamart', 'bb now', 'country delight', 'milkbasket',
    'licious', 'freshtohome', 'fresh to home'
]) AS kw WHERE c.name = 'Groceries'
ON CONFLICT DO NOTHING;

-- Transport
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'uber', 'ola', 'rapido', 'metro', 'irctc', 'railway',
    'petrol', 'diesel', 'fuel', 'parking', 'fastag', 'toll',
    'indian oil', 'bharat petroleum', 'hp petrol', 'auto',
    'cab', 'taxi', 'namma yatri', 'uber auto', 'meru'
]) AS kw WHERE c.name = 'Transport'
ON CONFLICT DO NOTHING;

-- Shopping
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'meesho',
    'snapdeal', 'tatacliq', 'croma', 'reliance digital',
    'vijay sales', 'decathlon', 'ikea', 'h&m', 'zara',
    'uniqlo', 'lifestyle', 'shoppers stop', 'westside',
    'pantaloons', 'bewakoof', 'boat', 'noise', 'apple'
]) AS kw WHERE c.name = 'Shopping'
ON CONFLICT DO NOTHING;

-- Entertainment
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'pvr', 'inox', 'bookmyshow', 'book my show', 'netflix',
    'hotstar', 'prime video', 'sony liv', 'zee5', 'voot',
    'mubi', 'youtube premium', 'gaming', 'steam', 'playstation',
    'xbox', 'movie', 'cinema', 'theatre', 'concert'
]) AS kw WHERE c.name = 'Entertainment'
ON CONFLICT DO NOTHING;

-- Subscriptions
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'spotify', 'apple music', 'audible', 'kindle', 'notion',
    'chatgpt', 'openai', 'claude', 'anthropic', 'github',
    'figma', 'canva', 'adobe', 'microsoft 365', 'google one',
    'icloud', 'dropbox', 'vpn', 'nordvpn', 'expressvpn',
    'subscription', 'recurring', 'annual plan', 'premium'
]) AS kw WHERE c.name = 'Subscriptions'
ON CONFLICT DO NOTHING;

-- Utilities
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'electricity', 'water bill', 'gas bill', 'internet', 'broadband',
    'airtel', 'jio', 'vodafone', 'vi ', 'bsnl', 'act fibernet',
    'tata play', 'dth', 'recharge', 'mobile bill', 'phone bill',
    'wifi', 'postpaid'
]) AS kw WHERE c.name = 'Utilities'
ON CONFLICT DO NOTHING;

-- Rent & Housing
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'rent', 'house rent', 'maintenance', 'society', 'housing',
    'nobroker', 'magicbricks', 'urban clap', 'urbanclap', 'urban company',
    'plumber', 'electrician', 'carpenter', 'painter', 'cleaning'
]) AS kw WHERE c.name = 'Rent & Housing'
ON CONFLICT DO NOTHING;

-- Health & Fitness
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'pharmacy', 'medical', 'hospital', 'doctor', 'clinic',
    'apollo', 'medplus', 'netmeds', 'pharmeasy', '1mg', 'tata 1mg',
    'gym', 'cult.fit', 'cultfit', 'cure.fit', 'healthify',
    'lab test', 'diagnostic', 'dental', 'eye care', 'lens',
    'practo', 'mfine'
]) AS kw WHERE c.name = 'Health & Fitness'
ON CONFLICT DO NOTHING;

-- Education
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'udemy', 'coursera', 'skillshare', 'masterclass', 'brilliant',
    'unacademy', 'byju', 'book', 'kindle', 'education', 'course',
    'tuition', 'school', 'college', 'university', 'exam fee'
]) AS kw WHERE c.name = 'Education'
ON CONFLICT DO NOTHING;

-- Travel
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'makemytrip', 'goibibo', 'cleartrip', 'yatra', 'easemytrip',
    'airbnb', 'oyo', 'hotel', 'flight', 'indigo', 'air india',
    'spicejet', 'vistara', 'akasa', 'booking.com', 'agoda',
    'hostel', 'resort', 'holiday', 'trip', 'ixigo'
]) AS kw WHERE c.name = 'Travel'
ON CONFLICT DO NOTHING;

-- Insurance
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'insurance', 'lic', 'hdfc life', 'icici prudential', 'sbi life',
    'max life', 'star health', 'bajaj allianz', 'policy', 'premium',
    'digit insurance', 'acko', 'policybazaar'
]) AS kw WHERE c.name = 'Insurance'
ON CONFLICT DO NOTHING;

-- Investments
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'zerodha', 'groww', 'kuvera', 'coin', 'mutual fund', 'sip',
    'nps', 'ppf', 'fixed deposit', 'fd ', 'rd ', 'stocks',
    'shares', 'demat', 'trading', 'smallcase', 'upstox',
    'angel', 'motilal', 'edelweiss', 'nippon', 'dhan'
]) AS kw WHERE c.name = 'Investments'
ON CONFLICT DO NOTHING;

-- EMI & Loans
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'emi', 'loan', 'home loan', 'personal loan', 'car loan',
    'bajaj finserv', 'hdfc ltd', 'pnb housing', 'installment',
    'no cost emi', 'flexipay', 'pay later', 'simpl', 'lazypay',
    'slice', 'uni card'
]) AS kw WHERE c.name = 'EMI & Loans'
ON CONFLICT DO NOTHING;

-- Cash Withdrawal
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'atm', 'cash withdrawal', 'cash wdl', 'neft', 'self transfer',
    'atm/cash'
]) AS kw WHERE c.name = 'Cash Withdrawal'
ON CONFLICT DO NOTHING;

-- UPI Transfer
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'upi', 'gpay', 'google pay', 'phonepe', 'paytm', 'bhim',
    'imps', 'fund transfer', 'neft', 'rtgs'
]) AS kw WHERE c.name = 'UPI Transfer'
ON CONFLICT DO NOTHING;

-- Salary
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'salary', 'payroll', 'stipend', 'wages'
]) AS kw WHERE c.name = 'Salary'
ON CONFLICT DO NOTHING;

-- Refund
INSERT INTO category_keywords (category_id, keyword)
SELECT c.id, kw FROM categories c, UNNEST(ARRAY[
    'refund', 'reversal', 'cashback', 'credit back', 'return'
]) AS kw WHERE c.name = 'Refund'
ON CONFLICT DO NOTHING;
