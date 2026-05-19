"""Health + readiness endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db

router = APIRouter(tags=["health"])


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Liveness — process is up."""
    return {"status": "ok"}


@router.get("/readyz")
async def readyz(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    """Readiness — process is up AND can serve traffic."""
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"db_unreachable: {e}")
    return {"status": "ready"}


@router.get("/api/v1/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict[str, int]:
    """Quick row counts for the dashboard."""
    tables = ("products", "competitor_skus", "price_observations", "reviews",
              "review_embeddings", "users", "conversations", "messages")
    out: dict[str, int] = {}
    for table in tables:
        try:
            out[table] = int(await db.scalar(text(f"SELECT COUNT(*) FROM {table}")) or 0)
        except Exception:
            out[table] = -1
    return out
