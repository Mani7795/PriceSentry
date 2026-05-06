# Dataset Acquisition Guide — Pet Supplies

The single biggest beginner trap in DE portfolio projects is *"I'll just scrape the data live"* and then spending three weeks fighting Cloudflare bots, Captchas, and IP bans. **Don't do that.**

The right pattern is:

1. **Bootstrap with a real public dataset.** It gives you ~10M rows of legitimately-licensed text, prices, and metadata. Your pipeline, sentiment model, RAG, and dashboards are all fully functional from day 1.
2. **Layer in live scraping later** as a *demonstration* of the streaming pipeline — limited scope, well-throttled, against safer targets.
3. **Always have a reproducible "load from public source" path** so a recruiter can `make bootstrap` and get a working demo in 10 minutes.

This doc covers both paths.

---

## A. Primary bootstrap dataset (do this first)

### Amazon Reviews 2023 — Pet Supplies subset

- **Source:** McAuley Lab @ UCSD, hosted on Hugging Face Datasets.
- **License:** Free for research and personal/portfolio use.
- **URL:** <https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023>
- **Size (Pet Supplies):** ~6.5M reviews, ~500K product metadata records.
- **What's in it:**
  - `raw_review_Pet_Supplies` — review text, rating, timestamp, user_id, parent_asin, helpful_vote, verified_purchase.
  - `raw_meta_Pet_Supplies` — product title, brand, categories, price (when present), description, features, image URLs, average_rating, rating_number.
- **Why this is gold:** the metadata gives you **prices** (so you can simulate price observations) and the reviews give you **sentiment + RAG** material — both of the data flavors you need.

### One-command load (we'll write the script in `scripts/bootstrap_amazon_reviews.py`)

```bash
make bootstrap-reviews
```

What that script does:
1. `pip install datasets huggingface_hub` (lazy import, only if needed).
2. Streams `raw_meta_Pet_Supplies` → upserts into `products` and `competitor_skus` (competitor='amazon').
3. Streams `raw_review_Pet_Supplies` → upserts into `reviews`.
4. For each metadata row with a `price`, inserts a synthetic **price_observation** at the metadata's `last_updated` time. (You can layer real time-series later when you scrape live.)
5. Logs row counts and writes a checkpoint file so re-running is idempotent.

### Suggested load sizes for Phase 1

You don't need all 6.5M reviews. Start small:

| Phase | Target rows | Why |
|---|---|---|
| 1 | 50,000 reviews, ~10K products | Fits easily in a free RDS t3.micro (20 GB). Trains/evals run in minutes. |
| 2 | 500,000 reviews | Stresses your indexes, exposes batching issues. |
| 3 | All 6.5M | The big-data demo. Run once in S3+Athena to brag about it. |

The bootstrap script accepts a `--limit` flag — start with `--limit 50000` and crank it up.

---

## B. Complementary public datasets

### 1. PetFinder.my Adoption Dataset (Kaggle)
- **URL:** <https://www.kaggle.com/datasets/c/petfinder-adoption-prediction>
- **Use:** dim_pet attributes (breed, age, color) for richer joins. Useful for the matching layer when you correlate reviews mentioning breeds.

### 2. Reddit pet-subreddit comments (Pushshift archives)
- **Sources:** `r/dogs`, `r/cats`, `r/aquariums`, `r/PetFood`, `r/DogFood`.
- **Pushshift:** the 2005–2023 dump is on Academic Torrents and the Hugging Face mirror at <https://huggingface.co/datasets/HuggingFaceH4/reddit_archive> (filtered subsets).
- **Use:** off-site sentiment — *"what does Reddit say about Brand X?"* is a killer feature.
- **Note:** Reddit changed terms in 2023. Use existing archive snapshots; do not re-scrape live without API.

### 3. USDA / FDA pet food recall datasets (FDA OpenFDA API)
- **URL:** <https://open.fda.gov/apis/animalandveterinary/event/>
- **Use:** join recall events to brand mentions in reviews → "Is sentiment dropping because of a recall?" angle.

### 4. Open Food Facts (pet food subset)
- **URL:** <https://world.openfoodfacts.org/data> — has pet products with structured nutrition data.
- **Use:** standardized product attributes for entity resolution.

### 5. Synthetic price drift generator (ours)
- For Phase 1, write a tiny Python utility that takes the bootstrap product price and generates a 90-day random walk of `price_observations` per SKU (Brownian motion with occasional discontinuous drops to simulate sales). Gives you time-series to demo before you have live scraping.

---

## C. Live scraping path (Phase 2/3, optional, ethics-first)

### What you can scrape and how

| Target | Robots/ToS | Recommended approach |
|---|---|---|
| **Chewy.com** | Disallows most bots; product pages disallowed in robots.txt. | Build the parser as **structural reference** and **don't run it at scale**. Fine for occasional manual fetches for demo; not fine for continuous scraping. |
| **Amazon.com** | Disallows scraping. | Don't. Use the bootstrap dataset. Their PA-API is invite-only. |
| **Petco.com / PetSmart.com** | Similar to Chewy. | Same approach as Chewy. |
| **Reddit** | Public API but throttled & paid above small tiers. | Use **PRAW** with credentials; respect 60 req/min. Or use Pushshift archives. |
| **Books to Scrape** (sandbox) | Explicitly built for learning. | Use as your **demo target** for the live-streaming pipeline so you can show the architecture working without any ToS concern. URL: <http://books.toscrape.com>. |
| **Quotes to Scrape** (sandbox) | Same. | Useful for testing JS-heavy scraping. |
| **Open Pricing APIs** | Various. | If you really want live prices: **Best Buy Open API**, **Walmart Open API** (limited but free), eBay Browse API. None have great pet selection but proves the architecture. |

### Ethical defaults baked into our scraper

- Read `/robots.txt` first; abort if disallowed.
- Set a real `User-Agent` with contact email (yours).
- Concurrency limited to 1 request per domain at a time, with 5–10s polite jitter.
- Cache HTML for 24h so re-runs hit local cache.
- No login-walled or PII data.
- Rate-limited by token bucket per domain.

The default scraper target in this repo is `books.toscrape.com` so you can demo end-to-end without anyone's ToS in question. The `chewy.py` parser is included with the network layer **disabled by default** — you must explicitly set `CHEWY_LIVE=1` in `.env`.

---

## D. Step-by-step: load your first 50K reviews

```bash
# 1. Bring up the local stack
make up

# 2. Confirm Postgres is healthy
docker compose exec postgres psql -U pricesentry -c "\dt"

# 3. Run the bootstrap with a small limit first
docker compose exec scraper python /app/scripts/bootstrap_amazon_reviews.py \
  --limit 50000 \
  --batch-size 500

# 4. Verify
docker compose exec postgres psql -U pricesentry -c \
  "SELECT competitor, COUNT(*) FROM competitor_skus GROUP BY 1;"
docker compose exec postgres psql -U pricesentry -c \
  "SELECT COUNT(*) FROM reviews;"
```

Expected output after step 4:

```
 competitor | count
------------+-------
 amazon     |  ~9800
(1 row)

 count
-------
 50000
(1 row)
```

Then embed:

```bash
make embed-reviews   # ~5–10 min on CPU for 50K reviews with bge-small
```

Then ask:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "What do customers think of Blue Buffalo dog food packaging?"}'
```

You'll get a JSON answer with `[review_id]` citations.

---

## E. Where the data lives at each phase

| Phase | Location | Format |
|---|---|---|
| 1 | Local Docker volume (Postgres) | Tables (silver), JSONB (bronze) |
| 2 | Same Postgres + dbt-built marts | Tables + Parquet exports |
| 3 | S3 (bronze/silver/gold) + RDS Postgres for serving | Parquet on S3, indexed tables on RDS |

In Phase 3 the bootstrap script gets re-pointed at S3 instead of Postgres. The transformation logic stays the same; only the destination changes. **That's the medallion pattern paying off.**

---

## F. Common pitfalls (from experience)

1. **Don't load the whole Hugging Face dataset into RAM.** Always use `streaming=True` mode. The script in `scripts/bootstrap_amazon_reviews.py` does this.
2. **Don't embed reviews one at a time.** Batch in groups of 32–64. CPU time goes from hours to minutes.
3. **Don't store embeddings as TEXT.** Use the pgvector `vector(384)` type so you can build an IVFFLAT index.
4. **Don't forget the index.** `CREATE INDEX ... USING ivfflat (...)` — without it, similarity search does a full table scan and degrades catastrophically past ~10K rows.
5. **Don't re-embed unchanged reviews.** The embedding script's `WHERE NOT EXISTS` clause handles this — keep it.
6. **Don't commit your `.env` file.** It's in `.gitignore`. Even for portfolio projects, especially if you put a Bedrock API key in there.

---

## G. Future data sources to plug in

Once Phase 3 is solid, these extend the project's "wow" without re-architecting:

- **Walmart Open API** — adds a 4th competitor with real-time prices.
- **Reddit live via PRAW** — sentiment as it happens, not historical.
- **Trustpilot review pages** — off-marketplace sentiment.
- **Google Trends API** — search-interest as a leading indicator.

Each of these slots into your existing scraper interface (`targets/base.py`) without touching the rest of the pipeline. **That's the power of a clean abstraction layer.**
