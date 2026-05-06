"""API config."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = (
        "postgresql+psycopg://pricesentry:pricesentry_dev@postgres:5432/pricesentry"
    )

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384

    # RAG
    rag_top_k: int = 20
    rag_rerank_top_n: int = 5

    # LLM
    llm_provider: str = "anthropic"  # anthropic | bedrock | ollama
    anthropic_api_key: str | None = None
    aws_region: str = "us-east-1"
    bedrock_model_id: str = "anthropic.claude-haiku-4-5-20251001-v1:0"
    ollama_base_url: str = "http://host.docker.internal:11434"
    ollama_model: str = "llama3.1:8b"

    log_level: str = "INFO"


settings = Settings()
