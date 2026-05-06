# Getting Started — Your First 30 Minutes

A literal walkthrough. Read top-to-bottom, copy commands, no surprises.

## Prerequisites

| Tool | Why | Install |
|---|---|---|
| Docker Desktop | Runs Postgres + scraper + API locally | <https://docs.docker.com/desktop/> |
| `make` | Convenience wrapper | macOS: built-in. Windows: `choco install make` or use WSL. |
| `git` | Source control | <https://git-scm.com/> |
| Python 3.11 (optional) | Only needed if you run scripts outside Docker | <https://www.python.org/> |

Disk: ~10 GB. RAM: 8 GB minimum, 16 GB comfortable.

---

## Step 1 — Clone and configure (5 min)

```bash
cd ~/code   # or wherever you keep projects
git clone <your-fork-url> priceSentry
cd priceSentry
cp .env.example .env
```

Open `.env` and decide your LLM provider:
- **No API key, $0 cost?** → set `LLM_PROVIDER=ollama`, then `brew install ollama` (or download), `ollama pull llama3.1:8b`. Ollama runs on the host; the API container reaches it via `host.docker.internal`.
- **Want better answers and willing to spend ~$0.50 in Phase 1?** → `LLM_PROVIDER=anthropic`, paste your Anthropic API key. Get one at <https://console.anthropic.com>.
- **Defer to Phase 3** → `LLM_PROVIDER=bedrock`, leave the AWS variables alone for now.

---

## Step 2 — Start the stack (3 min)

```bash
make up
```

What happens: Docker pulls the `pgvector/pgvector:pg16` image, builds the scraper and API images (the first build is the slow one — Playwright downloads Chromium ~150 MB), then starts everything. Tail the logs:

```bash
make logs
```

You should see:
- Postgres → `database system is ready to accept connections`
- API → `Uvicorn running on http://0.0.0.0:8000`

Verify the API:

```bash
curl http://localhost:8000/health
# {"status":"ok"}

curl http://localhost:8000/stats
# {"products":0,"competitor_skus":0,"price_observations":0,"reviews":0,"review_embeddings":0}
```

Open <http://localhost:8000/docs> for the interactive Swagger UI.

---

## Step 3 — Run the demo scraper (1 min)

This proves the silver pipeline end-to-end without touching the public internet.

```bash
make scrape-once
```

Then re-check stats:

```bash
curl http://localhost:8000/stats
# {"products":25,"competitor_skus":25,"price_observations":25,"reviews":~150,"review_embeddings":0}
```

Look at the data:

```bash
make psql
```

```sql
SELECT competitor, COUNT(*) FROM competitor_skus GROUP BY 1;
SELECT source, COUNT(*), AVG(rating)::numeric(3,2) AS avg_rating FROM reviews GROUP BY 1;
\q
```

---

## Step 4 — Bootstrap the real Pet Supplies dataset (5–15 min)

```bash
make bootstrap-reviews
```

This runs `scripts/bootstrap_amazon_reviews.py --limit 50000 --batch-size 500`. The first 30s downloads the Hugging Face dataset metadata; then it streams. You'll see progress logs every batch:

```
{"event": "bootstrap.meta.progress", "loaded": 5000, "level": "info", "timestamp": "..."}
{"event": "bootstrap.reviews.progress", "loaded": 10000, "level": "info", "timestamp": "..."}
```

When it's done:

```bash
curl http://localhost:8000/stats
# {"products":~9800,"competitor_skus":~9800,"price_observations":~7500,"reviews":~50000,"review_embeddings":0}
```

(Numbers are approximate — the dataset has nulls in some metadata rows.)

---

## Step 5 — Embed the reviews (5–10 min on CPU)

```bash
make embed-reviews
```

The first run downloads the BGE-small model (~133 MB). Then it embeds in batches of 64. On a modern laptop, ~100–300 reviews/sec.

Verify:

```bash
curl http://localhost:8000/stats
# review_embeddings should now equal reviews count (or close to it)
```

---

## Step 6 — Ask your first question (10 sec)

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{
        "question": "What do customers say about the smell of dog kibble?",
        "brand": null
      }' | jq
```

You should get a JSON response with:
- `answer`: a paragraph or two with `[review_id]` citations.
- `citations`: array of the actual reviews used (IDs, brand, rating, snippet).
- `retrieved`: how many made the cut.

Try a brand-filtered query:

```bash
curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"question": "Common complaints?", "brand": "Blue Buffalo"}' | jq
```

🎉 **You've just used a production-shape RAG pipeline.** Postgres + pgvector ANN, embeddings via sentence-transformers, generation via your LLM of choice, with grounded citations.

---

## Step 7 — Run the smoke tests

```bash
make test
```

Four tests run; all should pass. They cover:
1. Demo target yields pages.
2. Demo target parses to a valid `ScrapeEvent`.
3. End-to-end pipeline writes silver rows.
4. Bronze writes are idempotent on SHA-256.

---

## Common first-time issues

| Symptom | Fix |
|---|---|
| `pgvector` extension missing | You're using the wrong Postgres image. The compose file specifies `pgvector/pgvector:pg16`. Run `make clean && make up`. |
| Scraper container can't reach Postgres | Compose `depends_on` with `service_healthy` should handle this. If you started services manually, restart Postgres first. |
| `ANTHROPIC_API_KEY` invalid | Check for typos; key starts with `sk-ant-`. Test outside the app first with `curl https://api.anthropic.com/...`. |
| Ollama unreachable | On Linux Docker, `host.docker.internal` doesn't resolve by default. Add `extra_hosts: ["host.docker.internal:host-gateway"]` to the API service. |
| `make` not found on Windows | Use WSL2 (`wsl --install`), then run all commands from inside WSL. |
| Embedding job is slow | Normal on CPU. If you have an Nvidia GPU, install CUDA Torch in the scraper image and increase `EMBEDDING_BATCH_SIZE` to 128. |

---

## What to do next

You've completed Phase 1, Week 1. From here:
1. Re-read `docs/02-phase-roadmap.md` and start Week 2.
2. Make your first commit + push to GitHub.
3. Add a screenshot of the `/ask` response to your README's top section.
4. Start a `LEARNINGS.md` in the repo root — write down 3 things that surprised you each week. This becomes your interview prep.

Welcome to data engineering.
