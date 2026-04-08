"""
ChaosMesh Arena — LLM Router (Ollama → OpenRouter → Cache fallback chain).

Implements the dual-LLM strategy: always try local Ollama first (free,
unlimited), fall back to OpenRouter if Ollama is unavailable or too slow,
and finally serve from Redis cache if both fail.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

import structlog

from chaosmesh_arena.config import get_settings
from chaosmesh_arena.llm.cache import LLMCache
from chaosmesh_arena.llm.ollama_client import OllamaClient
from chaosmesh_arena.llm.openrouter_client import OpenRouterClient

log = structlog.get_logger(__name__)


class LLMRouter:
    """
    Routes LLM inference requests through the fallback chain:
    1. Ollama (local, primary — unlimited, free)
    2. OpenRouter (cloud, rate-limited — 200 req/day budget)
    3. Cache (Redis — returns most similar cached response)

    All methods are async-safe and include structured logging.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._ollama = OllamaClient()
        self._openrouter = OpenRouterClient()
        self._cache = LLMCache()
        self._ollama_timeout = (
            settings.ollama_timeout_demo_seconds if settings.demo_mode else 30.0
        )
        self._openrouter_timeout = (
            settings.openrouter_timeout_demo_seconds if settings.demo_mode else 20.0
        )

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        agent_role: str = "unknown",
        allow_cache: bool = True,
    ) -> tuple[str, str]:
        """
        Generate a response through the fallback chain.

        Returns:
            (response_text, source) where source is "ollama", "openrouter", or "cache"
        """
        cache_key = self._make_cache_key(prompt, system, temperature, max_tokens=max_tokens)

        # ── Try cache first (for identical prompts) ──────────────────────────
        if allow_cache:
            cached = await self._cache.get(cache_key)
            if cached:
                log.debug("llm_cache_hit", agent=agent_role, key=cache_key[:12])
                return cached, "cache"

        # ── 1. Ollama (primary) ───────────────────────────────────────────────
        try:
            response = await asyncio.wait_for(
                self._ollama.generate(prompt, system=system, temperature=temperature,
                                      max_tokens=max_tokens),
                timeout=self._ollama_timeout,
            )
            log.info("llm_ollama_success", agent=agent_role, tokens=len(response.split()))
            if allow_cache:
                await self._cache.set(cache_key, response)
            return response, "ollama"
        except asyncio.TimeoutError:
            log.warning("llm_ollama_timeout", agent=agent_role, timeout=self._ollama_timeout)
        except Exception as e:
            log.warning("llm_ollama_error", agent=agent_role, error=str(e))

        # ── 2. OpenRouter (secondary) ─────────────────────────────────────────
        try:
            response = await asyncio.wait_for(
                self._openrouter.generate(prompt, system=system, temperature=temperature,
                                          max_tokens=max_tokens),
                timeout=self._openrouter_timeout,
            )
            log.info(
                "llm_openrouter_success",
                agent=agent_role,
                budget_remaining=self._openrouter.budget_remaining,
            )
            if allow_cache:
                await self._cache.set(cache_key, response)
            return response, "openrouter"
        except asyncio.TimeoutError:
            log.warning("llm_openrouter_timeout", agent=agent_role)
        except Exception as e:
            log.warning("llm_openrouter_error", agent=agent_role, error=str(e))

        # ── 3. Cache fallback (similar prompt) ───────────────────────────────
        similar = await self._cache.get_any_recent()
        if similar:
            log.warning("llm_cache_fallback", agent=agent_role)
            return f"[DEGRADED — cached response] {similar}", "cache_fallback"

        # ── 4. Last resort hardcoded stub ─────────────────────────────────────
        log.error("llm_all_backends_failed", agent=agent_role)
        return (
            '{"finding": "Unable to analyze — LLM backends unavailable", '
            '"confidence": 0.0, "recommended_action": "noop"}',
            "stub",
        )

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        agent_role: str = "unknown",
        allow_cache: bool = True,
    ) -> tuple[str, str]:
        """
        Chat-style generation (with conversation history).
        Same fallback chain as generate().
        """
        # Build a single string for cache key
        prompt_str = json.dumps(messages, sort_keys=True)
        cache_key = self._make_cache_key(prompt_str, "", temperature, max_tokens=max_tokens)

        if allow_cache:
            cached = await self._cache.get(cache_key)
            if cached:
                return cached, "cache"

        # 1. Ollama
        try:
            response = await asyncio.wait_for(
                self._ollama.chat(messages, temperature=temperature, max_tokens=max_tokens),
                timeout=self._ollama_timeout,
            )
            if allow_cache:
                await self._cache.set(cache_key, response)
            return response, "ollama"
        except Exception as e:
            log.warning("llm_ollama_chat_error", error=str(e))

        # 2. OpenRouter
        try:
            response = await asyncio.wait_for(
                self._openrouter.chat(messages, temperature=temperature, max_tokens=max_tokens),
                timeout=self._openrouter_timeout,
            )
            if allow_cache:
                await self._cache.set(cache_key, response)
            return response, "openrouter"
        except Exception as e:
            log.warning("llm_openrouter_chat_error", error=str(e))

        return '{"error": "all LLM backends failed"}', "stub"

    async def infer(
        self,
        system: str,
        prompt: str,
        max_tokens: int = 512,
        temperature: float = 0.3,
        agent_role: str = "unknown",
    ) -> str:
        """
        Alias used by BaseAgent.act() — delegates to generate().
        Returns only the text (not the source tuple).
        """
        text, _ = await self.generate(
            prompt=prompt,
            system=system,
            temperature=temperature,
            max_tokens=max_tokens,
            agent_role=agent_role,
        )
        return text

    async def check_backends(self) -> dict[str, bool]:
        """Health check for all backends."""
        ollama_ok, openrouter_ok = await asyncio.gather(
            self._ollama.is_available(),
            self._openrouter.is_available(),
            return_exceptions=True,
        )
        return {
            "ollama": bool(ollama_ok) if not isinstance(ollama_ok, Exception) else False,
            "openrouter": bool(openrouter_ok) if not isinstance(openrouter_ok, Exception) else False,
            "cache": await self._cache.ping(),
        }

    @staticmethod
    def _make_cache_key(
        prompt: str,
        system: str,
        temperature: float,
        max_tokens: int,
    ) -> str:
        content = f"{system}|||{prompt}|||{temperature:.2f}|||{max_tokens}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]
