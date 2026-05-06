"""Abstract base class for scrape targets."""
from __future__ import annotations

import abc
from typing import Iterable

from scraper.models import ScrapeEvent


class BaseTarget(abc.ABC):
    """All competitors implement this."""

    name: str  # set by subclass

    @abc.abstractmethod
    def iter_pages(self) -> Iterable[dict]:
        """Yield raw payloads (one per page). Each gets bronze-stored."""
        raise NotImplementedError

    @abc.abstractmethod
    def parse(self, payload: dict) -> ScrapeEvent | None:
        """Convert a raw payload into a validated ScrapeEvent.

        Return None if the payload should be skipped (e.g. error page).
        """
        raise NotImplementedError
