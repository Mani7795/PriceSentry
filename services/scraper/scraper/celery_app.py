"""Celery application + beat schedule.

Run:
    worker:  celery -A scraper.celery_app worker --loglevel=info
    beat:    celery -A scraper.celery_app beat   --loglevel=info
"""
from __future__ import annotations

from celery import Celery
from celery.schedules import crontab

from scraper.config import settings

app = Celery(
    "pricesentry",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["scraper.tasks"],
)

app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    result_expires=3600,
)

# Beat schedule: the "overnight" pipeline.
# Runs daily at 02:00 UTC. For a live demo you can trigger it manually
# (see scripts/run_jobs.py) without waiting for the schedule.
app.conf.beat_schedule = {
    "nightly-price-refresh": {
        "task": "scraper.tasks.nightly_refresh",
        "schedule": crontab(hour=2, minute=0),
    },
}
