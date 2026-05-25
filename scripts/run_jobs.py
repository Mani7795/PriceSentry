"""Run the background jobs synchronously — for testing without waiting for beat.

Usage (inside the worker or scraper container):
    python /app/scripts/run_jobs.py nightly        # full pipeline
    python /app/scripts/run_jobs.py prices         # just refresh prices
    python /app/scripts/run_jobs.py deals          # just recompute deal stats
    python /app/scripts/run_jobs.py alerts         # just check alerts
"""
from __future__ import annotations

import sys

sys.path.insert(0, "/app")

from scraper import alerts, pricing  # noqa: E402
from scraper.logging_setup import configure_logging, get_logger  # noqa: E402

log = get_logger("run_jobs")


def main() -> int:
    configure_logging()
    cmd = sys.argv[1] if len(sys.argv) > 1 else "nightly"

    if cmd in ("nightly", "all"):
        priced = pricing.refresh_current_prices()
        deals = pricing.recompute_deal_stats()
        fired = alerts.check_price_alerts()
        log.info("run_jobs.nightly.done", priced=priced, deals=deals, alerts=fired)
    elif cmd == "prices":
        pricing.refresh_current_prices()
    elif cmd == "deals":
        pricing.recompute_deal_stats()
    elif cmd == "alerts":
        alerts.check_price_alerts()
    else:
        log.error("run_jobs.unknown_command", cmd=cmd)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
