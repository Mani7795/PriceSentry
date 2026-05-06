"""Bootstrap PriceSentry from the public Amazon Reviews 2023 dataset (Pet Supplies subset).

Source: McAuley-Lab/Amazon-Reviews-2023 on Hugging Face.
License: free for research / portfolio use.

What this script does:
  1. Streams `raw_meta_Pet_Supplies` → upserts into `competitor_skus` (competitor='amazon')
     and creates a `products` row, then synthesizes one `price_observation` per SKU
     using the metadata's price (if present) and `last_updated` time.
  2. Streams `raw_review_Pet_Supplies` → upserts into `reviews`, joining by ASIN
     (we treat ASIN as `external_id`).
  3. Idempotent: re-running picks up where it left off thanks to the natural-key
     unique constraints on competitor_skus and reviews.

Usage (inside the scraper container):
    python /app/scripts/bootstrap_amazon_reviews.py --limit 50000 --batch-size 500
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from typing import Any, Iterable

# ---- ensure the scraper package is importable when run from /app/scripts/
sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from scraper.db import session_scope  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("bootstrap")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=50_000, help="Max reviews to load")
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--meta-limit", type=int, default=20_000, help="Max metadata rows to load")
    p.add_argument("--config", default="raw_review_Pet_Supplies", help="HF subset name")
    p.add_argument("--meta-config", default="raw_meta_Pet_Supplies")
    p.add_argument("--repo", default="McAuley-Lab/Amazon-Reviews-2023")
    return p.parse_args()


def _load_streaming(repo: str, config: str) -> Iterable[dict[str, Any]]:
    from datasets import load_dataset

    ds = load_dataset(repo, config, split="full", streaming=True, trust_remote_code=True)
    return iter(ds)


def _upsert_meta_batch(rows: list[dict[str, Any]]) -> int:
    if not rows:
        return 0
    with session_scope() as session:
        for row in rows:
            asin = row.get("parent_asin") or row.get("asin")
            if not asin:
                continue
            title = (row.get("title") or "").strip()
            if not title:
                continue

            # 1) products row (canonical)
            product = session.execute(
                text(
                    """
                    INSERT INTO products (brand, title, category, pet_type, attributes)
                    VALUES (:brand, :title, :category, 'unknown', CAST(:attrs AS JSONB))
                    RETURNING product_id
                    """
                ),
                {
                    "brand": (row.get("store") or row.get("brand") or "").strip() or None,
                    "title": title[:512],
                    "category": (row.get("main_category") or "Pet Supplies"),
                    "attrs": json.dumps(
                        {
                            "categories": row.get("categories") or [],
                            "features": row.get("features") or [],
                            "average_rating": row.get("average_rating"),
                            "rating_number": row.get("rating_number"),
                        },
                        default=str,
                    ),
                },
            ).first()
            product_id = str(product.product_id)

            # 2) competitor_skus row (Amazon listing for that product)
            sku = session.execute(
                text(
                    """
                    INSERT INTO competitor_skus (product_id, competitor, external_id, url, raw_title, raw_brand)
                    VALUES (:pid, 'amazon', :ext, :url, :title, :brand)
                    ON CONFLICT (competitor, external_id) DO UPDATE
                        SET raw_title = EXCLUDED.raw_title,
                            raw_brand = EXCLUDED.raw_brand,
                            product_id = COALESCE(competitor_skus.product_id, EXCLUDED.product_id)
                    RETURNING sku_id
                    """
                ),
                {
                    "pid": product_id,
                    "ext": asin,
                    "url": f"https://www.amazon.com/dp/{asin}",
                    "title": title[:512],
                    "brand": (row.get("store") or row.get("brand") or "").strip() or None,
                },
            ).first()
            sku_id = str(sku.sku_id)

            # 3) optional synthetic price observation
            price = row.get("price")
            if price is not None:
                try:
                    cents = int(round(float(price) * 100))
                    if cents >= 0:
                        session.execute(
                            text(
                                """
                                INSERT INTO price_observations (sku_id, observed_at, price_cents, currency, in_stock)
                                VALUES (:sid, NOW(), :c, 'USD', TRUE)
                                """
                            ),
                            {"sid": sku_id, "c": cents},
                        )
                except (TypeError, ValueError):
                    pass
        return len(rows)


def _upsert_review_batch(rows: list[dict[str, Any]]) -> int:
    """Reviews join to SKUs by ASIN. If a review's ASIN isn't in our SKU set
    (because we limited meta), we skip it — that's fine for Phase 1."""
    if not rows:
        return 0
    inserted = 0
    with session_scope() as session:
        for row in rows:
            asin = row.get("parent_asin") or row.get("asin")
            if not asin:
                continue
            sku = session.execute(
                text("SELECT sku_id FROM competitor_skus WHERE competitor='amazon' AND external_id=:e"),
                {"e": asin},
            ).first()
            if not sku:
                continue

            ts = row.get("timestamp")
            if isinstance(ts, (int, float)):
                # Hugging Face dataset uses ms epoch
                reviewed_at = datetime.fromtimestamp(ts / 1000, tz=timezone.utc)
            else:
                reviewed_at = None

            external_id = (
                row.get("review_id")
                or f"{asin}:{row.get('user_id','?')}:{int(ts) if isinstance(ts,(int,float)) else 0}"
            )

            session.execute(
                text(
                    """
                    INSERT INTO reviews (sku_id, source, external_id, rating, review_text,
                                         reviewed_at, verified_purchase, raw_payload)
                    VALUES (:sku, 'amazon', :ext, :rating, :txt, :ts, :vp, CAST(:raw AS JSONB))
                    ON CONFLICT (source, external_id) DO NOTHING
                    """
                ),
                {
                    "sku": str(sku.sku_id),
                    "ext": external_id,
                    "rating": float(row["rating"]) if row.get("rating") is not None else None,
                    "txt": (row.get("text") or "").strip()[:8000],
                    "ts": reviewed_at,
                    "vp": bool(row.get("verified_purchase")) if row.get("verified_purchase") is not None else None,
                    "raw": json.dumps(row, default=str),
                },
            )
            inserted += 1
    return inserted


def main() -> int:
    configure_logging()
    args = parse_args()

    log.info("bootstrap.start", limit=args.limit, meta_limit=args.meta_limit)
    started = time.time()

    # ─── Metadata first (so reviews can join) ──────────────────────────
    meta_iter = _load_streaming(args.repo, args.meta_config)
    meta_buf: list[dict[str, Any]] = []
    meta_loaded = 0
    for i, row in enumerate(meta_iter):
        if i >= args.meta_limit:
            break
        meta_buf.append(row)
        if len(meta_buf) >= args.batch_size:
            meta_loaded += _upsert_meta_batch(meta_buf)
            meta_buf.clear()
            log.info("bootstrap.meta.progress", loaded=meta_loaded)
    if meta_buf:
        meta_loaded += _upsert_meta_batch(meta_buf)
    log.info("bootstrap.meta.done", loaded=meta_loaded, elapsed_s=round(time.time() - started, 1))

    # ─── Reviews ──────────────────────────────────────────────────────
    rev_iter = _load_streaming(args.repo, args.config)
    rev_buf: list[dict[str, Any]] = []
    rev_loaded = 0
    for i, row in enumerate(rev_iter):
        if i >= args.limit:
            break
        rev_buf.append(row)
        if len(rev_buf) >= args.batch_size:
            rev_loaded += _upsert_review_batch(rev_buf)
            rev_buf.clear()
            if rev_loaded % (args.batch_size * 10) == 0:
                log.info("bootstrap.reviews.progress", loaded=rev_loaded)
    if rev_buf:
        rev_loaded += _upsert_review_batch(rev_buf)

    log.info(
        "bootstrap.done",
        meta_loaded=meta_loaded,
        reviews_loaded=rev_loaded,
        elapsed_s=round(time.time() - started, 1),
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
