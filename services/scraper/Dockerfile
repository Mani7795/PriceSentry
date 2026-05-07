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

# Playwright browsers (chromium only — keep image small)
RUN playwright install --with-deps chromium

# Source
COPY scraper /app/scraper

# Runtime user (don't run as root)
RUN useradd -ms /bin/bash app && chown -R app:app /app
USER app
