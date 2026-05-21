"""Conversation + message persistence."""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.settings import settings
from app.db.models import Conversation, Message, MessageCitation


class ChatService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_conversations(self, user_id: uuid.UUID) -> list[Conversation]:
        result = await self.db.execute(
            select(Conversation)
            .where(Conversation.user_id == user_id)
            .order_by(desc(Conversation.updated_at))
        )
        return list(result.scalars().all())

    async def get_conversation(self, user_id: uuid.UUID, conv_id: uuid.UUID) -> Conversation | None:
        return await self.db.scalar(
            select(Conversation).where(
                Conversation.conversation_id == conv_id,
                Conversation.user_id == user_id,
            )
        )

    async def create_conversation(
        self, user_id: uuid.UUID, *, title: str | None, brand_filter: str | None
    ) -> Conversation:
        conv = Conversation(
            user_id=user_id,
            title=title or "New conversation",
            brand_filter=brand_filter,
        )
        self.db.add(conv)
        await self.db.commit()
        await self.db.refresh(conv)
        return conv

    async def list_messages(self, conv_id: uuid.UUID) -> list[Message]:
        # Eager-load citations: async SQLAlchemy cannot lazy-load relationships
        # implicitly, so we must fetch them up front or Pydantic serialization
        # triggers a MissingGreenlet error.
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .options(selectinload(Message.citations))
            .order_by(Message.created_at)
        )
        return list(result.scalars().all())

    async def history_for_prompt(self, conv_id: uuid.UUID, window: int | None = None) -> list[dict[str, str]]:
        """Last N messages, oldest-first, for inclusion in the LLM prompt."""
        window = window or settings.rag_history_window
        result = await self.db.execute(
            select(Message)
            .where(Message.conversation_id == conv_id)
            .order_by(desc(Message.created_at))
            .limit(window)
        )
        msgs = list(reversed(result.scalars().all()))
        return [{"role": m.role, "content": m.content} for m in msgs]

    async def append_message(
        self,
        conv: Conversation,
        *,
        role: str,
        content: str,
        model: str | None = None,
        citations: list[dict[str, Any]] | None = None,
        latency_ms: int | None = None,
    ) -> Message:
        msg = Message(
            conversation_id=conv.conversation_id,
            role=role,
            content=content,
            model=model,
            latency_ms=latency_ms,
        )
        self.db.add(msg)
        await self.db.flush()

        if citations:
            for i, c in enumerate(citations):
                self.db.add(
                    MessageCitation(
                        message_id=msg.message_id,
                        review_id=uuid.UUID(c["review_id"]),
                        rank=i + 1,
                        similarity=c.get("similarity"),
                        snippet=(c.get("snippet") or "")[:500],
                    )
                )

        # Auto-title from first user message if still default
        if role == "user" and (conv.title or "").startswith("New conversation"):
            conv.title = content[:60] + ("…" if len(content) > 60 else "")

        await self.db.commit()
        await self.db.refresh(msg)
        return msg
