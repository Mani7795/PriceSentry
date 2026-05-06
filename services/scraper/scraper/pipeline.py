"""Scrape pipeline: fetch → bronze → parse → silver.

The flow is:

    target.iter_pages() ─► raw payload ─► bronze.raw_events (idempotent on SHA-256)
                                                │
                                                ▼
                                       target.parse(payload)
                                                │
                                                ▼
                            ScrapeEvent ──► upsert into silver tables

If parse() returns None, only the bronze write occurs. We never lose data.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from sqlalchemy import text
from sqlalchemy.orm import Session

from scraper.db import session_scope
from scraper.logging_setup import get_logger
from scraper.models import ScrapeEvent
from scraper.targets.base import BaseTarget

log = get_logger(__name__)


def _sha256(payload: dict) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()


def _bronze_insert(session: Session, source: str, payload: dict, url: str | None) -> str | None:
    """Insert into bronze.raw_events. Returns raw_event_id, or None if duplicate."""
    sha = _sha256(payload)
    row = session.execute(
        text(
            """
            INSERT INTO bronze.raw_events (source, fetched_at, url, http_status, payload, payload_sha256)
            VALUES (:source, NOW(), :url, 200, CAST(:payload AS JSONB), :sha)
            ON CONFLICT (source, payload_sha256) DO NOTHING
            RETURNING raw_event_id
            """
        ),
        {"source": source, "url": url, "payload": json.dumps(payload, default=str), "sha": sha},
    ).first()
    return str(row.raw_event_id) if row else None


def _upsert_competitor_sku(session: Session, ev: ScrapeEvent) -> str:
    """Returns sku_id."""
    row = session.execute(
        text(
            """
            INSERT INTO competitor_skus (competitor, external_id, url, raw_title, raw_brand)
            VALUES (:competitor, :external_id, :url, :raw_title, :raw_brand)
            ON CONFLICT (competitor, external_id) DO UPDATE
                SET url = EXCLUDED.url,
                    raw_title = EXCLUDED.raw_title,
                    raw_brand = EXCLUDED.raw_brand
            RETURNING sku_id
            """
        ),
        {
            "competitor": ev.product.competitor,
            "external_id": ev.product.external_id,
            "url": str(ev.product.url) if ev.product.url else None,
            "raw_title": ev.product.raw_title,
            "raw_brand": ev.product.raw_brand,
        },
    ).first()
    return str(row.sku_id)


def _insert_prices(session: Session, sku_id: str, ev: ScrapeEvent, raw_event_id: str | None) -> int:
    inserted = 0
    for p in ev.prices:
        session.execute(
            text(
                """
                INSERT INTO price_observations
                    (sku_id, observed_at, price_cents, currency, in_stock, raw_event_id)
                VALUES
                    (:sku_id, :observed_at, :price_cents, :currency, :in_stock, :raw_event_id)
                """
            ),
            {
                "sku_id": sku_id,
                "observed_at": p.observed_at,
                "price_cents": p.price_cents,
                "currency": p.currency,
                "in_stock": p.in_stock,
                "raw_event_id": raw_event_id,
            },
        )
        inserted += 1
    return inserted


def _upsert_reviews(session: Session, sku_id: str, ev: ScrapeEvent) -> int:
    inserted = 0
    for r in ev.reviews:
        session.execute(
            text(
                """
                INSERT INTO reviews
                    (sku_id, source, external_id, rating, review_text, reviewed_at,
                     verified_purchase, raw_payload)
                VALUES
                    (:sku_id, :source, :external_id, :rating, :review_text, :reviewed_at,
                     :verified_purchase, CAST(:raw AS JSONB))
                ON CONFLICT (source, external_id) DO UPDATE
                    SET review_text = EXCLUDED.review_text,
                        rating      = EXCLUDED.rating
                """
            ),
            {
                "sku_id": sku_id,
                "source": r.source,
                "external_id": r.external_id,
                "rating": r.rating,
                "review_text": r.review_text,
                "reviewed_at": r.reviewed_at,
                "verified_purchase": r.verified_purchase,
                "raw": json.dumps(r.raw, default=str),
            },
        )
        inserted += 1
    return inserted


def run_target(target: BaseTarget) -> dict:
    """Run a single target end-to-end and return summary stats."""
    pages = 0
    bronze_writes = 0
    silver_skus = 0
    silver_prices = 0
    silver_reviews = 0
    parse_failures = 0

    with session_scope() as session:
        # operational job marker
        job = session.execute(
            text(
                "INSERT INTO scrape_jobs (target, status) VALUES (:t, 'running') RETURNING job_id"
            ),
            {"t": target.name},
        ).first()
        job_id = str(job.job_id)

    try:
        for payload in target.iter_pages():
            pages += 1
            url = payload.get("url")
            with session_scope() as session:
                raw_event_id = _bronze_insert(session, target.name, payload, url)
                if raw_event_id:
                    bronze_writes += 1

                ev = target.parse(payload)
                if ev is None:
                    parse_failures += 1
                    continue

                sku_id = _upsert_competitor_sku(session, ev)
                silver_skus += 1
                silver_prices += _insert_prices(session, sku_id, ev, raw_event_id)
                silver_reviews += _upsert_reviews(session, sku_id, ev)

        with session_scope() as session:
            session.execute(
                text(
                    """
                    UPDATE scrape_jobs
                       SET finished_at = NOW(),
                           status = 'ok',
                           pages_fetched = :pages,
                           events_written = :events
                     WHERE job_id = :id
                    """
                ),
                {"pages": pages, "events": bronze_writes, "id": job_id},
            )

    except Exception as e:
        log.error("pipeline.error", error=str(e))
        with session_scope() as session:
            session.execute(
                text(
                    "UPDATE scrape_jobs SET finished_at=NOW(), status='error', error=:e WHERE job_id=:id"
                ),
                {"e": str(e)[:500], "id": job_id},
            )
        raise

    summary = {
        "target": target.name,
        "pages": pages,
        "bronze_writes": bronze_writes,
        "silver_skus": silver_skus,
        "silver_prices": silver_prices,
        "silver_reviews": silver_reviews,
        "parse_failures": parse_failures,
    }
    log.info("pipeline.done", **summary)
    return summary
