"""
ChaosMesh SDK — Gymnasium-Compatible Environment Wrapper.

Wraps the ChaosMesh HTTP API as a standard gym.Env so any
RL framework (Stable-Baselines3, RLlib, CleanRL) can use it
without modification.

    import gymnasium as gym
    from chaosmesh_sdk.gymnasium_env import ChaosMeshGymEnv

    env = ChaosMeshGymEnv(api_key="cm_live_...", level=1)
    obs, info = env.reset()
    for _ in range(100):
        action = env.action_space.sample()
        obs, reward, terminated, truncated, info = env.step(action)
        if terminated or truncated:
            break
    env.close()
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    HAS_GYMNASIUM = True
except ImportError:
    HAS_GYMNASIUM = False

from chaosmesh_sdk.client import ChaosMeshClient

# Action space dimensions
_N_AGENTS = 4        # IC, DX, RM, SA
_N_ACTION_TYPES = 12
_N_TARGETS = 20

# Observation space size (flattened)
_OBS_DIM = 128


def _flatten_obs(obs_dict: dict) -> np.ndarray:
    """Flatten the dict observation into a fixed-size float32 array."""
    cluster = obs_dict.get("cluster", {})
    pods = cluster.get("pods", {})
    metrics = obs_dict.get("metrics", {})

    values: list[float] = []

    # Pod health stats (top 10 pods)
    for pod_data in list(pods.values())[:10]:
        values.extend([
            float(pod_data.get("status", 0) == "RUNNING"),
            float(pod_data.get("status", 0) == "CRASH_LOOP_BACK_OFF"),
            float(pod_data.get("latency_ms", 0) / 1000.0),
            float(pod_data.get("error_rate", 0)),
        ])

    # Pad / truncate pods to 10
    while len(values) < 40:
        values.append(0.0)
    values = values[:40]

    # Global metrics
    values.extend([
        float(metrics.get("error_rate_global", 0)),
        float(metrics.get("p99_latency_ms", 0) / 1000.0),
        float(metrics.get("throughput_rps", 0) / 1000.0),
        float(obs_dict.get("step", 0) / 50.0),
        float(obs_dict.get("incidents_active", 0) / 5.0),
    ])

    # Pad to _OBS_DIM
    values.extend([0.0] * (_OBS_DIM - len(values)))
    return np.array(values[:_OBS_DIM], dtype=np.float32)


def _build_action_dict(action_idx: int, targets: list[str]) -> dict:
    """Map integer action index to API action dict."""
    from chaosmesh_sdk.action_space import ACTION_INDEX_MAP
    agent_idx = action_idx % _N_AGENTS
    type_idx = (action_idx // _N_AGENTS) % _N_ACTION_TYPES
    target_idx = action_idx // (_N_AGENTS * _N_ACTION_TYPES)

    agents = ["incident_commander", "diagnostician", "remediator", "security_analyst"]
    types = [
        "diagnose", "scale_up", "rollback", "forward_traffic",
        "isolate_service", "collect_logs", "run_healthcheck",
        "update_config", "send_message", "analyze_metrics",
        "escalate", "resolve",
    ]

    target = targets[target_idx % len(targets)] if targets else "default-service"
    return {
        "agent": agents[agent_idx % len(agents)],
        "action_type": types[type_idx % len(types)],
        "target": target,
        "parameters": {},
        "reasoning": "gymnasium_agent",
    }


class ChaosMeshGymEnv:
    """
    Gymnasium-style environment wrapping the ChaosMesh Arena HTTP API.

    Requires `gymnasium` to be installed for full gym compliance.
    Works without gymnasium for basic observation/action loop.
    """

    metadata = {"render_modes": ["json"], "name": "ChaosMeshArena-v1"}

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "http://localhost:8000",
        level: int = 1,
        timeout: float = 30.0,
    ) -> None:
        self._client = ChaosMeshClient(api_key=api_key, base_url=base_url, timeout=timeout)
        self._level = level
        self._episode_id: str = ""
        self._targets: list[str] = []

        n_actions = _N_AGENTS * _N_ACTION_TYPES * _N_TARGETS

        if HAS_GYMNASIUM:
            self.observation_space = spaces.Box(
                low=0.0, high=1.0, shape=(_OBS_DIM,), dtype=np.float32
            )
            self.action_space = spaces.Discrete(n_actions)
        else:
            self.observation_space = None
            self.action_space = None

    def reset(
        self,
        seed: int | None = None,
        options: dict | None = None,
    ) -> tuple[np.ndarray, dict]:
        level = (options or {}).get("level", self._level)
        obs_dict, info = self._client.reset(level=level)
        self._episode_id = info.get("episode_id", "")
        self._targets = list(obs_dict.get("cluster", {}).get("pods", {}).keys())[:_N_TARGETS]
        return _flatten_obs(obs_dict), info

    def step(self, action: int | dict) -> tuple[np.ndarray, float, bool, bool, dict]:
        if isinstance(action, int):
            action_dict = _build_action_dict(action, self._targets)
        else:
            action_dict = action

        result = self._client.step(self._episode_id, action_dict)
        obs = _flatten_obs(result.observation)
        reward = float(result.reward.total if hasattr(result.reward, "total") else result.reward)
        return obs, reward, result.terminated, result.truncated, result.info

    def render(self) -> dict:
        return self._client.get_state()

    def close(self) -> None:
        self._client.close_session()
        self._client.close()

    @property
    def unwrapped(self) -> "ChaosMeshGymEnv":
        return self

    def __repr__(self) -> str:
        return f"ChaosMeshGymEnv(level={self._level}, api_key=...)"
