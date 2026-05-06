"""FastAPI app — PriceSentry RAG endpoint."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.deps import get_engine
from app.rag import answer_question

app = FastAPI(
    title="PriceSentry API",
    version="0.1.0",
    description="Phase 1 — RAG over customer reviews for pet-supply competitive intelligence.",
)


class AskRequest(BaseModel):
    question: str = Field(..., min_length=3, max_length=500)
    brand: str | None = Field(default=None, description="Optional brand filter (case-insensitive)")


class Citation(BaseModel):
    review_id: str
    brand: str | None = None
    rating: float | None = None
    similarity: float
    snippet: str


class AskResponse(BaseModel):
    answer: str
    retrieved: int
    citations: list[Citation]


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness + DB ping."""
    eng = get_engine()
    try:
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"db_unreachable: {e}")


@app.get("/stats")
def stats() -> dict[str, int]:
    """Quick row counts so you can see the system is alive."""
    eng = get_engine()
    out: dict[str, int] = {}
    with eng.connect() as conn:
        for table in ("products", "competitor_skus", "price_observations", "reviews", "review_embeddings"):
            out[table] = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar_one()
    return out


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest) -> AskResponse:
    result = answer_question(req.question, brand=req.brand)
    return AskResponse(
        answer=result["answer"],
        retrieved=result["retrieved"],
        citations=[Citation(**c) for c in result["citations"]],
    )
