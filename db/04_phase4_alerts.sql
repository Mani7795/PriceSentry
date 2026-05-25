-- Phase 4: watchlists, deal stats, price alerts
-- Apply with:
--   docker compose cp db/04_phase4_alerts.sql postgres:/tmp/04.sql
--   docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/04.sql

-- ─────────────────────────────────────────────────────────────────────
-- WATCHLISTS  (a user wants to be alerted when a product hits a price)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS watchlists (
  watch_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
  product_id         UUID NOT NULL REFERENCES products(product_id) ON DELETE CASCADE,
  target_price_cents INTEGER,                  -- alert when cheapest <= this; NULL = any drop / great deal
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, product_id)
);
CREATE INDEX IF NOT EXISTS idx_watchlists_user ON watchlists (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_product ON watchlists (product_id);

-- ─────────────────────────────────────────────────────────────────────
-- DEAL STATS  (one row per product; recomputed by the nightly job)
--   pct_rank: fraction of trailing-90d observations at or below the current
--   cheapest price. Lower = current price is cheaper than most of history.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS deal_stats (
  product_id      UUID PRIMARY KEY REFERENCES products(product_id) ON DELETE CASCADE,
  current_cents   INTEGER,           -- cheapest current price across retailers
  min_90d_cents   INTEGER,
  avg_90d_cents   INTEGER,
  max_90d_cents   INTEGER,
  pct_rank        REAL,              -- 0..1
  deal_label      TEXT,              -- great | good | typical | high
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ─────────────────────────────────────────────────────────────────────
-- ALERT EVENTS  (append-only log; also used for dedup so we don't spam)
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_events (
  event_id     BIGSERIAL PRIMARY KEY,
  user_id      UUID REFERENCES users(user_id) ON DELETE CASCADE,
  product_id   UUID REFERENCES products(product_id) ON DELETE CASCADE,
  kind         TEXT NOT NULL,        -- 'price_target' | 'great_deal'
  price_cents  INTEGER,
  message      TEXT,
  delivered    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_alert_events_user ON alert_events (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_alert_events_dedup ON alert_events (user_id, product_id, created_at DESC);

-- ─────────────────────────────────────────────────────────────────────
-- Rebuild the dashboard view to expose deal columns (appended at the end).
-- (Full definition repeated so CREATE OR REPLACE is valid.)
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
  COALESCE(rs.review_count,
           NULLIF(p.attributes->>'rating_number', '')::int,
           0)                          AS review_count,
  COALESCE(rs.avg_rating,
           NULLIF(p.attributes->>'average_rating', '')::real) AS avg_rating,
  rs.avg_sentiment,
  rs.pct_positive,
  ps.competitor_count,
  ps.min_price_cents,
  ps.max_price_cents,
  ps.cheapest_competitor,
  -- deal columns (NULL until the nightly job runs)
  ds.deal_label                        AS deal_label,
  ds.pct_rank                          AS deal_pct_rank,
  ds.current_cents                     AS deal_current_cents
FROM products p
LEFT JOIN review_stats rs ON rs.product_id = p.product_id
LEFT JOIN price_stats  ps ON ps.product_id = p.product_id
LEFT JOIN deal_stats   ds ON ds.product_id = p.product_id;

DO $$
BEGIN
  RAISE NOTICE 'Phase 4 alerts/deals schema initialized successfully.';
END $$;
