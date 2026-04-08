"""
ChaosMesh Arena — Ollama Client (Primary LLM backend).

Wraps the Ollama HTTP API for local Llama 3.1 8B inference.
Fully async, with timeout and error handling.
"""

from __future__ import annotations

import json
import structlog

import httpx

from chaosmesh_arena.config import get_settings

log = structlog.get_logger(__name__)


class OllamaClient:
    """
    Async client for local Ollama inference.

    API reference: https://github.com/ollama/ollama/blob/main/docs/api.md
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._base_url = settings.ollama_base_url.rstrip("/")
        self._model = settings.ollama_model
        self._timeout = settings.ollama_timeout_seconds

    async def generate(
        self,
        prompt: str,
        system: str = "",
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Generate a completion via Ollama /api/generate.
        Returns the assistant text response.
        Raises httpx.TimeoutException if the model is too slow.
        """
        payload: dict = {
            "model": self._model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/generate",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "").strip()

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """
        Chat completion via Ollama /api/chat.
        messages: list of {"role": "user"/"assistant"/"system", "content": "..."}
        """
        payload = {
            "model": self._model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.post(
                f"{self._base_url}/api/chat",
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
            return data.get("message", {}).get("content", "").strip()

    async def is_available(self) -> bool:
        """Health check — returns True if Ollama is running and model is loaded."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self._base_url}/api/tags")
                if resp.status_code != 200:
                    return False
                models = [m["name"] for m in resp.json().get("models", [])]
                model_base = self._model.split(":")[0]
                return any(model_base in m for m in models)
        except Exception:
            return False

    async def pull_model(self) -> bool:
        """Pull the configured model if not already present."""
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                resp = await client.post(
                    f"{self._base_url}/api/pull",
                    json={"name": self._model, "stream": False},
                )
                return resp.status_code == 200
        except Exception as e:
            log.error("ollama_pull_failed", model=self._model, error=str(e))
            return False
