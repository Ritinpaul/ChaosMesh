"""
ChaosMesh Arena — ORM Database Models.

Tables:
  users         — registered user accounts
  api_keys      — per-user API keys (bcrypt hashed)
  organizations — team accounts
  memberships   — user ↔ org membership
  episode_results — episode history + leaderboard data
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index,
    Integer, JSON, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from chaosmesh_arena.database.base import Base


def _now() -> datetime:
    return datetime.utcnow()


def _uuid() -> str:
    return str(uuid.uuid4())


# ── Users ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    # plan values: "free" | "pro" | "enterprise"
    org_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    episodes_this_month: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_active: Mapped[datetime] = mapped_column(DateTime, default=_now, onupdate=_now)

    # Relationships
    api_keys: Mapped[list[APIKey]] = relationship(
        "APIKey", back_populates="user", cascade="all, delete-orphan"
    )
    episodes: Mapped[list[EpisodeResult]] = relationship(
        "EpisodeResult", back_populates="user"
    )
    org: Mapped[Organization | None] = relationship("Organization", back_populates="members")


# ── API Keys ───────────────────────────────────────────────────────────────────

class APIKey(Base):
    __tablename__ = "api_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    key_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g. "cm_live_BnZ..."
    name: Mapped[str] = mapped_column(String(100), nullable=False, default="Default")
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    last_used: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship("User", back_populates="api_keys")

    __table_args__ = (
        Index("idx_api_keys_user_active", "user_id", "revoked"),
    )


# ── Organizations ──────────────────────────────────────────────────────────────

class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    seat_limit: Mapped[int] = mapped_column(Integer, default=5)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    members: Mapped[list[User]] = relationship("User", back_populates="org")
    memberships: Mapped[list[Membership]] = relationship(
        "Membership", back_populates="org", cascade="all, delete-orphan"
    )


class Membership(Base):
    __tablename__ = "memberships"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id", ondelete="CASCADE"))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(20), default="member")
    # role values: "admin" | "member" | "viewer"
    joined_at: Mapped[datetime] = mapped_column(DateTime, default=_now)

    org: Mapped[Organization] = relationship("Organization", back_populates="memberships")

    __table_args__ = (
        UniqueConstraint("user_id", "org_id", name="uq_membership"),
    )


# ── Episode Results & Leaderboard ──────────────────────────────────────────────

class EpisodeResult(Base):
    __tablename__ = "episode_results"

    episode_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    org_id: Mapped[str | None] = mapped_column(String(36), nullable=True)

    # Curriculum
    level: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # Scores (normalized)
    score: Mapped[float] = mapped_column(Float, default=0.0)          # [0.0, 1.0]
    cumulative_reward: Mapped[float] = mapped_column(Float, default=0.0)
    mttr_minutes: Mapped[float] = mapped_column(Float, default=0.0)
    steps: Mapped[int] = mapped_column(Integer, default=0)
    resolved: Mapped[bool] = mapped_column(Boolean, default=False)

    # Full action history for replay
    action_log: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User | None] = relationship("User", back_populates="episodes")

    __table_args__ = (
        Index("idx_episode_leaderboard", "level", "score"),
        Index("idx_episode_user_level", "user_id", "level"),
    )
