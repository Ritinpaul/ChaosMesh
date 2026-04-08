"""
ChaosMesh SDK — HTTP Client.

Supports both sync and async usage:

  # Sync
  client = ChaosMeshClient(api_key="cm_live_...")
  profile = client.get_profile()

  # Async
  async with ChaosMeshClient(api_key="cm_live_...") as client:
      profile = await client.async_get_profile()

All methods have both sync (blocking) and async variants.
Retry logic with exponential backoff is built in.
"""

from __future__ import annotations

import time
from typing import Any, Literal, Optional

import httpx

from chaosmesh_sdk.exceptions import (
    AuthError,
    ChaosMeshError,
    ConnectionError,
    EpisodeConflict,
    PlanLimitError,
    RateLimitError,
    ServerError,
)
from chaosmesh_sdk.models import (
    APIKeyInfo,
    EpisodeSummary,
    LeaderboardEntry,
    RewardBreakdown,
    StepResult,
    UserProfile,
)

_DEFAULT_BASE_URL = "http://localhost:8000"
_DEFAULT_TIMEOUT = 30.0
_MAX_RETRIES = 3


def _parse_reward(data: dict) -> RewardBreakdown:
    r = data.get("reward", {})
    if isinstance(r, (int, float)):
        return RewardBreakdown(total=float(r))
    return RewardBreakdown(
        individual=r.get("individual", 0.0),
        coordination=r.get("coordination", 0.0),
        efficiency=r.get("efficiency", 0.0),
        resolution=r.get("resolution", 0.0),
        total=r.get("total", 0.0),
    )


def _check_response(resp: httpx.Response) -> dict:
    """Map HTTP status codes to typed exceptions."""
    if resp.status_code == 200 or resp.status_code == 201:
        try:
            return resp.json()
        except Exception:
            return {}
    if resp.status_code == 204:
        return {}

    try:
        detail = resp.json().get("detail", resp.text)
    except Exception:
        detail = resp.text

    if resp.status_code == 401:
        raise AuthError(f"Authentication failed: {detail}")
    if resp.status_code == 402:
        raise PlanLimitError(detail)
    if resp.status_code == 409:
        raise EpisodeConflict(detail)
    if resp.status_code == 429:
        retry_after = float(resp.headers.get("Retry-After", 60))
        raise RateLimitError(detail, retry_after=retry_after)
    if resp.status_code >= 500:
        raise ServerError(resp.status_code, detail)
    raise ChaosMeshError(f"HTTP {resp.status_code}: {detail}")


class ChaosMeshClient:
    """
    Main client for the ChaosMesh Arena API.

    Args:
        api_key: Your ChaosMesh API key (cm_live_...)
        base_url: Server URL (default: http://localhost:8000)
        timeout: Request timeout in seconds
        jwt_token: JWT token (auto-fetched if not provided)

    Usage (sync):
        client = ChaosMeshClient(api_key="cm_live_...")
        obs, info = client.reset(level=1)

    Usage (async context manager):
        async with ChaosMeshClient(api_key="cm_live_...") as client:
            obs, info = await client.async_reset(level=1)
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = _DEFAULT_BASE_URL,
        timeout: float = _DEFAULT_TIMEOUT,
        jwt_token: str = "",
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._jwt_token = jwt_token
        self._timeout = timeout
        self._sync_client: httpx.Client | None = None
        self._async_client: httpx.AsyncClient | None = None

    # ── Auth headers ───────────────────────────────────────────────────────────

    def _headers(self) -> dict:
        if self._jwt_token:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        if self._api_key:
            return {"X-API-Key": self._api_key}
        return {}

    # ── Sync HTTP ──────────────────────────────────────────────────────────────

    def _get_sync_client(self) -> httpx.Client:
        if self._sync_client is None or self._sync_client.is_closed:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self._timeout,
                headers=self._headers(),
                follow_redirects=True,
            )
        return self._sync_client

    def _request(self, method: str, path: str, **kwargs) -> dict:
        client = self._get_sync_client()
        for attempt in range(_MAX_RETRIES):
            try:
                resp = client.request(method, path, **kwargs)
                return _check_response(resp)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise ConnectionError(f"Cannot connect to {self.base_url}: {exc}") from exc
                time.sleep(2 ** attempt)
            except (AuthError, PlanLimitError, EpisodeConflict):
                raise
            except RateLimitError as exc:
                if attempt < _MAX_RETRIES - 1:
                    time.sleep(min(exc.retry_after, 10))
                else:
                    raise

    # ── Async HTTP ─────────────────────────────────────────────────────────────

    def _get_async_client(self) -> httpx.AsyncClient:
        if self._async_client is None or self._async_client.is_closed:
            self._async_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                headers=self._headers(),
                follow_redirects=True,
            )
        return self._async_client

    async def _async_request(self, method: str, path: str, **kwargs) -> dict:
        import asyncio
        client = self._get_async_client()
        for attempt in range(_MAX_RETRIES):
            try:
                resp = await client.request(method, path, **kwargs)
                return _check_response(resp)
            except (httpx.ConnectError, httpx.TimeoutException) as exc:
                if attempt == _MAX_RETRIES - 1:
                    raise ConnectionError(f"Cannot connect to {self.base_url}: {exc}") from exc
                await asyncio.sleep(2 ** attempt)
            except (AuthError, PlanLimitError, EpisodeConflict):
                raise
            except RateLimitError as exc:
                if attempt < _MAX_RETRIES - 1:
                    await asyncio.sleep(min(exc.retry_after, 10))
                else:
                    raise

    # ── Context managers ───────────────────────────────────────────────────────

    def __enter__(self) -> "ChaosMeshClient":
        return self

    def __exit__(self, *args) -> None:
        self.close()

    async def __aenter__(self) -> "ChaosMeshClient":
        return self

    async def __aexit__(self, *args) -> None:
        await self.async_close()

    def close(self) -> None:
        if self._sync_client:
            self._sync_client.close()

    async def async_close(self) -> None:
        if self._async_client:
            await self._async_client.aclose()

    # ── Token exchange ─────────────────────────────────────────────────────────

    def fetch_token(self) -> str:
        """Exchange API key for a JWT. Stores token internally."""
        data = self._request("POST", "/auth/token", json={"api_key": self._api_key})
        self._jwt_token = data["access_token"]
        # Refresh sync client headers
        self._sync_client = None
        return self._jwt_token

    async def async_fetch_token(self) -> str:
        data = await self._async_request("POST", "/auth/token", json={"api_key": self._api_key})
        self._jwt_token = data["access_token"]
        self._async_client = None
        return self._jwt_token

    # ── Auth / User ────────────────────────────────────────────────────────────

    def get_profile(self) -> UserProfile:
        data = self._request("GET", "/auth/me")
        return UserProfile(**{k: data[k] for k in UserProfile.__dataclass_fields__})

    async def async_get_profile(self) -> UserProfile:
        data = await self._async_request("GET", "/auth/me")
        return UserProfile(**{k: data[k] for k in UserProfile.__dataclass_fields__})

    def list_api_keys(self) -> list[APIKeyInfo]:
        data = self._request("GET", "/auth/keys")
        return [APIKeyInfo(
            key_id=k["key_id"], name=k["name"],
            key_prefix=k["key_prefix"], created_at=k["created_at"],
            last_used=k.get("last_used"),
        ) for k in data]

    # ── Environment ────────────────────────────────────────────────────────────

    def reset(self, level: int = 1) -> tuple[dict, dict]:
        """Reset and start a new episode. Returns (observation, info)."""
        data = self._request("POST", "/env/reset", json={"level": level})
        return data.get("observation", {}), {"episode_id": data.get("episode_id", "")}

    async def async_reset(self, level: int = 1) -> tuple[dict, dict]:
        data = await self._async_request("POST", "/env/reset", json={"level": level})
        return data.get("observation", {}), {"episode_id": data.get("episode_id", "")}

    def step(self, episode_id: str, action: dict) -> StepResult:
        """Submit an agent action. Returns StepResult."""
        data = self._request("POST", "/env/step", json={
            "episode_id": episode_id,
            "action": action,
        })
        return StepResult(
            observation=data.get("observation", {}),
            reward=_parse_reward(data),
            terminated=data.get("terminated", False),
            truncated=data.get("truncated", False),
            info=data.get("info", {}),
        )

    async def async_step(self, episode_id: str, action: dict) -> StepResult:
        data = await self._async_request("POST", "/env/step", json={
            "episode_id": episode_id,
            "action": action,
        })
        return StepResult(
            observation=data.get("observation", {}),
            reward=_parse_reward(data),
            terminated=data.get("terminated", False),
            truncated=data.get("truncated", False),
            info=data.get("info", {}),
        )

    def get_state(self) -> dict:
        return self._request("GET", "/env/state")

    def close_session(self) -> None:
        try:
            self._request("DELETE", "/env/session")
        except Exception:
            pass

    # ── Leaderboard ────────────────────────────────────────────────────────────

    def get_leaderboard(
        self,
        level: int | None = None,
        period: Literal["all_time", "week", "month"] = "all_time",
        limit: int = 10,
    ) -> list[LeaderboardEntry]:
        params: dict = {"limit": limit, "period": period}
        if level:
            params["level"] = level
        data = self._request("GET", "/leaderboard/global", params=params)
        return [LeaderboardEntry(**e) for e in (data if isinstance(data, list) else [])]

    async def async_get_leaderboard(self, level=None, period="all_time", limit=10):
        params: dict = {"limit": limit, "period": period}
        if level:
            params["level"] = level
        data = await self._async_request("GET", "/leaderboard/global", params=params)
        return [LeaderboardEntry(**e) for e in (data if isinstance(data, list) else [])]

    def get_my_rank(self, level: int | None = None) -> dict:
        params = {}
        if level:
            params["level"] = level
        return self._request("GET", "/leaderboard/me", params=params)

    # ── Episodes ───────────────────────────────────────────────────────────────

    def list_episodes(self, limit: int = 20, level: int | None = None) -> list[EpisodeSummary]:
        params: dict = {"limit": limit}
        if level:
            params["level"] = level
        data = self._request("GET", "/episodes/", params=params)
        return [EpisodeSummary(**e) for e in (data if isinstance(data, list) else [])]

    def get_episode(self, episode_id: str) -> EpisodeSummary:
        data = self._request("GET", f"/episodes/{episode_id}")
        return EpisodeSummary(**data)

    def get_replay(self, episode_id: str) -> dict:
        return self._request("GET", f"/episodes/{episode_id}/replay")

    # ── Health ─────────────────────────────────────────────────────────────────

    def health(self) -> dict:
        return self._request("GET", "/health")

    async def async_health(self) -> dict:
        return await self._async_request("GET", "/health")
