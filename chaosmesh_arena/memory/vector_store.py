"""
ChaosMesh Arena — ChromaDB Vector Store (Persistent Agent Memory).

Embedded mode: SQLite backend, persists to ./data/chromadb.
Per-agent collections with episode namespace isolation.
"""

from __future__ import annotations

from typing import Optional

import chromadb
import structlog

from chaosmesh_arena.config import get_settings
from chaosmesh_arena.models import AgentRole

log = structlog.get_logger(__name__)


# Collection names — one per agent role
_COLLECTIONS = {
    AgentRole.DIAGNOSTICS: "diagnostics_patterns",
    AgentRole.SECURITY: "security_patterns",
    AgentRole.REMEDIATION: "remediation_playbooks",
    AgentRole.INCIDENT_COMMANDER: "commander_decisions",
    AgentRole.DATABASE: "database_patterns",
    "incidents": "incident_history",
}


class VectorStore:
    """
    ChromaDB embedded vector store for agent persistent memory.

    Each agent has its own collection.
    Documents are namespaced by episode_id for isolation.
    Cross-episode retrieval is supported for knowledge accumulation.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = chromadb.PersistentClient(path=settings.chromadb_path)
        self._collections: dict[str, chromadb.Collection] = {}
        self._init_collections()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_collections(self) -> None:
        for role, col_name in _COLLECTIONS.items():
            self._collections[str(role)] = self._client.get_or_create_collection(
                name=col_name,
                metadata={"hnsw:space": "cosine"},
            )
        log.info("vector_store_ready", collections=list(self._collections.keys()))

    # ── Write ─────────────────────────────────────────────────────────────────

    def store_finding(
        self,
        agent: AgentRole,
        episode_id: str,
        finding: str,
        metadata: Optional[dict] = None,
    ) -> str:
        """
        Store an agent finding as a vector document.
        Returns the document ID for later reference.
        """
        import uuid
        doc_id = f"{episode_id}-{uuid.uuid4().hex[:8]}"
        collection = self._collections.get(str(agent))
        if not collection:
            return doc_id
        collection.add(
            documents=[finding],
            ids=[doc_id],
            metadatas=[{"episode_id": episode_id, "agent": str(agent), **(metadata or {})}],
        )
        log.debug("vector_store_stored", agent=str(agent), doc_id=doc_id)
        return doc_id

    def store_incident_pattern(
        self,
        episode_id: str,
        incident_description: str,
        resolution: str,
        level: int,
        mttr_minutes: float,
    ) -> None:
        """Store a resolved incident pattern for cross-episode learning."""
        col = self._collections.get("incidents")
        if not col:
            return
        import uuid
        col.add(
            documents=[f"Incident: {incident_description}\nResolution: {resolution}"],
            ids=[f"inc-{episode_id}-{uuid.uuid4().hex[:8]}"],
            metadatas={
                "episode_id": episode_id,
                "level": level,
                "mttr_minutes": mttr_minutes,
            },
        )

    # ── Read ──────────────────────────────────────────────────────────────────

    def query_similar(
        self,
        agent: AgentRole,
        query_text: str,
        n_results: int = 5,
        episode_filter: Optional[str] = None,
    ) -> list[dict]:
        """
        Find similar past findings for an agent.
        Returns list of {"document": ..., "metadata": ..., "distance": ...}
        """
        collection = self._collections.get(str(agent))
        if not collection or collection.count() == 0:
            return []

        where = {"episode_id": episode_filter} if episode_filter else None

        try:
            results = collection.query(
                query_texts=[query_text],
                n_results=min(n_results, collection.count()),
                where=where,
            )
        except Exception as e:
            log.warning("vector_query_error", error=str(e))
            return []

        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        dists = results.get("distances", [[]])[0]

        return [
            {"document": d, "metadata": m, "distance": dist}
            for d, m, dist in zip(docs, metas, dists)
        ]

    def query_incident_history(
        self,
        query_text: str,
        n_results: int = 3,
    ) -> list[dict]:
        """Find similar past incidents for the Chaos Engine and agents."""
        col = self._collections.get("incidents")
        if not col or col.count() == 0:
            return []
        try:
            results = col.query(
                query_texts=[query_text],
                n_results=min(n_results, col.count()),
            )
            docs = results.get("documents", [[]])[0]
            metas = results.get("metadatas", [[]])[0]
            return [{"document": d, "metadata": m} for d, m in zip(docs, metas)]
        except Exception:
            return []

    def collection_stats(self) -> dict[str, int]:
        """Return document count per collection."""
        return {name: col.count() for name, col in self._collections.items()}

    def reset_episode(self, episode_id: str) -> None:
        """
        Remove all documents for a given episode_id.
        Preserves cross-episode knowledge — only clears episode-specific data.
        """
        for collection in self._collections.values():
            try:
                results = collection.get(where={"episode_id": episode_id})
                if results and results["ids"]:
                    collection.delete(ids=results["ids"])
            except Exception:
                pass

    # ── Async adapters (used by BaseAgent) ────────────────────────────────────

    async def query(
        self,
        collection: str,
        query_text: str,
        n_results: int = 3,
        episode_filter: str | None = None,
    ) -> list[dict]:
        """
        Async adapter — BaseAgent calls this interface.
        Maps to query_similar() with role-key lookup.
        """
        import asyncio
        loop = asyncio.get_event_loop()
        # Try direct collection key first, then try as AgentRole
        from chaosmesh_arena.models import AgentRole
        role = None
        for r in AgentRole:
            if r.value == collection or str(r) == collection:
                role = r
                break
        if role is None:
            return []
        return await loop.run_in_executor(
            None,
            lambda: self.query_similar(
                agent=role,
                query_text=query_text,
                n_results=n_results,
                episode_filter=episode_filter,
            ),
        )

    async def add(
        self,
        collection: str,
        document: str,
        metadata: dict,
        doc_id: str,
    ) -> None:
        """
        Async adapter — BaseAgent calls this to persist findings.
        Maps to store_finding().
        """
        import asyncio
        from chaosmesh_arena.models import AgentRole
        loop = asyncio.get_event_loop()
        role = None
        for r in AgentRole:
            if r.value == collection or str(r) == collection:
                role = r
                break
        if role is None:
            return
        col = self._collections.get(str(role))
        if col is None:
            return

        def _add() -> None:
            try:
                col.add(
                    documents=[document],
                    ids=[doc_id],
                    metadatas=[{**metadata}],
                )
            except Exception as e:
                log.warning("vector_add_failed", error=str(e), doc_id=doc_id)

        await loop.run_in_executor(None, _add)
