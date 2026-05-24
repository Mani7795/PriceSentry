# Phase 3 Runbook — Public Dashboard + Product Detail

This adds the explore-first SaaS frontend: a public product-intelligence dashboard, product detail pages with price-history charts, real review sentiment, and AI insights. Builds on Phases 1–2; no data loss.

What you'll do: apply new schema → compute real sentiment → ingest pricing → rebuild containers → explore.

---

## 0. Sync the new files to your working repo

(You work in `C:\Drive D\GIt project\PriceSentry`; I write to the OneDrive copy.) In PowerShell:

```powershell
robocopy "C:\Users\manir\OneDrive\Documents\Claude\Projects\Building my portfolio\priceSentry" "C:\Drive D\GIt project\PriceSentry" /E /XD .git node_modules .next __pycache__ .pytest_cache /XF .env
```

---

## 1. Apply the Phase 3 schema

```bash
docker compose cp db/03_phase3_dashboard.sql postgres:/tmp/03.sql
docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/03.sql
```

Expect `Phase 3 dashboard schema initialized successfully.` Verify the new pieces:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "\dt review_aspects ai_query_log"
docker compose exec postgres psql -U pricesentry -d pricesentry -c "\dv v_product_dashboard v_product_competitor_price"
```

---

## 2. Rebuild the scraper image (adds vaderSentiment)

The sentiment pipeline needs the `vaderSentiment` package, which is new in requirements:

```bash
docker compose build scraper
docker compose up -d scraper
```

---

## 3. Compute REAL sentiment over your reviews

This runs an actual sentiment model over your ~9,400 reviews plus aspect-level analysis (packaging, price, quality, smell, ingredients, shipping, taste, value). Fast on CPU — a few minutes.

```bash
docker compose exec scraper python /app/scripts/compute_sentiment.py --batch-size 500
```

Verify:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c \
  "SELECT sentiment_label, COUNT(*) FROM reviews WHERE sentiment_label IS NOT NULL GROUP BY 1;"
docker compose exec postgres psql -U pricesentry -d pricesentry -c \
  "SELECT aspect, COUNT(*) FROM review_aspects GROUP BY 1 ORDER BY 2 DESC;"
```

You should see a positive/neutral/negative breakdown and aspect counts.

---

## 4. Ingest competitor pricing + 90-day history

This populates Amazon/Chewy/Petco/PetSmart prices and 90 days of daily history per product. (Real pricing-ingestion architecture; the 3 non-Amazon retailers use the derivation adapter because live retailer access is ToS-blocked — see the file header and docs/01-dataset-guide.md.)

```bash
docker compose exec scraper python /app/scripts/ingest_pricing.py --history-days 90
```

This can take a few minutes depending on how many products you bootstrapped. Verify:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c \
  "SELECT competitor, COUNT(*) FROM v_product_competitor_price GROUP BY 1;"
```

You should see all four retailers.

---

## 5. Rebuild the API and web containers

The API gained new routers; the web app gained Recharts, Framer Motion, and react-markdown.

```bash
docker compose build api web
docker compose up -d
```

The web rebuild (`npm install` + `next build`) takes a few minutes.

---

## 6. Verify the new API endpoints

```bash
# Catalog (public, no auth)
curl "http://localhost:8000/api/v1/products?sort=reviews&page_size=3" | head -c 600

# Facets
curl "http://localhost:8000/api/v1/products/facets" | head -c 400

# Pick a product_id from the catalog response, then:
PID=<paste-a-product_id>
curl "http://localhost:8000/api/v1/products/$PID" | head -c 600

# AI insight (needs Ollama running)
curl -X POST "http://localhost:8000/api/v1/products/$PID/insights" | head -c 600
```

---

## 7. Explore in the browser

Open **http://localhost:3000** — it now opens directly to the **public dashboard** (no login).

You should see:
- A left nav rail (Dashboard / AI Assistant) with a theme toggle.
- A filters sidebar (search, sort, sentiment, brand, category).
- KPI cards.
- A responsive grid of product cards, each showing brand, rating, review count, sentiment badge, and competitor price rows with cheapest-seller highlight + price-diff arrows.

Click any product → the **detail page**:
- Overview + competitor pricing widget.
- 90-day multi-retailer price-history chart (Recharts).
- "AI Insights" card — click "Generate insights" for a RAG-grounded summary with citations (requires Ollama).
- Review intelligence: positive/negative split, "customers love / dislike" themes, aspect breakdown bars.

Click "AI Assistant" in the nav → if not logged in, you're routed to `/login` (only the chat requires auth, exactly as specified).

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Dashboard shows "No products match" | You haven't run steps 3–4, or no products have reviews. Re-run sentiment + pricing. Also confirm bootstrap loaded products (Phase 1). |
| Price chart empty | Step 4 (`ingest_pricing.py`) didn't run or found no products. Check `v_product_competitor_price` has rows. |
| Sentiment panel all neutral | Step 3 didn't run. Check `reviews.sentiment_label` is populated. |
| AI insights button errors | Ollama isn't running, or `LLM_PROVIDER` is misconfigured. Same setup as chat. |
| Web build fails on `recharts`/`framer-motion` | `docker compose build web --no-cache` |
| 404 on `/products/...` API | API didn't rebuild with the new router. `docker compose build api && docker compose up -d api` |

---

## What's next (Phase 3.2 / 3.3)

- Grid/table toggle, price-range slider, real-time refresh simulation
- Markdown + syntax highlighting + suggested prompts + retrieval-debug panel in the chat
- Admin dashboard + analytics page (uses `ai_query_log`)
- Saved chats / saved reports
- AWS deploy (ECS + RDS + S3 + CloudFront) + Vercel frontend option + CI/CD
