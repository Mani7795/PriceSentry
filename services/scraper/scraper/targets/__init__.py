"""Pluggable scrape targets.

Each target implements the `BaseTarget` interface:
    - name: short string identifier
    - iter_pages() -> Iterable[dict]
    - parse(payload) -> ScrapeEvent | None

To add a new competitor: drop a new module here, register it in `REGISTRY`.
"""
from __future__ import annotations

from typing import Callable

from scraper.targets.base import BaseTarget
from scraper.targets.demo import DemoTarget


# Import the Chewy target lazily so its (optional) Playwright deps aren't
# required for callers who only run the demo target.
def _build_chewy() -> BaseTarget:
    from scraper.targets.chewy import ChewyTarget
    return ChewyTarget()


REGISTRY: dict[str, Callable[[], BaseTarget]] = {
    "demo": lambda: DemoTarget(),
    "chewy": _build_chewy,
}


def get_target(name: str) -> BaseTarget:
    if name not in REGISTRY:
        raise ValueError(
            f"Unknown scrape target {name!r}. Known: {sorted(REGISTRY)}"
        )
    return REGISTRY[name]()
