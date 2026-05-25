"""Centralized config (env-backed)."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # DB
    database_url: str = (
        "postgresql+psycopg://pricesentry:pricesentry_dev@postgres:5432/pricesentry"
    )

    # Scraper
    scrape_target: str = "demo"
    chewy_live: bool = False
    scrape_request_delay_seconds: float = 8.0
    scrape_user_agent: str = (
        "PriceSentry-portfolio (+https://github.com/<you>; <you>@example.com)"
    )

    # Embeddings
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_dim: int = 384
    embedding_batch_size: int = 64

    # Celery / background jobs
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # Logging
    log_level: str = "INFO"


settings = Settings()
