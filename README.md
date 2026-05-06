# PriceSentry

> Real-time competitor price + review intelligence for Pet Supplies DTC brands. Built solo, from scratch, on AWS Free Tier.

**Status:** Phase 1 (Crawl) — local Docker MVP
**Domain:** Pet Supplies (Chewy, Amazon Pet, Petco, PetSmart)
**Target role:** Data Engineer

---

## What this project demonstrates

- A real **medallion data lake** (raw → silver → gold) built locally first, ported to AWS later.
- **OLTP/OLAP separation** — operational Postgres vs analytical mart (Athena/Redshift in Phase 3).
- **Streaming-flavored ingestion** with batch fallback (Kinesis in Phase 3, simple queue in Phase 1).
- **Embedding-based product matching** across competitors (an entity-resolution problem).
- **Aspect-based sentiment** on reviews (DistilBERT fine-tune).
- **Production-style RAG** with hybrid retrieval, reranker, and citation contracts (Bedrock + pgvector).
- **IaC + CI/CD + observability** as first-class citizens, not afterthoughts.

---

## Three-phase build

| Phase | Goal | Stack | Time |
|---|---|---|---|
| **1. Crawl** | Local end-to-end MVP. One scraper → Postgres → simple RAG. Prove the loop. | Docker Compose, Postgres+pgvector, Playwright, FastAPI | Weeks 1–3 |
| **2. Walk** | Add orchestration, dbt, embeddings pipeline, sentiment model. | Airflow, dbt, sentence-transformers, MLflow | Weeks 4–6 |
| **3. Run** | Migrate to AWS Free Tier. ECS scrapers, S3 medallion, Athena, RDS, Bedrock. | Terraform, ECS, S3, Athena, RDS, Bedrock | Weeks 7–10 |

See [`docs/02-phase-roadmap.md`](docs/02-phase-roadmap.md) for week-by-week detail.

---

## Quick start (Phase 1, local)

Prereqs: Docker Desktop, Python 3.11, Make, ~10 GB free disk.

```bash
# 1. Clone and enter
git clone <your-fork> priceSentry && cd priceSentry

# 2. Copy env template
cp .env.example .env

# 3. Bring up Postgres + API + scraper
make up

# 4. Bootstrap with Amazon Pet Supplies reviews (~5 min)
make bootstrap-reviews

# 5. Run the scraper once (uses the demo target by default)
make scrape-once

# 6. Generate embeddings for the loaded reviews
make embed-reviews

# 7. Hit the RAG endpoint
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Why are customers unhappy with Brand X dog food?"}'
```

---

## Repository layout

```
priceSentry/
├── README.md                       # this file
├── Makefile                        # convenience commands
├── docker-compose.yml              # local dev stack
├── .env.example                    # environment template
├── .gitignore
├── docs/
│   ├── 00-architecture.md          # end-to-end architecture (all 3 phases)
│   ├── 01-dataset-guide.md         # where to get data + how to load it
│   └── 02-phase-roadmap.md         # week-by-week plan
├── db/
│   └── init.sql                    # Postgres schema (OLTP + pgvector)
├── services/
│   ├── scraper/                    # Phase 1 scraper service
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── scraper/
│   │       ├── __init__.py
│   │       ├── main.py             # entry point
│   │       ├── db.py               # connection helper
│   │       ├── models.py           # Pydantic data contracts
│   │       ├── targets/
│   │       │   ├── __init__.py
│   │       │   ├── base.py         # abstract scraper interface
│   │       │   ├── demo.py         # safe sandbox target
│   │       │   └── chewy.py        # parser stub (read the docs first!)
│   │       └── pipeline.py         # orchestrates fetch → parse → store
│   └── api/                        # Phase 1 FastAPI service (RAG endpoint)
│       ├── Dockerfile
│       ├── requirements.txt
│       └── app/
│           ├── __init__.py
│           ├── main.py             # FastAPI app
│           ├── rag.py              # retrieval + generation
│           └── deps.py             # DB + embedding model deps
├── scripts/
│   ├── bootstrap_amazon_reviews.py # download + load HuggingFace dataset
│   └── embed_reviews.py            # batch embed reviews into pgvector
└── tests/
    └── test_smoke.py               # one minimal end-to-end test
```

---

## Read these in order

1. [`docs/00-architecture.md`](docs/00-architecture.md) — the big picture
2. [`docs/01-dataset-guide.md`](docs/01-dataset-guide.md) — where data comes from
3. [`docs/02-phase-roadmap.md`](docs/02-phase-roadmap.md) — what to build, when
4. [`docs/03-getting-started.md`](docs/03-getting-started.md) — a literal 30-minute first run

---

## Important: ethics and ToS

Chewy, Amazon, and Petco all restrict automated access in their robots.txt and terms of service. For this **portfolio** project:

- **Primary data source:** the publicly-licensed Amazon Reviews 2023 dataset (Pet Supplies subset). That gives you ~10M+ rows of legitimately downloadable review text and product metadata to build, demo, and benchmark every component.
- **Live scraping:** the scraper code targets a *safe sandbox demo site* by default (`books.toscrape.com`-style). The Chewy parser is included as a **structural reference** with the request layer disabled by default — flip it on at your own risk and with proper rate-limiting / proxies / a real legal review.
- Recruiters will not penalize you for honesty here; they *will* penalize you for getting your IP banned mid-demo.

Details in [`docs/01-dataset-guide.md`](docs/01-dataset-guide.md).