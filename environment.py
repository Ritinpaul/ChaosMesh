"""
environment.py  ―  Lightweight ChaosMesh Arena environment wrapper.

This file lives at the repo root so the OpenEnv validator can import it
WITHOUT needing the heavy chaosmesh_arena package dependencies
(ChromaDB, gymnasium, structlog, etc.)

The validator imports:
    entry_point: environment:ChaosMeshArenaEnv
and calls:
    env = ChaosMeshArenaEnv()
    tasks = env.get_tasks()               # ← required for Phase 2
    score = env.evaluate_trajectory(...)  # ← evaluated per task
"""

from __future__ import annotations

# ── Task catalogue (mirrors openenv.yaml exactly) ─────────────────────────────

_TASKS = [
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
    },
]

_GRADER_FN_MAP = {
    "sre-pod-crashloop":    "grade_task_0",
    "sre-db-timeout":       "grade_task_1",
    "sre-high-latency":     "grade_task_1",
    "sre-node-pressure":    "grade_task_2",
    "sre-security-anomaly": "grade_task_2",
    "sre-compound-chaos":   "grade_task_2",
}


# ── Minimal env class for validator ──────────────────────────────────────────

class ChaosMeshArenaEnv:
    """
    Lightweight OpenEnv environment class.

    The full heavy implementation lives in chaosmesh_arena.env.
    This thin wrapper exists so the OpenEnv validator can:
      1. Import this file without needing gymnasium / chromadb / etc.
      2. Call get_tasks() to discover the task catalogue.
      3. Call evaluate_trajectory() to score episodes.
    """

    metadata = {"render_modes": []}

    # ── OpenEnv required methods ──────────────────────────────────────────────

    def get_tasks(self) -> list:
        """Return all tasks with their grader references."""
        return list(_TASKS)

    def evaluate_trajectory(
        self,
        task_id: str,
        trajectory: list,
        episode: dict,
    ) -> float:
        """
        Score a completed trajectory using the task's grader.

        Parameters
        ----------
        task_id    : str  — one of the task IDs above
        trajectory : list — list of step dicts
        episode    : dict — includes keys like ``score``, ``success``, ``steps``

        Returns
        -------
        float in [0.0, 1.0]
        """
        import graders as _g  # standalone, no external deps

        fn_name = _GRADER_FN_MAP.get(task_id, "grade_task_0")
        fn = getattr(_g, fn_name)

        state = episode if isinstance(episode, dict) else {}
        reward = float(state.get("score", state.get("reward", 0.0)))
        return fn(state, reward)

    # ── Gymnasium-like stubs (for compatibility only) ─────────────────────────

    def reset(self, *, seed=None, options=None):
        return {}, {}

    def step(self, action):
        return {}, 0.0, False, False, {}

    def close(self):
        pass

    def render(self):
        pass
