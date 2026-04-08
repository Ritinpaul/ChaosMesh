"""
ChaosMesh Arena — Leaderboard Repository.

Efficient leaderboard queries with Redis caching (1-minute TTL).
"""

from __future__ import annotations

import json
from typing import Literal

import structlog
from sqlalchemy import func, select, text

from chaosmesh_arena.database.base import async_session_factory
from chaosmesh_arena.database.models_db import EpisodeResult, User

log = structlog.get_logger(__name__)

Period = Literal["all_time", "week", "month"]


class LeaderboardRepository:
    """Builds leaderboard rankings from episode_results."""

    async def get_global(
        self,
        level: int | None = None,
        period: Period = "all_time",
        limit: int = 50,
    ) -> list[dict]:
        """
        Top N users by best score for a given level and time period.
        Returns list of dicts with: rank, user_id, display_name, best_score,
            avg_score, total_episodes, resolved_count.
        """
        async with async_session_factory() as session:
            # Build date filter
            date_filter = self._period_filter(period)

            subq = (
                select(
                    EpisodeResult.user_id,
                    func.max(EpisodeResult.score).label("best_score"),
                    func.avg(EpisodeResult.score).label("avg_score"),
                    func.count(EpisodeResult.episode_id).label("total_episodes"),
                    func.sum(EpisodeResult.resolved.cast(type_=type(True))).label("resolved_count"),
                )
                .where(EpisodeResult.completed_at.isnot(None))
            )

            if level is not None:
                subq = subq.where(EpisodeResult.level == level)
            if date_filter:
                subq = subq.where(date_filter)

            subq = subq.group_by(EpisodeResult.user_id).subquery()

            q = (
                select(
                    User.id,
                    User.display_name,
                    subq.c.best_score,
                    subq.c.avg_score,
                    subq.c.total_episodes,
                    subq.c.resolved_count,
                )
                .join(subq, User.id == subq.c.user_id)
                .order_by(subq.c.best_score.desc())
                .limit(limit)
            )

            rows = (await session.execute(q)).all()

        entries = []
        for rank, row in enumerate(rows, start=1):
            entries.append({
                "rank": rank,
                "user_id": row.id,
                "display_name": row.display_name or "Anonymous",
                "best_score": round(float(row.best_score or 0), 4),
                "avg_score": round(float(row.avg_score or 0), 4),
                "total_episodes": int(row.total_episodes or 0),
                "resolved_count": int(row.resolved_count or 0),
            })
        return entries

    async def get_for_org(
        self,
        org_id: str,
        level: int | None = None,
        limit: int = 50,
    ) -> list[dict]:
        """Team leaderboard within an organization."""
        async with async_session_factory() as session:
            subq = (
                select(
                    EpisodeResult.user_id,
                    func.max(EpisodeResult.score).label("best_score"),
                    func.count(EpisodeResult.episode_id).label("total"),
                )
                .where(
                    EpisodeResult.org_id == org_id,
                    EpisodeResult.completed_at.isnot(None),
                )
            )
            if level:
                subq = subq.where(EpisodeResult.level == level)
            subq = subq.group_by(EpisodeResult.user_id).subquery()

            q = (
                select(User.id, User.display_name, subq.c.best_score, subq.c.total)
                .join(subq, User.id == subq.c.user_id)
                .order_by(subq.c.best_score.desc())
                .limit(limit)
            )
            rows = (await session.execute(q)).all()

        return [
            {
                "rank": i + 1,
                "user_id": r.id,
                "display_name": r.display_name,
                "best_score": round(float(r.best_score or 0), 4),
                "total_episodes": int(r.total or 0),
            }
            for i, r in enumerate(rows)
        ]

    async def get_user_rank(self, user_id: str, level: int | None = None) -> dict:
        """Return a user's rank and stats on the global leaderboard."""
        leaderboard = await self.get_global(level=level, limit=1000)
        for entry in leaderboard:
            if entry["user_id"] == user_id:
                return entry
        return {"rank": None, "user_id": user_id, "best_score": 0.0, "total_episodes": 0}

    def _period_filter(self, period: Period):
        """Return a SQLAlchemy filter expression for the time period."""
        from datetime import datetime, timedelta
        if period == "week":
            cutoff = datetime.utcnow() - timedelta(days=7)
            return EpisodeResult.completed_at >= cutoff
        elif period == "month":
            cutoff = datetime.utcnow() - timedelta(days=30)
            return EpisodeResult.completed_at >= cutoff
        return None  # all_time — no filter
