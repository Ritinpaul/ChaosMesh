"""
ChaosMesh Arena — Auth Routes.

POST /auth/register  — create account, get first API key
POST /auth/token     — exchange API key for JWT
GET  /auth/me        — current user info
POST /auth/keys      — generate additional API key
DELETE /auth/keys/{id} — revoke a key
"""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from chaosmesh_arena.auth.jwt_handler import create_access_token
from chaosmesh_arena.auth.middleware import AuthenticatedUser, require_auth
from chaosmesh_arena.config import get_settings
from chaosmesh_arena.database.user_repo import UserRepository

router = APIRouter(prefix="/auth", tags=["auth"])


# ── Request / Response Schemas ─────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(default="", max_length=100)


class RegisterResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    plan: str
    api_key: str  # raw key shown ONCE
    message: str = "Save your API key — it won't be shown again."


class TokenRequest(BaseModel):
    api_key: str = Field(min_length=10, max_length=200)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class UserMeResponse(BaseModel):
    user_id: str
    email: str
    display_name: str
    plan: str
    episodes_this_month: int
    created_at: str


class NewKeyRequest(BaseModel):
    name: str = Field(default="New Key", max_length=100)


class KeyCreatedResponse(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    api_key: str  # raw key shown ONCE
    message: str = "Save your API key — it won't be shown again."


class KeyListItem(BaseModel):
    key_id: str
    name: str
    key_prefix: str
    created_at: str
    last_used: str | None


# ── Routes ─────────────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=RegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new account",
)
async def register(request: RegisterRequest):
    """
    Register a new user. Returns the user record and their first API key.
    The raw key is shown **once** — save it securely.
    """
    repo = UserRepository()

    # Check if email already taken
    existing = await repo.get_user_by_email(request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user, raw_key = await repo.create_user(
        email=request.email,
        display_name=request.display_name,
    )

    return RegisterResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        plan=user.plan,
        api_key=raw_key,
    )


@router.post(
    "/token",
    response_model=TokenResponse,
    summary="Exchange API key for JWT",
)
async def get_token(request: TokenRequest):
    """
    Exchange a valid API key for a short-lived JWT.
    JWT expires in 24 hours (configurable via JWT_EXPIRE_HOURS).
    """
    repo = UserRepository()
    user = await repo.get_by_api_key(request.api_key)

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key.",
        )

    settings = get_settings()
    token = create_access_token(
        subject=user.email,
        user_id=user.id,
        plan=user.plan,
        org_id=str(user.org_id) if user.org_id else None,
    )

    return TokenResponse(
        access_token=token,
        expires_in_seconds=settings.jwt_expire_hours * 3600,
    )


@router.get(
    "/me",
    response_model=UserMeResponse,
    summary="Get current user info",
)
async def me(user: AuthenticatedUser = Depends(require_auth)):
    """Return the authenticated user's profile."""
    repo = UserRepository()
    record = await repo.get_user_by_id(user.user_id)
    if not record:
        # Demo/legacy auth fallback
        return UserMeResponse(
            user_id=user.user_id,
            email=user.subject,
            display_name="Demo User",
            plan=user.plan,
            episodes_this_month=0,
            created_at=datetime.utcnow().isoformat(),
        )
    return UserMeResponse(
        user_id=str(record.id),
        email=record.email,
        display_name=record.display_name,
        plan=record.plan,
        episodes_this_month=record.episodes_this_month,
        created_at=record.created_at.isoformat(),
    )


@router.post(
    "/keys",
    response_model=KeyCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Generate a new API key",
)
async def create_key(
    request: NewKeyRequest,
    user: AuthenticatedUser = Depends(require_auth),
):
    """Generate an additional API key for the current user."""
    if user.user_id == "demo":
        raise HTTPException(status_code=403, detail="Demo users cannot create API keys.")
    repo = UserRepository()
    api_key_record, raw_key = await repo.generate_api_key(user.user_id, name=request.name)
    return KeyCreatedResponse(
        key_id=str(api_key_record.id),
        name=api_key_record.name,
        key_prefix=api_key_record.key_prefix,
        api_key=raw_key,
    )


@router.get(
    "/keys",
    response_model=list[KeyListItem],
    summary="List your API keys",
)
async def list_keys(user: AuthenticatedUser = Depends(require_auth)):
    """List all active (non-revoked) API keys for the current user."""
    if user.user_id == "demo":
        return []
    repo = UserRepository()
    keys = await repo.list_api_keys(user.user_id)
    return [
        KeyListItem(
            key_id=str(k.id),
            name=k.name,
            key_prefix=k.key_prefix,
            created_at=k.created_at.isoformat(),
            last_used=k.last_used.isoformat() if k.last_used else None,
        )
        for k in keys
    ]


@router.delete(
    "/keys/{key_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke an API key",
)
async def revoke_key(
    key_id: str,
    user: AuthenticatedUser = Depends(require_auth),
):
    """Revoke an API key. It will immediately stop working."""
    if user.user_id == "demo":
        raise HTTPException(status_code=403, detail="Demo users cannot revoke API keys.")
    repo = UserRepository()
    ok = await repo.revoke_api_key(key_id=key_id, user_id=user.user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="API key not found.")
