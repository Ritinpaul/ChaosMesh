"""
ChaosMesh SDK — Typed Exceptions.
"""

from __future__ import annotations


class ChaosMeshError(Exception):
    """Base exception for all SDK errors."""


class AuthError(ChaosMeshError):
    """Authentication failed — invalid API key or expired JWT."""


class TokenExpiredError(ChaosMeshError):
    """JWT token has expired. Call client.refresh_token() or re-authenticate."""


class EpisodeConflict(ChaosMeshError):
    """Episode ID mismatch — another session is active."""


class EpisodeNotStarted(ChaosMeshError):
    """No active episode. Call episode.reset() or use the Episode context manager."""


class RateLimitError(ChaosMeshError):
    """Too many requests. Retry after the specified delay."""

    def __init__(self, message: str = "Rate limit exceeded", retry_after: float = 60.0) -> None:
        super().__init__(message)
        self.retry_after = retry_after


class PlanLimitError(ChaosMeshError):
    """
    Feature requires a higher plan.
    Upgrade at https://chaosmesh.io/billing
    """


class ServerError(ChaosMeshError):
    """Unexpected server error (5xx)."""

    def __init__(self, status_code: int, detail: str = "") -> None:
        super().__init__(f"Server error {status_code}: {detail}")
        self.status_code = status_code


class ConnectionError(ChaosMeshError):
    """Cannot connect to ChaosMesh server."""
