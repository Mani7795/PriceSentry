-- PriceSentry — Postgres schema (Phase 1)
-- This file is mounted into the official postgres image at:
--   /docker-entrypoint-initdb.d/00_init.sql
-- It runs automatically on first container start (only).

-- ─────────────────────────────────────────────────────────────────────
-- Extensions
-- ─────────────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";    -- gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "vector";      -- pgvector (provided by pgvector/pgvector image)

-- ─────────────────────────────────────────────────────────────────────
-- Schema layout
-- ─────────────────────────────────────────────────────────────────────
-- bronze:  raw, untouched payloads
-- silver:  parsed, validated, deduped (the "clean OLTP" tables)
-- gold:    business marts (created later by dbt; we just reserve the schema)
CREATE SCHEMA IF NOT EXISTS bronze;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;

-- For convenience in Phase 1 we put the working OLTP tables in `public`
-- so beginners don't have to qualify every name. We'll migrate to silver.*
-- in Phase 2 with `ALTER TABLE ... SET SCHEMA silver;`

-- ─────────────────────────────────────────────────────────────────────
-- BRONZE: raw_events
-- Every payload we ever received, byte-for-byte.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bronze.raw_events (
  raw_event_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  source          TEXT NOT NULL,                -- 'demo', 'chewy', 'amazon-bootstrap'
  fetched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  url             TEXT,
  http_status     INT,
  payload         JSONB NOT NULL,
  payload_sha256  TEXT NOT NULL,
  CONSTRAINT raw_events_dedup UNIQUE (source, payload_sha256)
);
CREATE INDEX IF NOT EXISTS idx_raw_events_source_fetched
  ON bronze.raw_events (source, fetched_at DESC);
CREATE INDEX IF NOT EXISTS idx_raw_events_payload_gin
  ON bronze.raw_events USING GIN (payload);

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: products  (canonical product entity)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS products (
  product_id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  brand         TEXT,
  title         TEXT NOT NULL,
  category      TEXT,
  pet_type      TEXT,                            -- 'dog', 'cat', 'fish', 'bird', ...
  upc           TEXT,
  attributes    JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_brand        ON products (brand);
CREATE INDEX IF NOT EXISTS idx_products_pet_type     ON products (pet_type);
CREATE INDEX IF NOT EXISTS idx_products_attrs_gin    ON products USING GIN (attributes);

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: competitor_skus  (each retailer's listing)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS competitor_skus (
  sku_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  product_id        UUID REFERENCES products(product_id) ON DELETE SET NULL,
  competitor        TEXT NOT NULL,               -- 'amazon', 'chewy', 'petco', 'demo'
  external_id       TEXT NOT NULL,               -- ASIN, Chewy SKU, etc.
  url               TEXT,
  raw_title         TEXT,
  raw_brand         TEXT,
  match_confidence  REAL,
  matched_at        TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT competitor_skus_natural_key UNIQUE (competitor, external_id)
);
CREATE INDEX IF NOT EXISTS idx_competitor_skus_product ON competitor_skus (product_id);
CREATE INDEX IF NOT EXISTS idx_competitor_skus_unmatched
  ON competitor_skus (competitor) WHERE product_id IS NULL;

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: price_observations  (append-only time series)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS price_observations (
  observation_id    BIGSERIAL PRIMARY KEY,
  sku_id            UUID NOT NULL REFERENCES competitor_skus(sku_id) ON DELETE CASCADE,
  observed_at       TIMESTAMPTZ NOT NULL,
  price_cents       INTEGER,
  currency          TEXT NOT NULL DEFAULT 'USD',
  in_stock          BOOLEAN,
  raw_event_id      UUID REFERENCES bronze.raw_events(raw_event_id),
  CONSTRAINT price_obs_sane CHECK (price_cents IS NULL OR price_cents >= 0)
);
CREATE INDEX IF NOT EXISTS idx_price_obs_sku_time
  ON price_observations (sku_id, observed_at DESC);
CREATE INDEX IF NOT EXISTS idx_price_obs_observed_at
  ON price_observations (observed_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: reviews
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS reviews (
  review_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  sku_id             UUID REFERENCES competitor_skus(sku_id) ON DELETE CASCADE,
  source             TEXT NOT NULL,
  external_id        TEXT,
  rating             REAL,
  review_text        TEXT,
  reviewed_at        TIMESTAMPTZ,
  verified_purchase  BOOLEAN,
  raw_payload        JSONB,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  CONSTRAINT reviews_natural_key UNIQUE (source, external_id)
);
CREATE INDEX IF NOT EXISTS idx_reviews_sku            ON reviews (sku_id);
CREATE INDEX IF NOT EXISTS idx_reviews_source_time    ON reviews (source, reviewed_at DESC);
CREATE INDEX IF NOT EXISTS idx_reviews_text_trgm      ON reviews USING GIN (review_text gin_trgm_ops);

-- (gin_trgm_ops needs pg_trgm; we'll create it lazily so it doesn't fail on minimal images)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_trgm') THEN
    CREATE EXTENSION IF NOT EXISTS pg_trgm;
  END IF;
EXCEPTION WHEN OTHERS THEN
  -- ok, optional
  NULL;
END $$;

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: review_embeddings (vector(384) for BGE-small)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS review_embeddings (
  review_id      UUID PRIMARY KEY REFERENCES reviews(review_id) ON DELETE CASCADE,
  embedding      vector(384) NOT NULL,
  model_version  TEXT NOT NULL DEFAULT 'BAAI/bge-small-en-v1.5',
  created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
-- IVFFLAT ANN index for cosine similarity search.
-- Note: build the index AFTER you have at least a few thousand rows for it to be useful.
-- We pre-create it; pgvector handles empty index fine.
CREATE INDEX IF NOT EXISTS idx_review_emb_ivfflat
  ON review_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- ─────────────────────────────────────────────────────────────────────
-- SILVER: scrape_jobs  (operational metadata, helpful for ops)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS scrape_jobs (
  job_id        UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  target        TEXT NOT NULL,
  started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at   TIMESTAMPTZ,
  status        TEXT NOT NULL DEFAULT 'running',  -- running, ok, error
  pages_fetched INT NOT NULL DEFAULT 0,
  events_written INT NOT NULL DEFAULT 0,
  error         TEXT
);

-- ─────────────────────────────────────────────────────────────────────
-- Convenience view: "latest price per SKU"
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_latest_price AS
SELECT DISTINCT ON (sku_id)
  sku_id,
  observed_at,
  price_cents,
  currency,
  in_stock
FROM price_observations
ORDER BY sku_id, observed_at DESC;

-- ─────────────────────────────────────────────────────────────────────
-- Sanity check
-- ─────────────────────────────────────────────────────────────────────
DO $$
BEGIN
  RAISE NOTICE 'PriceSentry schema initialized successfully.';
END $$;