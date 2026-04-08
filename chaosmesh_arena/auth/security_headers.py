"""
ChaosMesh Arena — Security Headers Middleware.

Adds hardened HTTP security headers to every response.
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    Inject security headers on every HTTP response.

    Headers applied:
    - X-Content-Type-Options: prevents MIME sniffing
    - X-Frame-Options: prevents clickjacking
    - X-XSS-Protection: legacy XSS filter
    - Referrer-Policy: controls referrer leakage
    - Permissions-Policy: disables unused browser features
    - Content-Security-Policy: restricts resource origins
    - Strict-Transport-Security: enforces HTTPS (prod only)
    """

    def __init__(self, app, production: bool = False) -> None:
        super().__init__(app)
        self._production = production

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=(), payment=()"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self' ws: wss:;"
        )

        if self._production:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )

        # Remove server fingerprinting headers
        response.headers.pop("server", None)
        response.headers.pop("x-powered-by", None)

        return response


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject request bodies larger than max_bytes (default 64KB)."""

    def __init__(self, app, max_bytes: int = 65536) -> None:
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > self._max_bytes:
            return Response(
                content=f'{{"detail":"Request body too large (max {self._max_bytes} bytes)"}}',
                status_code=413,
                media_type="application/json",
            )
        return await call_next(request)
