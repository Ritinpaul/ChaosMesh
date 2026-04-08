"""
ChaosMesh Arena — Environment API Routes (RFC 001/002/003).

POST /env/reset  — RFC 001: Initialize episode
POST /env/step   — RFC 002: Submit agent action
GET  /env/state  — RFC 003: Get full internal state
GET  /env/render — Visualization data for dashboard
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from chaosmesh_arena.auth.middleware import require_api_key
from chaosmesh_arena.env import ChaosMeshArenaEnv
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

# Shared environment instance (single-user demo)
_env: ChaosMeshArenaEnv | None = None
_current_episode_id: str | None = None


def get_env() -> ChaosMeshArenaEnv:
    global _env
    if _env is None:
        _env = ChaosMeshArenaEnv()
    return _env


@router.post(
    "/reset",
    summary="RFC 001 — Initialize a new episode",
    dependencies=[Depends(require_api_key)],
)
async def reset(request: ResetRequest) -> Response:
    """
    Initialize a new episode at the given curriculum level.
    Returns the initial observation and episode ID.
    """
    global _current_episode_id
    env = get_env()
    obs, info = env.reset(options={"level": request.level.value})
    _current_episode_id = info["episode_id"]

    result = ResetResponse(episode_id=_current_episode_id, observation=obs)

    # Broadcast episode start to dashboard
    await ws_manager.broadcast("episode_started", {
        "episode_id": _current_episode_id,
        "level": request.level.value,
    })
    return Response(
        content=result.model_dump_json(),
        media_type="application/json",
    )


@router.post(
    "/step",
    summary="RFC 002 — Submit an agent action",
    dependencies=[Depends(require_api_key)],
)
async def step(request: StepRequest) -> Response:
    """Submit an agent action and receive the next observation and reward."""
    env = get_env()
    if not env._episode_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active episode. Call /env/reset first.",
        )
    if request.episode_id != env._episode_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Episode ID mismatch. Active: {env._episode_id}",
        )

    obs, reward, terminated, truncated, info = env.step(request.action)
    result = StepResult(
        observation=obs,
        reward=reward,
        terminated=terminated,
        truncated=truncated,
        info=info,
    )

    # Broadcast step event
    await ws_manager.broadcast("step_complete", {
        "step": env._step,
        "agent": str(request.action.agent),
        "action_type": str(request.action.action_type),
        "reward": reward.total,
        "terminated": terminated,
        "truncated": truncated,
    })

    if terminated or truncated:
        await ws_manager.broadcast("episode_ended", {
            "episode_id": env._episode_id,
            "status": "resolved" if terminated else "timed_out",
            "cumulative_reward": env._cumulative_reward,
            "steps": env._step,
        })

    return Response(content=result.model_dump_json(), media_type="application/json")


@router.get(
    "/state",
    summary="RFC 003 — Get full internal state",
    dependencies=[Depends(require_api_key)],
)
async def get_state() -> Response:
    """Return the complete internal environment state including ground truth."""
    env = get_env()
    if not env._episode_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active episode.",
        )
    return Response(content=env.state().model_dump_json(), media_type="application/json")


@router.get(
    "/render",
    summary="Get visualization data for the dashboard",
    dependencies=[Depends(require_api_key)],
)
async def render() -> dict:
    """Return cluster state as dict — optimized for Plotly/D3 rendering."""
    env = get_env()
    if not env._episode_id:
        return {"status": "idle", "cluster": {}}
    return env.state().cluster_state.model_dump(mode="json")
