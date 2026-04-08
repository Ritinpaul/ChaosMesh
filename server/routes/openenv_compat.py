"""
OpenEnv compatibility aliases.

Some validators call canonical routes without the /env prefix:
  POST /reset, POST /step, GET /state

These handlers forward to the primary /env/* implementations.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from chaosmesh_arena.auth.middleware import AuthenticatedUser, require_auth
from chaosmesh_arena.models import ResetRequest, StepRequest
from server.routes.env import get_state as env_state
from server.routes.env import reset as env_reset
from server.routes.env import step as env_step

router = APIRouter(tags=["openenv-compat"])


@router.post("/reset", include_in_schema=False)
@router.post("/openenv/reset", include_in_schema=False)
@router.post("/api/reset", include_in_schema=False)
@router.post("/api/openenv/reset", include_in_schema=False)
async def reset_alias(
    request: ResetRequest,
    user: AuthenticatedUser = Depends(require_auth),
) -> Response:
    return await env_reset(request=request, user=user)


@router.post("/step", include_in_schema=False)
@router.post("/openenv/step", include_in_schema=False)
@router.post("/api/step", include_in_schema=False)
@router.post("/api/openenv/step", include_in_schema=False)
async def step_alias(
    request: StepRequest,
    user: AuthenticatedUser = Depends(require_auth),
) -> Response:
    return await env_step(request=request, user=user)


@router.get("/state", include_in_schema=False)
@router.get("/openenv/state", include_in_schema=False)
@router.get("/api/state", include_in_schema=False)
@router.get("/api/openenv/state", include_in_schema=False)
async def state_alias(
    user: AuthenticatedUser = Depends(require_auth),
) -> Response:
    return await env_state(user=user)
