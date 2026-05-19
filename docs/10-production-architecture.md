# PriceSentry — Production Architecture (Phase 2)

This is the production-ready architecture for PriceSentry's user-facing application. It builds on the Phase 1 data pipeline (already running locally) and adds: a Next.js frontend, JWT auth, streaming chat over the RAG index, conversation history with citations, and an AWS-ready deployment shape.

> Phase 1 = data pipeline + RAG endpoint (DONE).
> Phase 2 = real product on top of it (THIS DOC).
> Phase 3 = AWS deploy + K8s/CI/CD (next response).

---

## 1. High-level shape

```
┌────────────────────────────────────────────────────────────────────┐
│                            BROWSER                                 │
│                                                                    │
│   Next.js 14 (App Router)  +  TS  +  Tailwind  +  shadcn/ui        │
│   - /(auth)/login, /(auth)/register                                │
│   - /(app)/chat[/[conversationId]]                                 │
│   - Streams SSE responses, renders citations panel                 │
└─────────────────────────┬──────────────────────────────────────────┘
                          │ HTTPS, JWT in Authorization header
                          ▼
┌────────────────────────────────────────────────────────────────────┐
│                       FastAPI (Python 3.11)                        │
│                                                                    │
│   app/                                                             │
│   ├── core/      settings, security (JWT, bcrypt), logging         │
│   ├── db/        SQLAlchemy 2 ORM, models, session                 │
│   ├── schemas/   Pydantic v2 request/response models               │
│   ├── api/       FastAPI routers: auth, conversations, chat, health│
│   ├── services/  business logic: auth, chat, rag, llm providers    │
│   └── main.py    app factory + middleware (CORS, request-id)       │
│                                                                    │
│   Endpoints:                                                       │
│     POST /api/v1/auth/register                                     │
│     POST /api/v1/auth/login                                        │
│     POST /api/v1/auth/refresh                                      │
│     GET  /api/v1/auth/me                                           │
│     GET  /api/v1/conversations                                     │
│     POST /api/v1/conversations                                     │
│     GET  /api/v1/conversations/{id}/messages                       │
│     POST /api/v1/chat/stream  (SSE) ◄── the main event             │
│     GET  /healthz, /readyz                                         │
└──────────────┬─────────────────────────────────┬───────────────────┘
               │                                 │
               ▼                                 ▼
   ┌─────────────────────┐         ┌──────────────────────────┐
   │  Postgres + pgvector│         │  LLM Provider (one of):  │
   │                     │         │   • Ollama (local CPU)   │
   │  users, refresh_tok │         │   • Anthropic Claude     │
   │  conversations      │         │   • AWS Bedrock          │
   │  messages           │         │   • OpenAI               │
   │  message_citations  │         │  Streamed via SSE pass-  │
   │  reviews + emb...   │         │  through                 │
   └─────────────────────┘         └──────────────────────────┘
```

---

## 2. Why each technology

| Layer | Choice | Why this specifically |
|---|---|---|
| Frontend framework | **Next.js 14 App Router** | First-class streaming (Suspense, RSC), industry-standard, recruiters recognize it instantly. App Router gives us layouts and route groups for `(auth)` vs `(app)`. |
| Frontend styling | **Tailwind + shadcn/ui** | Composable utility classes; shadcn copies primitives into your repo (you own them, no version lock). Looks polished without a designer. |
| Frontend state | **TanStack Query + Zustand** | TanStack handles server state (conversations, messages) with caching/invalidation; Zustand for transient UI state. Lightweight, type-safe. |
| Streaming transport | **Server-Sent Events (SSE)** | One-way streaming, simpler than WebSockets, works through every proxy and load balancer without sticky sessions. ChatGPT, Anthropic, OpenAI all use SSE for streaming. |
| Backend framework | **FastAPI** | Async-by-default, Pydantic v2 validation, auto OpenAPI docs, great DX. Industry standard for Python AI/ML APIs. |
| ORM | **SQLAlchemy 2.0 (async)** | Mature, async support, type hints, you'll see it on every senior Python job listing. Alembic for migrations. |
| Auth | **JWT (access + refresh) + bcrypt** | Real auth code (showcases backend skills), but standard enough to integrate with any frontend. No third-party dependency. |
| Streaming LLM clients | **httpx async streams** | Same client for Ollama, Anthropic, Bedrock, OpenAI. Each provider has different streaming wire formats — we normalize. |

---

## 3. Auth flow (in detail)

```
┌────────┐                   ┌─────────┐                ┌──────────┐
│Browser │                   │ FastAPI │                │ Postgres │
└───┬────┘                   └────┬────┘                └────┬─────┘
    │                             │                          │
    │ POST /auth/register         │                          │
    │ {email, password}           │                          │
    ├────────────────────────────►│                          │
    │                             │  bcrypt hash             │
    │                             │  INSERT INTO users       │
    │                             ├─────────────────────────►│
    │                             │◄─────────────────────────┤
    │   201 + access + refresh    │                          │
    │◄────────────────────────────┤                          │
    │                             │                          │
    │   store access in memory    │                          │
    │   store refresh in httpOnly │                          │
    │   cookie (set by server)    │                          │
    │                             │                          │
    │ GET /conversations          │                          │
    │ Authorization: Bearer ...   │                          │
    ├────────────────────────────►│                          │
    │                             │  verify JWT signature    │
    │                             │  load user from DB       │
    │                             ├─────────────────────────►│
    │                             │◄─────────────────────────┤
    │  200 + conversations[]      │                          │
    │◄────────────────────────────┤                          │
    │                             │                          │
    │   (access expires after 15m)│                          │
    │ POST /auth/refresh          │                          │
    │ (cookie sent automatically) │                          │
    ├────────────────────────────►│                          │
    │                             │  validate refresh in DB  │
    │                             │  rotate refresh          │
    │                             │  issue new access        │
    │  200 + new access           │                          │
    │◄────────────────────────────┤                          │
```

**Key design choices:**

- **Access token: 15 minutes, in-memory only.** Short-lived; XSS gets blast-radius limited.
- **Refresh token: 30 days, httpOnly cookie + DB-tracked.** httpOnly cookie blocks XSS exfiltration; DB tracking lets us revoke on logout / breach.
- **Token rotation.** Every refresh issues a new refresh token and invalidates the old. Detects token theft.
- **No "remember me" checkbox** — just sane defaults. (Simpler beats configurable.)

---

## 4. Streaming chat flow

```
Browser                    FastAPI                    Postgres        Ollama
  │                          │                           │              │
  │ POST /chat/stream        │                           │              │
  │ {conversation_id, msg}   │                           │              │
  ├─────────────────────────►│                           │              │
  │                          │  load conv messages      │              │
  │                          ├──────────────────────────►│              │
  │                          │◄──────────────────────────┤              │
  │                          │  retrieve top-K reviews  │              │
  │                          │  via pgvector ANN        │              │
  │                          ├──────────────────────────►│              │
  │                          │◄──────────────────────────┤              │
  │                          │                           │              │
  │                          │  build prompt (system+    │              │
  │                          │  history+snippets+q)      │              │
  │                          │                           │              │
  │                          │  POST /api/chat stream=1  │              │
  │                          ├──────────────────────────────────────────►│
  │                          │◄───── token, token, token ──────────────────│
  │ SSE: event=token         │                           │              │
  │ data: "..."              │                           │              │
  │◄─────────────────────────┤                           │              │
  │ ...streaming...          │                           │              │
  │                          │  (after stream ends)      │              │
  │                          │  INSERT user message      │              │
  │                          │  INSERT assistant message │              │
  │                          │  INSERT citations[]       │              │
  │                          ├──────────────────────────►│              │
  │ SSE: event=done          │                           │              │
  │ data: {message_id,...}   │                           │              │
  │◄─────────────────────────┤                           │              │
```

**Why we persist AFTER streaming completes:** if the stream is interrupted halfway, we want the partial assistant message saved so the user can see what was generated. We use a generator pattern: yield tokens to the client; in a `finally:` block, write the final state to DB.

---

## 5. Folder structure (Phase 2)

```
priceSentry/
├── docker-compose.yml                  ← updated: adds `web` service
├── .env.example                        ← updated: JWT_SECRET, NEXT_PUBLIC_API_URL
├── db/
│   ├── init.sql                        ← Phase 1 schema (existing)
│   └── 02_phase2_chat.sql              ← NEW: users, conversations, messages, citations
├── services/
│   ├── scraper/                        ← unchanged from Phase 1
│   ├── api/                            ← MAJOR refactor
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   ├── alembic.ini                 (future: migrations)
│   │   └── app/
│   │       ├── main.py                 ← app factory, mounts routers
│   │       ├── core/
│   │       │   ├── settings.py         ← centralized config
│   │       │   ├── security.py         ← bcrypt, JWT encode/decode
│   │       │   └── logging.py          ← structured request-scoped logging
│   │       ├── db/
│   │       │   ├── session.py          ← async engine + session
│   │       │   └── models.py           ← ORM models
│   │       ├── schemas/
│   │       │   ├── auth.py
│   │       │   └── chat.py
│   │       ├── api/
│   │       │   ├── deps.py             ← FastAPI deps (current_user, db)
│   │       │   ├── auth.py             ← /auth router
│   │       │   ├── conversations.py    ← /conversations router
│   │       │   ├── chat.py             ← /chat/stream SSE router
│   │       │   └── health.py
│   │       └── services/
│   │           ├── auth_service.py     ← register/login/refresh logic
│   │           ├── chat_service.py     ← persist messages, manage convos
│   │           ├── rag_service.py      ← retrieval + prompt building
│   │           └── llm_providers.py    ← unified streaming interface
│   └── web/                            ← NEW: Next.js 14 frontend
│       ├── package.json
│       ├── tsconfig.json
│       ├── tailwind.config.ts
│       ├── next.config.mjs
│       ├── Dockerfile
│       ├── .env.local.example
│       └── app/
│           ├── layout.tsx              ← root layout + providers
│           ├── page.tsx                ← redirect to /chat
│           ├── globals.css
│           ├── (auth)/
│           │   ├── layout.tsx
│           │   ├── login/page.tsx
│           │   └── register/page.tsx
│           ├── (app)/
│           │   ├── layout.tsx          ← sidebar shell
│           │   └── chat/
│           │       ├── page.tsx        ← new chat
│           │       └── [conversationId]/page.tsx
│           ├── components/
│           │   ├── chat/
│           │   │   ├── composer.tsx
│           │   │   ├── message-list.tsx
│           │   │   ├── message.tsx
│           │   │   └── citations-panel.tsx
│           │   ├── sidebar.tsx
│           │   └── ui/                 ← shadcn primitives (button, input, ...)
│           └── lib/
│               ├── api.ts              ← typed API client
│               ├── auth.ts             ← token store + interceptor
│               ├── stream.ts           ← SSE parser
│               └── types.ts
└── docs/
    ├── 10-production-architecture.md   ← THIS FILE
    └── 11-phase2-runbook.md            (how to bring up the new stack)
```

---

## 6. What ships in this delivery vs Phase 2.2 / 2.3

**Phase 2.1 (this delivery — ~30 files of working code):**
- Auth (register/login/refresh/me) with JWT + bcrypt
- Conversations CRUD
- Streaming chat over RAG via SSE
- Next.js 14 frontend with login, register, chat, citations panel
- Updated docker-compose with the `web` service
- Multi-provider LLM streaming (Ollama / Anthropic / Bedrock / OpenAI)

**Phase 2.2 (next round):**
- Conversation history / sidebar list
- Settings page (provider switcher, embedding-model picker)
- Admin dashboard + analytics page
- Feedback / thumbs-up-down on messages
- Background workers (Celery + Redis) for slow tasks
- Rate limiting (slowapi)
- Structured request logging + Prometheus metrics
- Alembic migrations replacing raw SQL

**Phase 2.3 (after that):**
- AWS Terraform (ECS Fargate + RDS + S3 + Bedrock + CloudFront)
- Kubernetes manifests + Helm chart
- GitHub Actions CI/CD (lint → test → build → deploy)
- Health checks, readiness probes, graceful shutdown
- Multi-cloud configs as a portfolio bonus (Railway, Fly.io)

This phased plan keeps each delivery debuggable. You'll have a real, demoable product after Phase 2.1, which is what recruiters watch first.
