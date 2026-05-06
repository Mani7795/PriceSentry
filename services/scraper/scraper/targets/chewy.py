"""Chewy target — STRUCTURAL REFERENCE ONLY by default.

Chewy's robots.txt disallows automated access to product pages. This module
is included to demonstrate how a real scraper would be structured, but the
network layer is gated behind the CHEWY_LIVE env var (default: 0).

If you choose to enable it, you assume responsibility for:
  - obeying robots.txt and ToS,
  - using residential proxies and aggressive rate limiting,
  - obtaining any required permissions.

For portfolio purposes, prefer the bootstrap dataset (Amazon Reviews 2023)
and the demo target. The architecture is identical.
"""
from __future__ import annotations

import time
from typing import Iterable

from scraper.config import settings
from scraper.logging_setup import get_logger
from scraper.models import PriceEvent, ProductEvent, ReviewEvent, ScrapeEvent
from scraper.targets.base import BaseTarget

log = get_logger(__name__)


# A short, hard-coded seed list. In a real build this would come from a
# `seed_skus` table or sitemap.xml fetch.
SEED_URLS = [
    # Examples (do NOT actually hit these without enabling CHEWY_LIVE):
    # "https://www.chewy.com/blue-buffalo-life-protection-formula/dp/36272",
    # "https://www.chewy.com/hills-science-diet-adult-perfect/dp/36374",
]


class ChewyTarget(BaseTarget):
    name = "chewy"

    def __init__(self) -> None:
        if not settings.chewy_live:
            log.warning(
                "chewy.disabled",
                msg="ChewyTarget is disabled (CHEWY_LIVE=0). It will yield zero pages.",
            )

    # ------------------------------------------------------------------
    def iter_pages(self) -> Iterable[dict]:
        if not settings.chewy_live:
            return iter([])
        # When live: use Playwright. We import here to avoid pulling it in
        # for callers who only want the parser shape.
        from playwright.sync_api import sync_playwright  # noqa

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(user_agent=settings.scrape_user_agent)
            page = ctx.new_page()

            for url in SEED_URLS:
                log.info("chewy.fetch", url=url)
                try:
                    page.goto(url, timeout=30_000, wait_until="domcontentloaded")
                    html = page.content()
                    yield {
                        "url": url,
                        "html": html,
                        "fetched_at": time.time(),
                    }
                except Exception as e:
                    log.warning("chewy.fetch_failed", url=url, error=str(e))
                finally:
                    time.sleep(settings.scrape_request_delay_seconds)

            browser.close()

    # ------------------------------------------------------------------
    def parse(self, payload: dict) -> ScrapeEvent | None:
        """Stub parser. Replace with real BeautifulSoup selectors when you
        wire this up. The shape of ScrapeEvent is the same as for the
        demo target, so downstream code never needs to change.
        """
        log.info("chewy.parse_stub", url=payload.get("url"))
        # In a real implementation:
        #   soup = BeautifulSoup(payload["html"], "html.parser")
        #   title = soup.select_one("h1[data-testid=product-title]").text
        #   price = ...
        #   reviews = ...
        # For now, return None so the bronze write happens but no silver row is created.
        return None
