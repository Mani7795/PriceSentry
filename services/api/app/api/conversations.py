"""Conversation routes."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.models import User
from app.db.session import get_db
from app.schemas.chat import ConversationCreate, ConversationOut, MessageOut
from app.services.chat_service import ChatService

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[ConversationOut]:
    convs = await ChatService(db).list_conversations(user.user_id)
    return [ConversationOut.model_validate(c) for c in convs]


@router.post("", response_model=ConversationOut, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    body: ConversationCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConversationOut:
    conv = await ChatService(db).create_conversation(
        user.user_id, title=body.title, brand_filter=body.brand_filter
    )
    return ConversationOut.model_validate(conv)


@router.get("/{conversation_id}/messages", response_model=list[MessageOut])
async def get_messages(
    conversation_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[MessageOut]:
    svc = ChatService(db)
    conv = await svc.get_conversation(user.user_id, conversation_id)
    if not conv:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "conversation not found")
    messages = await svc.list_messages(conversation_id)
    return [MessageOut.model_validate(m) for m in messages]
