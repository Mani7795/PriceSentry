# Phase 2 Runbook — Auth + Streaming Chat

This brings up the new stack on top of your Phase 1 data. **You don't lose any data** — the `pgdata` volume from Phase 1 is reused. We only add new tables (`users`, `conversations`, `messages`, `citations`, ...) on top.

If you've never run Phase 1 before, do that first (`docs/03-getting-started.md`). Phase 2 assumes you already have reviews + embeddings in Postgres.

---

## 1. Apply the new schema to an existing DB

The new schema file `db/02_phase2_chat.sql` only runs automatically on a fresh container. Since you already have data, apply it manually:

```bash
# From the repo root:
docker compose cp db/02_phase2_chat.sql postgres:/tmp/02.sql
docker compose exec postgres psql -U pricesentry -d pricesentry -f /tmp/02.sql
```

You should see `Phase 2 schema initialized successfully.` near the end of the output. Verify:

```bash
docker compose exec postgres psql -U pricesentry -d pricesentry -c "\dt users conversations messages message_citations"
```

You should see all four tables listed.

> If you'd rather start fresh, `docker compose down -v && docker compose up -d` will pick up both schema files in order. But you'll lose your existing reviews + embeddings.

---

## 2. Update environment

```bash
# Pull in the new env keys
cp .env.example .env.new
# Merge by hand: keep your existing LLM_PROVIDER/OLLAMA_MODEL values,
# add the new JWT_SECRET, CORS_ORIGINS, etc.
# When done:
mv .env.new .env
```

Set a real JWT secret (the default warns at boot):

```bash
# Generate a strong one
docker compose exec api python -c "import secrets; print(secrets.token_urlsafe(48))"
# Paste output into .env as: JWT_SECRET=...
```

---

## 3. Rebuild & start everything

```bash
docker compose down
docker compose up -d --build
```

First-time `web` build is ~3-5 minutes (npm install + next build). Watch:

```bash
docker compose logs -f api
docker compose logs -f web
```

You're done when the API logs say `Uvicorn running on http://0.0.0.0:8000` and the web logs say `▲ Next.js 14.2.x` then `Ready in ...ms`.

---

## 4. Smoke test the new endpoints

```bash
# Health
curl http://localhost:8000/healthz
curl http://localhost:8000/readyz

# OpenAPI docs (open in browser)
# http://localhost:8000/docs

# Register
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"correcthorsebattery","full_name":"You"}'
# → {"access_token":"eyJ...","token_type":"bearer","expires_in_seconds":900}

# Save the access_token, then:
ACCESS=eyJ...   # paste

# Who am I?
curl http://localhost:8000/api/v1/auth/me -H "Authorization: Bearer $ACCESS"

# Streaming chat (SSE — events stream as text)
curl -N -X POST http://localhost:8000/api/v1/chat/stream \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $ACCESS" \
  -d '{"message":"What do customers say about kibble packaging?"}'
```

You'll see SSE events:

```
event: start
data: {"conversation_id":"...","user_message_id":"..."}

event: citations
data: {"citations":[...]}

event: token
data: {"text":"Based "}

event: token
data: {"text":"on the reviews..."}

event: done
data: {"conversation_id":"...","message_id":"...","model":"llama3.2:3b","latency_ms":4231}
```

---

## 5. Use the frontend

Open **http://localhost:3000** in your browser.

You should see:
1. A redirect to `/login`.
2. Click "Create one" → register with any email + password (≥8 chars).
3. After registering, you're routed to `/chat`.
4. Click a suggested question or type your own and hit Enter.
5. You should see tokens stream in real-time, with citations populating the right-side panel.
6. New conversations appear in the left sidebar; click to reopen them.
7. The avatar at the bottom shows your user; the logout button (the door icon) signs you out.

If the stream feels slow, that's Ollama on CPU. Each token is real-time as the model generates it.

---

## 6. What's running where

| Port | Service | What it serves |
|---|---|---|
| 3000 | Next.js (`web`) | The browser-facing app |
| 8000 | FastAPI (`api`) | REST + SSE backend |
| 5432 | Postgres (`postgres`) | Data + pgvector |
| 11434 | Ollama (on Windows host) | LLM inference |

The browser talks only to `web` (port 3000). The web container proxies `/api/v1/*` to the `api` container via the rewrite in `next.config.mjs`. The api container talks to Postgres and Ollama.

---

## 7. Common issues

**`Cookie not being set` / login works but page bounces back to /login.**
You're hitting CORS or SameSite issues. Make sure `.env` has `CORS_ORIGINS=http://localhost:3000` and that you're accessing via `localhost:3000`, not `127.0.0.1:3000` (cookies are scoped per origin). Recreate the API after editing .env: `docker compose up -d --force-recreate api`.

**Frontend builds fail with `Module not found: clsx`.**
The web Dockerfile hasn't installed deps yet. Rebuild: `docker compose build web --no-cache`.

**Chat starts streaming but cuts off after ~30s.**
The Ollama 3B model is fast enough that this shouldn't happen, but if your laptop is heavily loaded, the read timeout in `llm_providers.py` is 300s — bump if needed. More likely: you're using the 8B model and ran out of memory; switch to `OLLAMA_MODEL=llama3.2:3b` in `.env`.

**`401 Unauthorized` on every request after a few minutes.**
Access tokens expire after 15 min. The frontend auto-refreshes via the httpOnly cookie. If refresh fails (e.g. you cleared cookies), you'll be sent to `/login`. That's the design.

---

## 8. What's queued for Phase 2.2 (next delivery)

Already designed; will land in the next response so this delivery stays debuggable:

- File upload (S3) + ingestion pipeline (the "upload doc" feature)
- Background workers (Celery + Redis) for slow tasks (re-embed, recompute)
- Settings page (provider switcher, embedding model picker, retrieval debug panel)
- Admin dashboard + analytics page + feedback collection
- Rate limiting (slowapi) + structured request metrics (Prometheus)
- Alembic migrations replacing raw SQL

## 9. What's queued for Phase 2.3

- AWS Terraform: ECS Fargate + RDS + S3 + CloudFront + Bedrock
- Kubernetes manifests + Helm chart
- GitHub Actions: lint → test → build → deploy
- Nginx config + multi-cloud reference (Railway, Fly.io)
- Production hardening: health checks, graceful shutdown, log shipping
