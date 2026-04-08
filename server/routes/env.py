"""
ChaosMesh Arena — Environment API Routes (RFC 001/002/003) — Hardened.

Uses EnvPool for per-user concurrent session management.
All routes require authentication.
Free plan limited to Level 1-3 and 100 episodes/month.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status

from chaosmesh_arena.auth.middleware import AuthenticatedUser, require_auth
from chaosmesh_arena.config import get_settings
from chaosmesh_arena.database.episode_repo import EpisodeRepository
from chaosmesh_arena.database.user_repo import UserRepository
from chaosmesh_arena.env_pool import env_pool
from chaosmesh_arena.models import (
    ActionModel,
    FullStateModel,
    InjectRequest,
    ObservationModel,
    ResetRequest,
    ResetResponse,
    StepRequest,
    StepResult,
)
from server.ws_manager import ws_manager

router = APIRouter(prefix="/env", tags=["environment"])

# Per-user session mapping: user_id → session_id
# Allows one active session per user (extendable to N per org)
_user_sessions: dict[str, str] = {}


def _get_session_id(user_id: str) -> str:
    session_id = _user_sessions.get(user_id)
    if not session_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active session. Call POST /env/reset first.",
        )
    return session_id


@router.post(
    "/reset",
    summary="RFC 001 — Initialize a new episode",
)
async def reset(
    request: ResetRequest | None = None,
    user: AuthenticatedUser = Depends(require_auth),
) -> Response:
    """
    Initialize a new episode at the given curriculum level.
    Free plan: levels 1–3 only. Pro: levels 1–5.
    Free plan: max 100 episodes/month.
    """
    settings = get_settings()
    request = request or ResetRequest()

    # ── Plan enforcement ───────────────────────────────────────────────────────
    if request.level.value > 3 and not user.is_pro:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Levels 4 and 5 require a Pro plan. Upgrade at /billing/upgrade",
        )

    # ── Episode quota (free plan) ──────────────────────────────────────────────
    if not user.is_pro and user.user_id != "demo":
        user_repo = UserRepository()
        user_record = await user_repo.get_user_by_id(user.user_id)
        if user_record:
            count = user_record.episodes_this_month
            if count >= settings.free_plan_episodes_per_month:
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail=(
                        f"Monthly episode limit reached ({settings.free_plan_episodes_per_month}). "
                        "Upgrade to Pro for unlimited episodes."
                    ),
                )

    # ── Close existing session if any ──────────────────────────────────────────
    old_session = _user_sessions.get(user.user_id)
    if old_session:
        try:
            await env_pool.close_session(old_session)
        except Exception:
            pass

    # ── Create new session ─────────────────────────────────────────────────────
    try:
        session_id = await env_pool.create_session(user_id=user.user_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))

    _user_sessions[user.user_id] = session_id

    # ── Reset the env ──────────────────────────────────────────────────────────
    obs, info = await env_pool.reset(session_id, level=request.level.value)
    episode_id = info.get("episode_id", "")

    # ── Persist episode start ──────────────────────────────────────────────────
    if user.user_id != "demo":
        ep_repo = EpisodeRepository()
        user_repo = UserRepository()
        await asyncio.gather(
            ep_repo.create(episode_id, user.user_id, level=request.level.value, org_id=user.org_id),
            user_repo.increment_episode_count(user.user_id),
        )

    result = ResetResponse(episode_id=episode_id, observation=obs)
    await ws_manager.broadcast("episode_started", {
        "episode_id": episode_id,
        "level": request.level.value,
        "user_id": user.user_id,
    })

    return Response(content=result.model_dump_json(), media_type="application/json")


@router.post(
    "/step",
    summary="RFC 002 — Submit an agent action",
)
async def step(
    request: StepRequest,
    user: AuthenticatedUser = Depends(require_auth),
) -> Response:
    """Submit an agent action and receive the next observation and reward."""
    session_id = _get_session_id(user.user_id)

    # Validate episode_id matches active session
    active_episode = env_pool.get_episode_id(session_id)
    if request.episode_id != active_episode:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Episode ID mismatch. Active: {active_episode}",
        )

    obs, reward, terminated, truncated, info = await env_pool.step(session_id, request.action)

    result = StepResult(
        observation=obs,
        reward=reward,
        terminated=terminated,
        truncated=truncated,
        info=info,
    )

    await ws_manager.broadcast("step_complete", {
        "step": info.get("step", 0),
        "agent": str(request.action.agent),
        "action_type": str(request.action.action_type),
        "reward": reward.total,
        "terminated": terminated,
        "truncated": truncated,
        "user_id": user.user_id,
    })

    if terminated or truncated:
        cumulative_reward = info.get("cumulative_reward", 0.0)
        await _finalize_episode(
            episode_id=active_episode,
            user_id=user.user_id,
            info=info,
            terminated=terminated,
        )
        await ws_manager.broadcast("episode_ended", {
            "episode_id": active_episode,
            "status": "resolved" if terminated else "timed_out",
            "cumulative_reward": cumulative_reward,
            "steps": info.get("step", 0),
        })

    return Response(content=result.model_dump_json(), media_type="application/json")


@router.get(
    "/state",
    summary="RFC 003 — Get full internal state",
)
async def get_state(user: AuthenticatedUser = Depends(require_auth)) -> Response:
    """Return the complete internal environment state including ground truth."""
    session_id = _get_session_id(user.user_id)
    state = await asyncio.to_thread(env_pool.get_state, session_id)
    return Response(content=state.model_dump_json(), media_type="application/json")


@router.get(
    "/render",
    summary="Get visualization data for the dashboard",
)
async def render(user: AuthenticatedUser = Depends(require_auth)) -> dict:
    """Return cluster state as dict — optimized for Plotly/D3 rendering."""
    session_id = _user_sessions.get(user.user_id)
    if not session_id:
        return {"status": "idle", "cluster": {}}
    try:
        render_data = await asyncio.to_thread(env_pool.get_render, session_id)
        return render_data
    except KeyError:
        return {"status": "idle", "cluster": {}}


@router.get(
    "/session",
    summary="Get current session info",
)
async def session_info(user: AuthenticatedUser = Depends(require_auth)) -> dict:
    """Return session metadata for the current user."""
    session_id = _user_sessions.get(user.user_id)
    if not session_id:
        return {"active": False}
    try:
        return {"active": True, **env_pool.get_session_info(session_id)}
    except KeyError:
        return {"active": False}


@router.delete(
    "/session",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Close current session",
)
async def close_session(user: AuthenticatedUser = Depends(require_auth)):
    """Gracefully close the current session and free resources."""
    session_id = _user_sessions.pop(user.user_id, None)
    if session_id:
        await env_pool.close_session(session_id)


# ── Internal helpers ───────────────────────────────────────────────────────────

async def _finalize_episode(
    episode_id: str,
    user_id: str,
    info: dict,
    terminated: bool,
) -> None:
    """Persist episode results on completion (fire-and-forget)."""
    if user_id == "demo":
        return
    try:
        ep_repo = EpisodeRepository()
        await ep_repo.complete(
            episode_id=episode_id,
            cumulative_reward=info.get("cumulative_reward", 0.0),
            mttr_minutes=info.get("sim_time_minutes", 0.0),
            steps=info.get("step", 0),
            resolved=terminated,
            action_log=info.get("action_log", []),
            level=info.get("level", 1),
        )
    except Exception as exc:
        import structlog
        structlog.get_logger().error("episode_finalize_error", error=str(exc))
