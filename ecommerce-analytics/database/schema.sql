-- ============================================================
-- schema.sql — PostgreSQL Database Schema
-- E-Commerce Analytics Data Warehouse
-- ============================================================
--
-- WHAT IS A DATABASE SCHEMA?
--   A schema is the blueprint of your database — it defines
--   what tables exist, what columns they have, what data types
--   each column stores, and the relationships between tables.
--
-- DATABASE DESIGN PATTERN USED:
--   Normalized (3NF) for raw/staging tables.
--   Star Schema for the analytical marts layer.
--
-- HOW TO RUN:
--   psql -U ecommerce_user -d ecommerce_dw -f database/schema.sql
--   OR: It auto-runs via Docker Compose on first startup.
--
-- SCHEMAS (namespaces):
--   raw     → Original data, no transformations
--   staging → Cleaned and typed data
--   marts   → Star schema (facts + dimensions) for analytics
-- ============================================================

-- ── Create Schemas ──────────────────────────────────────────────────────────
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- ── Enable useful extensions ────────────────────────────────────────────────
-- uuid-ossp: Generate UUIDs (useful for primary keys)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
-- pg_trgm: Trigram text search (fast LIKE queries)
CREATE EXTENSION IF NOT EXISTS pg_trgm;


-- ============================================================
-- STAGING SCHEMA — Clean, typed, validated data
-- ============================================================

-- ── staging.categories ──────────────────────────────────────
-- Reference table for product categories.
-- This is a "lookup table" — small, rarely changes.
CREATE TABLE IF NOT EXISTS staging.categories (
    category_id   VARCHAR(10)  PRIMARY KEY,
    category_name VARCHAR(100) NOT NULL,
    department    VARCHAR(100) NOT NULL,
    _cleaned_at   TIMESTAMP    DEFAULT NOW(),
    _source_file  VARCHAR(255)
);

COMMENT ON TABLE  staging.categories              IS 'Product category reference data';
COMMENT ON COLUMN staging.categories.category_id  IS 'Unique category identifier (CAT0001 format)';
COMMENT ON COLUMN staging.categories.department   IS 'Top-level department grouping multiple categories';

-- ── staging.sellers ─────────────────────────────────────────
-- Marketplace sellers (third-party vendors).
CREATE TABLE IF NOT EXISTS staging.sellers (
    seller_id   VARCHAR(10)  PRIMARY KEY,
    seller_name VARCHAR(200) NOT NULL,
    city        VARCHAR(100),
    state       CHAR(2)      NOT NULL,
    zip_code    VARCHAR(10),
    email       VARCHAR(200),
    phone       VARCHAR(30),
    created_at  TIMESTAMP,
    _cleaned_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE staging.sellers IS 'Third-party marketplace seller profiles';

-- ── staging.customers ───────────────────────────────────────
-- Customer profiles. The "who" of every order.
CREATE TABLE IF NOT EXISTS staging.customers (
    customer_id VARCHAR(15)  PRIMARY KEY,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(200) NOT NULL UNIQUE,
    city        VARCHAR(100),
    state       CHAR(2),
    zip_code    VARCHAR(10),
    signup_date DATE         NOT NULL,
    is_active   BOOLEAN      DEFAULT TRUE,
    _cleaned_at TIMESTAMP    DEFAULT NOW()
);

COMMENT ON TABLE  staging.customers            IS 'Customer account profiles';
COMMENT ON COLUMN staging.customers.is_active  IS 'FALSE if account was deactivated or churned';

-- Index for fast email lookups
CREATE INDEX IF NOT EXISTS idx_customers_email ON staging.customers(email);
-- Index for geographic queries
CREATE INDEX IF NOT EXISTS idx_customers_state ON staging.customers(state);

-- ── staging.products ────────────────────────────────────────
-- Product catalog. Links to categories.
CREATE TABLE IF NOT EXISTS staging.products (
    product_id     VARCHAR(12)    PRIMARY KEY,
    category_id    VARCHAR(10)    NOT NULL REFERENCES staging.categories(category_id),
    product_name   VARCHAR(300)   NOT NULL,
    description    TEXT,
    price          NUMERIC(10,2)  NOT NULL CHECK (price > 0),
    cost_price     NUMERIC(10,2)  CHECK (cost_price >= 0),
    weight_g       INTEGER        CHECK (weight_g > 0),
    length_cm      INTEGER,
    height_cm      INTEGER,
    width_cm       INTEGER,
    stock_quantity INTEGER        DEFAULT 0 CHECK (stock_quantity >= 0),
    is_active      BOOLEAN        DEFAULT TRUE,
    created_at     TIMESTAMP,
    _cleaned_at    TIMESTAMP      DEFAULT NOW()
);

COMMENT ON TABLE  staging.products            IS 'Product catalog with pricing and dimensions';
COMMENT ON COLUMN staging.products.price      IS 'Current selling price in USD';
COMMENT ON COLUMN staging.products.cost_price IS 'Cost of goods sold (COGS) for margin calculation';

-- Indexes for common filters
CREATE INDEX IF NOT EXISTS idx_products_category  ON staging.products(category_id);
CREATE INDEX IF NOT EXISTS idx_products_price_range ON staging.products(price);

-- ── staging.orders ──────────────────────────────────────────
-- Order header table. One row per customer order.
-- References customers for who placed the order.
CREATE TABLE IF NOT EXISTS staging.orders (
    order_id           VARCHAR(15)  PRIMARY KEY,
    customer_id        VARCHAR(15)  NOT NULL REFERENCES staging.customers(customer_id),
    order_date         TIMESTAMP    NOT NULL,
    order_status       VARCHAR(20)  NOT NULL,
    delivery_date      TIMESTAMP,   -- NULL if not yet delivered
    estimated_delivery TIMESTAMP,
    freight_value      NUMERIC(8,2) DEFAULT 0,
    _cleaned_at        TIMESTAMP    DEFAULT NOW(),

    -- Constraint: delivery_date must be AFTER order_date
    CONSTRAINT chk_delivery_after_order
        CHECK (delivery_date IS NULL OR delivery_date >= order_date)
);

COMMENT ON TABLE  staging.orders              IS 'Order headers — one row per customer purchase';
COMMENT ON COLUMN staging.orders.order_status IS 'delivered | shipped | processing | cancelled | pending';
COMMENT ON COLUMN staging.orders.freight_value IS 'Shipping cost charged to customer';

-- Critical indexes for time-series analytics
CREATE INDEX IF NOT EXISTS idx_orders_customer   ON staging.orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date       ON staging.orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_status     ON staging.orders(order_status);
-- Partial index: only index delivered orders (most queries filter by this)
CREATE INDEX IF NOT EXISTS idx_orders_delivered 
    ON staging.orders(order_date) WHERE order_status = 'delivered';

-- ── staging.order_items ─────────────────────────────────────
-- The actual products in each order. One row per line item.
-- This is the MOST IMPORTANT table for revenue analysis.
CREATE TABLE IF NOT EXISTS staging.order_items (
    order_item_id VARCHAR(15)   PRIMARY KEY,
    order_id      VARCHAR(15)   NOT NULL REFERENCES staging.orders(order_id),
    product_id    VARCHAR(12)   NOT NULL REFERENCES staging.products(product_id),
    seller_id     VARCHAR(10)   NOT NULL REFERENCES staging.sellers(seller_id),
    quantity      INTEGER       NOT NULL CHECK (quantity > 0),
    unit_price    NUMERIC(10,2) NOT NULL CHECK (unit_price > 0),
    total_price   NUMERIC(12,2) NOT NULL,  -- unit_price * quantity

    -- Computed check: total_price must equal unit_price * quantity (with small rounding tolerance)
    CONSTRAINT chk_total_price
        CHECK (ABS(total_price - (unit_price * quantity)) < 0.05)
);

COMMENT ON TABLE  staging.order_items          IS 'Line items within each order — one row per product';
COMMENT ON COLUMN staging.order_items.total_price IS 'Pre-computed unit_price * quantity for fast aggregation';

-- Critical indexes for JOIN performance
CREATE INDEX IF NOT EXISTS idx_order_items_order   ON staging.order_items(order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product ON staging.order_items(product_id);
CREATE INDEX IF NOT EXISTS idx_order_items_seller  ON staging.order_items(seller_id);

-- ── staging.payments ────────────────────────────────────────
-- Payment records. One order can have multiple payment methods.
CREATE TABLE IF NOT EXISTS staging.payments (
    payment_id       VARCHAR(15)   PRIMARY KEY,
    order_id         VARCHAR(15)   NOT NULL REFERENCES staging.orders(order_id),
    payment_sequence INTEGER       NOT NULL DEFAULT 1,
    payment_type     VARCHAR(20)   NOT NULL,
    installments     INTEGER       NOT NULL DEFAULT 1 CHECK (installments >= 1),
    payment_value    NUMERIC(10,2) NOT NULL CHECK (payment_value > 0),
    payment_status   VARCHAR(20),

    UNIQUE(order_id, payment_sequence)
);

COMMENT ON TABLE  staging.payments                 IS 'Payment transactions for each order';
COMMENT ON COLUMN staging.payments.payment_sequence IS 'Order of payment when split across multiple methods';
COMMENT ON COLUMN staging.payments.installments     IS 'Number of monthly installments (credit card only)';

CREATE INDEX IF NOT EXISTS idx_payments_order ON staging.payments(order_id);

-- ── staging.reviews ─────────────────────────────────────────
-- Customer product reviews linked to orders.
CREATE TABLE IF NOT EXISTS staging.reviews (
    review_id     VARCHAR(15)  PRIMARY KEY,
    order_id      VARCHAR(15)  NOT NULL REFERENCES staging.orders(order_id),
    review_score  SMALLINT     NOT NULL CHECK (review_score BETWEEN 1 AND 5),
    comment_title VARCHAR(200),
    comment_text  TEXT,
    review_date   DATE,
    _cleaned_at   TIMESTAMP    DEFAULT NOW()
);

COMMENT ON TABLE  staging.reviews              IS 'Customer review scores and comments';
COMMENT ON COLUMN staging.reviews.review_score IS '1 (worst) to 5 (best) star rating';

CREATE INDEX IF NOT EXISTS idx_reviews_order ON staging.reviews(order_id);
CREATE INDEX IF NOT EXISTS idx_reviews_score ON staging.reviews(review_score);


-- ============================================================
-- MARTS SCHEMA — Pre-created for dbt to populate
-- (dbt will CREATE OR REPLACE these views/tables)
-- We just ensure the schema exists here.
-- ============================================================

-- dbt will create all fact_* and dim_* tables in the marts schema.
-- See dbt/models/marts/ for the SQL definitions.


-- ============================================================
-- UTILITY: Row count verification view
-- ============================================================
CREATE OR REPLACE VIEW staging.v_table_stats AS
SELECT
    schemaname,
    tablename,
    n_live_tup AS row_count,
    pg_size_pretty(pg_total_relation_size(schemaname || '.' || tablename)) AS total_size,
    last_vacuum,
    last_analyze
FROM pg_stat_user_tables
WHERE schemaname IN ('raw', 'staging', 'marts')
ORDER BY schemaname, tablename;

COMMENT ON VIEW staging.v_table_stats IS 'Quick overview of all table sizes and row counts';


-- ============================================================
-- Confirmation message
-- ============================================================
DO $$
BEGIN
    RAISE NOTICE '✓ E-Commerce Analytics database schema created successfully!';
    RAISE NOTICE '  Schemas: raw, staging, marts';
    RAISE NOTICE '  Run: python python/ingest/generate_dataset.py';
    RAISE NOTICE '  Then: python python/ingest/load_raw.py';
END $$;
