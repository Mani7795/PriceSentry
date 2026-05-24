"""Public product catalog + analytics + AI insights routes.

These are PUBLIC (no auth) — the dashboard and product browsing are open.
Only the AI Assistant chat (api/chat.py) requires login.
"""
from __future__ import annotations

import asyncio
import time
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.db.session import get_db
from app.schemas.catalog import (
    AIInsightResponse,
    CatalogFacets,
    CatalogResponse,
    ProductDetail,
    ProductSummary,
    SentimentSummary,
)
from app.services.catalog_service import CatalogService
from app.services.llm_providers import complete, current_model_label
from app.services.rag_service import embed_query

router = APIRouter(prefix="/products", tags=["products"])
log = get_logger(__name__)


@router.get("", response_model=CatalogResponse)
async def list_products(
    q: str | None = Query(default=None, max_length=120),
    brand: str | None = None,
    category: str | None = None,
    pet_type: str | None = None,
    sentiment: str | None = Query(default=None, pattern="^(positive|neutral|negative)$"),
    min_price_cents: int | None = Query(default=None, ge=0),
    max_price_cents: int | None = Query(default=None, ge=0),
    sort: str = Query(default="reviews"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=24, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> CatalogResponse:
    total, items = await CatalogService(db).list_products(
        q=q, brand=brand, category=category, pet_type=pet_type, sentiment=sentiment,
        min_price_cents=min_price_cents, max_price_cents=max_price_cents,
        sort=sort, page=page, page_size=page_size,
    )
    return CatalogResponse(
        total=total, page=page, page_size=page_size,
        items=[ProductSummary.model_validate(i) for i in items],
    )


@router.get("/facets", response_model=CatalogFacets)
async def facets(db: AsyncSession = Depends(get_db)) -> CatalogFacets:
    f = await CatalogService(db).facets()
    return CatalogFacets.model_validate(f)


@router.get("/{product_id}", response_model=ProductDetail)
async def product_detail(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> ProductDetail:
    svc = CatalogService(db)
    product = await svc.get_product(product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")
    history = await svc.price_history(product_id, days=90)
    sentiment = await svc.sentiment_summary(product_id)
    return ProductDetail(
        product=ProductSummary.model_validate(product),
        price_history=history,
        sentiment=SentimentSummary.model_validate(sentiment),
    )


@router.get("/{product_id}/sentiment", response_model=SentimentSummary)
async def product_sentiment(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> SentimentSummary:
    return SentimentSummary.model_validate(await CatalogService(db).sentiment_summary(product_id))


# ────────────────────────────── AI insights ──────────────────────────────
INSIGHT_SYSTEM = """You are a product analyst for pet-supply brands.
Given REVIEW SNIPPETS for ONE product, produce a tight, structured insight:

**What customers like** — 2-3 bullets, each citing review_ids [id].
**What customers dislike** — 2-3 bullets, each citing review_ids [id].
**Competitive risks** — 1-2 bullets.
**Pricing insight** — 1 short suggestion if reviews mention price/value.

Use ONLY the snippets. Cite review_ids in [brackets]. If evidence is thin, say so.
Keep under ~180 words. Use markdown.
"""


async def _product_reviews_for_rag(db: AsyncSession, product_id: uuid.UUID, q_vec: list[float], k: int):
    """Vector search restricted to ONE product's reviews."""
    rows = (await db.execute(
        text("""
            SELECT r.review_id::text AS review_id, r.review_text, r.rating,
                   r.sentiment_label,
                   (1 - (re.embedding <=> CAST(:qvec AS vector))) AS similarity
              FROM review_embeddings re
              JOIN reviews r ON r.review_id = re.review_id
              JOIN competitor_skus cs ON cs.sku_id = r.sku_id
             WHERE cs.product_id = :pid AND r.review_text IS NOT NULL
             ORDER BY re.embedding <=> CAST(:qvec AS vector)
             LIMIT :k
        """),
        {"qvec": str(q_vec), "pid": str(product_id), "k": k},
    )).mappings().all()
    return [dict(r) for r in rows]


@router.post("/{product_id}/insights", response_model=AIInsightResponse)
async def product_insights(
    product_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> AIInsightResponse:
    svc = CatalogService(db)
    product = await svc.get_product(product_id)
    if not product:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")

    started = time.monotonic()
    q = "what do customers like and dislike about this product, quality, price, packaging, risks"
    q_vec = await asyncio.to_thread(embed_query, q)
    rows = await _product_reviews_for_rag(db, product_id, q_vec, k=12)

    if not rows:
        return AIInsightResponse(
            product_id=product_id, summary="Not enough review evidence to generate insights yet.",
            citations=[], model=current_model_label(), retrieved=0,
        )

    snippets = "\n\n".join(
        f"[{r['review_id']}] (rating={r.get('rating')}, sentiment={r.get('sentiment_label')})\n"
        f"{(r.get('review_text') or '').strip()[:400]}"
        for r in rows
    )
    user_prompt = f"PRODUCT: {product['title']}\n\nREVIEW SNIPPETS:\n{snippets}\n\nWrite the insight."

    summary = await complete(INSIGHT_SYSTEM, user_prompt)

    citations = [
        {
            "review_id": r["review_id"],
            "rating": float(r["rating"]) if r.get("rating") is not None else None,
            "sentiment": r.get("sentiment_label"),
            "snippet": (r.get("review_text") or "")[:280],
        }
        for r in rows[:6]
    ]

    # log for analytics (best-effort)
    try:
        await db.execute(
            text("""INSERT INTO ai_query_log (product_id, kind, question, model, latency_ms, retrieved_count)
                    VALUES (:pid, 'product_insight', :q, :m, :lat, :rc)"""),
            {"pid": str(product_id), "q": q, "m": current_model_label(),
             "lat": int((time.monotonic() - started) * 1000), "rc": len(rows)},
        )
        await db.commit()
    except Exception:
        await db.rollback()

    return AIInsightResponse(
        product_id=product_id, summary=summary, citations=citations,
        model=current_model_label(), retrieved=len(rows),
    )
