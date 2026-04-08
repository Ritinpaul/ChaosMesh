"""
ChaosMesh SDK — Public API.

from chaosmesh_sdk import ChaosMeshClient, Episode, ChaosMeshGymEnv
"""

from chaosmesh_sdk.client import ChaosMeshClient
from chaosmesh_sdk.episode import Episode
from chaosmesh_sdk.exceptions import (
    AuthError,
    ChaosMeshError,
    ConnectionError,
    EpisodeConflict,
    EpisodeNotStarted,
    PlanLimitError,
    RateLimitError,
    ServerError,
    TokenExpiredError,
)
from chaosmesh_sdk.gymnasium_env import ChaosMeshGymEnv
from chaosmesh_sdk.models import (
    APIKeyInfo,
    EpisodeSummary,
    LeaderboardEntry,
    RewardBreakdown,
    StepResult,
    UserProfile,
)

__version__ = "0.2.0"
__all__ = [
    "ChaosMeshClient",
    "Episode",
    "ChaosMeshGymEnv",
    # Exceptions
    "ChaosMeshError",
    "AuthError",
    "TokenExpiredError",
    "EpisodeConflict",
    "EpisodeNotStarted",
    "RateLimitError",
    "PlanLimitError",
    "ServerError",
    "ConnectionError",
    # Models
    "StepResult",
    "RewardBreakdown",
    "EpisodeSummary",
    "LeaderboardEntry",
    "UserProfile",
    "APIKeyInfo",
    "__version__",
]
