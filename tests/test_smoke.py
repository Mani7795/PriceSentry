"""Smoke tests — verify the moving parts wire up correctly.

Run inside the scraper container:
    docker compose exec scraper pytest -q /app/tests
"""
from __future__ import annotations

from sqlalchemy import text

from scraper.db import session_scope
from scraper.pipeline import run_target
from scraper.targets.demo import DemoTarget


def test_demo_target_iterates_pages():
    target = DemoTarget(page_count=3)
    pages = list(target.iter_pages())
    assert len(pages) == 3
    assert all("external_id" in p for p in pages)
    assert all("reviews" in p for p in pages)


def test_demo_target_parses_to_scrape_event():
    target = DemoTarget(page_count=1)
    payload = next(iter(target.iter_pages()))
    ev = target.parse(payload)
    assert ev is not None
    assert ev.product.competitor == "demo"
    assert len(ev.prices) == 1
    assert len(ev.reviews) >= 1


def test_pipeline_end_to_end():
    """Run the demo pipeline once and verify rows landed in silver tables."""
    summary = run_target(DemoTarget(page_count=5, seed=1))
    assert summary["pages"] == 5
    assert summary["silver_skus"] == 5
    assert summary["silver_prices"] == 5
    assert summary["silver_reviews"] >= 15  # at least 3 per product

    with session_scope() as s:
        sku_count = s.execute(text("SELECT COUNT(*) FROM competitor_skus WHERE competitor='demo'")).scalar_one()
        review_count = s.execute(text("SELECT COUNT(*) FROM reviews WHERE source='demo'")).scalar_one()
    assert sku_count >= 5
    assert review_count >= 15


def test_idempotency_of_bronze_writes():
    """Running the same target twice should not duplicate raw_events."""
    target = DemoTarget(page_count=3, seed=99)
    run_target(target)
    with session_scope() as s:
        first = s.execute(text("SELECT COUNT(*) FROM bronze.raw_events WHERE source='demo'")).scalar_one()
    # second run with same seed → identical payloads → same SHAs → no new bronze rows
    target2 = DemoTarget(page_count=3, seed=99)
    run_target(target2)
    with session_scope() as s:
        second = s.execute(text("SELECT COUNT(*) FROM bronze.raw_events WHERE source='demo'")).scalar_one()
    assert second == first  # idempotent
