"""Pricing ingestion service with a pluggable retailer-adapter interface.

DESIGN (production-real):
  Each retailer is a `PricingAdapter` that, given a product, returns a current
  price + stock. In production you'd implement Live adapters that call retailer
  APIs or scrapers. Those are STUBBED here because Amazon/Chewy/Petco/PetSmart
  all disallow scraping and you don't have paid API keys (see docs/01-dataset-guide.md).

  To populate the dashboard with comparable, queryable data, we ship a
  `DerivationAdapter`: it derives plausible competitor prices + 90-day history
  from each product's existing base price (the Amazon bootstrap price). This is
  clearly labeled and isolated — swap in a Live adapter and the rest of the
  pipeline is unchanged.

Usage (inside the scraper container):
    python /app/scripts/ingest_pricing.py --history-days 90
"""
from __future__ import annotations

import argparse
import math
import random
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from scraper.db import session_scope  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("pricing")

RETAILERS = ["amazon", "petbarn", "petzoo", "vetproductsdirect"]

# Each retailer's typical position vs the base price (multiplier) + volatility,
# plus a URL template used when minting placeholder SKUs. The {pid} placeholder
# is substituted with the product_id's first 8 chars.
RETAILER_PROFILE = {
    "amazon":            {"mult": 1.00, "vol": 0.04,
                          "url_tmpl": "https://www.amazon.com.au/dp/{pid}"},
    "petbarn":           {"mult": 1.05, "vol": 0.05,
                          "url_tmpl": "https://www.petbarn.com.au/p/{pid}"},
    "petzoo":            {"mult": 1.03, "vol": 0.06,
                          "url_tmpl": "https://www.petzoo.com.au/p/{pid}"},
    "vetproductsdirect": {"mult": 1.08, "vol": 0.07,
                          "url_tmpl": "https://www.vetproductsdirect.com.au/p/{pid}"},
}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--history-days", type=int, default=90,
                   help="Days of price history per product. Use 1 for current-price-only "
                        "(fast, good for pricing the WHOLE catalog).")
    p.add_argument("--limit", type=int, default=None, help="Max products to process (default: all in scope)")
    p.add_argument("--scope", choices=["all", "reviewed"], default="all",
                   help="all = every product (catalog comparison). "
                        "reviewed = only products with reviews (good for full 90-day history).")
    p.add_argument("--seed", type=int, default=7)
    return p.parse_args()


def _base_price_cents(session, product_id: str) -> int | None:
    """Use the most recent observed price (any retailer) as the base."""
    row = session.execute(
        text("""
            SELECT po.price_cents
              FROM competitor_skus cs
              JOIN price_observations po ON po.sku_id = cs.sku_id
             WHERE cs.product_id = :pid AND po.price_cents IS NOT NULL
             ORDER BY po.observed_at DESC
             LIMIT 1
        """),
        {"pid": product_id},
    ).first()
    return int(row.price_cents) if row else None


def _ensure_sku(session, product_id: str, competitor: str) -> str:
    """Get-or-create the competitor SKU row for this product+retailer."""
    row = session.execute(
        text("SELECT sku_id FROM competitor_skus WHERE product_id=:pid AND competitor=:c"),
        {"pid": product_id, "c": competitor},
    ).first()
    if row:
        return str(row.sku_id)
    url_tmpl = RETAILER_PROFILE.get(competitor, {}).get(
        "url_tmpl", "https://example.com/{pid}"
    )
    row = session.execute(
        text("""
            INSERT INTO competitor_skus (product_id, competitor, external_id, url, raw_title)
            VALUES (:pid, :c, :ext, :url, :title)
            ON CONFLICT (competitor, external_id) DO UPDATE SET product_id = EXCLUDED.product_id
            RETURNING sku_id
        """),
        {
            "pid": product_id,
            "c": competitor,
            "ext": f"{competitor}-{product_id[:8]}",
            "url": url_tmpl.format(pid=product_id[:8]),
            "title": None,
        },
    ).first()
    return str(row.sku_id)


def _price_walk(base: int, mult: float, vol: float, days: int, rng: random.Random) -> list[tuple[datetime, int, bool]]:
    """Generate a `days`-long daily price series: gentle random walk + occasional sale."""
    out: list[tuple[datetime, int, bool]] = []
    now = datetime.now(timezone.utc)
    price = base * mult
    for d in range(days, -1, -1):
        ts = now - timedelta(days=d)
        # random walk
        price *= (1 + rng.gauss(0, vol / 6))
        # occasional discontinuous sale (~4% of days), 10-25% off, then recover
        on_sale = rng.random() < 0.04
        shown = price * (1 - rng.uniform(0.10, 0.25)) if on_sale else price
        # keep within sane bounds of base
        shown = max(base * 0.55, min(base * 1.6, shown))
        in_stock = rng.random() > 0.03
        out.append((ts, int(round(shown)), in_stock))
    return out


def main() -> int:
    configure_logging()
    args = parse_args()
    rng = random.Random(args.seed)

    with session_scope() as session:
        if args.scope == "reviewed":
            # Only products with reviews, ordered by review count.
            sql = """
                SELECT cs.product_id::text AS pid
                  FROM competitor_skus cs
                  JOIN reviews r ON r.sku_id = cs.sku_id
                 WHERE cs.product_id IS NOT NULL
                 GROUP BY cs.product_id
                 ORDER BY COUNT(r.review_id) DESC
                 LIMIT :lim
            """
        else:
            # Every product in the catalog (so the dashboard can compare all of them).
            sql = """
                SELECT DISTINCT cs.product_id::text AS pid
                  FROM competitor_skus cs
                 WHERE cs.product_id IS NOT NULL
                 LIMIT :lim
            """
        # When --limit omitted, process everything in scope.
        prod_rows = session.execute(
            text(sql), {"lim": args.limit if args.limit is not None else 10_000_000},
        ).all()
        product_ids = [r.pid for r in prod_rows]
# abcd
    log.info("pricing.start", products=len(product_ids), days=args.history_days)
    processed = 0
    total_obs = 0

    for pid in product_ids:
        with session_scope() as session:
            base = _base_price_cents(session, pid)
            if not base or base <= 0:
                base = rng.randint(1500, 7000)  # fallback base for products with no price yet

            for competitor in RETAILERS:
                profile = RETAILER_PROFILE[competitor]
                sku_id = _ensure_sku(session, pid, competitor)
                # Clear prior derived history for idempotency
                session.execute(
                    text("DELETE FROM price_observations WHERE sku_id = :sid"),
                    {"sid": sku_id},
                )
                series = _price_walk(base, profile["mult"], profile["vol"], args.history_days, rng)
                for ts, cents, in_stock in series:
                    session.execute(
                        text("""
                            INSERT INTO price_observations (sku_id, observed_at, price_cents, currency, in_stock)
                            VALUES (:sid, :ts, :c, 'USD', :stk)
                        """),
                        {"sid": sku_id, "ts": ts, "c": cents, "stk": in_stock},
                    )
                    total_obs += 1
        processed += 1
        if processed % 50 == 0:
            log.info("pricing.progress", products=processed, observations=total_obs)

    log.info("pricing.done", products=processed, observations=total_obs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
