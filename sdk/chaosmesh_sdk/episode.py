"""
ChaosMesh SDK — Episode Context Manager.

Provides a clean interface for running a complete episode:

    with client.episode(level=2) as ep:
        while not ep.done:
            action = my_agent.decide(ep.observation)
            ep.step(action)
        print(f"Score: {ep.score:.3f}")

Also supports async:

    async with client.episode(level=2) as ep:
        while not ep.done:
            action = await my_agent.decide(ep.observation)
            await ep.astep(action)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from chaosmesh_sdk.exceptions import EpisodeNotStarted
from chaosmesh_sdk.models import RewardBreakdown, StepResult

if TYPE_CHECKING:
    from chaosmesh_sdk.client import ChaosMeshClient


class Episode:
    """
    Manages the lifecycle of a single ChaosMesh episode.

    Automatically resets on enter, closes session on exit.
    Accumulates step history for post-episode analysis.
    """

    def __init__(self, client: "ChaosMeshClient", level: int = 1) -> None:
        self._client = client
        self._level = level

        self.observation: dict[str, Any] = {}
        self.episode_id: str = ""
        self.step_count: int = 0
        self.cumulative_reward: float = 0.0
        self.terminated: bool = False
        self.truncated: bool = False
        self._history: list[dict] = []

    # ── Context managers ───────────────────────────────────────────────────────

    def __enter__(self) -> "Episode":
        obs, info = self._client.reset(level=self._level)
        self._init(obs, info)
        return self

    def __exit__(self, *args) -> None:
        self._client.close_session()

    async def __aenter__(self) -> "Episode":
        obs, info = await self._client.async_reset(level=self._level)
        self._init(obs, info)
        return self

    async def __aexit__(self, *args) -> None:
        self._client.close_session()

    # ── State ──────────────────────────────────────────────────────────────────

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated

    @property
    def score(self) -> float:
        """Normalized score [0.0, 1.0] based on cumulative reward."""
        from chaosmesh_sdk.database_constants import LEVEL_MAX_REWARD
        max_r = LEVEL_MAX_REWARD.get(self._level, 25.0)
        return max(0.0, min(1.0, self.cumulative_reward / max_r))

    @property
    def history(self) -> list[dict]:
        """Returns action history: [{step, action, reward, terminated}]"""
        return self._history.copy()

    # ── Actions ────────────────────────────────────────────────────────────────

    def step(self, action: dict) -> StepResult:
        """Submit an action and advance the episode by one step."""
        if not self.episode_id:
            raise EpisodeNotStarted("Episode not started. Use the context manager.")

        result = self._client.step(self.episode_id, action)
        self._apply(action, result)
        return result

    async def astep(self, action: dict) -> StepResult:
        """Async version of step()."""
        if not self.episode_id:
            raise EpisodeNotStarted("Episode not started. Use the async context manager.")

        result = await self._client.async_step(self.episode_id, action)
        self._apply(action, result)
        return result

    # ── Internal ───────────────────────────────────────────────────────────────

    def _init(self, obs: dict, info: dict) -> None:
        self.observation = obs
        self.episode_id = info.get("episode_id", "")
        self.step_count = 0
        self.cumulative_reward = 0.0
        self.terminated = False
        self.truncated = False
        self._history = []

    def _apply(self, action: dict, result: StepResult) -> None:
        self.observation = result.observation
        self.terminated = result.terminated
        self.truncated = result.truncated
        reward_val = result.reward.total if isinstance(result.reward, RewardBreakdown) else float(result.reward)
        self.cumulative_reward += reward_val
        self.step_count += 1
        self._history.append({
            "step": self.step_count,
            "action": action,
            "reward": reward_val,
            "terminated": result.terminated,
            "truncated": result.truncated,
        })
