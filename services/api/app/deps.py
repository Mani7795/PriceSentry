"""Lazily-initialized singletons (DB engine, embedding model, LLM client)."""
from __future__ import annotations

from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.config import settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        future=True,
    )


@lru_cache(maxsize=1)
def get_embedding_model():
    """Returns a SentenceTransformer instance. Loaded once per process."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(settings.embedding_model)


@lru_cache(maxsize=1)
def get_llm_client():
    """Returns a callable: fn(system_prompt, user_prompt) -> str."""
    provider = settings.llm_provider.lower()

    if provider == "anthropic":
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)

        def _call(system: str, user: str) -> str:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=1024,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            # Concatenate all text blocks
            return "".join(
                block.text for block in resp.content if getattr(block, "type", None) == "text"
            )

        return _call

    if provider == "bedrock":
        import boto3
        import json

        client = boto3.client("bedrock-runtime", region_name=settings.aws_region)

        def _call(system: str, user: str) -> str:
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
            }
            resp = client.invoke_model(
                modelId=settings.bedrock_model_id,
                body=json.dumps(body),
                contentType="application/json",
            )
            payload = json.loads(resp["body"].read())
            return "".join(b["text"] for b in payload.get("content", []) if b.get("type") == "text")

        return _call

    if provider == "ollama":
        import httpx

        def _call(system: str, user: str) -> str:
            r = httpx.post(
                f"{settings.ollama_base_url}/api/chat",
                json={
                    "model": settings.ollama_model,
                    "stream": False,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                },
                timeout=60,
            )
            r.raise_for_status()
            return r.json()["message"]["content"]

        return _call

    raise ValueError(f"Unsupported LLM_PROVIDER={provider!r}")
