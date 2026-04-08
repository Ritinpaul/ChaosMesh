"""
ChaosMesh Arena — Auth Middleware (Single-User, API Key based).

Validates X-API-Key header on all protected routes.
Enforces single active session to prevent concurrent episode conflicts.
"""

from __future__ import annotations

import time
import uuid

import structlog
from fastapi import HTTPException, Query, Request, Security, status
from fastapi.security import APIKeyHeader

from chaosmesh_arena.config import get_settings

log = structlog.get_logger(__name__)


class SingleUserSessionManager:
    """
    Manages a single active session for the demo environment.

    Only one session can be active at a time. Starting a new session
    invalidates the previous one.
    """

    def __init__(self) -> None:
        self._session_id: str | None = None
        self._created_at: float = 0.0

    def create_session(self) -> str:
        session_id = str(uuid.uuid4())
        self._session_id = session_id
        self._created_at = time.time()
        log.info("session_created", session_id=session_id)
        return session_id

    def validate(self, session_id: str) -> bool:
        return self._session_id is not None and self._session_id == session_id

    def invalidate(self) -> None:
        self._session_id = None
        log.info("session_invalidated")

    @property
    def active_session_id(self) -> str | None:
        return self._session_id

    @property
    def session_age_seconds(self) -> float:
        if self._session_id is None:
            return 0.0
        return time.time() - self._created_at


# Singleton session manager
session_manager = SingleUserSessionManager()


class APIKeyAuth:
    """
    FastAPI dependency for API key validation.

    Usage:
        @app.get("/protected")
        async def endpoint(auth: None = Depends(require_api_key)):
            ...
    """

    async def __call__(self, request: Request) -> None:
        settings = get_settings()
        # Accept key from header OR query param (for WebSocket)
        api_key = (
            request.headers.get("X-API-Key")
            or request.query_params.get("api_key")
        )
        if not api_key:
            log.warning("auth_missing_key", path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing X-API-Key header or api_key query parameter",
            )
        if api_key != settings.chaosmesh_api_key:
            log.warning("auth_invalid_key", path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )


require_api_key = APIKeyAuth()

api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="ApiKeyAuth",
    description="API key required for all protected ChaosMesh Arena endpoints.",
    auto_error=False,
)


async def require_api_key(
    request: Request,
    api_key_header_value: str | None = Security(api_key_header),
    api_key_query: str | None = Query(default=None, alias="api_key"),
) -> None:
    """OpenAPI-visible API key guard used by protected HTTP routes."""
    settings = get_settings()

    api_key = api_key_header_value or api_key_query
    if not api_key:
        log.warning("auth_missing_key", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-API-Key header or api_key query parameter",
        )
    if api_key != settings.chaosmesh_api_key:
        log.warning("auth_invalid_key", path=request.url.path)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )
