"""Scraper entry point.

Usage:
    python -m scraper.main --once             # one-shot run against $SCRAPE_TARGET
    python -m scraper.main --once --target chewy
    python -m scraper.main --loop --interval 3600   # naive loop (Phase 1 only)
"""
from __future__ import annotations

import argparse
import sys
import time

from scraper.config import settings
from scraper.logging_setup import configure_logging, get_logger
from scraper.pipeline import run_target
from scraper.targets import get_target

log = get_logger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PriceSentry scraper")
    parser.add_argument("--target", default=settings.scrape_target)
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--loop", action="store_true", help="Run forever with --interval seconds between runs")
    parser.add_argument("--interval", type=int, default=3600)
    return parser.parse_args()


def main() -> int:
    configure_logging()
    args = parse_args()
    if not (args.once or args.loop):
        # default to once
        args.once = True

    target = get_target(args.target)
    log.info("scraper.start", target=target.name)

    while True:
        try:
            run_target(target)
        except Exception as e:
            log.error("scraper.run_failed", error=str(e))
        if args.once:
            break
        log.info("scraper.sleep", seconds=args.interval)
        time.sleep(args.interval)

    return 0


if __name__ == "__main__":
    sys.exit(main())
