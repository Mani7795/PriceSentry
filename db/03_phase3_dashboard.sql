-- Phase 3: dashboard data layer
-- Adds: review sentiment, aspect-level sentiment, and read-optimized views
-- for the public product-intelligence dashboard.
--
-- Apply to an existing DB with:
--   docker compose cp db/03_phase3_dashboard.sql postgres:/tmp/03.sql
--   docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/03.sql

-- ─────────────────────────────────────────────────────────────────────
-- Sentiment columns on reviews (populated by scripts/compute_sentiment.py)
-- ─────────────────────────────────────────────────────────────────────
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_score REAL;     -- -1..1
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_label TEXT;     -- positive|neutral|negative
ALTER TABLE reviews ADD COLUMN IF NOT EXISTS sentiment_model TEXT;

CREATE INDEX IF NOT EXISTS idx_reviews_sentiment ON reviews (sentiment_label);

-- ─────────────────────────────────────────────────────────────────────
-- Aspect-level sentiment (one row per detected aspect mention)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS review_aspects (
  aspect_id        BIGSERIAL PRIMARY KEY,
  review_id        UUID NOT NULL REFERENCES reviews(review_id) ON DELETE CASCADE,
  product_id       UUID REFERENCES products(product_id) ON DELETE CASCADE,
  aspect           TEXT NOT NULL,         -- 'packaging','price','quality','smell','ingredients','shipping','value'
  sentiment_score  REAL NOT NULL,         -- -1..1 for this aspect mention
  sentiment_label  TEXT NOT NULL,         -- positive|neutral|negative
  snippet          TEXT,                  -- the sentence that mentioned the aspect
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_review_aspects_product ON review_aspects (product_id, aspect);
CREATE INDEX IF NOT EXISTS idx_review_aspects_review ON review_aspects (review_id);

-- ─────────────────────────────────────────────────────────────────────
-- AI query log (records each AI insight / chat generation for analytics)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_query_log (
  query_id         BIGSERIAL PRIMARY KEY,
  user_id          UUID REFERENCES users(user_id) ON DELETE SET NULL,
  product_id       UUID REFERENCES products(product_id) ON DELETE SET NULL,
  kind             TEXT NOT NULL,         -- 'chat' | 'product_insight'
  question         TEXT,
  model            TEXT,
  latency_ms       INTEGER,
  retrieved_count  INTEGER,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_query_log_created ON ai_query_log (created_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- VIEW: per-product, per-competitor latest price
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_product_competitor_price AS
SELECT DISTINCT ON (cs.product_id, cs.competitor)
  cs.product_id,
  cs.competitor,
  cs.sku_id,
  cs.url,
  po.price_cents,
  po.currency,
  po.in_stock,
  po.observed_at
FROM competitor_skus cs
JOIN price_observations po ON po.sku_id = cs.sku_id
WHERE cs.product_id IS NOT NULL
ORDER BY cs.product_id, cs.competitor, po.observed_at DESC;

-- ─────────────────────────────────────────────────────────────────────
-- VIEW: product dashboard summary (one row per product)
--   - review_count, avg_rating
--   - avg_sentiment, pct_positive
--   - cheapest competitor + price
--   - number of competitors tracked
-- ─────────────────────────────────────────────────────────────────────
CREATE OR REPLACE VIEW v_product_dashboard AS
WITH review_stats AS (
  SELECT
    cs.product_id,
    COUNT(r.review_id)                              AS review_count,
    AVG(r.rating)                                   AS avg_rating,
    AVG(r.sentiment_score)                          AS avg_sentiment,
    AVG(CASE WHEN r.sentiment_label = 'positive' THEN 1.0
             WHEN r.sentiment_label IS NOT NULL THEN 0.0 END) AS pct_positive
  FROM competitor_skus cs
  JOIN reviews r ON r.sku_id = cs.sku_id
  WHERE cs.product_id IS NOT NULL
  GROUP BY cs.product_id
),
price_stats AS (
  SELECT
    product_id,
    COUNT(DISTINCT competitor)                      AS competitor_count,
    MIN(price_cents)                                AS min_price_cents,
    MAX(price_cents)                                AS max_price_cents,
    (ARRAY_AGG(competitor ORDER BY price_cents ASC))[1] AS cheapest_competitor
  FROM v_product_competitor_price
  WHERE price_cents IS NOT NULL
  GROUP BY product_id
)
SELECT
  p.product_id,
  p.brand,
  p.title,
  p.category,
  p.pet_type,
  p.attributes,
  COALESCE(rs.review_count, 0)        AS review_count,
  rs.avg_rating,
  rs.avg_sentiment,
  rs.pct_positive,
  ps.competitor_count,
  ps.min_price_cents,
  ps.max_price_cents,
  ps.cheapest_competitor
FROM products p
LEFT JOIN review_stats rs ON rs.product_id = p.product_id
LEFT JOIN price_stats  ps ON ps.product_id = p.product_id;

DO $$
BEGIN
  RAISE NOTICE 'Phase 3 dashboard schema initialized successfully.';
END $$;
