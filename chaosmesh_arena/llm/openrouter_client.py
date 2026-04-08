"""
ChaosMesh Arena — OpenRouter Client (Secondary LLM backend).

OpenRouter is OpenAI-compatible, so we use the openai SDK.
Rate-limited to OPENROUTER_DAILY_BUDGET requests per day.
Falls back transparently when budget is exhausted.
"""

from __future__ import annotations

import time
from datetime import date

import structlog
from openai import AsyncOpenAI

from chaosmesh_arena.config import get_settings

log = structlog.get_logger(__name__)


class OpenRouterBudget:
    """Tracks daily request budget for OpenRouter."""

    def __init__(self, daily_limit: int) -> None:
        self._limit = daily_limit
        self._count = 0
        self._reset_date = date.today()

    def consume(self) -> bool:
        """Returns True if budget allows, False if exhausted."""
        self._maybe_reset()
        if self._count >= self._limit:
            return False
        self._count += 1
        return True

    @property
    def remaining(self) -> int:
        self._maybe_reset()
        return max(0, self._limit - self._count)

    def _maybe_reset(self) -> None:
        today = date.today()
        if today != self._reset_date:
            self._count = 0
            self._reset_date = today


class OpenRouterClient:
    """
    Async client for OpenRouter API (OpenAI-compatible).
    Enforces daily budget and provides structured output support.
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self) -> None:
        settings = get_settings()
        self._model = settings.openrouter_model
        self._budget = OpenRouterBudget(settings.openrouter_daily_budget)
        self._api_key = settings.openrouter_api_key or "dummy"
        self._client: AsyncOpenAI | None = None
        self._init_error: str | None = None

    def _get_client(self) -> AsyncOpenAI:
        if self._client is not None:
            return self._client
        if self._init_error:
            raise RuntimeError(self._init_error)
        try:
            self._client = AsyncOpenAI(
                api_key=self._api_key,
                base_url=self.BASE_URL,
            )
            return self._client
        except Exception as e:
            self._init_error = f"OpenRouter client init failed: {e}"
            raise RuntimeError(self._init_error)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        model: str | None = None,
    ) -> str:
        """
        Chat completion via OpenRouter.
        Returns empty string if budget exhausted or API key not set.
        """
        settings = get_settings()
        if not settings.openrouter_available:
            raise RuntimeError("OpenRouter API key not configured")

        if not self._budget.consume():
            raise RuntimeError(f"OpenRouter daily budget exhausted ({self._budget._limit} req/day)")

        client = self._get_client()
        response = await client.chat.completions.create(
            model=model or self._model,
            messages=messages,  # type: ignore[arg-type]
            temperature=temperature,
            max_tokens=max_tokens,
            extra_headers={
                "HTTP-Referer": "https://github.com/chaosmesh-arena",
                "X-Title": "ChaosMesh Arena",
            },
        )
        content = response.choices[0].message.content or ""
        log.debug(
            "openrouter_response",
            model=model or self._model,
            tokens=response.usage.total_tokens if response.usage else 0,
            budget_remaining=self._budget.remaining,
        )
        return content.strip()

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Convenience wrapper — build messages and call chat()."""
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages, temperature=temperature, max_tokens=max_tokens)

    async def is_available(self) -> bool:
        """Returns True if API key is valid and budget remains."""
        settings = get_settings()
        return settings.openrouter_available and self._budget.remaining > 0

    @property
    def budget_remaining(self) -> int:
        return self._budget.remaining
