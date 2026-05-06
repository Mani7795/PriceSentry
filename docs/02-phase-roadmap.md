# PriceSentry — Phase Roadmap (10 weeks, solo, evenings/weekends)

This is your battle plan. Each week ends with a *demonstrable* checkpoint — something you can record a 60-second screen capture of and post to your portfolio site. **Recruiters love progress artifacts more than finished products.**

---

## Phase 1 — CRAWL (Weeks 1–3)

> **Goal:** end-to-end local pipeline. Bootstrap data → silver tables → embeddings → RAG answer with citations. Everything in Docker Compose.

### Week 1 — Foundation

- Install: Docker Desktop, Python 3.11, VS Code, `make`, `git`.
- Clone this scaffold; `make up`; verify Postgres is reachable.
- Read **all** of `docs/00-architecture.md` and `docs/01-dataset-guide.md`.
- Walk through `db/init.sql` line by line; understand every table.
- Run `make bootstrap-reviews --limit 5000` (small first).
- Hand-write 3 SQL queries against the loaded data to feel it.
- **Checkpoint:** screenshot of `psql` showing `SELECT COUNT(*) FROM reviews` returning 5000.

### Week 2 — Scraper + bronze layer

- Implement the demo target (`targets/demo.py`) end-to-end.
- Get `pipeline.py` parsing bronze → silver. Add Pydantic validation.
- Run scraper 50 times in a row; verify `raw_events` deduplicates via SHA-256.
- Add structured logging (JSON) and basic counters.
- Write your first unit test.
- **Checkpoint:** demo video of `make scrape-once` running, raw events landing in DB, then silver rows materializing.

### Week 3 — Embeddings + RAG MVP

- Write `scripts/embed_reviews.py`. Test on 1K rows first.
- Add the IVFFLAT index to `review_embeddings`.
- Implement `/ask` in FastAPI: embed question → retrieve top-K → format prompt → call LLM.
- Use Anthropic Claude Haiku via API key (cheapest option) **or** Ollama with `llama3.1:8b` for $0.
- Enforce citation contract in the system prompt (every fact cites `[review_id]`).
- **Checkpoint:** screen recording of `curl /ask` returning a grounded answer with citations. Post to your portfolio site/LinkedIn.

---

## Phase 2 — WALK (Weeks 4–6)

> **Goal:** add the pieces a real DE team expects. Orchestration, transformation framework, ML lifecycle, observability.

### Week 4 — Airflow + dbt

- Add Airflow to `docker-compose.yml` (CeleryExecutor or LocalExecutor).
- Write 3 DAGs:
  1. `scrape_competitors_daily` — runs the scraper for each target.
  2. `embed_pending_reviews_hourly` — picks up unembedded reviews.
  3. `build_marts_daily` — kicks off `dbt run` + `dbt test`.
- Initialize a dbt project (`dbt-postgres` adapter) inside `dbt/`.
- Build first marts: `fact_price_daily`, `fact_review`, `dim_product`, `dim_competitor`.
- Add `dbt test`s (`unique`, `not_null`, custom).
- **Checkpoint:** Airflow UI screenshot with 3 green DAGs; dbt docs page screenshot.

### Week 5 — Sentiment model + product matching

- Fine-tune DistilBERT on a 50K labeled subset of Amazon reviews (you can label by mapping rating 1–2 → negative, 4–5 → positive, with neutral ignored — quick and dirty but fine).
- Track in MLflow.
- Serve as a tiny FastAPI service `services/sentiment/` (or call from a Python operator in Airflow).
- Add `sentiment_score` column populated by a daily batch.
- Implement product matcher: encode title+brand with `BGE-small`, FAISS index, k-NN lookup → cross-encoder rerank → write `match_confidence` to `competitor_skus`.
- **Checkpoint:** ROC curve for sentiment, precision-recall curve for matcher (charts saved to `evals/`).

### Week 6 — Observability + dashboard

- Add Prometheus + Grafana to `docker-compose.yml`.
- Instrument every service with `prometheus_client`.
- Build 3 dashboards: pipeline freshness, model performance, RAG quality.
- Add Great Expectations checks running in pre-commit + CI.
- Add OpenLineage emitter from Airflow → Marquez (single Docker container).
- Add Streamlit UI under `services/dashboard/` showing top-line KPIs.
- **Checkpoint:** demo video walking through the Streamlit dashboard, then drilling into Grafana for ops, then Marquez for lineage.

---

## Phase 3 — RUN (Weeks 7–10)

> **Goal:** lift to AWS Free Tier. Terraform-managed, monitored, demo-ready.

### Week 7 — IaC + RDS + S3

- Set up AWS account; create budget alarm at $5/$10/$15.
- Write Terraform under `infra/`: VPC, subnets, IGW, NAT (use a NAT instance not gateway to stay free), SGs, S3 buckets (raw/silver/gold), RDS Postgres (t3.micro), ECR.
- Migrate Postgres schema to RDS via a migration tool (`alembic`).
- Move Phase 1 bootstrap script to write to RDS instead of local Postgres.
- **Checkpoint:** `terraform apply` from clean state in <10 min; data loaded into RDS.

### Week 8 — ECS scrapers + Lambda writers + S3 medallion

- Containerize scrapers; push to ECR.
- ECS Fargate task definition with EventBridge cron (every 6h).
- Scrapers write JSON events to S3 raw zone via Firehose-free path: scraper writes object directly to `s3://pricesentry-raw/competitor=chewy/year=2026/...`.
- Lambda triggered by S3 PUT → parses → writes Parquet to silver zone.
- Glue Crawler over silver/gold → tables in Glue Catalog.
- Athena queries against gold (free tier: 1TB/month scanned).
- **Checkpoint:** Athena query screenshot returning `SELECT * FROM gold.fact_price_daily LIMIT 10`.

### Week 9 — Bedrock RAG + frontend deploy

- Replace local LLM call with Bedrock `claude-haiku` (or `claude-sonnet-4` for quality).
- Replace `bge-small` embeddings with Titan Embeddings via Bedrock (or keep local and run on ECS — both fine).
- Deploy FastAPI to ECS Fargate (single task) behind API Gateway.
- Build minimal Next.js frontend; deploy as static site to S3 + CloudFront.
- Add CloudWatch dashboards mirroring the Grafana ones from Phase 2.
- **Checkpoint:** public demo URL works end-to-end.

### Week 10 — Polish, evals, write-up

- Run Ragas (faithfulness, answer relevancy, context recall) on a 50-question test set.
- Document everything: cost dashboard, architecture diagrams (Excalidraw → SVG), runbook, eval report.
- Record a 3-minute walkthrough video.
- Write a blog post: "How I built a competitor-intelligence platform on AWS Free Tier."
- Pin to LinkedIn + GitHub README.
- **Checkpoint:** post your demo to one DE community (`r/dataengineering`, locallyoptimistic.com Slack, etc.) and collect feedback.

---

## What "done" looks like at end of week 10

A recruiter cloning the repo:

1. Reads README → understands in 2 minutes what was built.
2. Sees a green CI badge.
3. Watches the 3-min demo video.
4. Sees the architecture diagrams.
5. Sees Ragas/evals results.
6. Sees the Terraform that they could `apply` themselves.
7. Sees a `cost.md` that says "$14/month with X traffic".
8. Sees Phase-by-phase commit history showing the build journey.

If that's true, **you are highly hireable as a junior-to-mid Data Engineer** on the strength of this one project.

---

## When you'll get stuck (and how to unstick)

| Problem | Most likely cause | Fix |
|---|---|---|
| `make up` fails on `pgvector` extension | Wrong Postgres image | Use `pgvector/pgvector:pg16` not `postgres:16` |
| Scraper hangs at first request | Playwright not installing browsers | `playwright install chromium` inside container |
| Embedding takes forever | Doing one row at a time | Batch in groups of 64; convert lists to numpy first |
| RAG answers ignore citations | Weak system prompt | Make it strict; reject answers without `[review_id]` patterns and retry |
| Athena returns 0 rows | Glue crawler hasn't run | `aws glue start-crawler --name pricesentry-silver` |
| RDS connection times out from ECS | Security group blocking | Open port 5432 from ECS SG to RDS SG |
| Bedrock returns "model not found" | Model not enabled in your region | Bedrock console → Model access → request access (5 min approval) |

---

## Cheat sheet: tools and what they're for

For your benefit and for talking with recruiters.

| Tool | One-line description |
|---|---|
| **Docker Compose** | Define + run multi-container apps with one YAML file |
| **Postgres** | The reliable, boring, perfect SQL database |
| **pgvector** | Postgres extension that adds a `vector` type + ANN indexes |
| **Playwright** | Modern browser automation (headless Chrome/Firefox/Webkit) |
| **FastAPI** | Async Python web framework with auto-docs |
| **sentence-transformers** | Pre-trained sentence-embedding models (BGE, MiniLM) |
| **Anthropic Claude / Bedrock** | LLM provider; Haiku is cheap, Sonnet is smart |
| **Airflow** | DAG-based job scheduler — the standard in DE |
| **dbt** | SQL-based transformation framework with tests + docs |
| **Great Expectations** | Data quality test suite |
| **Prometheus + Grafana** | Metrics collection + dashboards |
| **MLflow** | Experiment tracking + model registry |
| **Terraform** | Infrastructure-as-code for AWS (and others) |
| **ECS Fargate** | Run containers without managing servers (pay per second) |
| **Athena** | Run SQL on data sitting in S3, no warehouse needed |
| **Bedrock** | AWS-hosted LLM API (Anthropic/Amazon/Meta models) |

When you can fluently explain *why* you used each one (and what you'd use instead at higher scale), you're ready for mid-level DE interviews.
