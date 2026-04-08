"""
ChaosMesh Arena — Episode Repository.

Stores and retrieves episode results for replay and leaderboard.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

import structlog
from sqlalchemy import select, update

from chaosmesh_arena.database.base import async_session_factory
from chaosmesh_arena.database.models_db import EpisodeResult

log = structlog.get_logger(__name__)

# Per-level theoretical maximum cumulative reward (used for normalization)
_LEVEL_MAX_REWARD: dict[int, float] = {
    1: 25.0,
    2: 35.0,
    3: 45.0,
    4: 60.0,
    5: 80.0,
}


class EpisodeRepository:
    """Async repository for episode storage, retrieval, and replay."""

    async def create(
        self,
        episode_id: str,
        user_id: str,
        level: int,
        org_id: str | None = None,
    ) -> EpisodeResult:
        """Insert a new in-progress episode record."""
        async with async_session_factory() as session:
            record = EpisodeResult(
                episode_id=episode_id,
                user_id=user_id,
                org_id=org_id,
                level=level,
            )
            session.add(record)
            await session.commit()
            await session.refresh(record)
        return record

    async def complete(
        self,
        episode_id: str,
        cumulative_reward: float,
        mttr_minutes: float,
        steps: int,
        resolved: bool,
        action_log: list[dict],
        level: int,
    ) -> Optional[EpisodeResult]:
        """Mark an episode as complete and compute normalized score."""
        max_reward = _LEVEL_MAX_REWARD.get(level, 25.0)
        score = max(0.0, min(1.0, cumulative_reward / max_reward))

        async with async_session_factory() as session:
            await session.execute(
                update(EpisodeResult)
                .where(EpisodeResult.episode_id == episode_id)
                .values(
                    score=round(score, 4),
                    cumulative_reward=cumulative_reward,
                    mttr_minutes=mttr_minutes,
                    steps=steps,
                    resolved=resolved,
                    action_log=action_log,
                    completed_at=datetime.utcnow(),
                )
            )
            await session.commit()
            result = await session.execute(
                select(EpisodeResult).where(EpisodeResult.episode_id == episode_id)
            )
            return result.scalar_one_or_none()

    async def get(self, episode_id: str) -> Optional[EpisodeResult]:
        async with async_session_factory() as session:
            result = await session.execute(
                select(EpisodeResult).where(EpisodeResult.episode_id == episode_id)
            )
            return result.scalar_one_or_none()

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 20,
        level: int | None = None,
    ) -> list[EpisodeResult]:
        async with async_session_factory() as session:
            q = (
                select(EpisodeResult)
                .where(EpisodeResult.user_id == user_id)
                .order_by(EpisodeResult.created_at.desc())
                .limit(limit)
            )
            if level is not None:
                q = q.where(EpisodeResult.level == level)
            result = await session.execute(q)
            return list(result.scalars().all())
