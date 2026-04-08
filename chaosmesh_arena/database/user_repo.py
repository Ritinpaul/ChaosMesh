"""
ChaosMesh Arena — User Repository.

All user / API key DB operations.
Passwords/keys are NEVER stored in plaintext.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

import structlog
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload

from chaosmesh_arena.auth.jwt_handler import (
    generate_api_key,
    get_key_prefix,
    hash_api_key,
    verify_api_key,
)
from chaosmesh_arena.database.base import async_session_factory
from chaosmesh_arena.database.models_db import APIKey, Organization, User

log = structlog.get_logger(__name__)


class UserRepository:
    """Async repository for user and API key management."""

    async def create_user(
        self,
        email: str,
        display_name: str = "",
        plan: str = "free",
    ) -> tuple[User, str]:
        """
        Create a new user and generate their first API key.

        Returns:
            (User ORM record, raw_api_key string)
            The raw key is returned ONCE — store it safely.
        """
        raw_key = generate_api_key("cm_live_")
        key_hash = hash_api_key(raw_key)
        prefix = get_key_prefix(raw_key)

        async with async_session_factory() as session:
            user = User(
                email=email,
                display_name=display_name or email.split("@")[0],
                plan=plan,
            )
            session.add(user)
            await session.flush()  # get user.id

            api_key = APIKey(
                user_id=user.id,
                key_hash=key_hash,
                key_prefix=prefix,
                name="Default",
            )
            session.add(api_key)
            await session.commit()
            await session.refresh(user)

        log.info("user_created", user_id=user.id, email=email, plan=plan)
        return user, raw_key

    async def get_user_by_email(self, email: str) -> Optional[User]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.email == email, User.is_active == True)
            )
            return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[User]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(User).where(User.id == user_id, User.is_active == True)
            )
            return result.scalar_one_or_none()

    async def get_by_api_key(self, raw_key: str) -> Optional[User]:
        """
        Look up a user by their raw API key.
        Uses bcrypt comparison — safe against timing attacks.
        """
        if not raw_key or len(raw_key) < 10:
            return None

        prefix = get_key_prefix(raw_key)
        async with async_session_factory() as session:
            # Narrow by prefix first (avoids full-table bcrypt scan)
            result = await session.execute(
                select(APIKey)
                .options(selectinload(APIKey.user))
                .where(
                    APIKey.key_prefix == prefix,
                    APIKey.revoked == False,
                )
            )
            candidates = result.scalars().all()

        for candidate in candidates:
            if verify_api_key(raw_key, candidate.key_hash):
                # Update last_used (fire and forget)
                await self._touch_key(str(candidate.id))
                if candidate.user and candidate.user.is_active:
                    return candidate.user
        return None

    async def generate_api_key(
        self,
        user_id: str,
        name: str = "New Key",
    ) -> tuple[APIKey, str]:
        """Generate an additional API key for an existing user."""
        raw_key = generate_api_key("cm_live_")
        key_hash = hash_api_key(raw_key)
        prefix = get_key_prefix(raw_key)

        async with async_session_factory() as session:
            api_key = APIKey(
                user_id=user_id,
                key_hash=key_hash,
                key_prefix=prefix,
                name=name,
            )
            session.add(api_key)
            await session.commit()
            await session.refresh(api_key)

        log.info("api_key_generated", user_id=user_id, key_id=api_key.id)
        return api_key, raw_key

    async def revoke_api_key(self, key_id: str, user_id: str) -> bool:
        """Revoke an API key (soft delete). Returns True if found and revoked."""
        async with async_session_factory() as session:
            result = await session.execute(
                update(APIKey)
                .where(APIKey.id == key_id, APIKey.user_id == user_id)
                .values(revoked=True)
            )
            await session.commit()
            return result.rowcount > 0

    async def list_api_keys(self, user_id: str) -> list[APIKey]:
        """List all active API keys for a user (hashes not returned)."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(APIKey)
                .where(APIKey.user_id == user_id, APIKey.revoked == False)
                .order_by(APIKey.created_at.desc())
            )
            return list(result.scalars().all())

    async def update_plan(self, user_id: str, plan: str) -> None:
        async with async_session_factory() as session:
            await session.execute(
                update(User).where(User.id == user_id).values(plan=plan)
            )
            await session.commit()
        log.info("user_plan_updated", user_id=user_id, plan=plan)

    async def increment_episode_count(self, user_id: str) -> int:
        """Increment monthly episode count. Returns new count."""
        async with async_session_factory() as session:
            result = await session.execute(
                select(User.episodes_this_month).where(User.id == user_id)
            )
            current = result.scalar_one_or_none() or 0
            new_count = current + 1
            await session.execute(
                update(User).where(User.id == user_id).values(episodes_this_month=new_count)
            )
            await session.commit()
        return new_count

    async def _touch_key(self, key_id: str) -> None:
        try:
            async with async_session_factory() as session:
                await session.execute(
                    update(APIKey)
                    .where(APIKey.id == key_id)
                    .values(last_used=datetime.utcnow())
                )
                await session.commit()
        except Exception:
            pass  # Non-critical
