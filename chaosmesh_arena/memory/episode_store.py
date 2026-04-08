"""
ChaosMesh Arena — SQLite Episode Store.

Persists full episode logs: actions, observations, rewards, messages.
Uses SQLAlchemy async with aiosqlite. WAL mode for concurrency.
"""

from __future__ import annotations

import json
import os
from datetime import datetime

import structlog
from sqlalchemy import Column, DateTime, Float, Integer, String, Text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from chaosmesh_arena.config import get_settings

log = structlog.get_logger(__name__)


# ── SQLAlchemy Models ─────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


class EpisodeRow(Base):
    __tablename__ = "episodes"
    id = Column(String, primary_key=True)
    level = Column(Integer, nullable=False)
    status = Column(String, default="active")
    cumulative_reward = Column(Float, default=0.0)
    step_count = Column(Integer, default=0)
    mttr_sim_minutes = Column(Float, nullable=True)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    seed = Column(Integer, nullable=True)


class StepRow(Base):
    __tablename__ = "steps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    episode_id = Column(String, nullable=False, index=True)
    step = Column(Integer, nullable=False)
    agent = Column(String, nullable=False)
    action_type = Column(String, nullable=False)
    action_json = Column(Text, nullable=False)
    reward_total = Column(Float, default=0.0)
    reward_json = Column(Text, nullable=False)
    sim_time_minutes = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)


class MessageRow(Base):
    __tablename__ = "messages"
    id = Column(String, primary_key=True)
    episode_id = Column(String, nullable=False, index=True)
    step = Column(Integer, nullable=False)
    sender = Column(String, nullable=False)
    recipient = Column(String, nullable=True)
    message_type = Column(String, nullable=False)
    urgency = Column(String, nullable=False)
    content_json = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class IncidentRow(Base):
    __tablename__ = "incidents"
    id = Column(String, primary_key=True)
    episode_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    level = Column(Integer, nullable=False)
    status = Column(String, default="active")
    root_cause = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    mttr_sim_minutes = Column(Float, nullable=True)


# ── Episode Store ─────────────────────────────────────────────────────────────

class EpisodeStore:
    """
    Async SQLite store for episode history.
    All writes are fire-and-forget; reads are used for debugging / dashboards.
    """

    def __init__(self) -> None:
        settings = get_settings()
        db_path = settings.sqlite_path
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        self._engine = create_async_engine(
            f"sqlite+aiosqlite:///{db_path}",
            echo=False,
        )
        self._session_factory = async_sessionmaker(
            self._engine, expire_on_commit=False, class_=AsyncSession
        )

    async def init_db(self) -> None:
        """Create tables and enable WAL mode."""
        from sqlalchemy import text
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            # Enable WAL for concurrent reads
            await conn.execute(text("PRAGMA journal_mode=WAL"))
            await conn.execute(text("PRAGMA synchronous=NORMAL"))
        log.info("episode_store_ready")

    # ── Write operations ──────────────────────────────────────────────────────

    async def create_episode(
        self,
        episode_id: str,
        level: int,
        seed: int | None = None,
    ) -> None:
        async with self._session_factory() as session:
            session.add(EpisodeRow(id=episode_id, level=level, seed=seed))
            await session.commit()

    async def log_step(
        self,
        episode_id: str,
        step: int,
        agent: str,
        action_type: str,
        action_dict: dict,
        reward_dict: dict,
        sim_time: float,
    ) -> None:
        async with self._session_factory() as session:
            session.add(StepRow(
                episode_id=episode_id,
                step=step,
                agent=agent,
                action_type=action_type,
                action_json=json.dumps(action_dict),
                reward_total=reward_dict.get("total", 0.0),
                reward_json=json.dumps(reward_dict),
                sim_time_minutes=sim_time,
            ))
            await session.commit()

    async def log_message(
        self,
        episode_id: str,
        step: int,
        msg_id: str,
        sender: str,
        recipient: str | None,
        msg_type: str,
        urgency: str,
        content: dict,
    ) -> None:
        async with self._session_factory() as session:
            session.add(MessageRow(
                id=msg_id,
                episode_id=episode_id,
                step=step,
                sender=sender,
                recipient=recipient,
                message_type=msg_type,
                urgency=urgency,
                content_json=json.dumps(content),
            ))
            await session.commit()

    async def log_incident(
        self,
        episode_id: str,
        incident_id: str,
        title: str,
        level: int,
        root_cause: str = "",
    ) -> None:
        async with self._session_factory() as session:
            session.add(IncidentRow(
                id=incident_id,
                episode_id=episode_id,
                title=title,
                level=level,
                root_cause=root_cause,
            ))
            await session.commit()

    async def close_episode(
        self,
        episode_id: str,
        status: str,
        cumulative_reward: float,
        step_count: int,
        mttr_minutes: float | None = None,
    ) -> None:
        from sqlalchemy import update
        async with self._session_factory() as session:
            await session.execute(
                update(EpisodeRow)
                .where(EpisodeRow.id == episode_id)
                .values(
                    status=status,
                    cumulative_reward=cumulative_reward,
                    step_count=step_count,
                    mttr_sim_minutes=mttr_minutes,
                    ended_at=datetime.utcnow(),
                )
            )
            await session.commit()

    # ── Read operations ───────────────────────────────────────────────────────

    async def get_episode_summary(self, episode_id: str) -> dict | None:
        from sqlalchemy import select
        async with self._session_factory() as session:
            row = await session.get(EpisodeRow, episode_id)
            if not row:
                return None
            return {
                "id": row.id,
                "level": row.level,
                "status": row.status,
                "cumulative_reward": row.cumulative_reward,
                "step_count": row.step_count,
                "mttr_sim_minutes": row.mttr_sim_minutes,
                "started_at": row.started_at.isoformat() if row.started_at else None,
                "ended_at": row.ended_at.isoformat() if row.ended_at else None,
            }

    async def list_episodes(self, limit: int = 20) -> list[dict]:
        from sqlalchemy import select
        async with self._session_factory() as session:
            result = await session.execute(
                select(EpisodeRow).order_by(EpisodeRow.started_at.desc()).limit(limit)
            )
            rows = result.scalars().all()
            return [
                {
                    "id": r.id, "level": r.level, "status": r.status,
                    "cumulative_reward": r.cumulative_reward, "step_count": r.step_count,
                    "mttr_sim_minutes": r.mttr_sim_minutes,
                }
                for r in rows
            ]
