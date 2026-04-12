"""
ChaosMesh Arena — FastAPI Application Entry Point (Hardened).

Changes from v0.1:
  - EnvPool replaces global _env (concurrent-safe)
  - JWT + API Key auth on all protected routes
  - Security headers middleware (X-Frame-Options, CSP, etc.)
  - Request body size limit (64KB)
  - Real Redis health probe
  - Prometheus /metrics endpoint
  - Strict CORS (no wildcard with credentials)
  - WebSocket auth via token query param
  - New routers: /auth, /leaderboard, /episodes
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from chaosmesh_arena.auth.middleware import require_auth
from chaosmesh_arena.auth.security_headers import RequestSizeLimitMiddleware, SecurityHeadersMiddleware
from chaosmesh_arena.auth.jwt_handler import decode_token, TokenInvalidError, TokenExpiredError
from chaosmesh_arena.config import get_settings
from chaosmesh_arena.database.base import init_db
from chaosmesh_arena.env_pool import env_pool
from chaosmesh_arena.models import HealthResponse
from server.routes.auth import router as auth_router
from server.routes.demo import router as demo_router
from server.routes.env import router as env_router
from server.routes.episodes import router as episodes_router
from server.routes.leaderboard import router as leaderboard_router
from server.routes.openenv_compat import router as openenv_compat_router
from server.ws_manager import ws_manager

log = structlog.get_logger(__name__)
_start_time = time.time()


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    import logging
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    log.info(
        "chaosmesh_starting",
        version="0.2.0",
        demo_mode=settings.demo_mode,
        db_url=settings.effective_database_url.split("@")[-1],  # hide credentials
    )

    # Initialize database tables
    await init_db()
    log.info("database_ready")

    # Start EnvPool background cleanup
    await env_pool.start()
    log.info("env_pool_ready", max_sessions=settings.max_concurrent_sessions)

    log.info("chaosmesh_ready", port=settings.server_port, version="0.2.0")
    yield

    log.info("chaosmesh_shutting_down")
    await env_pool.stop()


# ── FastAPI App ────────────────────────────────────────────────────────────────

settings = get_settings()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[settings.rate_limit_default],
)

app = FastAPI(
    title="ChaosMesh Arena",
    description=(
        "Multi-agent adversarial SRE training environment.\n\n"
        "**OpenEnv RFC 001/002/003 compliant.**\n\n"
        "## Authentication\n"
        "All endpoints require:\n"
        "- `Authorization: Bearer <jwt>` — from POST /auth/token\n"
        "- OR `X-API-Key: <key>` — your raw API key\n\n"
        "Register at `POST /auth/register` to get started."
    ),
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Security Middleware ────────────────────────────────────────────────────────
# Order matters: outermost runs last on request, first on response
app.add_middleware(
    SecurityHeadersMiddleware,
    production=bool(settings.hf_space_base_url),
)
app.add_middleware(
    RequestSizeLimitMiddleware,
    max_bytes=65536,  # 64KB
)

# ── CORS — Strict ─────────────────────────────────────────────────────────────
# IMPORTANT: allow_credentials=True requires explicit origins (no "*")
_cors_origins = [o for o in settings.cors_origins if o and o != "*"]
if not _cors_origins:
    _cors_origins = ["http://localhost:3000", "http://localhost:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "X-API-Key", "Content-Type", "Accept"],
)

# ── Prometheus Metrics ────────────────────────────────────────────────────────
try:
    from prometheus_fastapi_instrumentator import Instrumentator
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        excluded_handlers=["/health", "/metrics"],
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
    log.info("prometheus_metrics_enabled")
except ImportError:
    log.warning("prometheus_not_installed", hint="pip install prometheus-fastapi-instrumentator")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth_router)      # /auth/*
app.include_router(env_router)       # /env/*
app.include_router(openenv_compat_router)  # /reset /step /state aliases
app.include_router(demo_router)      # /demo/*
app.include_router(episodes_router)  # /episodes/*
app.include_router(leaderboard_router)  # /leaderboard/*

# ── Static Frontend ───────────────────────────────────────────────────────────
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_react(full_path: str):
        """SPA fallback — serve index.html for all non-API routes."""
        _api_prefixes = ("env/", "demo/", "auth/", "episodes/", "leaderboard/",
                         "health", "metrics", "docs", "redoc", "openapi.json",
                         "tasks", "grader", "reset", "step", "state",
                         "openenv/", "api/")
        if any(full_path.startswith(p) for p in _api_prefixes):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        index = frontend_dist / "index.html"
        if index.exists():
            return FileResponse(str(index))
        return {"error": "Frontend not built. Run: cd frontend && npm install && npm run build"}
else:
    log.warning("react_frontend_not_found", path=str(frontend_dist))

    @app.get("/", include_in_schema=False)
    async def root_fallback():
        """OpenEnv-standard root endpoint — used by validators to discover endpoints."""
        return {
            "status": "ok",
            "endpoints": ["/reset", "/step", "/state", "/tasks", "/grader"],
        }


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["meta"], include_in_schema=True)
async def health() -> HealthResponse:
    """Health check — no auth required. Probes Redis and Ollama."""
    from chaosmesh_arena.llm.ollama_client import OllamaClient

    # Real Redis probe
    redis_ok = False
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.redis_url, socket_timeout=0.5)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass

    # Real Ollama probe
    ollama_ok = False
    try:
        ollama_ok = await OllamaClient().is_available()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        version="0.2.0",
        uptime_seconds=round(time.time() - _start_time, 1),
        ollama_available=ollama_ok,
        openrouter_available=settings.openrouter_available,
        redis_connected=redis_ok,
        active_episode=None,  # no longer meaningful with EnvPool (N sessions)
    )


# ── WebSocket — Hardened ──────────────────────────────────────────────────────

@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Real-time event stream.

    Auth: Pass JWT token via query param: /ws/stream?token=<jwt>
    (WebSocket protocol does not support custom headers from browsers)
    """
    token = websocket.query_params.get("token")
    api_key = websocket.query_params.get("api_key")

    authenticated = False

    if token:
        try:
            decode_token(token)
            authenticated = True
        except (TokenInvalidError, TokenExpiredError):
            pass

    if not authenticated and api_key:
        # Legacy single shared key
        if settings.chaosmesh_api_key and api_key == settings.chaosmesh_api_key:
            authenticated = True
        else:
            # Try API key lookup
            from chaosmesh_arena.database.user_repo import UserRepository
            try:
                repo = UserRepository()
                user = await repo.get_by_api_key(api_key)
                if user:
                    authenticated = True
            except Exception:
                pass

    if not authenticated:
        await websocket.close(code=4001, reason="Unauthorized — supply ?token=<jwt> or ?api_key=<key>")
        return

    await ws_manager.connect(websocket)
    try:
        await ws_manager.send_to(websocket, "connected", {
            "message": "ChaosMesh Arena WebSocket ready",
            "clients": ws_manager.connection_count,
            "version": "0.2.0",
        })
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_to(websocket, "pong", {"active_sessions": env_pool.active_session_count})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Entry point ───────────────────────────────────────────────────────────────

def run() -> None:
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
        access_log=True,
    )


if __name__ == "__main__":
    run()
