-- Phase 5: product images
-- Apply with:
--   docker compose cp db/05_phase5_images.sql postgres:/tmp/05.sql
--   docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/05.sql

ALTER TABLE products ADD COLUMN IF NOT EXISTS image_url TEXT;

-- Rebuild the dashboard view to expose image_url (appended at the end).
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
  ds.deal_label                        AS deal_label,
  ds.pct_rank                          AS deal_pct_rank,
  ds.current_cents                     AS deal_current_cents,
  p.image_url                          AS image_url
FROM products p
LEFT JOIN review_stats rs ON rs.product_id = p.product_id
LEFT JOIN price_stats  ps ON ps.product_id = p.product_id
LEFT JOIN deal_stats   ds ON ds.product_id = p.product_id;

DO $$
BEGIN
  RAISE NOTICE 'Phase 5 images schema initialized successfully.';
END $$;
