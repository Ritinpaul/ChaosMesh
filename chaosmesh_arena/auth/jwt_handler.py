"""
ChaosMesh Arena — JWT Handler.

Creates and validates JWT access tokens.
API keys are hashed with bcrypt — never stored in plaintext.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError
from passlib.context import CryptContext

log = structlog.get_logger(__name__)

# bcrypt context for API key hashing
_pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── API Key helpers ────────────────────────────────────────────────────────────

def generate_api_key(prefix: str = "cm_live_") -> str:
    """Generate a cryptographically secure API key."""
    return f"{prefix}{secrets.token_urlsafe(32)}"


def hash_api_key(raw_key: str) -> str:
    """Return bcrypt hash of raw API key. Store this, never the raw key."""
    return _pwd_ctx.hash(raw_key)


def verify_api_key(raw_key: str, hashed_key: str) -> bool:
    """Constant-time comparison of raw key against stored hash."""
    try:
        return _pwd_ctx.verify(raw_key, hashed_key)
    except Exception:
        return False


def get_key_prefix(raw_key: str) -> str:
    """Return the safe displayable prefix (first 12 chars) of a key."""
    return raw_key[:12] + "..." if len(raw_key) > 12 else raw_key


# ── JWT helpers ────────────────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    user_id: str,
    plan: str = "free",
    org_id: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Create a signed JWT access token."""
    from chaosmesh_arena.config import get_settings
    settings = get_settings()

    expire = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours)
    payload: dict[str, Any] = {
        "sub": subject,
        "user_id": user_id,
        "plan": plan,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": "access",
    }
    if org_id:
        payload["org_id"] = org_id
    if extra:
        payload.update(extra)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    """
    Decode and validate a JWT token.

    Raises:
        TokenExpiredError: if token has expired
        TokenInvalidError: if token signature/format is invalid
    """
    from chaosmesh_arena.config import get_settings
    settings = get_settings()

    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except ExpiredSignatureError:
        raise TokenExpiredError("Token has expired")
    except JWTError as exc:
        raise TokenInvalidError(f"Invalid token: {exc}")


# ── Custom exceptions ──────────────────────────────────────────────────────────

class TokenExpiredError(Exception):
    """JWT token has expired."""


class TokenInvalidError(Exception):
    """JWT token is malformed or signature invalid."""
