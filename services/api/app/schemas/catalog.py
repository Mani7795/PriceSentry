"""Product catalog / analytics schemas (public dashboard)."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel


class CompetitorPrice(BaseModel):
    competitor: str
    price_cents: int | None = None
    currency: str = "USD"
    in_stock: bool | None = None
    observed_at: datetime | None = None
    price_diff_pct: float | None = None   # vs cheapest competitor
    is_cheapest: bool = False
    url: str | None = None


class ProductSummary(BaseModel):
    product_id: uuid.UUID
    brand: str | None = None
    title: str
    category: str | None = None
    pet_type: str | None = None
    review_count: int = 0
    avg_rating: float | None = None
    avg_sentiment: float | None = None
    pct_positive: float | None = None
    competitor_count: int | None = None
    min_price_cents: int | None = None
    max_price_cents: int | None = None
    cheapest_competitor: str | None = None
    # deal indicator (populated by the nightly job)
    deal_label: str | None = None          # great | good | typical | high
    deal_pct_rank: float | None = None     # 0..1
    deal_current_cents: int | None = None
    competitors: list[CompetitorPrice] = []


class CatalogResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ProductSummary]


class FacetValue(BaseModel):
    value: str
    count: int


class CatalogFacets(BaseModel):
    brands: list[FacetValue]
    categories: list[FacetValue]
    pet_types: list[FacetValue]


class PricePoint(BaseModel):
    observed_at: datetime
    competitor: str
    price_cents: int


class AspectSentiment(BaseModel):
    aspect: str
    mentions: int
    avg_sentiment: float
    label: str            # positive|neutral|negative
    sample_snippet: str | None = None


class SentimentSummary(BaseModel):
    review_count: int
    avg_sentiment: float | None = None
    pct_positive: float | None = None
    pct_negative: float | None = None
    aspects: list[AspectSentiment] = []
    top_complaints: list[str] = []
    top_praises: list[str] = []


class ProductDetail(BaseModel):
    product: ProductSummary
    price_history: list[PricePoint] = []
    sentiment: SentimentSummary


class AIInsightCitation(BaseModel):
    review_id: str
    rating: float | None = None
    sentiment: str | None = None
    snippet: str


class AIInsightResponse(BaseModel):
    product_id: uuid.UUID
    summary: str
    citations: list[AIInsightCitation] = []
    model: str
    retrieved: int
