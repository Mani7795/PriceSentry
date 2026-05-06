"""Pydantic data contracts for scraped events.

These are validated *before* they hit the silver tables. If a parser ever
emits something that doesn't validate, the bronze write still happens
(we never lose raw data) but the silver write is skipped and logged.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class ReviewEvent(BaseModel):
    source: str
    external_id: str
    rating: float | None = Field(default=None, ge=0, le=5)
    review_text: str | None = None
    reviewed_at: datetime | None = None
    verified_purchase: bool | None = None
    raw: dict[str, Any] = Field(default_factory=dict)


class PriceEvent(BaseModel):
    competitor: str
    external_id: str
    observed_at: datetime
    price_cents: int | None = Field(default=None, ge=0)
    currency: str = "USD"
    in_stock: bool | None = None


class ProductEvent(BaseModel):
    competitor: str
    external_id: str
    url: HttpUrl | None = None
    raw_title: str
    raw_brand: str | None = None
    category: str | None = None
    pet_type: str | None = None
    upc: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class ScrapeEvent(BaseModel):
    """One scraped page yields one of these. Bundles everything together."""
    product: ProductEvent
    prices: list[PriceEvent] = Field(default_factory=list)
    reviews: list[ReviewEvent] = Field(default_factory=list)
