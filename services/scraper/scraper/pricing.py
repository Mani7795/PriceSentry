"""Price refresh + deal-stat computation (runs in the nightly job).

These are plain functions (no Celery import) so they can be:
  - called by Celery tasks (scraper/tasks.py)
  - run directly for testing (scripts/run_jobs.py)
"""
from __future__ import annotations

from sqlalchemy import text

from scraper.db import session_scope
from scraper.logging_setup import get_logger

log = get_logger("pricing")


def refresh_current_prices(limit: int | None = None) -> int:
    """Append ONE new price observation per competitor SKU, derived from its
    last price with a small random walk (±~3%). This is how a real price
    tracker grows its time-series: add today's point, don't regenerate history.

    Single set-based INSERT...SELECT — fast even for tens of thousands of SKUs.
    """
    limit_clause = f"LIMIT {int(limit)}" if limit else ""
    sql = f"""
        INSERT INTO price_observations (sku_id, observed_at, price_cents, currency, in_stock)
        SELECT latest.sku_id,
               NOW(),
               GREATEST(50, ROUND(latest.price_cents * (1 + (random() - 0.5) * 0.06)))::int,
               'USD',
               (random() > 0.03)
          FROM (
              SELECT DISTINCT ON (sku_id) sku_id, price_cents
                FROM price_observations
               WHERE price_cents IS NOT NULL
               ORDER BY sku_id, observed_at DESC
          ) latest
          {limit_clause}
    """
    with session_scope() as s:
        result = s.execute(text(sql))
        count = result.rowcount or 0
    log.info("pricing.refresh_current_prices.done", rows=count)
    return count


def recompute_deal_stats() -> int:
    """Recompute the deal indicator for every product with price history.

    pct_rank = fraction of trailing-90d observations at or below the current
    cheapest price (lower = better deal). Label derived from pct_rank.
    """
    sql = """
        WITH hist AS (
            SELECT cs.product_id AS pid, po.price_cents AS cents
              FROM competitor_skus cs
              JOIN price_observations po ON po.sku_id = cs.sku_id
             WHERE cs.product_id IS NOT NULL
               AND po.price_cents IS NOT NULL
               AND po.observed_at >= NOW() - INTERVAL '90 days'
        ),
        latest_per_retailer AS (
            SELECT DISTINCT ON (cs.product_id, cs.competitor)
                   cs.product_id AS pid, po.price_cents AS cents
              FROM competitor_skus cs
              JOIN price_observations po ON po.sku_id = cs.sku_id
             WHERE cs.product_id IS NOT NULL AND po.price_cents IS NOT NULL
             ORDER BY cs.product_id, cs.competitor, po.observed_at DESC
        ),
        cur AS (
            SELECT pid, MIN(cents) AS current_cents
              FROM latest_per_retailer
             GROUP BY pid
        ),
        agg AS (
            SELECT pid, MIN(cents) AS min_c, AVG(cents)::int AS avg_c, MAX(cents) AS max_c
              FROM hist GROUP BY pid
        ),
        rnk AS (
            SELECT h.pid,
                   AVG(CASE WHEN h.cents <= c.current_cents THEN 1.0 ELSE 0.0 END) AS pct_rank
              FROM hist h JOIN cur c ON c.pid = h.pid
             GROUP BY h.pid
        )
        INSERT INTO deal_stats
            (product_id, current_cents, min_90d_cents, avg_90d_cents, max_90d_cents,
             pct_rank, deal_label, updated_at)
        SELECT cur.pid, cur.current_cents, agg.min_c, agg.avg_c, agg.max_c,
               rnk.pct_rank,
               CASE WHEN rnk.pct_rank <= 0.10 THEN 'great'
                    WHEN rnk.pct_rank <= 0.30 THEN 'good'
                    WHEN rnk.pct_rank >= 0.85 THEN 'high'
                    ELSE 'typical' END,
               NOW()
          FROM cur
          JOIN agg ON agg.pid = cur.pid
          JOIN rnk ON rnk.pid = cur.pid
        ON CONFLICT (product_id) DO UPDATE
            SET current_cents = EXCLUDED.current_cents,
                min_90d_cents = EXCLUDED.min_90d_cents,
                avg_90d_cents = EXCLUDED.avg_90d_cents,
                max_90d_cents = EXCLUDED.max_90d_cents,
                pct_rank      = EXCLUDED.pct_rank,
                deal_label    = EXCLUDED.deal_label,
                updated_at    = EXCLUDED.updated_at
    """
    with session_scope() as s:
        result = s.execute(text(sql))
        count = result.rowcount or 0
    log.info("pricing.recompute_deal_stats.done", products=count)
    return count
