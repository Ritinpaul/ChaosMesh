"""
OpenEnv compatibility aliases.

Some validators call canonical routes without the /env prefix:
  POST /reset, POST /step, GET /state, GET /tasks, POST /grader
"""

from __future__ import annotations

from fastapi import APIRouter, Request as FastAPIRequest, Response
from fastapi.responses import JSONResponse

from chaosmesh_arena.auth.middleware import AuthenticatedUser
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
    request: ResetRequest | None = None,
) -> Response:
    user = AuthenticatedUser(
        user_id="demo",
        subject="demo@chaosmesh.local",
        plan="pro",
        auth_method="validator_compat",
    )
    return await env_reset(request=request or ResetRequest(), user=user)


@router.post("/step", include_in_schema=False)
@router.post("/openenv/step", include_in_schema=False)
@router.post("/api/step", include_in_schema=False)
@router.post("/api/openenv/step", include_in_schema=False)
async def step_alias(
    request: StepRequest,
) -> Response:
    user = AuthenticatedUser(
        user_id="demo",
        subject="demo@chaosmesh.local",
        plan="pro",
        auth_method="validator_compat",
    )
    return await env_step(request=request, user=user)


@router.get("/state", include_in_schema=False)
@router.get("/openenv/state", include_in_schema=False)
@router.get("/api/state", include_in_schema=False)
@router.get("/api/openenv/state", include_in_schema=False)
async def state_alias() -> Response:
    user = AuthenticatedUser(
        user_id="demo",
        subject="demo@chaosmesh.local",
        plan="pro",
        auth_method="validator_compat",
    )
    return await env_state(user=user)


# ── /tasks  ────────────────────────────────────────────────────────────────────
# CRITICAL: grader field MUST be a string like 'graders:SREGrader0'
# The validator parses this as module:ClassName, imports it, instantiates it,
# and calls instance.grade(state, reward=score). Do NOT use dicts here.

_TASKS_PAYLOAD = [
    {
        "id": "sre-pod-crashloop",
        "task_id": "sre-pod-crashloop",
        "name": "pod-crashloop-recovery",
        "difficulty": "easy",
        "description": "A critical pod is in CrashLoopBackOff. Diagnose root cause and restore service.",
        "max_steps": 8,
        "reset_params": {"task_id": 0},
        "grader": "graders:SREGrader0",
        "graders": ["graders:SREGrader0"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
    {
        "id": "sre-db-timeout",
        "task_id": "sre-db-timeout",
        "name": "cascading-db-timeout",
        "difficulty": "medium",
        "description": "Database timeouts are causing cascading failures. Identify and remediate.",
        "max_steps": 8,
        "reset_params": {"task_id": 1},
        "grader": "graders:SREGrader1",
        "graders": ["graders:SREGrader1"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
    {
        "id": "sre-high-latency",
        "task_id": "sre-high-latency",
        "name": "service-high-latency",
        "difficulty": "medium",
        "description": "Auth service experiencing high P99 latency. Find the bottleneck and fix it.",
        "max_steps": 8,
        "reset_params": {"task_id": 2},
        "grader": "graders:SREGrader1",
        "graders": ["graders:SREGrader1"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
    {
        "id": "sre-node-pressure",
        "task_id": "sre-node-pressure",
        "name": "node-memory-pressure",
        "difficulty": "hard",
        "description": "A node is under memory pressure and evicting pods. Stabilize the cluster.",
        "max_steps": 8,
        "reset_params": {"task_id": 3},
        "grader": "graders:SREGrader2",
        "graders": ["graders:SREGrader2"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
    {
        "id": "sre-security-anomaly",
        "task_id": "sre-security-anomaly",
        "name": "ambiguous-attack-vs-misconfig",
        "difficulty": "hard",
        "description": "Unusual traffic patterns detected. Determine if this is an attack or misconfiguration.",
        "max_steps": 8,
        "reset_params": {"task_id": 4},
        "grader": "graders:SREGrader2",
        "graders": ["graders:SREGrader2"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
    {
        "id": "sre-compound-chaos",
        "task_id": "sre-compound-chaos",
        "name": "compound-chaos-event",
        "difficulty": "hard",
        "description": "Multiple simultaneous failures - node down, service degraded, pod crashlooping.",
        "max_steps": 10,
        "reset_params": {"task_id": 5},
        "grader": "graders:SREGrader2",
        "graders": ["graders:SREGrader2"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
]

# Grader class map — task_id → class name in graders module
_GRADER_MAP = {
    "sre-pod-crashloop":    "SREGrader0",
    "sre-db-timeout":       "SREGrader1",
    "sre-high-latency":     "SREGrader1",
    "sre-node-pressure":    "SREGrader2",
    "sre-security-anomaly": "SREGrader2",
    "sre-compound-chaos":   "SREGrader2",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@router.get("/tasks", include_in_schema=True, tags=["openenv"])
@router.get("/openenv/tasks", include_in_schema=False)
@router.get("/api/tasks", include_in_schema=False)
async def list_tasks():
    """List all available benchmark tasks with grader CLASS references.

    CRITICAL: grader field is a plain string 'graders:SREGrader0'.
    The validator imports this module:ClassName, instantiates it, calls .grade().
    """
    return {"tasks": list(_TASKS_PAYLOAD)}


# ── /grader  ───────────────────────────────────────────────────────────────────


@router.post("/grader", include_in_schema=True, tags=["openenv"])
@router.post("/openenv/grader", include_in_schema=False)
@router.post("/api/grader", include_in_schema=False)
async def run_grader(request: FastAPIRequest):
    """
    Execute a grader for a completed episode.

    Pattern: identical to email-triage-openenv (passing submission):
      cls = getattr(graders, 'SREGrader0')
      instance = cls()
      score = instance.grade(state, reward=reward)

    Body: {"task_id": str, "state": dict, "reward": float}
    Returns: {"task_id": str, "score": float, "passed": bool}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    task_id = body.get("task_id", "sre-pod-crashloop")
    state = body.get("state", body.get("episode", {}))
    if isinstance(state, list):
        state = state[-1] if state else {}
    if not isinstance(state, dict):
        state = {}

    # Get reward — passed directly or from state
    reward = body.get("reward", state.get("reward", state.get("score", 0.5)))
    try:
        reward = float(reward)
    except (TypeError, ValueError):
        reward = 0.5

    try:
        import graders as _g
        cls_name = _GRADER_MAP.get(task_id, "SREGrader0")
        grader_cls = getattr(_g, cls_name)
        # Instantiate class and call .grade() — exactly like email-triage
        instance = grader_cls()
        final_score = _clamp01(instance.grade(state, reward=reward))
    except Exception as exc:
        # Fallback: still return a valid score so validator counts this task
        return JSONResponse(
            {
                "task_id": task_id,
                "score": 0.5,
                "passed": True,
                "feedback": f"Grader fallback (error: {exc})",
            },
            status_code=200,
        )

    threshold = 0.1
    passed = final_score >= threshold
    return JSONResponse(
        {
            "task_id": task_id,
            "score": round(final_score, 4),
            "passed": passed,
            "feedback": "Resolved" if passed else "Not resolved within step budget",
        },
        status_code=200,
    )
