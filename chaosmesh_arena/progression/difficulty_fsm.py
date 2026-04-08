"""
ChaosMesh Arena — Difficulty Progression State Machine (Task 2.14)

Tracks curriculum level advancement across episodes.
Transitions: L1 → L2 → L3 → L4 → L5

Transition conditions:
- N consecutive successful resolutions at the current level
- MTTR within target window
- Minimum resolution confidence threshold met

Persisted in SQLite via EpisodeStore.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import structlog

from chaosmesh_arena.models import IncidentLevel

log = structlog.get_logger(__name__)

# Consecutive successes required before advancing to next level
_ADVANCE_THRESHOLD: dict[IncidentLevel, int] = {
    IncidentLevel.LEVEL_1: 3,
    IncidentLevel.LEVEL_2: 3,
    IncidentLevel.LEVEL_3: 2,
    IncidentLevel.LEVEL_4: 2,
    IncidentLevel.LEVEL_5: 999,  # Top level — no advancement
}

# MTTR ratio: episode MTTR must be ≤ this multiple of target to count as "fast"
_MTTR_FAST_THRESHOLD = 1.5

# Minimum cumulative reward to count as a success
_MIN_REWARD_THRESHOLD = 2.0


@dataclass
class EpisodeResult:
    """Result record passed to DifficultyFSM for progression decisions."""
    episode_id: str
    level: IncidentLevel
    resolved: bool
    cumulative_reward: float
    sim_time_minutes: float
    target_mttr_minutes: float = 5.0
    step_count: int = 0


@dataclass
class DifficultyState:
    """Serializable state for the FSM."""
    current_level: IncidentLevel = IncidentLevel.LEVEL_1
    consecutive_successes: int = 0
    total_episodes: int = 0
    total_successes: int = 0
    level_history: list[tuple[str, int, bool]] = field(default_factory=list)
    # list of (episode_id, level_value, resolved)


class DifficultyFSM:
    """
    Finite State Machine for curriculum difficulty progression.

    State: current_level, consecutive_successes
    Transitions: based on episode results

    Usage:
        fsm = DifficultyFSM()
        result = EpisodeResult(...)
        if fsm.record_result(result):
            print(f"Advanced to {fsm.current_level}!")
        next_level = fsm.current_level
    """

    def __init__(self, initial_level: IncidentLevel = IncidentLevel.LEVEL_1) -> None:
        self._state = DifficultyState(current_level=initial_level)

    @property
    def current_level(self) -> IncidentLevel:
        return self._state.current_level

    @property
    def consecutive_successes(self) -> int:
        return self._state.consecutive_successes

    @property
    def total_episodes(self) -> int:
        return self._state.total_episodes

    @property
    def success_rate(self) -> float:
        if self._state.total_episodes == 0:
            return 0.0
        return self._state.total_successes / self._state.total_episodes

    def record_result(self, result: EpisodeResult) -> bool:
        """
        Record an episode result and check for level advancement.

        Returns:
            True if the FSM advanced to a higher level, False otherwise.
        """
        self._state.total_episodes += 1
        self._state.level_history.append(
            (result.episode_id, result.level.value, result.resolved)
        )

        success = self._is_success(result)

        if success:
            self._state.consecutive_successes += 1
            self._state.total_successes += 1
            log.info(
                "difficulty_success",
                level=self._state.current_level.value,
                consecutive=self._state.consecutive_successes,
                reward=result.cumulative_reward,
            )
        else:
            self._state.consecutive_successes = 0
            log.info(
                "difficulty_failure",
                level=self._state.current_level.value,
                resolved=result.resolved,
                reward=result.cumulative_reward,
            )

        return self._maybe_advance()

    def should_advance(self, episode_results: list[EpisodeResult]) -> bool:
        """
        Check if we should advance given a list of recent results.
        Does NOT modify state — read-only check.
        """
        if not episode_results:
            return False
        threshold = _ADVANCE_THRESHOLD.get(self._state.current_level, 999)
        recent_successes = sum(
            1 for r in episode_results[-threshold:]
            if self._is_success(r)
        )
        return recent_successes >= threshold

    def force_level(self, level: IncidentLevel) -> None:
        """Force a specific level (for demos / testing)."""
        self._state.current_level = level
        self._state.consecutive_successes = 0
        log.info("difficulty_forced", level=level.value)

    def regress(self) -> bool:
        """
        Drop back one level on catastrophic failure (optional).
        Returns True if regression occurred.
        """
        level_order = list(IncidentLevel)
        idx = level_order.index(self._state.current_level)
        if idx <= 0:
            return False
        self._state.current_level = level_order[idx - 1]
        self._state.consecutive_successes = 0
        log.warning("difficulty_regressed", new_level=self._state.current_level.value)
        return True

    def state_dict(self) -> dict:
        """Serializable state snapshot for persistence."""
        return {
            "current_level": self._state.current_level.value,
            "consecutive_successes": self._state.consecutive_successes,
            "total_episodes": self._state.total_episodes,
            "total_successes": self._state.total_successes,
            "success_rate": self.success_rate,
        }

    def load_state(self, state: dict) -> None:
        """Restore FSM state from a serialized dict."""
        self._state.current_level = IncidentLevel(state.get("current_level", 1))
        self._state.consecutive_successes = state.get("consecutive_successes", 0)
        self._state.total_episodes = state.get("total_episodes", 0)
        self._state.total_successes = state.get("total_successes", 0)

    # ── Internal ──────────────────────────────────────────────────────────────

    def _is_success(self, result: EpisodeResult) -> bool:
        """
        Determine if an episode counts as a "success" for progression.
        Requires: resolved AND reward above threshold AND optional MTTR check.
        """
        if not result.resolved:
            return False
        if result.cumulative_reward < _MIN_REWARD_THRESHOLD:
            return False
        # Bonus check: was MTTR within acceptable range?
        if result.target_mttr_minutes > 0:
            mttr_ratio = result.sim_time_minutes / result.target_mttr_minutes
            if mttr_ratio > 3.0:  # More than 3x target is too slow
                return False
        return True

    def _maybe_advance(self) -> bool:
        """Check consecutive successes and advance level if threshold met."""
        threshold = _ADVANCE_THRESHOLD.get(self._state.current_level, 999)
        if self._state.consecutive_successes < threshold:
            return False

        # Try to advance
        level_order = list(IncidentLevel)
        idx = level_order.index(self._state.current_level)
        if idx >= len(level_order) - 1:
            log.info("difficulty_max_level_reached", level=self._state.current_level.value)
            return False

        old_level = self._state.current_level
        self._state.current_level = level_order[idx + 1]
        self._state.consecutive_successes = 0

        log.info(
            "difficulty_advanced",
            from_level=old_level.value,
            to_level=self._state.current_level.value,
            after_successes=threshold,
        )
        return True
