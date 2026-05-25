"""Watchlist routes (require auth).

A user can watch a product and optionally set a target price. The nightly
job (Celery) checks these and emits alerts.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


class WatchCreate(BaseModel):
    product_id: uuid.UUID
    target_price_cents: int | None = Field(default=None, ge=0)


class WatchItem(BaseModel):
    watch_id: uuid.UUID
    product_id: uuid.UUID
    title: str | None = None
    target_price_cents: int | None = None
    current_cents: int | None = None
    deal_label: str | None = None
    created_at: datetime


@router.get("", response_model=list[WatchItem])
async def list_watchlist(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WatchItem]:
    rows = (await db.execute(
        text("""
            SELECT w.watch_id, w.product_id, p.title, w.target_price_cents,
                   ds.current_cents, ds.deal_label, w.created_at
              FROM watchlists w
              JOIN products p ON p.product_id = w.product_id
              LEFT JOIN deal_stats ds ON ds.product_id = w.product_id
             WHERE w.user_id = :uid
             ORDER BY w.created_at DESC
        """),
        {"uid": str(user.user_id)},
    )).mappings().all()
    return [WatchItem.model_validate(dict(r)) for r in rows]


@router.post("", response_model=WatchItem, status_code=status.HTTP_201_CREATED)
async def add_watch(
    body: WatchCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WatchItem:
    exists = await db.scalar(
        text("SELECT 1 FROM products WHERE product_id = :pid"), {"pid": str(body.product_id)}
    )
    if not exists:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "product not found")

    await db.execute(
        text("""
            INSERT INTO watchlists (user_id, product_id, target_price_cents)
            VALUES (:uid, :pid, :tgt)
            ON CONFLICT (user_id, product_id)
            DO UPDATE SET target_price_cents = EXCLUDED.target_price_cents
        """),
        {"uid": str(user.user_id), "pid": str(body.product_id), "tgt": body.target_price_cents},
    )
    await db.commit()

    row = (await db.execute(
        text("""
            SELECT w.watch_id, w.product_id, p.title, w.target_price_cents,
                   ds.current_cents, ds.deal_label, w.created_at
              FROM watchlists w
              JOIN products p ON p.product_id = w.product_id
              LEFT JOIN deal_stats ds ON ds.product_id = w.product_id
             WHERE w.user_id = :uid AND w.product_id = :pid
        """),
        {"uid": str(user.user_id), "pid": str(body.product_id)},
    )).mappings().first()
    return WatchItem.model_validate(dict(row))


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_watch(
    product_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await db.execute(
        text("DELETE FROM watchlists WHERE user_id = :uid AND product_id = :pid"),
        {"uid": str(user.user_id), "pid": str(product_id)},
    )
    await db.commit()
    return None
