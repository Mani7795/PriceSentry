"""FastAPI application factory — PriceSentry API (Phase 2)."""
from __future__ import annotations

import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api import auth, chat, conversations, health
from app.core.logging import configure_logging, get_logger
from app.core.settings import settings

configure_logging()
log = get_logger("app.main")


def create_app() -> FastAPI:
    app = FastAPI(
        title=f"{settings.app_name} API",
        version="0.2.0",
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # ── CORS ─────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-Id"],
    )

    # ── Request ID + access log ──────────────────────────────────
    @app.middleware("http")
    async def request_id_mw(request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        request.state.request_id = req_id
        log.info("request.start", method=request.method, path=request.url.path, req_id=req_id)
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        log.info("request.end", status=response.status_code, path=request.url.path, req_id=req_id)
        return response

    # ── Global exception handler ─────────────────────────────────
    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception):
        log.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(status_code=500, content={"detail": "internal error"})

    # ── Routers ──────────────────────────────────────────────────
    prefix = settings.api_v1_prefix
    app.include_router(health.router)                              # /healthz, /readyz, /api/v1/stats
    app.include_router(auth.router, prefix=prefix)                 # /api/v1/auth/*
    app.include_router(conversations.router, prefix=prefix)        # /api/v1/conversations
    app.include_router(chat.router, prefix=prefix)                 # /api/v1/chat/stream

    return app


app = create_app()
