"""RAG retrieval + prompt building.

Phase 1 had simple top-K cosine retrieval. This adds:
- Hybrid-ready interface (BM25 hook left for Phase 2.2)
- Metadata filtering (brand)
- Reranker placeholder
- Conversation-history-aware prompt building
"""
from __future__ import annotations

from functools import lru_cache
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.settings import settings

log = get_logger(__name__)


SYSTEM_PROMPT_BASE = """You are PriceSentry's customer-feedback analyst.

You will be given conversation history, a USER QUESTION, and a numbered list of
REVIEW SNIPPETS retrieved from real customer reviews. Your job is to answer the
question using ONLY the information in those snippets.

RULES:
1. Every factual claim in your answer MUST cite at least one review using its
   review_id in square brackets, like this: [a3f1c2-...].
2. If the snippets do not support an answer, say "I don't have enough review
   evidence to answer that." Do NOT fabricate.
3. Quote sparingly — paraphrase. Cite, don't copy whole reviews.
4. Be concise (max ~5 short paragraphs).
"""


@lru_cache(maxsize=1)
def _embedding_model():
    from sentence_transformers import SentenceTransformer
    log.info("rag.embedder.loading", model=settings.embedding_model)
    return SentenceTransformer(settings.embedding_model)


def embed_query(text_in: str) -> list[float]:
    vec = _embedding_model().encode([text_in], normalize_embeddings=True)[0]
    return vec.tolist()


async def retrieve(
    db: AsyncSession,
    *,
    query_vec: list[float],
    brand: str | None,
    top_k: int,
) -> list[dict[str, Any]]:
    """Dense retrieval via pgvector cosine sim. Optional brand pre-filter."""
    sql = """
        SELECT
            r.review_id::text         AS review_id,
            r.review_text             AS review_text,
            r.rating                  AS rating,
            r.reviewed_at             AS reviewed_at,
            cs.competitor             AS competitor,
            cs.raw_brand              AS brand,
            cs.raw_title              AS product_title,
            (1 - (re.embedding <=> CAST(:qvec AS vector))) AS similarity
        FROM review_embeddings re
        JOIN reviews r ON r.review_id = re.review_id
        LEFT JOIN competitor_skus cs ON cs.sku_id = r.sku_id
        WHERE r.review_text IS NOT NULL
          AND (CAST(:brand AS TEXT) IS NULL OR LOWER(cs.raw_brand) = LOWER(CAST(:brand AS TEXT)))
        ORDER BY re.embedding <=> CAST(:qvec AS vector)
        LIMIT :k
    """
    result = await db.execute(
        text(sql),
        {"qvec": str(query_vec), "brand": brand, "k": top_k},
    )
    rows = result.mappings().all()
    return [dict(r) for r in rows]


def rerank(rows: list[dict[str, Any]], top_n: int) -> list[dict[str, Any]]:
    """Phase 1: truncate. Phase 2.2 will swap in bge-reranker-base."""
    return rows[:top_n]


def format_snippets(rows: list[dict[str, Any]]) -> str:
    lines = []
    for r in rows:
        sim = r.get("similarity") or 0.0
        lines.append(
            f"[{r['review_id']}] (brand={r.get('brand') or 'unknown'}, "
            f"rating={r.get('rating')}, sim={sim:.2f})\n"
            f"{(r.get('review_text') or '').strip()}"
        )
    return "\n\n".join(lines)


def build_user_prompt(history: list[dict[str, str]], question: str, snippets: str) -> str:
    parts = []
    if history:
        parts.append("CONVERSATION SO FAR:")
        for m in history:
            parts.append(f"{m['role'].upper()}: {m['content']}")
        parts.append("")
    parts.append(f"USER QUESTION:\n{question}\n")
    parts.append(f"REVIEW SNIPPETS:\n{snippets}\n")
    parts.append("Answer the question using ONLY the snippets above. Cite review_ids in brackets.")
    return "\n".join(parts)


def system_prompt() -> str:
    return SYSTEM_PROMPT_BASE
