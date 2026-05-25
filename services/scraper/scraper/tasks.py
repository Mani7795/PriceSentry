"""Celery tasks — thin wrappers over the plain job functions."""
from __future__ import annotations

from scraper import alerts, pricing
from scraper.celery_app import app
from scraper.logging_setup import get_logger

log = get_logger("tasks")


@app.task(name="scraper.tasks.refresh_prices")
def refresh_prices(limit: int | None = None) -> int:
    return pricing.refresh_current_prices(limit)


@app.task(name="scraper.tasks.recompute_deal_stats")
def recompute_deal_stats() -> int:
    return pricing.recompute_deal_stats()


@app.task(name="scraper.tasks.check_alerts")
def check_alerts() -> int:
    return alerts.check_price_alerts()


@app.task(name="scraper.tasks.nightly_refresh")
def nightly_refresh() -> dict[str, int]:
    """The overnight pipeline: new prices -> recompute deals -> fire alerts."""
    log.info("nightly_refresh.start")
    priced = pricing.refresh_current_prices()
    deals = pricing.recompute_deal_stats()
    fired = alerts.check_price_alerts()
    result = {"priced": priced, "deals": deals, "alerts": fired}
    log.info("nightly_refresh.done", **result)
    return result
