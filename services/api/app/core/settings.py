"""Centralized application settings.

All env-driven configuration goes through this single object. Importing it
gives type-checked, validated settings everywhere — never read os.environ
directly in app code.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    # ─── App ───────────────────────────────────────────────────────
    app_name: str = "PriceSentry"
    app_env: Literal["dev", "staging", "prod"] = "dev"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    # ─── CORS ──────────────────────────────────────────────────────
    # Comma-separated list in env: CORS_ORIGINS=http://localhost:3000,https://app.example.com
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    # ─── DB ────────────────────────────────────────────────────────
    database_url: str = (
        "postgresql+psycopg://pricesentry:pricesentry_dev@postgres:5432/pricesentry"
    )

    # ─── Auth / JWT ────────────────────────────────────────────────
    jwt_secret: str = Field(default="change-me-in-production-please")
    jwt_algorithm: str = "HS256"
    access_token_ttl_minutes: int = 15
    refresh_token_ttl_days: int = 30

    # ─── LLM provider ──────────────────────────────────────────────
    llm_provider: Literal["ollama", "anthropic", "bedrock", "openai"] = "ollama"

    anthropic_api_key: str | None = None
    anthropic_model: str = "claude-haiku-4-5-20251001"

    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"

    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"

    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.2:3b"

    # ─── Embeddings ────────────────────────────────────────────────
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # ─── RAG ───────────────────────────────────────────────────────
    rag_top_k: int = 10
    rag_rerank_top_n: int = 3
    rag_history_window: int = 6   # last N messages from convo included in prompt

    @field_validator("jwt_secret")
    @classmethod
    def warn_on_default_secret(cls, v: str) -> str:
        if v == "change-me-in-production-please":
            import warnings
            warnings.warn(
                "Using default JWT_SECRET. Set a strong random value in production.",
                stacklevel=2,
            )
        return v


settings = Settings()
