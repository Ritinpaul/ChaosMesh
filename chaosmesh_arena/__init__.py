"""
ChaosMesh Arena — OpenEnv-compatible multi-agent SRE training environment.

Registers the environment with Gymnasium so it can be used as:

    import gymnasium as gym
    import chaosmesh_arena

    env = gym.make("ChaosMeshArena-v0")
    obs, info = env.reset()

Spec: OpenEnv RFC 001/002/003
"""

from __future__ import annotations

import gymnasium as gym

from chaosmesh_arena.agents import (
    DatabaseAgent,
    DiagnosticsAgent,
    IncidentCommanderAgent,
    RemediationAgent,
    SecurityAgent,
)
from chaosmesh_arena.bus import MessageBus
from chaosmesh_arena.chaos import ChaosOrchestrator
from chaosmesh_arena.env import ChaosMeshArenaEnv
from chaosmesh_arena.memory.belief_tracker import BeliefTracker
from chaosmesh_arena.models import (
    ActionModel,
    ActionType,
    AgentRole,
    FullStateModel,
    IncidentLevel,
    ObservationModel,
    RewardBreakdown,
    StepResult,
)
from chaosmesh_arena.progression import DifficultyFSM, EpisodeResult
from chaosmesh_arena.rewards import RewardCalculator
from chaosmesh_arena.templates import IncidentRegistry

# ── Gymnasium Registration ────────────────────────────────────────────────────

gym.register(
    id="ChaosMeshArena-v0",
    entry_point="chaosmesh_arena.env:ChaosMeshArenaEnv",
    kwargs={"level": IncidentLevel.LEVEL_1},
    max_episode_steps=200,
    reward_threshold=10.0,
)

gym.register(
    id="ChaosMeshArena-L2-v0",
    entry_point="chaosmesh_arena.env:ChaosMeshArenaEnv",
    kwargs={"level": IncidentLevel.LEVEL_2},
    max_episode_steps=200,
)

gym.register(
    id="ChaosMeshArena-L3-v0",
    entry_point="chaosmesh_arena.env:ChaosMeshArenaEnv",
    kwargs={"level": IncidentLevel.LEVEL_3},
    max_episode_steps=300,
)

gym.register(
    id="ChaosMeshArena-L4-v0",
    entry_point="chaosmesh_arena.env:ChaosMeshArenaEnv",
    kwargs={"level": IncidentLevel.LEVEL_4},
    max_episode_steps=400,
)

gym.register(
    id="ChaosMeshArena-L5-v0",
    entry_point="chaosmesh_arena.env:ChaosMeshArenaEnv",
    kwargs={"level": IncidentLevel.LEVEL_5},
    max_episode_steps=500,
)

__version__ = "0.2.0"  # Phase 2
__all__ = [
    # Core env
    "ChaosMeshArenaEnv",
    # Agents
    "DatabaseAgent",
    "DiagnosticsAgent",
    "IncidentCommanderAgent",
    "RemediationAgent",
    "SecurityAgent",
    # Infrastructure
    "MessageBus",
    "ChaosOrchestrator",
    "BeliefTracker",
    "DifficultyFSM",
    "EpisodeResult",
    "RewardCalculator",
    "IncidentRegistry",
    # Models
    "ActionModel",
    "ActionType",
    "AgentRole",
    "FullStateModel",
    "IncidentLevel",
    "ObservationModel",
    "RewardBreakdown",
    "StepResult",
]
