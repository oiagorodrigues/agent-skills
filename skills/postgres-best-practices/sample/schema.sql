-- =============================================================================
-- E-Commerce Reference Schema
-- PostgreSQL 14+ / Aurora PostgreSQL compatible
-- Used by all examples in postgresql-best-practices/references/
-- =============================================================================

-- Enable extensions used in the schema
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- trigram indexes for LIKE/ILIKE
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- gen_random_uuid()

-- =============================================================================
-- Type: order_status
-- Enum for order lifecycle states (PostgreSQL CREATE TYPE for enums).
-- =============================================================================
CREATE TYPE order_status AS ENUM (
  'pending',
  'paid',
  'processing',
  'shipped',
  'delivered',
  'cancelled',
  'refunded'
);

-- =============================================================================
-- Table: users
-- Stores registered customers and admin accounts.
-- =============================================================================
CREATE TABLE users (
  id            BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  email         TEXT            NOT NULL,
  username      TEXT            NOT NULL,
  password_hash TEXT            NOT NULL,
  full_name     TEXT            NOT NULL DEFAULT '',
  status        TEXT            NOT NULL DEFAULT 'active'
                                CHECK (status IN ('active', 'suspended', 'deleted')),
  role          TEXT            NOT NULL DEFAULT 'customer'
                                CHECK (role IN ('customer', 'admin', 'vendor')),
  created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_users_email    UNIQUE (email),
  CONSTRAINT uq_users_username UNIQUE (username)
);

CREATE INDEX idx_users_status     ON users (status);
CREATE INDEX idx_users_created_at ON users (created_at);

COMMENT ON TABLE users IS 'Registered users including customers, admins, and vendors';


-- =============================================================================
-- Table: categories
-- Product taxonomy. Supports one level of parent/child hierarchy.
-- =============================================================================
CREATE TABLE categories (
  id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  parent_id   BIGINT                  DEFAULT NULL REFERENCES categories (id)
                                      ON DELETE SET NULL,
  name        TEXT        NOT NULL,
  slug        TEXT        NOT NULL,
  description TEXT                    DEFAULT NULL,
  is_active   BOOLEAN     NOT NULL DEFAULT TRUE,
  sort_order  INT         NOT NULL DEFAULT 0,
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_categories_slug UNIQUE (slug)
);

CREATE INDEX idx_categories_parent_id ON categories (parent_id);
CREATE INDEX idx_categories_is_active ON categories (is_active);

COMMENT ON TABLE categories IS 'Product categories with optional parent for one-level hierarchy';


-- =============================================================================
-- Table: products
-- Product catalog.
--   price uses NUMERIC(10,2) to avoid floating-point errors.
--   attributes is JSONB for flexible semi-structured product metadata.
--   tags is a TEXT array for multi-value categorical data.
-- =============================================================================
CREATE TABLE products (
  id            BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  category_id   BIGINT          NOT NULL REFERENCES categories (id)
                                ON DELETE RESTRICT,
  name          TEXT            NOT NULL,
  slug          TEXT            NOT NULL,
  description   TEXT            DEFAULT NULL,
  sku           TEXT            NOT NULL,
  price         NUMERIC(10,2)   NOT NULL CHECK (price >= 0),
  stock_qty     INT             NOT NULL DEFAULT 0 CHECK (stock_qty >= 0),
  weight_kg     NUMERIC(8,3)    DEFAULT NULL,
  status        TEXT            NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('active', 'draft', 'discontinued')),
  attributes    JSONB           DEFAULT '{}',           -- flexible product attributes
  tags          TEXT[]          DEFAULT '{}',            -- e.g. ARRAY['wireless','bluetooth']
  created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_products_sku  UNIQUE (sku),
  CONSTRAINT uq_products_slug UNIQUE (slug)
);

CREATE INDEX idx_products_category_id          ON products (category_id);
CREATE INDEX idx_products_status               ON products (status);
CREATE INDEX idx_products_status_created_at    ON products (status, created_at);
-- Composite covering index for category listing pages
CREATE INDEX idx_products_cat_status_price     ON products (category_id, status, price);
-- GIN index for JSONB containment queries (@>)
CREATE INDEX idx_products_attributes_gin       ON products USING gin (attributes);
-- GIN trigram index for LIKE/ILIKE search on product names
CREATE INDEX idx_products_name_trgm            ON products USING gin (name gin_trgm_ops);
-- GIN index on tags array for ANY/ALL array operations
CREATE INDEX idx_products_tags_gin             ON products USING gin (tags);

COMMENT ON TABLE  products             IS 'Product catalog; price stored as NUMERIC(10,2) to avoid float precision loss';
COMMENT ON COLUMN products.attributes  IS 'JSONB bag for variable product specs (color, size, material, etc.)';
COMMENT ON COLUMN products.tags        IS 'TEXT array of searchable tags; indexed with GIN for array operations';


-- =============================================================================
-- Table: orders
-- One row per customer order. total_amount is the authoritative order value.
-- =============================================================================
CREATE TABLE orders (
  id             BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  user_id        BIGINT          NOT NULL REFERENCES users (id)
                                 ON DELETE RESTRICT,
  status         order_status    NOT NULL DEFAULT 'pending',
  total_amount   NUMERIC(12,2)   NOT NULL DEFAULT 0.00 CHECK (total_amount >= 0),
  shipping_addr  TEXT            NOT NULL DEFAULT '',
  notes          TEXT            DEFAULT NULL,
  paid_at        TIMESTAMPTZ     DEFAULT NULL,
  shipped_at     TIMESTAMPTZ     DEFAULT NULL,
  delivered_at   TIMESTAMPTZ     DEFAULT NULL,
  created_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
  updated_at     TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user_id              ON orders (user_id);
CREATE INDEX idx_orders_status               ON orders (status);
CREATE INDEX idx_orders_created_at           ON orders (created_at);
-- Composite index for the most common filter: user + status, keyset pagination by id
CREATE INDEX idx_orders_user_status_id       ON orders (user_id, status, id);
-- Composite index for date-range reports on status
CREATE INDEX idx_orders_status_created_total ON orders (status, created_at, total_amount);

COMMENT ON TABLE orders IS 'Customer orders; status uses a PostgreSQL enum type; timestamps are TIMESTAMPTZ';


-- =============================================================================
-- Table: order_items
-- Line items for each order. unit_price is a snapshot at time of purchase.
-- =============================================================================
CREATE TABLE order_items (
  id          BIGINT          GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  order_id    BIGINT          NOT NULL REFERENCES orders (id)
                              ON DELETE CASCADE,
  product_id  BIGINT          NOT NULL REFERENCES products (id)
                              ON DELETE RESTRICT,
  quantity    INT             NOT NULL DEFAULT 1 CHECK (quantity > 0),
  unit_price  NUMERIC(10,2)   NOT NULL CHECK (unit_price >= 0),  -- snapshot price at purchase
  created_at  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_order_items_order_id   ON order_items (order_id);
CREATE INDEX idx_order_items_product_id ON order_items (product_id);
-- Covering index for per-order line-item listing (index-only scan candidate)
CREATE INDEX idx_order_items_order_product_price
  ON order_items (order_id, product_id, unit_price, quantity);

COMMENT ON TABLE  order_items            IS 'Order line items; unit_price is a snapshot and may differ from products.price';
COMMENT ON COLUMN order_items.unit_price IS 'Price at time of purchase, not current products.price';


-- =============================================================================
-- Table: reviews
-- Customer product reviews. One review per user per product enforced by
-- a unique constraint so ON CONFLICT DO UPDATE can be used for re-submits.
-- =============================================================================
CREATE TABLE reviews (
  id          BIGINT      GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  product_id  BIGINT      NOT NULL REFERENCES products (id)
                          ON DELETE CASCADE,
  user_id     BIGINT      NOT NULL REFERENCES users (id)
                          ON DELETE CASCADE,
  rating      SMALLINT    NOT NULL CHECK (rating BETWEEN 1 AND 5),
  title       TEXT        DEFAULT NULL,
  body        TEXT        DEFAULT NULL,
  is_verified BOOLEAN     NOT NULL DEFAULT FALSE,  -- verified purchase flag
  status      TEXT        NOT NULL DEFAULT 'pending'
                          CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),

  CONSTRAINT uq_reviews_product_user UNIQUE (product_id, user_id)
);

CREATE INDEX idx_reviews_user_id               ON reviews (user_id);
CREATE INDEX idx_reviews_status                ON reviews (status);
CREATE INDEX idx_reviews_product_status_rating ON reviews (product_id, status, rating);
-- Full-text search index on review title and body
CREATE INDEX idx_reviews_fts ON reviews
  USING gin (to_tsvector('english', COALESCE(title, '') || ' ' || COALESCE(body, '')));

COMMENT ON TABLE  reviews             IS 'Product reviews; unique per (product, user) to allow ON CONFLICT upsert on re-submit';
COMMENT ON COLUMN reviews.is_verified IS 'TRUE if the reviewer has a confirmed purchase of this product';
