"""
ChaosMesh SDK — Lightweight Data Models.

These mirror the server-side Pydantic models but with no
server-side imports — pure SDK dependency only on httpx + pydantic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RewardBreakdown:
    individual: float = 0.0
    coordination: float = 0.0
    efficiency: float = 0.0
    resolution: float = 0.0
    total: float = 0.0


@dataclass
class StepResult:
    observation: dict[str, Any]
    reward: RewardBreakdown
    terminated: bool
    truncated: bool
    info: dict[str, Any]

    @property
    def done(self) -> bool:
        return self.terminated or self.truncated


@dataclass
class EpisodeSummary:
    episode_id: str
    level: int
    score: float
    cumulative_reward: float
    mttr_minutes: float
    steps: int
    resolved: bool
    created_at: str
    completed_at: Optional[str] = None


@dataclass
class LeaderboardEntry:
    rank: int
    user_id: str
    display_name: str
    best_score: float
    avg_score: float = 0.0
    total_episodes: int = 0
    resolved_count: int = 0


@dataclass
class UserProfile:
    user_id: str
    email: str
    display_name: str
    plan: str
    episodes_this_month: int
    created_at: str


@dataclass
class APIKeyInfo:
    key_id: str
    name: str
    key_prefix: str
    created_at: str
    last_used: Optional[str] = None
