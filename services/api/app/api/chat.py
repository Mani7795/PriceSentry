"""Streaming chat endpoint (Server-Sent Events).

SSE event protocol:
  event: start         data: {"conversation_id":"...", "message_id":"..."}
  event: token         data: {"text":"..."}                  (repeated)
  event: citations     data: {"citations":[ ... ]}           (once, before done)
  event: done          data: {"message_id":"...", "model":"...", "latency_ms":...}
  event: error         data: {"detail":"..."}                (on failure)
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_user
from app.core.logging import get_logger
from app.core.settings import settings
from app.db.models import User
from app.db.session import AsyncSessionLocal, get_db
from app.schemas.chat import ChatStreamRequest
from app.services.chat_service import ChatService
from app.services.llm_providers import current_model_label, get_provider
from app.services.rag_service import (
    build_user_prompt,
    embed_query,
    format_snippets,
    rerank,
    retrieve,
    system_prompt,
)

router = APIRouter(prefix="/chat", tags=["chat"])
log = get_logger(__name__)


def _sse(event: str, data: dict) -> dict:
    return {"event": event, "data": json.dumps(data)}


async def _stream(req: Request, user: User, body: ChatStreamRequest) -> AsyncIterator[dict]:
    """Generator: yields SSE events for one chat turn.

    Opens its own DB session so we can keep streaming after FastAPI's request-
    scoped session would normally close. Persists the final message in finally.
    """
    started = time.monotonic()
    full_answer_parts: list[str] = []
    citations_payload: list[dict] = []
    assistant_msg_id: uuid.UUID | None = None
    model_label = current_model_label()

    async with AsyncSessionLocal() as db:
        chat = ChatService(db)

        # ── 1. resolve or create conversation ──────────────────────
        if body.conversation_id:
            conv = await chat.get_conversation(user.user_id, body.conversation_id)
            if not conv:
                yield _sse("error", {"detail": "conversation not found"})
                return
        else:
            conv = await chat.create_conversation(
                user.user_id, title=None, brand_filter=body.brand_filter,
            )

        # ── 2. persist USER message first ──────────────────────────
        user_msg = await chat.append_message(conv, role="user", content=body.message)

        # ── 3. retrieve + rerank ──────────────────────────────────
        try:
            q_vec = await asyncio.to_thread(embed_query, body.message)
            rows = await retrieve(
                db, query_vec=q_vec,
                brand=body.brand_filter or conv.brand_filter,
                top_k=settings.rag_top_k,
            )
        except Exception as e:
            log.error("chat.retrieval_failed", error=str(e))
            yield _sse("error", {"detail": f"retrieval failed: {e}"})
            return

        top_rows = rerank(rows, settings.rag_rerank_top_n)
        if not top_rows:
            yield _sse("token", {"text": "I don't have enough review evidence to answer that."})
            yield _sse("done", {"model": model_label, "latency_ms": int((time.monotonic() - started) * 1000)})
            return

        snippets = format_snippets(top_rows)
        history = await chat.history_for_prompt(conv.conversation_id, window=settings.rag_history_window)
        # Drop the just-inserted user message from history (it's about to be the question)
        history = [h for h in history if not (h["role"] == "user" and h["content"] == body.message)]

        user_prompt = build_user_prompt(history, body.message, snippets)

        # ── 4. announce start ─────────────────────────────────────
        yield _sse("start", {"conversation_id": str(conv.conversation_id),
                             "user_message_id": str(user_msg.message_id)})

        citations_payload = [
            {
                "review_id": r["review_id"],
                "brand": r.get("brand"),
                "rating": float(r["rating"]) if r.get("rating") is not None else None,
                "similarity": round(float(r["similarity"]), 3),
                "snippet": (r.get("review_text") or "")[:300],
            }
            for r in top_rows
        ]
        yield _sse("citations", {"citations": citations_payload})

        # ── 5. stream tokens from LLM ─────────────────────────────
        provider = get_provider()
        try:
            async for chunk in provider.stream(system_prompt(), [{"role": "user", "content": user_prompt}]):
                if await req.is_disconnected():
                    log.info("chat.client_disconnected")
                    break
                full_answer_parts.append(chunk)
                yield _sse("token", {"text": chunk})
        except Exception as e:
            log.error("chat.llm_failed", error=str(e))
            yield _sse("error", {"detail": f"llm error: {e}"})

        # ── 6. persist assistant message ─────────────────────────
        answer = "".join(full_answer_parts).strip() or "(no response generated)"
        try:
            assistant_msg = await chat.append_message(
                conv, role="assistant", content=answer, model=model_label,
                citations=citations_payload,
                latency_ms=int((time.monotonic() - started) * 1000),
            )
            assistant_msg_id = assistant_msg.message_id
        except Exception as e:
            log.error("chat.persist_failed", error=str(e))

        yield _sse("done", {
            "conversation_id": str(conv.conversation_id),
            "message_id": str(assistant_msg_id) if assistant_msg_id else None,
            "model": model_label,
            "latency_ms": int((time.monotonic() - started) * 1000),
        })


@router.post("/stream")
async def chat_stream(
    body: ChatStreamRequest,
    request: Request,
    user: User = Depends(get_current_user),
    _db: AsyncSession = Depends(get_db),  # ensures DB is reachable; we open our own in _stream
) -> EventSourceResponse:
    if not body.message.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "empty message")
    return EventSourceResponse(_stream(request, user, body), ping=15)
