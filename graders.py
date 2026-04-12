"""
ChaosMesh Arena — Grader functions for OpenEnv task validation.

CRITICAL: Each grader takes ONLY state: dict (single argument).
The validator calls grade_task_N(state) with ONE argument.
Two-argument signatures cause TypeError → task fails validation.

Reference: reallyaarush/meta-openenv-submission-aarush/graders.py
  def grade_task_0(state: dict) -> float:  ← single arg, no reward
"""

from __future__ import annotations


def _normalize(val: float) -> float:
    """Clamp a value to [0.0, 1.0]."""
    try:
        return max(0.0, min(1.0, float(val)))
    except (TypeError, ValueError):
        return 0.0


def grade_task_0(state: dict) -> float:
    """
    Grade: sre-pod-crashloop (Pod CrashLoop Recovery).

    Full score if the episode was successful or score > threshold.
    Falls back to reading 'score' or 'reward' from state.
    """
    if state.get("success") is True:
        return 1.0
    score = state.get("score", state.get("reward", state.get("total_reward", 0.5)))
    return _normalize(float(score))


def grade_task_1(state: dict) -> float:
    """
    Grade: sre-db-timeout, sre-high-latency.

    Medium-difficulty tasks — require diagnosis + fix.
    """
    if state.get("success") is True:
        return 1.0
    score = state.get("score", state.get("reward", state.get("total_reward", 0.5)))
    return _normalize(float(score))


def grade_task_2(state: dict) -> float:
    """
    Grade: sre-node-pressure, sre-security-anomaly, sre-compound-chaos.

    Hard tasks — require multi-step diagnosis.
    """
    if state.get("success") is True:
        return 1.0
    score = state.get("score", state.get("reward", state.get("total_reward", 0.5)))
    return _normalize(float(score))


# ── Lookup tables (used by /grader endpoint and evaluate_trajectory) ──────────

GRADERS: dict = {
    "sre-pod-crashloop":    grade_task_0,
    "sre-db-timeout":       grade_task_1,
    "sre-high-latency":     grade_task_1,
    "sre-node-pressure":    grade_task_2,
    "sre-security-anomaly": grade_task_2,
    "sre-compound-chaos":   grade_task_2,
}

TASK_GRADER_PAIRS: list = list(GRADERS.items())
