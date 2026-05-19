"""Chat / conversation schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    brand_filter: str | None = Field(default=None, max_length=100)


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    conversation_id: uuid.UUID
    title: str
    brand_filter: str | None = None
    created_at: datetime
    updated_at: datetime


class CitationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    rank: int
    similarity: float | None = None
    snippet: str | None = None


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    message_id: uuid.UUID
    role: str
    content: str
    model: str | None = None
    created_at: datetime
    citations: list[CitationOut] = []


class ChatStreamRequest(BaseModel):
    """Body of POST /api/v1/chat/stream."""

    conversation_id: uuid.UUID | None = None      # None => create new
    message: str = Field(min_length=1, max_length=4000)
    brand_filter: str | None = Field(default=None, max_length=100)
