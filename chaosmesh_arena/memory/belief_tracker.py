"""
ChaosMesh Arena — BeliefTracker (Task 2.15)

Persists and tracks agent belief accuracy across episodes in ChromaDB.
Provides cross-episode agent "profile" collections:
  - belief_history per agent
  - accuracy scoring against ground truth
  - snapshot retrieval for the observation model
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

import structlog

from chaosmesh_arena.models import AgentBeliefModel, AgentRole

log = structlog.get_logger(__name__)

# ChromaDB collection name for belief profiles
BELIEF_COLLECTION = "agent_belief_profiles"


class BeliefTracker:
    """
    Tracks agent beliefs across steps and episodes in ChromaDB.

    Each belief update is stored with:
    - episode_id, step, agent, hypothesis, confidence
    - Ground truth comparison (when resolved)
    - Cross-episode accuracy stats

    Used by:
    - ObservationModel.agent_beliefs (current episode snapshot)
    - RewardCalculator (belief accuracy bonus)
    - Dashboard (agent performance over time)
    """

    def __init__(self, vector_store_client=None) -> None:
        """
        Args:
            vector_store_client: chromadb.PersistentClient instance.
                                 If None, creates its own (embedded mode).
        """
        self._client = vector_store_client
        self._collection = None
        self._episode_beliefs: dict[str, dict[str, AgentBeliefModel]] = {}
        # episode_id → {agent_role → latest belief}
        self._resolution_cache: dict[str, list[bool]] = {}

    def _ensure_collection(self) -> None:
        """Lazy init ChromaDB collection."""
        if self._collection is not None:
            return
        try:
            if self._client is None:
                import chromadb
                from chaosmesh_arena.config import get_settings
                settings = get_settings()
                self._client = chromadb.PersistentClient(path=settings.chromadb_path)
            self._collection = self._client.get_or_create_collection(
                name=BELIEF_COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            log.info("belief_tracker_ready", collection=BELIEF_COLLECTION)
        except Exception as e:
            log.warning("belief_tracker_init_failed", error=str(e))

    # ── Write ─────────────────────────────────────────────────────────────────

    def update_belief(
        self,
        episode_id: str,
        step: int,
        belief: AgentBeliefModel,
    ) -> None:
        """
        Store or update an agent's belief for the current step.
        Updates in-memory cache immediately; persists to ChromaDB async-friendly.
        """
        agent_key = belief.agent.value

        # In-memory cache (fast access for obs building)
        if episode_id not in self._episode_beliefs:
            self._episode_beliefs[episode_id] = {}
        self._episode_beliefs[episode_id][agent_key] = belief

        # ChromaDB persistence
        self._ensure_collection()
        if self._collection is None:
            return

        doc_id = f"{episode_id}-{step}-{agent_key}"
        document = (
            f"Agent: {agent_key} | Episode: {episode_id} | Step: {step} | "
            f"Hypothesis: {belief.hypothesis[:300]} | Confidence: {belief.confidence:.2f}"
        )
        metadata = {
            "episode_id": episode_id,
            "step": str(step),
            "agent": agent_key,
            "confidence": str(round(belief.confidence, 4)),
            "hypothesis_snippet": belief.hypothesis[:200],
            "updated_at": datetime.utcnow().isoformat(),
        }

        try:
            # Upsert — ChromaDB allows adding same ID to update
            existing = self._collection.get(ids=[doc_id])
            if existing and existing["ids"]:
                self._collection.update(
                    ids=[doc_id],
                    documents=[document],
                    metadatas=[metadata],
                )
            else:
                self._collection.add(
                    ids=[doc_id],
                    documents=[document],
                    metadatas=[metadata],
                )
        except Exception as e:
            log.warning("belief_tracker_store_failed", error=str(e), doc_id=doc_id)

    def record_resolution(
        self,
        episode_id: str,
        agent: AgentRole,
        was_correct: bool,
        ground_truth: str,
    ) -> None:
        """
        Record whether an agent's final hypothesis matched ground truth.
        Called at episode end for reward calculation.
        """
        self._ensure_collection()
        if self._collection is None:
            return

        doc_id = f"{episode_id}-resolution-{agent.value}"
        document = (
            f"Resolution: agent={agent.value} | correct={was_correct} | "
            f"ground_truth={ground_truth[:300]}"
        )
        metadata = {
            "episode_id": episode_id,
            "agent": agent.value,
            "was_correct": str(was_correct),
            "ground_truth": ground_truth[:200],
            "resolved_at": datetime.utcnow().isoformat(),
            "type": "resolution",
        }

        try:
            self._collection.add(
                ids=[doc_id],
                documents=[document],
                metadatas=[metadata],
            )
            cache = self._resolution_cache.setdefault(agent.value, [])
            cache.append(was_correct)
            if len(cache) > 200:
                del cache[:-200]
        except Exception as e:
            log.warning("belief_resolution_failed", error=str(e))

    # ── Read ──────────────────────────────────────────────────────────────────

    def get_current_beliefs(
        self, episode_id: str
    ) -> dict[str, AgentBeliefModel]:
        """
        Return the current in-memory beliefs for a given episode.
        Used to populate ObservationModel.agent_beliefs.
        """
        return dict(self._episode_beliefs.get(episode_id, {}))

    def get_belief_history(
        self,
        agent: AgentRole,
        n: int = 10,
    ) -> list[dict]:
        """
        Retrieve the last n beliefs for an agent across all episodes.
        Useful for cross-episode pattern analysis.
        """
        self._ensure_collection()
        if self._collection is None or self._collection.count() == 0:
            return []

        try:
            results = self._collection.get(
                where={"agent": agent.value},
                limit=max(n * 4, n),
            )
            docs = results.get("documents", [])
            metas = results.get("metadatas", [])
            pairs = [
                (d, m)
                for d, m in zip(docs, metas)
                if m.get("type") != "resolution"
            ]
            pairs.sort(key=lambda item: int(item[1].get("step", "0")), reverse=True)
            pairs = pairs[:n]
            return [{"document": d, "metadata": m} for d, m in pairs]
        except Exception as e:
            log.warning("belief_history_failed", error=str(e))
            return []

    def compute_accuracy(
        self,
        agent: AgentRole,
        last_n_episodes: int = 10,
    ) -> float:
        """
        Compute resolution accuracy for an agent over recent episodes.
        Returns fraction of episodes where agent hypothesis was correct.
        """
        cached = self._resolution_cache.get(agent.value)
        if cached:
            window = cached[-last_n_episodes:]
            return sum(1 for v in window if v) / len(window)

        self._ensure_collection()
        if self._collection is None or self._collection.count() == 0:
            return 0.5  # Prior = 50%

        try:
            results = self._collection.get(
                where={"$and": [{"agent": agent.value}, {"type": "resolution"}]},
                limit=last_n_episodes,
            )
            metas = results.get("metadatas", [])
            if not metas:
                return 0.5
            vals = [m.get("was_correct") == "True" for m in metas]
            self._resolution_cache[agent.value] = vals[-200:]
            return sum(1 for v in vals if v) / len(vals)
        except Exception:
            return 0.5

    def clear_episode(self, episode_id: str) -> None:
        """Remove in-memory beliefs for a completed episode (keep ChromaDB for history)."""
        self._episode_beliefs.pop(episode_id, None)

    def reset(self) -> None:
        """Clear all in-memory state (ChromaDB persists)."""
        self._episode_beliefs.clear()
