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
# MUST match openenv.yaml tasks exactly — validator compares both

_TASKS_PAYLOAD = [
    {
        "id": "sre-pod-crashloop",
        "task_id": "sre-pod-crashloop",
        "name": "pod-crashloop-recovery",
        "difficulty": "easy",
        "description": "A critical pod is in CrashLoopBackOff. Diagnose root cause and restore service.",
        "max_steps": 8,
        "reset_params": {"task_id": 0},
        "grader": "graders:grade_task_0",
        "graders": ["graders:grade_task_0"],
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
        "grader": "graders:grade_task_1",
        "graders": ["graders:grade_task_1"],
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
        "grader": "graders:grade_task_1",
        "graders": ["graders:grade_task_1"],
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
        "grader": "graders:grade_task_2",
        "graders": ["graders:grade_task_2"],
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
        "grader": "graders:grade_task_2",
        "graders": ["graders:grade_task_2"],
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
        "grader": "graders:grade_task_2",
        "graders": ["graders:grade_task_2"],
        "reward_range": [0.0, 1.0],
        "max_reward": 1.0,
    },
]

# Grader function map — task_id → callable
_GRADER_MAP = {
    "sre-pod-crashloop":    "grade_task_0",
    "sre-db-timeout":       "grade_task_1",
    "sre-high-latency":     "grade_task_1",
    "sre-node-pressure":    "grade_task_2",
    "sre-security-anomaly": "grade_task_2",
    "sre-compound-chaos":   "grade_task_2",
}


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


@router.get("/tasks", include_in_schema=True, tags=["openenv"])
@router.get("/openenv/tasks", include_in_schema=False)
@router.get("/api/tasks", include_in_schema=False)
async def list_tasks():
    """List all available benchmark tasks with grader string references.

    CRITICAL: grader field MUST be a string like 'graders:grade_task_0'.
    The validator parses this as module:function and imports it.
    Do NOT transform grader into a dict object.
    """
    return {"tasks": list(_TASKS_PAYLOAD)}


# ── /grader  ───────────────────────────────────────────────────────────────────


@router.post("/grader", include_in_schema=True, tags=["openenv"])
@router.post("/openenv/grader", include_in_schema=False)
@router.post("/api/grader", include_in_schema=False)
async def run_grader(request: FastAPIRequest):
    """
    Execute a grader function for a completed episode.

    Body: {"task_id": str, "state": dict, "reward": float}
    Returns: {"score": float}
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    task_id = body.get("task_id", "sre-pod-crashloop")
    task = next((t for t in _TASKS_PAYLOAD if t.get("task_id") == task_id), None)
    if task is None:
        return JSONResponse(
            {
                "task_id": task_id,
                "score": 0.0,
                "passed": False,
                "feedback": f"Unknown task_id: {task_id}",
            },
            status_code=200,
        )

    # Fast path: evaluator may send score directly.
    if body.get("score") is not None:
        final_score = _clamp01(body.get("score"))
    else:
        # Trajectory path: compute normalized score from reward per step.
        trajectory = body.get("trajectory", [])
        if isinstance(trajectory, list) and trajectory:
            rewards: list[float] = []
            for step in trajectory:
                if not isinstance(step, dict):
                    continue
                reward_value = step.get("reward", 0.0)
                if isinstance(reward_value, dict):
                    reward_value = reward_value.get("total", 0.0)
                try:
                    rewards.append(float(reward_value))
                except (TypeError, ValueError):
                    rewards.append(0.0)
            total = sum(rewards)
            max_possible = len(rewards) * 5.0 if rewards else 1.0
            final_score = _clamp01(total / max_possible)
        else:
            # Backward-compat with state-based grader functions.
            state = body.get("state", body.get("episode", {}))
            if isinstance(state, list):
                state = state[-1] if state else {}
            try:
                import graders as _g
                fn_name = _GRADER_MAP.get(task_id, "grade_task_0")
                fn = getattr(_g, fn_name)
                final_score = _clamp01(fn(state if isinstance(state, dict) else {}))
            except Exception as exc:
                return JSONResponse(
                    {
                        "task_id": task_id,
                        "score": 0.0,
                        "passed": False,
                        "feedback": f"Grader error: {exc}",
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
