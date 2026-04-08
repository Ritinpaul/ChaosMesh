"""
ChaosMesh Arena — FastAPI Application Entry Point.

Mounts all routers, WebSocket endpoint, auth middleware,
CORS config, rate limiting, and lifespan startup/shutdown.
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from pathlib import Path

from chaosmesh_arena.auth.middleware import require_api_key
from chaosmesh_arena.config import get_settings
from chaosmesh_arena.memory.episode_store import EpisodeStore
from chaosmesh_arena.models import HealthResponse
from server.routes.demo import router as demo_router
from server.routes.env import router as env_router
from server.ws_manager import ws_manager
# Lazy import to avoid pandas circular dependency at startup
# from dashboard.app import mount_gradio_app

log = structlog.get_logger(__name__)

_start_time = time.time()
_episode_store: EpisodeStore | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _episode_store
    settings = get_settings()

    # Configure structlog
    import logging
    logging.basicConfig(level=getattr(logging, settings.log_level, logging.INFO))

    log.info(
        "chaosmesh_starting",
        version="0.1.0",
        demo_mode=settings.demo_mode,
        ollama_url=settings.ollama_base_url,
        openrouter=settings.openrouter_available,
    )

    # Initialize SQLite episode store
    _episode_store = EpisodeStore()
    await _episode_store.init_db()

    log.info("episode_store_ready")
    log.info("chaosmesh_ready", port=settings.server_port)
    yield

    log.info("chaosmesh_shutting_down")


# ── FastAPI App ────────────────────────────────────────────────────────────────

settings = get_settings()

limiter = Limiter(key_func=get_remote_address, default_limits=["10/second"])

app = FastAPI(
    title="ChaosMesh Arena",
    description=(
        "Multi-agent adversarial SRE training environment for OpenEnv.\n\n"
        "**OpenEnv RFC 001/002/003 compliant.**\n\n"
        "Authenticate all requests with `X-API-Key: <your_key>` header."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── CORS ────────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────────
app.include_router(env_router)
app.include_router(demo_router)

# ── Serve React Frontend ──────────────────────────────────────────────────────────
# Serve static files from React build
frontend_dist = Path(__file__).parent.parent / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(frontend_dist / "assets")), name="assets")
    
    @app.get("/{full_path:path}")
    async def serve_react(full_path: str):
        """Serve React app for all non-API routes."""
        if full_path == "health":
            return await health()

        # If it's an API route, let FastAPI handle it
        if full_path.startswith(("env/", "demo/", "health", "docs", "redoc", "openapi.json")):
            return {"detail": "Not Found"}
        
        # Serve index.html for all other routes (SPA routing)
        index_file = frontend_dist / "index.html"
        if index_file.exists():
            return FileResponse(str(index_file))
        else:
            return {"error": "Frontend not built. Run: cd frontend && npm install && npm run build"}
else:
    log.warning("react_frontend_not_found", path=str(frontend_dist))


# ── Health ───────────────────────────────────────────────────────────────────────
@app.get("/health", response_model=HealthResponse, tags=["meta"])
async def health() -> HealthResponse:
    """Health check — no auth required."""
    from chaosmesh_arena.llm.ollama_client import OllamaClient
    from server.routes.env import _current_episode_id

    ollama_ok = False
    try:
        ollama_ok = await OllamaClient().is_available()
    except Exception:
        pass

    return HealthResponse(
        status="ok",
        version="0.1.0",
        uptime_seconds=round(time.time() - _start_time, 1),
        ollama_available=ollama_ok,
        openrouter_available=settings.openrouter_available,
        redis_connected=True,  # Simplified — full check in production
        active_episode=_current_episode_id,
    )


# ── WebSocket Endpoint ────────────────────────────────────────────────────────────
@app.websocket("/ws/stream")
async def websocket_stream(websocket: WebSocket):
    """
    Real-time event stream to dashboard.
    Auth: pass api_key query param: /ws/stream?api_key=<key>
    """
    # Validate API key from query param
    api_key = websocket.query_params.get("api_key")
    if api_key != settings.chaosmesh_api_key:
        await websocket.close(code=4001, reason="Invalid API key")
        return

    await ws_manager.connect(websocket)
    try:
        # Send current state on connect
        await ws_manager.send_to(websocket, "connected", {
            "message": "ChaosMesh Arena WebSocket ready",
            "clients": ws_manager.connection_count,
        })
        # Keep alive — listen for any client messages (ping/pong)
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await ws_manager.send_to(websocket, "pong", {})
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)


# ── Entry point ───────────────────────────────────────────────────────────────────
def run() -> None:
    import uvicorn
    settings = get_settings()
    uvicorn.run(
        "server.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
