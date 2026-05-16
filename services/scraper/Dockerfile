FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONPATH=/app

WORKDIR /app

# System deps for Playwright + psycopg + sentence-transformers
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        ca-certificates \
        curl \
        git \
        libpq-dev \
        wget \
    && rm -rf /var/lib/apt/lists/*

# Python deps
COPY requirements.txt /app/requirements.txt
RUN pip install -r /app/requirements.txt

# Playwright Chromium is only needed for live scraping (Phase 2+).
# Skip by default; enable by setting INSTALL_PLAYWRIGHT_BROWSERS=1 at build time:
#   docker compose build --build-arg INSTALL_PLAYWRIGHT_BROWSERS=1
ARG INSTALL_PLAYWRIGHT_BROWSERS=0
RUN if [ "$INSTALL_PLAYWRIGHT_BROWSERS" = "1" ]; then \
        playwright install --with-deps chromium ; \
    else \
        echo "Skipping Playwright browser install (set INSTALL_PLAYWRIGHT_BROWSERS=1 to enable)" ; \
    fi

# Source
# Note: only files inside this Dockerfile's build context (./services/scraper)
# can be COPY-ed. `tests/` and `scripts/` live at the repo root and are
# mounted in via docker-compose volumes at runtime.
COPY scraper /app/scraper

# Runtime user (don't run as root)
RUN useradd -ms /bin/bash app && chown -R app:app /app
USER app
