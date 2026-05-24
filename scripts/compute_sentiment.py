"""Compute REAL sentiment + aspect-level sentiment over the reviews corpus.

This is a genuine NLP pipeline:
  1. Overall review sentiment via VADER (rule-based, tuned for short informal text
     like reviews — fast on CPU, no model download, deterministic).
  2. Aspect-based sentiment: for a fixed set of pet-product aspects, find sentences
     that mention the aspect and score that sentence's sentiment. This yields
     statements like "customers dislike packaging" / "customers love ingredients".

Why VADER and not a transformer:
  - Runs in-process on CPU in seconds for thousands of reviews (your laptop has no GPU).
  - Well-validated for product/social review text.
  - To upgrade later: swap _score_text() for a HuggingFace sentiment pipeline
    (e.g. distilbert-base-uncased-finetuned-sst-2-english). The interface is isolated.

Usage (inside the scraper container, which has the DB + deps):
    python /app/scripts/compute_sentiment.py --batch-size 500
"""
from __future__ import annotations

import argparse
import re
import sys
import time

sys.path.insert(0, "/app")

from sqlalchemy import text  # noqa: E402

from scraper.db import session_scope  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("sentiment")

# Aspect lexicon: aspect -> trigger keywords (lowercased, matched as word-ish)
ASPECTS: dict[str, list[str]] = {
    "packaging": ["packaging", "package", "packag", "bag", "seal", "sealed", "box", "container", "lid", "spill"],
    "price": ["price", "priced", "pricing", "expensive", "cheap", "cost", "costly", "overpriced", "affordable"],
    "value": ["value", "worth", "money", "deal", "bargain"],
    "quality": ["quality", "well made", "durable", "cheaply made", "flimsy", "sturdy"],
    "smell": ["smell", "smells", "odor", "odour", "stink", "stinky", "aroma", "scent"],
    "ingredients": ["ingredient", "ingredients", "formula", "recipe", "grain", "protein", "natural", "filler"],
    "shipping": ["shipping", "shipped", "delivery", "delivered", "arrived", "arrive", "fast", "slow", "late"],
    "taste": ["taste", "flavor", "flavour", "palatable", "picky", "loves it", "won't eat", "wouldn't eat"],
}

_SENT_SPLIT = re.compile(r"(?<=[.!?])\s+")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--batch-size", type=int, default=500)
    p.add_argument("--limit", type=int, default=None, help="Cap total reviews processed")
    p.add_argument("--recompute", action="store_true", help="Recompute even if already scored")
    return p.parse_args()


def _label(score: float) -> str:
    if score >= 0.05:
        return "positive"
    if score <= -0.05:
        return "negative"
    return "neutral"


def _make_scorer():
    """Returns a function text->compound score in [-1, 1]."""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    except ImportError:
        log.error("sentiment.vader_missing",
                  msg="Install with: pip install vaderSentiment --break-system-packages")
        raise
    analyzer = SentimentIntensityAnalyzer()

    def score(text_in: str) -> float:
        return analyzer.polarity_scores(text_in or "")["compound"]

    return score


def _aspects_in(text_lower: str) -> dict[str, list[str]]:
    """Return aspects whose keywords appear, mapped to matching sentences."""
    sentences = _SENT_SPLIT.split(text_lower)
    found: dict[str, list[str]] = {}
    for aspect, keywords in ASPECTS.items():
        hits = [s for s in sentences if any(k in s for k in keywords)]
        if hits:
            found[aspect] = hits
    return found


def _fetch_batch(batch_size: int, recompute: bool) -> list[dict]:
    where = "" if recompute else "AND r.sentiment_score IS NULL"
    sql = f"""
        SELECT r.review_id::text AS review_id,
               r.review_text       AS review_text,
               cs.product_id::text AS product_id
          FROM reviews r
          LEFT JOIN competitor_skus cs ON cs.sku_id = r.sku_id
         WHERE r.review_text IS NOT NULL
           AND length(r.review_text) > 3
           {where}
         LIMIT :n
    """
    with session_scope() as s:
        rows = s.execute(text(sql), {"n": batch_size}).mappings().all()
    return [dict(r) for r in rows]


def _persist(rows: list[dict], scorer) -> int:
    with session_scope() as s:
        for row in rows:
            rid = row["review_id"]
            pid = row["product_id"]
            body = row["review_text"] or ""
            overall = scorer(body)
            s.execute(
                text("""UPDATE reviews
                           SET sentiment_score = :sc,
                               sentiment_label = :lb,
                               sentiment_model = 'vader-3.3.2'
                         WHERE review_id = :rid"""),
                {"sc": overall, "lb": _label(overall), "rid": rid},
            )

            # Aspect-level: clear old, insert fresh
            s.execute(text("DELETE FROM review_aspects WHERE review_id = :rid"), {"rid": rid})
            for aspect, sentences in _aspects_in(body.lower()).items():
                joined = " ".join(sentences)[:500]
                asc = scorer(joined)
                s.execute(
                    text("""INSERT INTO review_aspects
                                (review_id, product_id, aspect, sentiment_score, sentiment_label, snippet)
                            VALUES (:rid, :pid, :asp, :sc, :lb, :sn)"""),
                    {"rid": rid, "pid": pid, "asp": aspect, "sc": asc,
                     "lb": _label(asc), "sn": joined},
                )
    return len(rows)


def main() -> int:
    configure_logging()
    args = parse_args()
    scorer = _make_scorer()

    total = 0
    started = time.time()
    while True:
        rows = _fetch_batch(args.batch_size, args.recompute)
        if not rows:
            break
        total += _persist(rows, scorer)
        log.info("sentiment.progress", total=total)
        if args.limit and total >= args.limit:
            break
        # If recompute, we'd loop forever; recompute is meant to be one-shot with --limit
        if args.recompute and not args.limit:
            break

    log.info("sentiment.done", total=total, elapsed_s=round(time.time() - started, 1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
