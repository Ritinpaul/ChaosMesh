"""
ChaosMesh Arena — Episode History & Replay Routes.

GET  /episodes/           — list caller's episodes
GET  /episodes/{id}       — get single episode result
GET  /episodes/{id}/replay — stream replay events
GET  /episodes/{id}/report — HTML post-mortem report
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from chaosmesh_arena.auth.middleware import AuthenticatedUser, require_auth
from chaosmesh_arena.database.episode_repo import EpisodeRepository
from chaosmesh_arena.reporting.html_reporter import generate_episode_report

router = APIRouter(prefix="/episodes", tags=["episodes"])


class EpisodeSummary(BaseModel):
    episode_id: str
    level: int
    score: float
    cumulative_reward: float
    mttr_minutes: float
    steps: int
    resolved: bool
    created_at: str
    completed_at: str | None


@router.get(
    "/",
    response_model=list[EpisodeSummary],
    summary="List your episode history",
)
async def list_episodes(
    limit: int = Query(default=20, ge=1, le=100),
    level: Optional[int] = Query(default=None, ge=1, le=5),
    user: AuthenticatedUser = Depends(require_auth),
):
    """List your most recent episodes, newest first."""
    repo = EpisodeRepository()
    records = await repo.list_for_user(user_id=user.user_id, limit=limit, level=level)
    return [
        EpisodeSummary(
            episode_id=r.episode_id,
            level=r.level,
            score=r.score,
            cumulative_reward=r.cumulative_reward,
            mttr_minutes=r.mttr_minutes,
            steps=r.steps,
            resolved=r.resolved,
            created_at=r.created_at.isoformat(),
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in records
    ]


@router.get(
    "/{episode_id}",
    response_model=EpisodeSummary,
    summary="Get episode result",
)
async def get_episode(
    episode_id: str,
    user: AuthenticatedUser = Depends(require_auth),
):
    """Get the result of a specific episode. Must belong to caller."""
    repo = EpisodeRepository()
    record = await repo.get(episode_id)
    if not record:
        raise HTTPException(status_code=404, detail="Episode not found.")
    if record.user_id and record.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    return EpisodeSummary(
        episode_id=record.episode_id,
        level=record.level,
        score=record.score,
        cumulative_reward=record.cumulative_reward,
        mttr_minutes=record.mttr_minutes,
        steps=record.steps,
        resolved=record.resolved,
        created_at=record.created_at.isoformat(),
        completed_at=record.completed_at.isoformat() if record.completed_at else None,
    )


@router.get(
    "/{episode_id}/replay",
    summary="Replay episode as event stream",
)
async def replay_episode(
    episode_id: str,
    user: AuthenticatedUser = Depends(require_auth),
):
    """
    Returns the full action log for step-by-step replay.
    Each item in the list is one step: {step, agent, action_type, target, reward}.
    """
    repo = EpisodeRepository()
    record = await repo.get(episode_id)
    if not record:
        raise HTTPException(status_code=404, detail="Episode not found.")
    if record.user_id and record.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")
    if not record.action_log:
        raise HTTPException(status_code=404, detail="No action log available for this episode.")

    return {
        "episode_id": episode_id,
        "level": record.level,
        "total_steps": record.steps,
        "score": record.score,
        "actions": record.action_log,
    }


@router.get(
    "/{episode_id}/report",
    response_class=HTMLResponse,
    summary="HTML post-mortem report",
)
async def episode_report(
    episode_id: str,
    user: AuthenticatedUser = Depends(require_auth),
):
    """
    Generate a self-contained HTML post-mortem report for an episode.
    Includes: score timeline, N+1 alerts, scale risks, action breakdown.
    Requires Pro plan.
    """
    if not user.is_pro:
        raise HTTPException(
            status_code=402,
            detail="HTML reports require a Pro plan. Upgrade at /billing/upgrade",
        )

    repo = EpisodeRepository()
    record = await repo.get(episode_id)
    if not record:
        raise HTTPException(status_code=404, detail="Episode not found.")
    if record.user_id and record.user_id != user.user_id:
        raise HTTPException(status_code=403, detail="Access denied.")

    html = await generate_episode_report(record)
    return HTMLResponse(content=html, status_code=200)
