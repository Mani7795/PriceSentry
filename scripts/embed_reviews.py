"""Embed reviews into pgvector.

Picks up any rows in `reviews` that don't yet have a `review_embeddings` row,
encodes them in batches, and inserts.

Usage:
    python /app/scripts/embed_reviews.py --batch-size 64 [--limit 10000]
"""
from __future__ import annotations

import argparse
import sys
import time

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from scraper.config import settings  # noqa: E402
from scraper.db import session_scope  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("embed")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--limit", type=int, default=None,
                   help="Optional cap on total reviews embedded in this run")
    return p.parse_args()


def _load_model():
    from sentence_transformers import SentenceTransformer
    log.info("embed.model.loading", model=settings.embedding_model)
    m = SentenceTransformer(settings.embedding_model)
    log.info("embed.model.ready", dim=m.get_sentence_embedding_dimension())
    return m


def _fetch_unembedded(batch_size: int) -> list[dict]:
    sql = """
        SELECT r.review_id::text AS review_id, r.review_text
          FROM reviews r
          LEFT JOIN review_embeddings re ON re.review_id = r.review_id
         WHERE re.review_id IS NULL
           AND r.review_text IS NOT NULL
           AND length(r.review_text) > 5
         LIMIT :n
    """
    with session_scope() as s:
        rows = s.execute(text(sql), {"n": batch_size}).mappings().all()
    return [dict(r) for r in rows]


def _insert_embeddings(rows: list[dict], vectors) -> int:
    sql = """
        INSERT INTO review_embeddings (review_id, embedding, model_version)
        VALUES (:rid, CAST(:vec AS vector), :mv)
        ON CONFLICT (review_id) DO NOTHING
    """
    with session_scope() as s:
        for row, vec in zip(rows, vectors):
            s.execute(
                text(sql),
                {"rid": row["review_id"], "vec": str(vec.tolist()), "mv": settings.embedding_model},
            )
    return len(rows)


def main() -> int:
    configure_logging()
    args = parse_args()

    model = _load_model()
    total = 0
    started = time.time()

    while True:
        rows = _fetch_unembedded(args.batch_size)
        if not rows:
            break
        texts = [r["review_text"] for r in rows]
        vectors = model.encode(texts, normalize_embeddings=True, batch_size=args.batch_size)
        total += _insert_embeddings(rows, vectors)
        if total % (args.batch_size * 10) == 0:
            log.info("embed.progress", total=total)
        if args.limit and total >= args.limit:
            break

    log.info("embed.done", total=total, elapsed_s=round(time.time() - started, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
