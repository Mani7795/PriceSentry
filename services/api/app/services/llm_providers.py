"""Unified streaming interface for LLM providers.

Every provider implements:
    async def stream(system: str, messages: list[dict]) -> AsyncIterator[str]
        yields incremental text chunks.

The caller doesn't care which provider is in use.
"""
from __future__ import annotations

import json
from typing import AsyncIterator, Protocol

import httpx

from app.core.logging import get_logger
from app.core.settings import settings

log = get_logger(__name__)


class LLMStream(Protocol):
    async def stream(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]: ...


# ──────────────────────────────────────────────────────────────────────
# Ollama
# ──────────────────────────────────────────────────────────────────────
class OllamaProvider:
    def __init__(self) -> None:
        self.base_url = settings.ollama_base_url
        self.model = settings.ollama_model

    async def stream(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10)) as client:
            async with client.stream("POST", f"{self.base_url}/api/chat", json=payload) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    msg = obj.get("message") or {}
                    chunk = msg.get("content")
                    if chunk:
                        yield chunk
                    if obj.get("done"):
                        return


# ──────────────────────────────────────────────────────────────────────
# Anthropic (direct API)
# ──────────────────────────────────────────────────────────────────────
class AnthropicProvider:
    def __init__(self) -> None:
        self.api_key = settings.anthropic_api_key
        self.model = settings.anthropic_model

    async def stream(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set")
        payload = {
            "model": self.model,
            "max_tokens": 1024,
            "system": system,
            "stream": True,
            "messages": [{"role": m["role"], "content": m["content"]} for m in messages],
        }
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10)) as client:
            async with client.stream(
                "POST", "https://api.anthropic.com/v1/messages", json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data or data == "[DONE]":
                        continue
                    try:
                        evt = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    if evt.get("type") == "content_block_delta":
                        delta = evt.get("delta") or {}
                        if delta.get("type") == "text_delta":
                            yield delta.get("text", "")


# ──────────────────────────────────────────────────────────────────────
# OpenAI
# ──────────────────────────────────────────────────────────────────────
class OpenAIProvider:
    def __init__(self) -> None:
        self.api_key = settings.openai_api_key
        self.model = settings.openai_model

    async def stream(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set")
        payload = {
            "model": self.model,
            "stream": True,
            "messages": [{"role": "system", "content": system}, *messages],
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "content-type": "application/json"}
        async with httpx.AsyncClient(timeout=httpx.Timeout(connect=10, read=300, write=10, pool=10)) as client:
            async with client.stream(
                "POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]" or not data:
                        continue
                    try:
                        evt = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    choices = evt.get("choices") or []
                    if not choices:
                        continue
                    delta = choices[0].get("delta") or {}
                    chunk = delta.get("content")
                    if chunk:
                        yield chunk


# ──────────────────────────────────────────────────────────────────────
# Bedrock (Anthropic models on AWS)
# ──────────────────────────────────────────────────────────────────────
class BedrockProvider:
    def __init__(self) -> None:
        self.model_id = settings.bedrock_model_id
        self.region = settings.aws_region

    async def stream(
        self, system: str, messages: list[dict[str, str]]
    ) -> AsyncIterator[str]:
        # boto3 streaming is sync; run in a thread to keep async surface.
        import asyncio
        import boto3

        def _iter() -> list[str]:
            client = boto3.client("bedrock-runtime", region_name=self.region)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "system": system,
                "messages": [{"role": m["role"], "content": [{"type": "text", "text": m["content"]}]}
                             for m in messages],
            }
            resp = client.invoke_model_with_response_stream(
                modelId=self.model_id, body=json.dumps(body), contentType="application/json"
            )
            chunks: list[str] = []
            for event in resp["body"]:
                if "chunk" not in event:
                    continue
                payload = json.loads(event["chunk"]["bytes"])
                if payload.get("type") == "content_block_delta":
                    delta = payload.get("delta") or {}
                    if delta.get("type") == "text_delta":
                        chunks.append(delta.get("text", ""))
            return chunks

        # Run sync iter in thread; not as nice as true async but functional.
        loop = asyncio.get_running_loop()
        for chunk in await loop.run_in_executor(None, _iter):
            yield chunk


# ──────────────────────────────────────────────────────────────────────
# Factory
# ──────────────────────────────────────────────────────────────────────
def get_provider() -> LLMStream:
    provider = settings.llm_provider.lower()
    if provider == "ollama":
        return OllamaProvider()
    if provider == "anthropic":
        return AnthropicProvider()
    if provider == "openai":
        return OpenAIProvider()
    if provider == "bedrock":
        return BedrockProvider()
    raise ValueError(f"Unknown LLM_PROVIDER={provider!r}")


def current_model_label() -> str:
    p = settings.llm_provider.lower()
    return {
        "ollama": settings.ollama_model,
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "bedrock": settings.bedrock_model_id,
    }.get(p, p)


async def complete(system: str, user: str) -> str:
    """Non-streaming convenience: collect a provider stream into one string.

    Used by endpoints that return a single JSON payload (e.g. product AI
    insights) rather than an SSE stream.
    """
    provider = get_provider()
    parts: list[str] = []
    async for chunk in provider.stream(system, [{"role": "user", "content": user}]):
        parts.append(chunk)
    return "".join(parts).strip()
