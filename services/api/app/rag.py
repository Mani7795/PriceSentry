"""DEPRECATED — moved to app.services.rag_service.

The streaming RAG implementation now lives in app/api/chat.py +
app/services/rag_service.py. This shim is kept only for backwards compat.
Delete after Phase 2.2.
"""
from app.services.rag_service import (  # noqa: F401
    build_user_prompt,
    embed_query,
    format_snippets,
    rerank,
    retrieve,
    system_prompt,
)
