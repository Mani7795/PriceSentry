"""Price-drop / great-deal alert checking.

Email delivery is console/log only for now (per current config). The alert
rows are persisted to `alert_events` so a real sender (Resend/SES) can later
pick up undelivered rows and mail them — the logic doesn't change.
"""
from __future__ import annotations

from sqlalchemy import text

from scraper.db import session_scope
from scraper.logging_setup import get_logger

log = get_logger("alerts")

# Don't re-alert the same user+product within this window.
DEDUP_HOURS = 24


def check_price_alerts() -> int:
    """Find watchlist matches and emit alerts (logged + persisted)."""
    find_sql = """
        SELECT w.user_id::text       AS user_id,
               w.product_id::text    AS product_id,
               w.target_price_cents  AS target,
               ds.current_cents      AS current_cents,
               ds.deal_label         AS deal_label,
               p.title               AS title,
               u.email               AS email
          FROM watchlists w
          JOIN deal_stats ds ON ds.product_id = w.product_id
          JOIN products p    ON p.product_id  = w.product_id
          JOIN users u       ON u.user_id     = w.user_id
         WHERE ds.current_cents IS NOT NULL
           AND (
                 (w.target_price_cents IS NOT NULL AND ds.current_cents <= w.target_price_cents)
              OR (w.target_price_cents IS NULL AND ds.deal_label = 'great')
           )
    """
    dedup_sql = """
        SELECT 1 FROM alert_events
         WHERE user_id = :uid AND product_id = :pid
           AND created_at >= NOW() - (:hours || ' hours')::interval
         LIMIT 1
    """
    insert_sql = """
        INSERT INTO alert_events (user_id, product_id, kind, price_cents, message, delivered)
        VALUES (:uid, :pid, :kind, :price, :msg, FALSE)
    """

    emitted = 0
    with session_scope() as s:
        rows = s.execute(text(find_sql)).mappings().all()
        for r in rows:
            # dedup
            already = s.execute(
                text(dedup_sql), {"uid": r["user_id"], "pid": r["product_id"], "hours": DEDUP_HOURS}
            ).first()
            if already:
                continue

            kind = "price_target" if r["target"] is not None else "great_deal"
            price = r["current_cents"]
            dollars = f"${price/100:.2f}"
            if kind == "price_target":
                msg = (f"Price alert: '{r['title']}' is now {dollars} "
                       f"(your target ${r['target']/100:.2f}).")
            else:
                msg = f"Great deal: '{r['title']}' is at {dollars} — among its lowest in 90 days."

            s.execute(text(insert_sql),
                      {"uid": r["user_id"], "pid": r["product_id"],
                       "kind": kind, "price": price, "msg": msg})

            # "Send" = log to console for now.
            log.info("alert.emit", to=r["email"], kind=kind, product=r["title"],
                     price_cents=price, message=msg)
            emitted += 1

    log.info("alerts.check.done", emitted=emitted)
    return emitted
