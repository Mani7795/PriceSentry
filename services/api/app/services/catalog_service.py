"""Catalog + product analytics queries (read side of the dashboard)."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class CatalogService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ───────────────────────────── catalog list ─────────────────────────
    async def list_products(
        self,
        *,
        q: str | None,
        brand: str | None,
        category: str | None,
        pet_type: str | None,
        sentiment: str | None,         # positive|neutral|negative
        deal: str | None,              # great|good|typical|high
        min_price_cents: int | None,
        max_price_cents: int | None,
        sort: str,                     # 'reviews'|'rating'|'sentiment'|'price_asc'|'price_desc'|'deals'
        page: int,
        page_size: int,
    ) -> tuple[int, list[dict[str, Any]]]:
        filters = ["1=1"]
        params: dict[str, Any] = {}

        if q:
            filters.append("(LOWER(d.title) LIKE :q OR LOWER(d.brand) LIKE :q)")
            params["q"] = f"%{q.lower()}%"
        if brand:
            filters.append("LOWER(d.brand) = LOWER(:brand)")
            params["brand"] = brand
        if category:
            filters.append("d.category = :category")
            params["category"] = category
        if pet_type:
            filters.append("d.pet_type = :pet_type")
            params["pet_type"] = pet_type
        if sentiment == "positive":
            filters.append("d.avg_sentiment >= 0.05")
        elif sentiment == "negative":
            filters.append("d.avg_sentiment <= -0.05")
        elif sentiment == "neutral":
            filters.append("d.avg_sentiment > -0.05 AND d.avg_sentiment < 0.05")
        if deal in ("great", "good", "typical", "high"):
            filters.append("d.deal_label = :deal")
            params["deal"] = deal
        if min_price_cents is not None:
            filters.append("d.min_price_cents >= :minp")
            params["minp"] = min_price_cents
        if max_price_cents is not None:
            filters.append("d.min_price_cents <= :maxp")
            params["maxp"] = max_price_cents
        # NOTE: we intentionally do NOT require reviews — the full catalog is
        # browsable and comparable by price + rating. Sentiment simply shows
        # as "neutral"/absent for products without review text.

        where = " AND ".join(filters)

        order = {
            "reviews": "d.review_count DESC NULLS LAST",
            "rating": "d.avg_rating DESC NULLS LAST",
            "sentiment": "d.avg_sentiment DESC NULLS LAST",
            "price_asc": "d.min_price_cents ASC NULLS LAST",
            "price_desc": "d.min_price_cents DESC NULLS LAST",
            "deals": "d.deal_pct_rank ASC NULLS LAST",   # best deals first
        }.get(sort, "d.review_count DESC NULLS LAST")

        total = int(await self.db.scalar(
            text(f"SELECT COUNT(*) FROM v_product_dashboard d WHERE {where}"), params
        ) or 0)

        params["limit"] = page_size
        params["offset"] = (page - 1) * page_size
        rows = (await self.db.execute(
            text(f"""
                SELECT d.* FROM v_product_dashboard d
                 WHERE {where}
                 ORDER BY {order}
                 LIMIT :limit OFFSET :offset
            """),
            params,
        )).mappings().all()

        items = [dict(r) for r in rows]
        # attach competitor prices for the page's products
        await self._attach_competitors(items)
        return total, items

    async def _attach_competitors(self, items: list[dict[str, Any]]) -> None:
        if not items:
            return
        ids = [str(it["product_id"]) for it in items]
        rows = (await self.db.execute(
            text("""
                SELECT product_id::text AS product_id, competitor, price_cents,
                       currency, in_stock, observed_at, url
                  FROM v_product_competitor_price
                 WHERE product_id::text = ANY(:ids)
            """),
            {"ids": ids},
        )).mappings().all()

        by_product: dict[str, list[dict]] = {}
        for r in rows:
            by_product.setdefault(r["product_id"], []).append(dict(r))

        for it in items:
            comps = by_product.get(str(it["product_id"]), [])
            cheapest = min((c["price_cents"] for c in comps if c["price_cents"]), default=None)
            for c in comps:
                if cheapest and c["price_cents"]:
                    c["price_diff_pct"] = round((c["price_cents"] - cheapest) / cheapest * 100, 1)
                    c["is_cheapest"] = c["price_cents"] == cheapest
                else:
                    c["price_diff_pct"] = None
                    c["is_cheapest"] = False
            # stable retailer order
            order = {"amazon": 0, "chewy": 1, "petco": 2, "petsmart": 3}
            comps.sort(key=lambda c: order.get(c["competitor"], 9))
            it["competitors"] = comps

    # ───────────────────────────── facets ───────────────────────────────
    async def facets(self) -> dict[str, list[dict[str, Any]]]:
        async def _facet(col: str) -> list[dict[str, Any]]:
            rows = (await self.db.execute(
                text(f"""
                    SELECT {col} AS value, COUNT(*) AS count
                      FROM v_product_dashboard
                     WHERE {col} IS NOT NULL
                     GROUP BY {col}
                     ORDER BY count DESC
                     LIMIT 30
                """)
            )).mappings().all()
            return [{"value": r["value"], "count": int(r["count"])} for r in rows]

        return {
            "brands": await _facet("brand"),
            "categories": await _facet("category"),
            "pet_types": await _facet("pet_type"),
        }

    # ───────────────────────────── product detail ───────────────────────
    async def get_product(self, product_id: uuid.UUID) -> dict[str, Any] | None:
        row = await self.db.execute(
            text("SELECT * FROM v_product_dashboard WHERE product_id = :pid"),
            {"pid": str(product_id)},
        )
        m = row.mappings().first()
        if not m:
            return None
        item = dict(m)
        await self._attach_competitors([item])
        return item

    async def price_history(self, product_id: uuid.UUID, days: int = 90) -> list[dict[str, Any]]:
        rows = (await self.db.execute(
            text("""
                SELECT po.observed_at, cs.competitor, po.price_cents
                  FROM competitor_skus cs
                  JOIN price_observations po ON po.sku_id = cs.sku_id
                 WHERE cs.product_id = :pid
                   AND po.observed_at >= NOW() - (:days || ' days')::interval
                   AND po.price_cents IS NOT NULL
                 ORDER BY po.observed_at ASC
            """),
            {"pid": str(product_id), "days": days},
        )).mappings().all()
        return [dict(r) for r in rows]

    async def sentiment_summary(self, product_id: uuid.UUID) -> dict[str, Any]:
        overall = (await self.db.execute(
            text("""
                SELECT COUNT(*) AS review_count,
                       AVG(r.sentiment_score) AS avg_sentiment,
                       AVG(CASE WHEN r.sentiment_label='positive' THEN 1.0 ELSE 0.0 END) AS pct_positive,
                       AVG(CASE WHEN r.sentiment_label='negative' THEN 1.0 ELSE 0.0 END) AS pct_negative
                  FROM competitor_skus cs
                  JOIN reviews r ON r.sku_id = cs.sku_id
                 WHERE cs.product_id = :pid AND r.sentiment_score IS NOT NULL
            """),
            {"pid": str(product_id)},
        )).mappings().first()

        aspects = (await self.db.execute(
            text("""
                SELECT aspect,
                       COUNT(*) AS mentions,
                       AVG(sentiment_score) AS avg_sentiment,
                       (ARRAY_AGG(snippet ORDER BY ABS(sentiment_score) DESC))[1] AS sample
                  FROM review_aspects
                 WHERE product_id = :pid
                 GROUP BY aspect
                 ORDER BY mentions DESC
            """),
            {"pid": str(product_id)},
        )).mappings().all()

        def label(v: float | None) -> str:
            if v is None:
                return "neutral"
            return "positive" if v >= 0.05 else "negative" if v <= -0.05 else "neutral"

        aspect_list = []
        for a in aspects:
            avg = float(a["avg_sentiment"]) if a["avg_sentiment"] is not None else 0.0
            aspect_list.append({
                "aspect": a["aspect"],
                "mentions": int(a["mentions"]),
                "avg_sentiment": round(avg, 3),
                "label": label(avg),
                "sample_snippet": a["sample"],
            })

        complaints = [a["aspect"] for a in aspect_list if a["label"] == "negative"][:5]
        praises = [a["aspect"] for a in aspect_list if a["label"] == "positive"][:5]

        return {
            "review_count": int(overall["review_count"]) if overall and overall["review_count"] else 0,
            "avg_sentiment": round(float(overall["avg_sentiment"]), 3) if overall and overall["avg_sentiment"] is not None else None,
            "pct_positive": round(float(overall["pct_positive"]), 3) if overall and overall["pct_positive"] is not None else None,
            "pct_negative": round(float(overall["pct_negative"]), 3) if overall and overall["pct_negative"] is not None else None,
            "aspects": aspect_list,
            "top_complaints": complaints,
            "top_praises": praises,
        }
