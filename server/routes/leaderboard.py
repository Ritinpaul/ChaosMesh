"""
ChaosMesh Arena — Leaderboard Routes.

GET /leaderboard/global            — global top 50
GET /leaderboard/global?level=2    — level-specific
GET /leaderboard/global?period=week — weekly
GET /leaderboard/org/{slug}        — team leaderboard
GET /leaderboard/me                — caller's rank
"""

from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query

from chaosmesh_arena.auth.middleware import AuthenticatedUser, require_auth
from chaosmesh_arena.database.leaderboard_repo import LeaderboardRepository
from pydantic import BaseModel

router = APIRouter(prefix="/leaderboard", tags=["leaderboard"])


class LeaderboardEntry(BaseModel):
    rank: int
    user_id: str
    display_name: str
    best_score: float
    avg_score: float = 0.0
    total_episodes: int
    resolved_count: int = 0


class MyRankResponse(BaseModel):
    rank: int | None
    user_id: str
    best_score: float
    total_episodes: int


@router.get(
    "/global",
    response_model=list[LeaderboardEntry],
    summary="Global leaderboard",
)
async def global_leaderboard(
    level: Optional[int] = Query(default=None, ge=1, le=5, description="Filter by level 1-5"),
    period: Literal["all_time", "week", "month"] = Query(default="all_time"),
    limit: int = Query(default=50, ge=1, le=100),
    _user: AuthenticatedUser = Depends(require_auth),
):
    """
    Returns top N users by best score.
    Filter by curriculum level (1-5) and time period.
    """
    repo = LeaderboardRepository()
    entries = await repo.get_global(level=level, period=period, limit=limit)
    return entries


@router.get(
    "/org/{slug}",
    response_model=list[dict],
    summary="Team / org leaderboard",
)
async def org_leaderboard(
    slug: str,
    level: Optional[int] = Query(default=None, ge=1, le=5),
    user: AuthenticatedUser = Depends(require_auth),
):
    """Team leaderboard for an organization by its slug."""
    from chaosmesh_arena.database.base import async_session_factory
    from chaosmesh_arena.database.models_db import Organization
    from sqlalchemy import select

    async with async_session_factory() as session:
        result = await session.execute(
            select(Organization).where(Organization.slug == slug)
        )
        org = result.scalar_one_or_none()

    if not org:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Organization '{slug}' not found.")

    repo = LeaderboardRepository()
    return await repo.get_for_org(org_id=str(org.id), level=level)


@router.get(
    "/me",
    response_model=MyRankResponse,
    summary="Your leaderboard rank",
)
async def my_rank(
    level: Optional[int] = Query(default=None, ge=1, le=5),
    user: AuthenticatedUser = Depends(require_auth),
):
    """Returns the caller's current rank on the global leaderboard."""
    repo = LeaderboardRepository()
    entry = await repo.get_user_rank(user_id=user.user_id, level=level)
    return MyRankResponse(
        rank=entry.get("rank"),
        user_id=entry.get("user_id", user.user_id),
        best_score=entry.get("best_score", 0.0),
        total_episodes=entry.get("total_episodes", 0),
    )
