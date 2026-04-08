"""
ChaosMesh Arena — EnvPool.

Manages per-user/per-session ChaosMeshArenaEnv instances.
Replaces the global `_env` singleton with a concurrent-safe pool.

Key properties:
  - Each session gets its own isolated env
  - Sessions expire after TTL (default 30 min)
  - Max concurrent sessions enforced
  - All gym calls dispatched via asyncio.to_thread() (non-blocking)
"""

from __future__ import annotations

import asyncio
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

import structlog

from chaosmesh_arena.config import get_settings
from chaosmesh_arena.env import ChaosMeshArenaEnv
from chaosmesh_arena.models import ActionModel, IncidentLevel

log = structlog.get_logger(__name__)


@dataclass
class SessionEntry:
    session_id: str
    user_id: str
    env: ChaosMeshArenaEnv
    episode_id: str = ""
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.last_active = time.time()

    def is_expired(self, ttl: int) -> bool:
        return (time.time() - self.last_active) > ttl


class EnvPool:
    """
    Thread-safe pool of ChaosMeshArenaEnv instances, one per user session.

    Usage:
        pool = EnvPool()
        session_id = await pool.create_session(user_id="u123")
        obs, info = await pool.reset(session_id, level=1)
        obs, reward, done, trunc, info = await pool.step(session_id, action)
        await pool.close_session(session_id)
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionEntry] = {}
        self._lock = asyncio.Lock()
        self._cleanup_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start the background session cleanup loop."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        log.info("env_pool_started")

    async def stop(self) -> None:
        """Cancel background tasks and close all envs."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        async with self._lock:
            for entry in list(self._sessions.values()):
                try:
                    await asyncio.to_thread(entry.env.close)
                except Exception:
                    pass
            self._sessions.clear()
        log.info("env_pool_stopped")

    async def create_session(self, user_id: str) -> str:
        """
        Create a new isolated env session for a user.

        Returns:
            session_id (UUID string)

        Raises:
            RuntimeError if pool is at capacity
        """
        settings = get_settings()
        async with self._lock:
            # Enforce capacity limit
            active = sum(1 for s in self._sessions.values() if s.user_id == user_id or True)
            # Per-pool limit
            if len(self._sessions) >= settings.max_concurrent_sessions:
                raise RuntimeError(
                    f"Server at capacity ({settings.max_concurrent_sessions} concurrent sessions). "
                    "Please try again shortly."
                )

            session_id = str(uuid.uuid4())
            env = ChaosMeshArenaEnv(demo_mode=settings.demo_mode)
            entry = SessionEntry(session_id=session_id, user_id=user_id, env=env)
            self._sessions[session_id] = entry
            log.info("session_created", session_id=session_id, user_id=user_id, total=len(self._sessions))
            return session_id

    async def reset(
        self,
        session_id: str,
        level: int = 1,
        seed: int | None = None,
        demo_scenario: str | None = None,
    ) -> tuple[Any, dict]:
        """Reset the env for a session and return (obs, info)."""
        entry = self._get_entry(session_id)
        options: dict[str, Any] = {"level": level}
        if demo_scenario:
            options["demo_scenario"] = demo_scenario

        obs, info = await asyncio.to_thread(
            entry.env.reset,
            seed=seed,
            options=options,
        )
        entry.episode_id = info.get("episode_id", "")
        entry.touch()
        log.info("session_reset", session_id=session_id, level=level, episode_id=entry.episode_id)
        return obs, info

    async def step(self, session_id: str, action: ActionModel) -> tuple:
        """Step the env and return (obs, reward, terminated, truncated, info)."""
        entry = self._get_entry(session_id)
        result = await asyncio.to_thread(entry.env.step, action)
        entry.touch()
        return result

    def get_state(self, session_id: str) -> Any:
        """Return FullStateModel (sync, call in to_thread if on hot path)."""
        entry = self._get_entry(session_id)
        entry.touch()
        return entry.env.state()

    def get_render(self, session_id: str) -> dict:
        """Return cluster state dict for visualization."""
        entry = self._get_entry(session_id)
        return entry.env.render()

    def get_episode_id(self, session_id: str) -> str:
        entry = self._get_entry(session_id)
        return entry.episode_id

    async def close_session(self, session_id: str) -> None:
        """Cleanly close and remove a session."""
        async with self._lock:
            entry = self._sessions.pop(session_id, None)
        if entry:
            try:
                await asyncio.to_thread(entry.env.close)
            except Exception as exc:
                log.warning("session_close_error", session_id=session_id, error=str(exc))
            log.info("session_closed", session_id=session_id)

    @property
    def active_session_count(self) -> int:
        return len(self._sessions)

    def get_session_info(self, session_id: str) -> dict:
        entry = self._get_entry(session_id)
        return {
            "session_id": session_id,
            "user_id": entry.user_id,
            "episode_id": entry.episode_id,
            "age_seconds": round(time.time() - entry.created_at, 1),
            "idle_seconds": round(time.time() - entry.last_active, 1),
        }

    # ── Internal helpers ───────────────────────────────────────────────────────

    def _get_entry(self, session_id: str) -> SessionEntry:
        entry = self._sessions.get(session_id)
        if entry is None:
            raise KeyError(f"Session '{session_id}' not found or expired.")
        return entry

    async def _cleanup_loop(self) -> None:
        """Background task: evict expired sessions every 60 seconds."""
        settings = get_settings()
        while True:
            try:
                await asyncio.sleep(60)
                await self._evict_expired(settings.session_ttl_seconds)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("cleanup_loop_error", error=str(exc))

    async def _evict_expired(self, ttl: int) -> None:
        async with self._lock:
            expired = [
                sid for sid, entry in self._sessions.items()
                if entry.is_expired(ttl)
            ]

        for sid in expired:
            log.info("session_evicted_ttl", session_id=sid)
            await self.close_session(sid)

        if expired:
            log.info("session_cleanup_done", evicted=len(expired), remaining=len(self._sessions))


# Global singleton — initialized in server lifespan
env_pool = EnvPool()
