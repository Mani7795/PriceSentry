# PriceSentry — End-to-End Architecture

This is the master architecture doc. It covers all three phases, the data flow, schema choices, the why-behind-the-tools, and the AWS free-tier.


---

## 1. The mental model: a 3-layer data lake (the "medallion" pattern)

The single biggest concept in modern data engineering is the **bronze / silver / gold** (a.k.a. raw / silver / gold) layered storage pattern.

```
       ┌──────────────────────────────────────────────────────────┐
       │                   BRONZE / RAW LAYER                     │
       │   Whatever you scraped/received, byte-for-byte.          │
       │   Never modified. The source of truth if anything breaks.│
       │   Format: JSON, HTML, raw API responses.                 │
       └──────────────────────────────────────────────────────────┘
                                    │
                          parse, clean, type, dedupe
                                    │
       ┌──────────────────────────────────────────────────────────┐
       │                   SILVER / CLEAN LAYER                   │
       │   Validated, typed, deduplicated. One row per "thing".   │
       │   Format: Parquet (columnar), Postgres tables.           │
       └──────────────────────────────────────────────────────────┘
                                    │
                          join, aggregate, enrich
                                    │
       ┌──────────────────────────────────────────────────────────┐
       │                   GOLD / MART LAYER                      │
       │   Business-ready facts and dimensions. Star schema.      │
       │   Powers dashboards, RAG retrieval, alerts.              │
       └──────────────────────────────────────────────────────────┘
```

**Why this matters:** if a downstream model is wrong, you can re-run silver → gold without re-scraping (which is expensive and rate-limited). If your *parser* has a bug, you can re-run bronze → silver. Layered immutability is what separates real DE from "I dump everything into one table."

---

## 2. Phase 1 architecture (CRAWL — local, ~3 weeks)

The simplest possible version that exercises every concept end-to-end. Everything runs on your laptop in Docker.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                          YOUR LAPTOP (Docker Compose)                   │
│                                                                         │
│  ┌─────────────┐    ┌────────────────┐                                  │
│  │  Scraper    │───►│   raw_events   │  (Postgres JSONB table          │
│  │ (Playwright)│    │   table        │   acts as Bronze layer)         │
│  └─────────────┘    └────────────────┘                                  │
│                              │                                          │
│                              │  pipeline.py parses + validates          │
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────┐                   │
│  │   SILVER tables: products, competitor_skus,      │                   │
│  │   price_observations, reviews                    │                   │
│  └──────────────────────────────────────────────────┘                   │
│                              │                                          │
│                              │  embed_reviews.py (sentence-transformers)│
│                              ▼                                          │
│  ┌──────────────────────────────────────────────────┐                   │
│  │   review_embeddings  (pgvector, 384-dim)         │                   │
│  └──────────────────────────────────────────────────┘                   │
│                              │                                          │
│                              │                                          │
│  ┌─────────────┐             ▼                                          │
│  │  FastAPI    │◄──── pgvector similarity search                        │
│  │  /ask       │                                                        │
│  └──────┬──────┘                                                        │
│         │  retrieved chunks + question                                  │
│         ▼                                                               │
│  ┌─────────────┐                                                        │
│  │ Local LLM   │  (Ollama/llama3 OR OpenAI/Anthropic API key)           │
│  └─────────────┘                                                        │
│         │                                                               │
│         ▼                                                               │
│      JSON answer with citations                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Phase 1 components

| Component | Role | Why this choice |
|---|---|---|
| **Postgres + pgvector** | OLTP + vector store, single DB | One database to learn well. pgvector is "good enough" up to ~1M vectors. |
| **Playwright** | Browser automation for scraping | Handles JS-rendered pages; one library covers Chrome/Firefox/Webkit. |
| **FastAPI** | HTTP API with auto-docs | Async by default, Pydantic validation, Swagger UI for free. |
| **sentence-transformers** | Embedding model (BGE-small) | Runs on CPU, no GPU needed. 384 dims is small + fast. |
| **Docker Compose** | Local orchestration | The simplest "infra as code" you can learn. |
| **Anthropic Claude Haiku** (or local Ollama) | LLM for RAG answers | Cheapest API LLM; or Ollama if you want $0 cost. |

### Phase 1 limitations (deliberate)
- No orchestrator (cron is fine for now).
- No separate analytics warehouse (pgvector and analytics share Postgres).
- No real-time streaming (just scheduled scrapes).
- Single-host. No HA. **This is correct for Phase 1.**

---

## 3. Phase 2 architecture (WALK — local, ~3 weeks)

Add the muscles a real data team would expect.

```
                    ┌───────────────────────────────────────┐
                    │       Airflow (local Docker)          │
                    │   DAGs: scrape → parse → embed → mart │
                    └────────────────┬──────────────────────┘
                                     │ schedules
                ┌────────────────────┼────────────────────┐
                ▼                    ▼                    ▼
        ┌──────────────┐    ┌────────────────┐   ┌──────────────┐
        │  Scrapers    │    │  Sentiment     │   │   Embeddings │
        │  (multiple   │    │  fine-tune +   │   │   batch job  │
        │   targets)   │    │  inference     │   │              │
        └──────┬───────┘    └────────┬───────┘   └──────┬───────┘
               │                     │                   │
               └─────────────────────┼───────────────────┘
                                     ▼
                       ┌──────────────────────────┐
                       │   Postgres (OLTP)        │
                       │   + pgvector             │
                       └────────┬─────────────────┘
                                │
                                │  dbt (using dbt-postgres)
                                ▼
                       ┌──────────────────────────┐
                       │   GOLD marts in Postgres │
                       │   schema: marts.         │
                       │   - fact_price_obs       │
                       │   - fact_review          │
                       │   - dim_product          │
                       └──────────────────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
        FastAPI RAG    Streamlit dashboard   Slack alerts
                                              (price drops)
```

**New things added in Phase 2:**
- **Airflow** with proper DAGs, retries, SLAs, sensors.
- **dbt** for SQL-based transformations and tests (`unique`, `not_null`, custom).
- **Great Expectations** suite running in CI.
- **MLflow** to track sentiment-model experiments.
- **Aspect-based sentiment** classifier — fine-tuned DistilBERT.
- **Reranker** in the RAG path (`bge-reranker-base`).
- **OpenLineage** emitters → simple Marquez UI for lineage.

---

## 4. Phase 3 architecture (RUN — AWS Free Tier, ~3–4 weeks)

The portfolio-grade target. Everything is in AWS, deployed by Terraform, monitored by CloudWatch.

```
                         ┌────────────────────────┐
                         │      Route 53          │
                         └───────────┬────────────┘
                                     │
                         ┌───────────▼────────────┐
                         │     CloudFront         │
                         └───────────┬────────────┘
                                     │
                         ┌───────────▼────────────┐
                         │     Next.js on S3      │  (static frontend)
                         └────────────────────────┘
                                     │
                                     │ API calls
                                     ▼
                         ┌────────────────────────┐
                         │     API Gateway        │
                         └───────────┬────────────┘
                                     │
                       ┌─────────────▼─────────────┐
                       │   FastAPI on ECS Fargate  │
                       │   (1 task, t3.micro tier) │
                       └─────┬──────────────┬──────┘
                             │              │
                ┌────────────▼─┐         ┌──▼────────────────┐
                │ RDS Postgres │         │ Bedrock           │
                │  (t3.micro)  │         │ Claude Haiku      │
                │  + pgvector  │         │ + Titan embeds    │
                └──────────────┘         └───────────────────┘

──────────────────────────  INGESTION SIDE  ──────────────────────────

  EventBridge cron (every 6h)
        │
        ▼
  ┌──────────────────────┐
  │ ECS Fargate scrapers │  (run, exit, no idle cost)
  │  one task per target │
  └──────────┬───────────┘
             │
             ▼  JSON events
  ┌──────────────────────┐
  │  Lambda: writer      │  (cheap, scales to zero)
  └──────────┬───────────┘
             │
             ▼
  ┌──────────────────────────────────────────┐
  │  S3  (Bronze, Silver, Gold zones)        │
  │  partitioned by competitor/year/month/   │
  │  format: Parquet (Snappy)                │
  └────┬───────────────┬────────────────┬────┘
       │               │                │
       ▼               ▼                ▼
   Glue Catalog    Athena (SQL    Glue ETL job
   (metadata)      ad-hoc on S3)  (silver→gold)
                                         │
                                         ▼
                                  RDS Postgres
                                  (the marts the
                                   API reads from)

──────────────────────────  ORCHESTRATION  ──────────────────────────

  Step Functions  ←  this replaces Airflow at this scale
  (cheaper than MWAA, fits free tier better)
        │
        ▼
  Drives the EventBridge schedule, Lambda chain, Glue jobs.

──────────────────────────  OBSERVABILITY  ──────────────────────────

  CloudWatch Logs + Metrics + Alarms
  → SNS → Email/Slack on:
       • scrape failure rate > 10%
       • freshness lag > 12h
       • RDS storage > 80%
```

### Why these AWS choices for Free Tier

| You might expect | Free-tier-friendly substitute | Why |
|---|---|---|
| MSK (managed Kafka) | EventBridge + Lambda + S3 | MSK starts at ~$150/mo. EventBridge is free for most usage. |
| Redshift | Athena on S3 (Parquet) | Athena is pay-per-query. Empty = $0. |
| MWAA (Managed Airflow) | Step Functions | MWAA is ~$300/mo minimum. Step Functions free tier covers your usage. |
| Pinecone / Weaviate | pgvector on RDS | RDS t3.micro is in free tier for 12 months. |
| OpenSearch | Postgres full-text search (`tsvector`) | OpenSearch t3.small is ~$30/mo. Postgres FTS is free. |

> **Net cost target Phase 3:** under $20/month (mostly Bedrock token spend; everything else is in free tier).

---

## 5. Schema design (the part that takes you from junior to mid-level)

### OLTP schema (Postgres) — Phase 1, evolves through all phases

We model **products** (canonical) separately from **competitor_skus** (per-retailer listings) because **the same product is sold by multiple retailers under different titles, prices, and SKUs**. The matching of `competitor_sku → product` is the entity-resolution problem.

```sql
-- Canonical product (what the world knows it as)
products (
  product_id        UUID PK
  brand             TEXT       -- e.g., 'Blue Buffalo'
  title             TEXT       -- canonical title we choose
  category          TEXT       -- 'dog_food', 'cat_litter', ...
  pet_type          TEXT       -- 'dog', 'cat', 'fish', ...
  upc               TEXT NULL  -- when known
  attributes        JSONB      -- weight, flavor, life_stage
  created_at        TIMESTAMPTZ
)

-- Each retailer's listing (a SKU)
competitor_skus (
  sku_id            UUID PK
  product_id        UUID FK -> products  (NULL until matched)
  competitor        TEXT       -- 'chewy', 'amazon', 'petco'
  external_id       TEXT       -- their internal id / ASIN
  url               TEXT
  raw_title         TEXT       -- as the retailer wrote it
  match_confidence  REAL NULL  -- 0..1 from the matcher
  matched_at        TIMESTAMPTZ NULL
  UNIQUE(competitor, external_id)
)

-- Time-series of prices (append-only)
price_observations (
  observation_id    BIGSERIAL PK
  sku_id            UUID FK
  observed_at       TIMESTAMPTZ
  price_cents       INTEGER
  currency          TEXT DEFAULT 'USD'
  in_stock          BOOLEAN
  raw_event_id      UUID NULL  -- back to bronze
)
CREATE INDEX ON price_observations (sku_id, observed_at DESC);

-- Reviews
reviews (
  review_id         UUID PK
  sku_id            UUID FK
  source            TEXT       -- 'chewy', 'amazon', 'reddit'
  external_id       TEXT
  rating            REAL
  review_text       TEXT
  reviewed_at       TIMESTAMPTZ
  verified_purchase BOOLEAN
  raw_payload       JSONB
)

-- Embeddings for RAG (pgvector)
review_embeddings (
  review_id         UUID PK FK
  embedding         vector(384)
  model_version     TEXT
)
CREATE INDEX ON review_embeddings USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- Bronze: every raw event we received
raw_events (
  raw_event_id      UUID PK
  source            TEXT
  fetched_at        TIMESTAMPTZ
  url               TEXT
  http_status       INT
  payload           JSONB      -- full response
  payload_sha256    TEXT       -- for idempotency
  UNIQUE(source, payload_sha256)
)
```

### Gold schema (dbt marts) — Phase 2 onwards

```sql
-- One row per (product, day, competitor)
fact_price_daily (
  product_id        UUID
  competitor        TEXT
  day               DATE
  min_price_cents   INTEGER
  max_price_cents   INTEGER
  close_price_cents INTEGER  -- last observation that day
  observations      INTEGER
)

-- One row per review, denormalized for analytics
fact_review (
  review_id         UUID
  product_id        UUID
  competitor        TEXT
  reviewed_at       TIMESTAMPTZ
  rating            REAL
  sentiment_score   REAL      -- -1..1, from sentiment model
  aspect_tags       TEXT[]    -- ['price','smell','packaging']
  embedding_id      UUID
)

dim_product (...)
dim_competitor (...)
dim_date (...)
```

### Why two schemas?

The OLTP schema is **normalized** (3NF) — fast writes, no duplicate data, integrity constraints. The OLAP/gold schema is **denormalized** (star) — fast reads for analytics, no joins on the hot path. **Knowing when to use which** is one of the most useful judgments in DE.

---

## 6. Data flow walkthrough — the path of a single review

This is the level of detail recruiters love when you can talk through it.

1. **Scrape:** scraper hits a product page on Chewy. Gets HTML + reviews JSON.
2. **Bronze write:** scraper inserts a row into `raw_events` with the full JSON payload and a SHA-256 of the payload. The `UNIQUE(source, payload_sha256)` constraint makes the write **idempotent** — re-running the scrape doesn't duplicate.
3. **Parse:** `pipeline.py` reads new `raw_events`, parses the JSON. For each review object:
   - Validate fields with a Pydantic model (`Review`).
   - Upsert into `reviews` keyed by `(source, external_id)`.
4. **Match:** the scraper also produces a `competitor_sku` row. A separate matcher job runs nightly to assign `product_id` to unmatched SKUs (Phase 2+).
5. **Embed:** `embed_reviews.py` finds rows in `reviews` with no `review_embeddings` entry. Embeds in batches of 64. Writes to `review_embeddings`.
6. **Mart (Phase 2+):** dbt models read from silver, produce `fact_review` with sentiment score + aspect tags.
7. **RAG query:** user asks *"why are customers unhappy with Brand X kibble?"*
   - API embeds the question.
   - Postgres ANN query against `review_embeddings`, filtered by brand.
   - Top-K reviews go to a reranker.
   - Top-N go to Claude with a system prompt requiring citations.
   - Response includes `[review_id]` footnotes.

---

## 7. Observability: what to monitor from day 1

Even in Phase 1, log structured JSON and have at least these counters:

- `scrape.requests.total{competitor, status}`
- `scrape.duration_seconds{competitor}` (histogram)
- `parse.errors.total{competitor, error_type}`
- `db.write.duration_seconds{table}`
- `embedding.batch.duration_seconds`
- `rag.retrieval.results_count`
- `rag.answer.tokens_in/tokens_out`

Phase 2 wires these to Prometheus + Grafana (one Docker container each). Phase 3 swaps to CloudWatch metrics with the same names.

**Why this matters:** "I can show you my pipeline's freshness, error rate, and cost-per-1K-reviews on a dashboard" beats "I built a pipeline" every time in interviews.

---

## 8. CI/CD from day 1

GitHub Actions pipeline (defined as code in `.github/workflows/`):

- **On PR:** lint (ruff), type-check (mypy), unit tests, dbt compile, Great Expectations suite on a small sample.
- **On main:** build Docker images, push to ECR (Phase 3), Terraform plan.
- **On tag:** Terraform apply, blue/green deploy of the API.

Even in Phase 1, set up the lint + test job. It becomes "free" and reviewers (recruiters peeking at your repo) immediately see green checks.

---

## 9. Cost ceiling and how we enforce it

| Phase | Monthly cost target | Mechanism |
|---|---|---|
| 1 | $0 (local) | n/a |
| 2 | < $5 (Anthropic API for RAG eval) | manual |
| 3 | < $20 | AWS Budget alarm at $15, hard cap at $25 via alarm → Lambda → stop ECS service |

Always have a budget alert set up *before* you provision anything in AWS. (Console → Billing → Budgets → New → email me at $5, $10, $15.)

---

## 10. What "good" looks like at the end of Phase 3

A recruiter cloning your repo should, in under 10 minutes:

1. Read the README and understand the architecture.
2. See a deployed demo URL (or a recorded demo video).
3. See architecture diagrams (`docs/`) at three altitudes (10K-foot, component, sequence).
4. See a green CI badge.
5. See a `cost.md` page with current spend.
6. See an `evals/` folder with Ragas results and dashboards.
7. See an `infra/` folder with Terraform that they could `apply` themselves.

If those seven things are present, you have a top-decile portfolio project for a junior/mid Data Engineer role.