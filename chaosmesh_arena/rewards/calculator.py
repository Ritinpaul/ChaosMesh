"""
ChaosMesh Arena — Multi-Level Reward Calculator (Task 2.16)

Replaces the inline env._compute_reward() with a structured, level-aware
reward function.

Level-adjusted reward weights:
  L1: 1.0x individual, 0.5x coordination  (learn basics)
  L2: 0.8x individual, 1.0x coordination  (teamwork matters)
  L3: 0.6x individual, 1.2x coordination  (ambiguity requires debate)
  L4: 0.5x individual, 1.5x coordination + chaos_adaptation bonus
  L5: 0.4x individual, 2.0x coordination + compound_resolution bonus

Additional signals:
  - Belief accuracy bonus (from BeliefTracker)
  - Authorization correctness (requested vs. granted vs. bypassed)
  - MTTR efficiency vs. level target
  - Message quality (length, confidence, finding content)
  - Premature resolution penalty
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

import structlog

from chaosmesh_arena.models import (
    ActionModel,
    ActionType,
    AgentBeliefModel,
    AgentRole,
    IncidentLevel,
    ObservationModel,
    RewardBreakdown,
)

if TYPE_CHECKING:
    from chaosmesh_arena.memory.belief_tracker import BeliefTracker
    from chaosmesh_arena.sim.cluster_state import ClusterStateMachine
    from chaosmesh_arena.sim.failure_injector import FailureInjector

log = structlog.get_logger(__name__)


# ── Level-specific reward multipliers ─────────────────────────────────────────

_INDIVIDUAL_WEIGHT: dict[IncidentLevel, float] = {
    IncidentLevel.LEVEL_1: 1.0,
    IncidentLevel.LEVEL_2: 0.8,
    IncidentLevel.LEVEL_3: 0.6,
    IncidentLevel.LEVEL_4: 0.5,
    IncidentLevel.LEVEL_5: 0.4,
}

_COORDINATION_WEIGHT: dict[IncidentLevel, float] = {
    IncidentLevel.LEVEL_1: 0.5,
    IncidentLevel.LEVEL_2: 1.0,
    IncidentLevel.LEVEL_3: 1.2,
    IncidentLevel.LEVEL_4: 1.5,
    IncidentLevel.LEVEL_5: 2.0,
}

# MTTR targets per level (simulated minutes)
_TARGET_MTTR: dict[IncidentLevel, float] = {
    IncidentLevel.LEVEL_1: 3.0,
    IncidentLevel.LEVEL_2: 6.0,
    IncidentLevel.LEVEL_3: 9.0,
    IncidentLevel.LEVEL_4: 12.0,
    IncidentLevel.LEVEL_5: 18.0,
}

# Max message count before spam penalty applies
_MSG_SPAM_THRESHOLD = 40


class RewardCalculator:
    """
    Multi-level reward calculator for ChaosMesh Arena.

    Instantiated once per environment and called by env.step().
    Requires access to cluster, injector, and belief tracker.
    """

    def __init__(
        self,
        level: IncidentLevel = IncidentLevel.LEVEL_1,
        belief_tracker: Optional["BeliefTracker"] = None,
        max_messages: int = 50,
    ) -> None:
        self._level = level
        self._belief_tracker = belief_tracker
        self._max_messages = max_messages
        self._message_count: int = 0

    def set_level(self, level: IncidentLevel) -> None:
        self._level = level

    def increment_message_count(self) -> None:
        self._message_count += 1

    def reset_message_count(self) -> None:
        self._message_count = 0

    def compute(
        self,
        action: ActionModel,
        obs: ObservationModel,
        cluster: "ClusterStateMachine",
        injector: "FailureInjector",
        episode_id: str,
    ) -> RewardBreakdown:
        """
        Compute the full reward for a single agent action.

        Returns:
            RewardBreakdown with individual, coordination, efficiency, resolution components.
        """
        level = self._level
        ind_w = _INDIVIDUAL_WEIGHT.get(level, 1.0)
        coord_w = _COORDINATION_WEIGHT.get(level, 1.0)
        target_mttr = _TARGET_MTTR.get(level, 5.0)

        individual = self._individual_reward(action, cluster) * ind_w
        coordination = self._coordination_reward(action, obs) * coord_w
        efficiency = self._efficiency_reward(obs.sim_time_minutes, target_mttr)
        resolution = self._resolution_reward(action, injector)

        # Level 4+ bonus: chaos adaptation (penalize for ignoring new symptoms)
        adaptation_bonus = 0.0
        if level in (IncidentLevel.LEVEL_4, IncidentLevel.LEVEL_5):
            adaptation_bonus = self._chaos_adaptation_bonus(action, obs)

        # Belief accuracy bonus
        belief_bonus = 0.0
        if self._belief_tracker and level.value >= 2:
            belief_bonus = self._belief_accuracy_bonus(action, episode_id)

        # Authorization correctness
        auth_reward = self._authorization_reward(action)

        # Message spam penalty
        spam_penalty = self._spam_penalty()

        total = round(
            individual + coordination + efficiency + resolution
            + adaptation_bonus + belief_bonus + auth_reward + spam_penalty,
            4,
        )

        breakdown = RewardBreakdown(
            individual=round(individual, 4),
            coordination=round(coordination + adaptation_bonus + belief_bonus + auth_reward, 4),
            efficiency=round(efficiency, 4),
            resolution=round(resolution + spam_penalty, 4),
            total=total,
        )

        log.debug(
            "reward_computed",
            level=level.value,
            agent=action.agent.value,
            action=action.action_type.value,
            total=total,
        )
        return breakdown

    # ── Component Reward Functions ─────────────────────────────────────────────

    def _individual_reward(
        self, action: ActionModel, cluster: "ClusterStateMachine"
    ) -> float:
        """Reward for individual agent actions that directly improve cluster state."""
        reward = 0.0

        if action.action_type == ActionType.RESTART_POD:
            pod = cluster.get_pod(action.target)
            if pod and pod.ready:
                reward += 1.5   # Successful pod restart
            else:
                reward -= 0.5   # Failed restart (wrong target or timing)

        elif action.action_type == ActionType.SCALE_DEPLOYMENT:
            svc = cluster.get_service(action.target)
            if svc and svc.error_rate_percent < 5.0:
                reward += 1.2   # Successful scale fixed the service
            else:
                reward -= 0.3

        elif action.action_type == ActionType.ROLLBACK_DEPLOYMENT:
            pod = cluster.get_pod(action.target)
            if pod and pod.ready:
                reward += 1.8   # Rollback is higher-impact
            else:
                reward -= 0.4

        elif action.action_type == ActionType.UPDATE_CONFIG:
            reward += 0.8       # Config updates usually positive

        elif action.action_type == ActionType.ISOLATE_POD:
            reward += 0.6       # Security-motivated isolation

        elif action.action_type == ActionType.DRAIN_NODE:
            reward += 0.5       # Node drain is correct but risky

        elif action.action_type in (
            ActionType.GET_LOGS,
            ActionType.QUERY_METRICS,
            ActionType.DESCRIBE_POD,
            ActionType.DESCRIBE_NODE,
            ActionType.QUERY_TRACES,
            ActionType.SCAN_TRAFFIC,
            ActionType.QUERY_DB_STATS,
        ):
            reward += 0.1   # Small positive for doing investigation work

        elif action.action_type == ActionType.NOOP:
            reward -= 0.05  # Tiny penalty for doing nothing

        return reward

    def _coordination_reward(
        self, action: ActionModel, obs: ObservationModel
    ) -> float:
        """Reward for inter-agent coordination quality."""
        reward = 0.0

        if action.action_type == ActionType.SEND_MESSAGE and action.message:
            content = action.message.content
            # Informative messages
            if content.finding and len(content.finding) > 30:
                reward += 0.3
            # High-confidence findings are worth more
            if content.confidence > 0.7:
                reward += 0.2
            if content.confidence > 0.85:
                reward += 0.1  # Bonus for high confidence
            # Evidence-backed messages
            if content.evidence and len(content.evidence) > 0:
                reward += 0.15

        elif action.action_type == ActionType.BROADCAST_STATUS:
            reward += 0.4   # IC broadcasting is active coordination

        elif action.action_type == ActionType.REQUEST_AUTHORIZATION:
            reward += 0.25  # Proper authorization chain followed

        elif action.action_type == ActionType.GRANT_AUTHORIZATION:
            reward += 0.2   # IC granting auth after review

        elif action.action_type == ActionType.ESCALATE:
            reward += 0.1   # Escalation is valid (if not premature)

        return reward

    def _efficiency_reward(
        self, sim_time_minutes: float, target_mttr: float
    ) -> float:
        """Reward proportional to how quickly the team is resolving the incident."""
        if sim_time_minutes <= 0:
            return 0.0
        if sim_time_minutes < target_mttr:
            # Bonus for being ahead of target
            return 0.15 * (target_mttr - sim_time_minutes)
        else:
            # Penalty for being behind target, capped at -3.0
            penalty = 0.08 * (sim_time_minutes - target_mttr)
            return -min(penalty, 3.0)

    def _resolution_reward(
        self, action: ActionModel, injector: "FailureInjector"
    ) -> float:
        """Reward/penalty for DECLARE_RESOLVED actions."""
        if action.action_type != ActionType.DECLARE_RESOLVED:
            return 0.0
        if injector.is_all_resolved():
            # Level-scaled resolution bonus
            level_bonus = self._level.value * 0.5
            return 3.0 + level_bonus
        else:
            return -1.0  # Premature declaration

    def _chaos_adaptation_bonus(
        self, action: ActionModel, obs: ObservationModel
    ) -> float:
        """
        L4/L5 bonus: reward agents for recognizing and responding to
        new symptoms introduced by the ChaosOrchestrator mutation.
        """
        if not obs.active_incidents:
            return 0.0
        # If the agent investigated after a new incident appeared, bonus
        if action.action_type in (
            ActionType.GET_LOGS, ActionType.QUERY_METRICS,
            ActionType.DESCRIBE_POD, ActionType.SCAN_TRAFFIC,
        ):
            # Heuristic: if there's an active incident and agent is still investigating
            # at a high step count, they're adapting to mutations
            if obs.step > 10:
                return 0.3
        return 0.0

    def _belief_accuracy_bonus(
        self, action: ActionModel, episode_id: str
    ) -> float:
        """Bonus based on historical belief accuracy of this agent."""
        if not self._belief_tracker:
            return 0.0
        try:
            accuracy = self._belief_tracker.compute_accuracy(
                action.agent, last_n_episodes=5
            )
            # Scale: 0.5 accuracy = 0, 1.0 accuracy = +0.3
            bonus = max(0.0, (accuracy - 0.5) * 0.6)
            return round(bonus, 3)
        except Exception:
            return 0.0

    def _authorization_reward(self, action: ActionModel) -> float:
        """Reward correct use of the authorization system."""
        if action.action_type == ActionType.REQUEST_AUTHORIZATION:
            return 0.1  # Properly requested
        # Penalty handled in RemediationAgent — it won't emit dangerous actions without auth
        return 0.0

    def _spam_penalty(self) -> float:
        """Penalty when message count far exceeds reasonable threshold."""
        if self._message_count <= 0:
            return 0.0
        threshold = self._max_messages * 0.8
        if self._message_count > threshold:
            overflow = self._message_count - threshold
            return -min(0.05 * overflow, 1.5)  # Cap at -1.5
        return 0.0
