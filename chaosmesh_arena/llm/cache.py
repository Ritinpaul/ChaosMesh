"""
ChaosMesh Arena — Redis-backed LLM Response Cache.

Caches LLM responses by prompt hash to avoid redundant API calls.
TTL: 1 hour (responses are context-dependent, so short TTL is intentional).
"""

from __future__ import annotations

import structlog
import redis.asyncio as aioredis

from chaosmesh_arena.config import get_settings

log = structlog.get_logger(__name__)

class LLMCache:
    """Redis-backed cache for LLM responses."""

    _PREFIX = "cm:llmcache:"
    _RECENT_LIST = "cm:llmcache:recent"

    def __init__(self) -> None:
        self._pool: aioredis.Redis | None = None
        settings = get_settings()
        self._ttl_seconds = settings.llm_cache_ttl_seconds
        self._recent_limit = settings.llm_cache_recent_limit

    async def _get_client(self) -> aioredis.Redis:
        if self._pool is None:
            settings = get_settings()
            self._pool = aioredis.from_url(
                settings.redis_url,
                max_connections=settings.redis_max_connections,
                decode_responses=True,
            )
        return self._pool

    async def get(self, key: str) -> str | None:
        try:
            r = await self._get_client()
            return await r.get(f"{self._PREFIX}{key}")
        except Exception as e:
            log.debug("cache_get_error", error=str(e))
            return None

    async def set(self, key: str, value: str) -> None:
        try:
            r = await self._get_client()
            cache_key = f"{self._PREFIX}{key}"
            pipe = r.pipeline()
            pipe.setex(cache_key, self._ttl_seconds, value)
            pipe.lrem(self._RECENT_LIST, 0, cache_key)
            pipe.lpush(self._RECENT_LIST, cache_key)
            pipe.ltrim(self._RECENT_LIST, 0, max(0, self._recent_limit - 1))
            await pipe.execute()
        except Exception as e:
            log.debug("cache_set_error", error=str(e))

    async def get_any_recent(self) -> str | None:
        """Return any recently cached response (for last-resort fallback)."""
        try:
            r = await self._get_client()
            recent_keys = await r.lrange(self._RECENT_LIST, 0, max(0, self._recent_limit - 1))
            for key in recent_keys:
                value = await r.get(key)
                if value:
                    return value
        except Exception:
            return None
        return None

    async def ping(self) -> bool:
        try:
            r = await self._get_client()
            return await r.ping()
        except Exception:
            return False

    async def flush(self) -> None:
        """Clear all cached responses (called on episode reset)."""
        try:
            r = await self._get_client()
            recent_keys = await r.lrange(self._RECENT_LIST, 0, max(0, self._recent_limit - 1))
            keys = list(dict.fromkeys(recent_keys))
            if keys:
                await r.delete(*keys)
            await r.delete(self._RECENT_LIST)
        except Exception as e:
            log.debug("cache_flush_error", error=str(e))
