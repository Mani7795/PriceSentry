"""Safe demo target — generates synthetic pet-supply pages.

Why this exists:
- Lets you exercise the full pipeline without scraping any real site.
- Deterministic: same seed → same data, ideal for tests.
- Zero ToS risk.

Replace with the Chewy target (or a `books.toscrape.com` style sandbox)
when you're ready to demo live traffic.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timedelta, timezone
from typing import Iterable

from scraper.models import PriceEvent, ProductEvent, ReviewEvent, ScrapeEvent
from scraper.targets.base import BaseTarget

_BRANDS = ["Blue Buffalo", "Hill's Science", "Purina Pro Plan", "Wellness Core",
           "Taste of the Wild", "Royal Canin", "Orijen", "Nutro"]
_PET_TYPES = ["dog", "cat"]
_CATEGORIES = ["dry_food", "wet_food", "treats", "supplements", "toys"]
_REVIEW_TEMPLATES = [
    "My {pet} loves this {category}! The packaging was well-sealed and arrived quickly.",
    "Switched my {pet} to {brand} last month. Coat is shinier, energy is up.",
    "Disappointed with this {brand} {category}. The smell is off-putting and my {pet} won't eat it.",
    "Best {category} I've found for my picky {pet}. Worth the price.",
    "Recently the formula seems to have changed — my {pet} got an upset stomach.",
    "Five stars. Ordering a second bag. Good value compared to the boutique brands.",
    "Packaging arrived torn and half the kibble spilled. Customer service was decent though.",
    "{brand} has been a staple for our two {pet}s for years. Never switching.",
]


class DemoTarget(BaseTarget):
    name = "demo"

    def __init__(self, page_count: int = 25, seed: int = 42) -> None:
        self.page_count = page_count
        self._rng = random.Random(seed)

    # ------------------------------------------------------------------
    # iter_pages: produce raw "payloads" — pretend HTTP responses
    # ------------------------------------------------------------------
    def iter_pages(self) -> Iterable[dict]:
        for i in range(self.page_count):
            external_id = f"DEMO-SKU-{i:05d}"
            brand = self._rng.choice(_BRANDS)
            category = self._rng.choice(_CATEGORIES)
            pet_type = self._rng.choice(_PET_TYPES)
            title = f"{brand} {pet_type.title()} {category.replace('_', ' ').title()} - {external_id}"

            base_price = self._rng.randint(1500, 7500)  # cents
            now = datetime.now(timezone.utc)

            reviews = []
            num_reviews = self._rng.randint(3, 12)
            for r in range(num_reviews):
                template = self._rng.choice(_REVIEW_TEMPLATES)
                text = template.format(brand=brand, category=category.replace("_", " "), pet=pet_type)
                reviews.append({
                    "external_id": f"{external_id}-R{r:03d}",
                    "rating": float(self._rng.choice([1, 2, 3, 4, 4, 5, 5, 5])),
                    "text": text,
                    "reviewed_at": (now - timedelta(days=self._rng.randint(1, 365))).isoformat(),
                    "verified_purchase": self._rng.random() > 0.2,
                })

            payload = {
                "external_id": external_id,
                "url": f"https://demo.local/products/{external_id}",
                "title": title,
                "brand": brand,
                "category": category,
                "pet_type": pet_type,
                "price_cents": base_price + self._rng.randint(-500, 500),
                "in_stock": self._rng.random() > 0.05,
                "observed_at": now.isoformat(),
                "reviews": reviews,
            }
            yield payload

    # ------------------------------------------------------------------
    # parse: validate + map to ScrapeEvent
    # ------------------------------------------------------------------
    def parse(self, payload: dict) -> ScrapeEvent | None:
        try:
            product = ProductEvent(
                competitor=self.name,
                external_id=payload["external_id"],
                url=payload["url"],
                raw_title=payload["title"],
                raw_brand=payload["brand"],
                category=payload["category"],
                pet_type=payload["pet_type"],
                attributes={"category": payload["category"]},
            )
            prices = [
                PriceEvent(
                    competitor=self.name,
                    external_id=payload["external_id"],
                    observed_at=payload["observed_at"],
                    price_cents=payload["price_cents"],
                    in_stock=payload.get("in_stock"),
                )
            ]
            reviews = [
                ReviewEvent(
                    source=self.name,
                    external_id=r["external_id"],
                    rating=r.get("rating"),
                    review_text=r.get("text"),
                    reviewed_at=r.get("reviewed_at"),
                    verified_purchase=r.get("verified_purchase"),
                    raw=r,
                )
                for r in payload.get("reviews", [])
            ]
            return ScrapeEvent(product=product, prices=prices, reviews=reviews)
        except Exception:
            return None


def payload_sha256(payload: dict) -> str:
    """Stable hash for idempotent bronze writes."""
    import json
    blob = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()
