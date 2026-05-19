"""RAG retrieval + generation.

Phase 1: simple but production-shaped.
- Embed the question with the same model used for indexing.
- Retrieve top-K via pgvector cosine similarity (with optional brand filter).
- Build a system prompt that REQUIRES citations like [review_id].
- Call the configured LLM provider.
- Return both the answer and the cited review snippets.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.config import settings
from app.deps import get_embedding_model, get_engine, get_llm_client


SYSTEM_PROMPT = """You are PriceSentry's customer-feedback analyst.

You will be given a USER QUESTION about pet-supply products and a numbered list of
REVIEW SNIPPETS retrieved from real customer reviews. Your job is to answer the
question using ONLY the information in those snippets.

RULES:
1. Every factual claim in your answer MUST cite at least one review using its
   review_id, in square brackets, like this: [a3f1c2...].
2. If the snippets do not support an answer, say "I don't have enough review
   evidence to answer that." Do NOT fabricate.
3. Quote sparingly — paraphrase. Cite, don't copy whole reviews.
4. Be concise (max ~6 short paragraphs).
"""


def _embed_question(q: str) -> list[float]:
    model = get_embedding_model()
    vec = model.encode([q], normalize_embeddings=True)[0]
    return vec.tolist()


def _retrieve(q_vec: list[float], brand: str | None, top_k: int) -> list[dict[str, Any]]:
    """Top-K reviews by cosine similarity, with optional brand filter.

    NOTE: parameters that may be NULL must be explicitly cast (CAST(:p AS TEXT))
    so Postgres can infer their data type — otherwise we get
    `AmbiguousParameter: could not determine data type` errors.
    """
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
    eng = get_engine()
    with eng.connect() as conn:
        rows = conn.execute(
            text(sql),
            {"qvec": str(q_vec), "brand": brand, "k": top_k},
        ).mappings().all()
    return [dict(r) for r in rows]


def _format_snippets(rows: list[dict[str, Any]]) -> str:
    lines = []
    for i, r in enumerate(rows, start=1):
        lines.append(
            f"[{r['review_id']}] (brand={r.get('brand') or 'unknown'}, "
            f"rating={r.get('rating')}, sim={r['similarity']:.2f})\n"
            f"{(r.get('review_text') or '').strip()}"
        )
    return "\n\n".join(lines)


def answer_question(question: str, brand: str | None = None) -> dict[str, Any]:
    q_vec = _embed_question(question)
    rows = _retrieve(q_vec, brand=brand, top_k=settings.rag_top_k)
    if not rows:
        return {
            "answer": "I don't have enough review evidence to answer that.",
            "citations": [],
            "retrieved": 0,
        }

    # Phase 1 has no reranker; just truncate to top-N. Phase 2 adds bge-reranker.
    rows = rows[: settings.rag_rerank_top_n]
    snippets = _format_snippets(rows)

    user_prompt = (
        f"USER QUESTION:\n{question}\n\n"
        f"REVIEW SNIPPETS:\n{snippets}\n\n"
        f"Answer the question using ONLY these snippets. Cite review_ids in brackets."
    )

    llm = get_llm_client()
    answer = llm(SYSTEM_PROMPT, user_prompt)

    citations = [
        {
            "review_id": r["review_id"],
            "brand": r.get("brand"),
            "rating": r.get("rating"),
            "similarity": round(float(r["similarity"]), 3),
            "snippet": (r.get("review_text") or "")[:300],
        }
        for r in rows
    ]

    return {"answer": answer, "citations": citations, "retrieved": len(rows)}
