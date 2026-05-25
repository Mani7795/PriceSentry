# Phase 4 Runbook — Scheduled Jobs, Deal Indicator, Price Alerts

Adds: Redis + Celery worker + Celery Beat, a nightly pipeline (refresh prices → recompute deal stats → check alerts), a good-deal indicator (90-day price percentile), watchlists, and console-logged price-drop alerts.

Builds on Phases 1–3; no data loss.

---

## 0. Sync new files to your working repo

```powershell
robocopy "C:\Users\manir\OneDrive\Documents\Claude\Projects\Building my portfolio\priceSentry" "C:\Drive D\GIt project\PriceSentry" /E /XD .git node_modules .next __pycache__ .pytest_cache /XF .env
```

---

## 1. Apply the Phase 4 schema

```bash
docker compose cp db/04_phase4_alerts.sql postgres:/tmp/04.sql
docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/04.sql
```

Expect `Phase 4 alerts/deals schema initialized successfully.` Verify:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "\dt watchlists deal_stats alert_events"
```

---

## 2. Rebuild the scraper image (adds celery + redis) and bring up the new services

The worker and beat reuse the scraper image, so it must be rebuilt with the new deps:

```bash
docker compose build scraper
docker compose up -d            # starts redis, worker, beat alongside everything else
```

Confirm the new containers are running:

```bash
docker compose ps
# Expect: postgres, redis, scraper, worker, beat, api, web — all running
```

Check the worker connected to Redis and registered tasks:

```bash
docker compose logs worker --tail 30
# Look for "celery@... ready." and the task list including scraper.tasks.nightly_refresh
```

---

## 3. Run the pipeline once (don't wait for 2 AM)

Beat will run it nightly at 02:00 UTC, but trigger it now to populate deal stats:

```bash
# Synchronous run inside the worker container (easiest to watch)
docker compose exec worker python /app/scripts/run_jobs.py nightly
```

You'll see logs for each stage:

```json
{"event": "pricing.refresh_current_prices.done", "rows": ...}
{"event": "pricing.recompute_deal_stats.done", "products": ...}
{"event": "alerts.check.done", "emitted": 0}
{"event": "run_jobs.nightly.done", "priced": ..., "deals": ..., "alerts": 0}
```

Or fire it through Celery (exercises the real broker path):

```bash
docker compose exec worker python -c "from scraper.tasks import nightly_refresh; print(nightly_refresh.delay().id)"
docker compose logs worker -f     # watch it execute
```

Verify deal stats landed:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "SELECT deal_label, COUNT(*) FROM deal_stats GROUP BY 1;"
```

You should see a distribution across great / good / typical / high.

---

## 4. Rebuild the API + web (deal fields + watchlist UI)

```bash
docker compose build api web
docker compose up -d
```

---

## 5. See it in the browser

Open **http://localhost:3000/dashboard**:
- Product cards now show a **deal badge** (Great deal / Good price / etc.).
- New filters: **Deals** (Great/Good) and a **Best deals** sort.

Open any product → detail page:
- Deal badge + a **Watch price** button.
- Click "Watch price" (logged out → routes to login; logged in → set an optional target price).

## 6. Test the alert loop

```bash
# 1. Log in / register in the browser, watch a product with a HIGH target price
#    (so the current price is already below it — guarantees a match).
# 2. Re-run the pipeline:
docker compose exec worker python /app/scripts/run_jobs.py alerts
# 3. Watch the worker/console log — you'll see the alert:
docker compose logs worker --tail 20
```

You should see an `alert.emit` log line with the recipient email, product, and price. The alert is also persisted:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "SELECT kind, message FROM alert_events ORDER BY created_at DESC LIMIT 5;"
```

(Email is console-only for now; swap in Resend/SES later by reading undelivered `alert_events` rows — the logic doesn't change.)

---

## How the schedule works

- **Celery Beat** (`beat` container) enqueues `nightly_refresh` daily at 02:00 UTC.
- **Celery Worker** (`worker` container) executes it: append today's prices → recompute deal stats → check alerts.
- **Redis** is the broker + result backend.
- To change the cadence, edit `beat_schedule` in `services/scraper/scraper/celery_app.py` (e.g., `crontab(minute="*/10")` to run every 10 min while demoing), then `docker compose restart beat`.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `worker`/`beat` crash-loop | Scraper image not rebuilt with celery. `docker compose build scraper && docker compose up -d worker beat` |
| Worker can't reach broker | Redis not up/healthy. `docker compose ps redis`; check `CELERY_BROKER_URL=redis://redis:6379/0` |
| Deal badges don't appear | Pipeline hasn't run, or api/web not rebuilt. Run step 3, then `docker compose build api web && docker compose up -d` |
| `deal_stats` empty after run | No price history exists. Make sure Phase 3 pricing ran (`v_product_competitor_price` has rows) |
| Alerts never fire | No watchlist rows, or target above current. Watch a product with a high target and re-run `run_jobs.py alerts` |

---

## What this demonstrates (portfolio value)

- **Distributed task queue** (Celery) with a **broker** (Redis) and a **scheduler** (Beat) — classic production DE infrastructure.
- **Idempotent, set-based SQL jobs** (the price refresh is a single `INSERT...SELECT`; deal stats is one CTE-driven upsert).
- **A real analytics feature** (90-day price percentile) computed on a schedule and surfaced in the product.
- **An event-driven alert pipeline** with dedup and a persistence layer ready for real email delivery.

## Next (Phase 4.2+)
- Real email via Resend/SES (read undelivered `alert_events`)
- Redis caching layer for the catalog/dashboard queries
- A "My Watchlist" page + a "Deals" page
- Flower (Celery monitoring UI) for the ops story
