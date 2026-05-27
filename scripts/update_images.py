"""Backfill product images from the Amazon Reviews 2023 metadata.

Streams raw_meta_Pet_Supplies, extracts each product's primary image URL,
and updates products.image_url (matched by ASIN via competitor_skus).

The Amazon CDN images (m.media-amazon.com) are real and load directly in the
browser — same images Amazon provides to affiliates.

Usage (inside the scraper container):
    python /app/scripts/update_images.py --meta-limit 20000
"""
from __future__ import annotations

import argparse
import sys
import time
from typing import Any

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from scraper.db import session_scope  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("images")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--repo", default="McAuley-Lab/Amazon-Reviews-2023")
    p.add_argument("--meta-config", default="raw_meta_Pet_Supplies")
    p.add_argument("--meta-limit", type=int, default=20000)
    p.add_argument("--batch-size", type=int, default=500)
    return p.parse_args()


def _extract_image_url(row: dict[str, Any]) -> str | None:
    """Handle the dataset's image field, which can be a list of dicts or a dict
    of parallel arrays. Prefer large/hi_res, fall back to thumb."""
    imgs = row.get("images")
    if not imgs:
        return None

    # Form A: list of dicts [{large, hi_res, thumb, variant}, ...]
    if isinstance(imgs, list):
        for img in imgs:
            if isinstance(img, dict):
                for key in ("large", "hi_res", "thumb"):
                    if img.get(key):
                        return img[key]
        return None

    # Form B: dict of parallel arrays {"large": [...], "hi_res": [...], "thumb": [...]}
    if isinstance(imgs, dict):
        for key in ("large", "hi_res", "thumb"):
            arr = imgs.get(key)
            if isinstance(arr, list) and arr and arr[0]:
                return arr[0]
    return None


def _update_batch(pairs: list[tuple[str, str]]) -> int:
    """pairs: list of (asin, image_url). Updates the product linked to that ASIN."""
    if not pairs:
        return 0
    updated = 0
    with session_scope() as s:
        for asin, image_url in pairs:
            res = s.execute(
                text("""
                    UPDATE products p
                       SET image_url = :img
                      FROM competitor_skus cs
                     WHERE cs.product_id = p.product_id
                       AND cs.competitor = 'amazon'
                       AND cs.external_id = :asin
                       AND (p.image_url IS NULL OR p.image_url = '')
                """),
                {"img": image_url, "asin": asin},
            )
            updated += res.rowcount or 0
    return updated


def main() -> int:
    configure_logging()
    args = parse_args()

    from datasets import load_dataset
    ds = load_dataset(args.repo, args.meta_config, split="full", streaming=True, trust_remote_code=True)

    started = time.time()
    buf: list[tuple[str, str]] = []
    seen = 0
    updated = 0
    for i, row in enumerate(ds):
        if i >= args.meta_limit:
            break
        seen += 1
        asin = row.get("parent_asin") or row.get("asin")
        if not asin:
            continue
        img = _extract_image_url(row)
        if not img:
            continue
        buf.append((asin, img))
        if len(buf) >= args.batch_size:
            updated += _update_batch(buf)
            buf.clear()
            log.info("images.progress", seen=seen, updated=updated)
    if buf:
        updated += _update_batch(buf)

    log.info("images.done", seen=seen, updated=updated, elapsed_s=round(time.time() - started, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
