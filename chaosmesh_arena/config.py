"""
ChaosMesh Arena — Central configuration (Pydantic Settings).

All config is loaded from environment variables (or .env file).
Instantiate once via `get_settings()` and reuse everywhere.
"""

from __future__ import annotations

import os
import secrets
from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Auth — API Key (backward compatible) ────────────────
    chaosmesh_api_key: str = Field(default="", alias="CHAOSMESH_API_KEY")

    # ── Auth — JWT ──────────────────────────────────────────
    # MUST be set in production — auto-generated default for local dev only
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        alias="JWT_SECRET_KEY",
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_expire_hours: int = Field(default=24, alias="JWT_EXPIRE_HOURS")

    # ── Database ─────────────────────────────────────────────
    # SQLite for local dev; Postgres for production
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/sqlite/chaosmesh.db",
        alias="DATABASE_URL",
    )
    # Postgres URL for production (takes priority over sqlite if set)
    postgres_url: str = Field(default="", alias="POSTGRES_URL")

    # ── LLM — Ollama (primary) ────────────────────────────
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1:8b", alias="OLLAMA_MODEL")
    ollama_timeout_seconds: int = Field(default=30, alias="OLLAMA_TIMEOUT_SECONDS")

    # ── LLM — OpenRouter (secondary) ─────────────────────
    openrouter_api_key: str = Field(default="", alias="OPENROUTER_API_KEY")
    openrouter_model: str = Field(default="openai/gpt-4o-mini", alias="OPENROUTER_MODEL")
    openrouter_daily_budget: int = Field(default=200, alias="OPENROUTER_DAILY_BUDGET")

    # ── Redis ────────────────────────────────────────────
    redis_url: str = Field(default="redis://localhost:6379", alias="REDIS_URL")
    redis_max_connections: int = Field(default=10, alias="REDIS_MAX_CONNECTIONS")
    llm_cache_ttl_seconds: int = Field(default=3600, alias="LLM_CACHE_TTL_SECONDS")
    llm_cache_recent_limit: int = Field(default=200, alias="LLM_CACHE_RECENT_LIMIT")

    # ── Persistence ──────────────────────────────────────
    chromadb_path: str = Field(default="./data/chromadb", alias="CHROMADB_PATH")
    sqlite_path: str = Field(default="./data/sqlite/episodes.db", alias="SQLITE_PATH")

    # ── Server ───────────────────────────────────────────
    server_host: str = Field(default="0.0.0.0", alias="SERVER_HOST")
    server_port: int = Field(default=8000, alias="SERVER_PORT")
    # Strict CORS — no wildcard with credentials
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://localhost:5173", "http://localhost:7860"],
        alias="CORS_ORIGINS",
    )

    # ── Rate Limiting ────────────────────────────────────
    rate_limit_default: str = Field(default="60/minute", alias="RATE_LIMIT_DEFAULT")
    rate_limit_auth: str = Field(default="10/minute", alias="RATE_LIMIT_AUTH")
    rate_limit_env: str = Field(default="30/minute", alias="RATE_LIMIT_ENV")

    # ── Episode limits ────────────────────────────────────
    max_episode_messages: int = Field(default=50, alias="MAX_EPISODE_MESSAGES")
    max_episode_wall_seconds: int = Field(default=30, alias="MAX_EPISODE_WALL_SECONDS")
    max_sim_minutes: int = Field(default=15, alias="MAX_SIM_MINUTES")
    demo_fast_max_steps: int = Field(default=8, alias="DEMO_FAST_MAX_STEPS")
    demo_fast_wall_seconds: int = Field(default=20, alias="DEMO_FAST_WALL_SECONDS")

    # ── EnvPool ───────────────────────────────────────────
    max_concurrent_sessions: int = Field(default=50, alias="MAX_CONCURRENT_SESSIONS")
    session_ttl_seconds: int = Field(default=1800, alias="SESSION_TTL_SECONDS")  # 30 min

    # ── Plan limits ───────────────────────────────────────
    free_plan_episodes_per_month: int = Field(default=100, alias="FREE_PLAN_EPISODES_PER_MONTH")

    # ── Fallback tuning ───────────────────────────────────
    ollama_timeout_demo_seconds: int = Field(default=8, alias="OLLAMA_TIMEOUT_DEMO_SECONDS")
    openrouter_timeout_demo_seconds: int = Field(default=6, alias="OPENROUTER_TIMEOUT_DEMO_SECONDS")

    # ── Demo / Debug ─────────────────────────────────────
    demo_mode: bool = Field(default=False, alias="DEMO_MODE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    hf_space_base_url: str = Field(default="", alias="HF_SPACE_BASE_URL")
    hf_warm_keeper_interval_seconds: int = Field(default=240, alias="HF_WARM_KEEPER_INTERVAL_SECONDS")

    @field_validator("chromadb_path", "sqlite_path", mode="before")
    @classmethod
    def ensure_parent_exists(cls, v: str) -> str:
        """Create parent directories for persistence paths if they don't exist."""
        os.makedirs(os.path.dirname(os.path.abspath(v)), exist_ok=True)
        return v

    @property
    def openrouter_available(self) -> bool:
        return bool(self.openrouter_api_key and not self.openrouter_api_key.startswith("sk-or-v1-REPLACE"))

    @property
    def effective_database_url(self) -> str:
        """Return Postgres URL if configured, otherwise SQLite."""
        if self.postgres_url:
            return self.postgres_url
        return self.database_url

    @property
    def api_key_configured(self) -> bool:
        return bool(self.chaosmesh_api_key and self.chaosmesh_api_key != "cm_demo_change_me")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a singleton Settings instance (cached after first call)."""
    return Settings()
