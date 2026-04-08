"""
ChaosMesh Arena — Enhanced WebSocket Broadcast Manager (Task 3.1)

Full-featured real-time event bus:
- Per-client subscription filtering (episode, agent role)
- Typed event schema with timestamps
- Dead-connection pruning with backpressure
- Room-style broadcast (episode-scoped)
- Agent chat stream relay
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Any

import structlog
from fastapi import WebSocket
from starlette.websockets import WebSocketState

log = structlog.get_logger(__name__)

# ── Event type constants ───────────────────────────────────────────────────────
EVT_EPISODE_STARTED  = "episode_started"
EVT_EPISODE_ENDED    = "episode_ended"
EVT_STEP_COMPLETE    = "step_complete"
EVT_INCIDENT_INJECTED = "incident_injected"
EVT_AGENT_MESSAGE    = "agent_message"
EVT_CLUSTER_SNAPSHOT = "cluster_snapshot"
EVT_METRICS_UPDATE   = "metrics_update"
EVT_REWARD_UPDATE    = "reward_update"
EVT_LEVEL_ADVANCED   = "level_advanced"
EVT_BELIEF_UPDATE    = "belief_update"
EVT_CHAOS_MUTATION   = "chaos_mutation"
EVT_PONG             = "pong"
EVT_CONNECTED        = "connected"
EVT_ERROR            = "error"


@dataclass
class WSClient:
    """Metadata for a single connected WebSocket client."""
    ws: WebSocket
    connected_at: float = field(default_factory=time.time)
    episode_filter: str | None = None   # Only receive events for this episode
    subscriptions: set[str] = field(default_factory=set)  # Event type filters
    client_id: str = field(default="")

    def __post_init__(self) -> None:
        if not self.client_id:
            import uuid
            self.client_id = str(uuid.uuid4())[:8]


class ConnectionManager:
    """
    Enhanced WebSocket connection manager.

    Features:
    - Multi-client broadcast with dead-connection pruning
    - Episode-scoped rooms (clients only get events for their episode)
    - Per-event-type subscription filtering
    - Agent chat stream relay
    - Structured event envelopes with timestamps
    """

    def __init__(self) -> None:
        self._clients: list[WSClient] = []
        self._lock = asyncio.Lock()

    # ── Connection lifecycle ───────────────────────────────────────────────────

    async def connect(self, ws: WebSocket, episode_filter: str | None = None) -> WSClient:
        """Accept and register a new WebSocket client."""
        await ws.accept()
        client = WSClient(ws=ws, episode_filter=episode_filter)
        async with self._lock:
            self._clients.append(client)
        log.info(
            "ws_client_connected",
            client_id=client.client_id,
            total=len(self._clients),
            episode_filter=episode_filter,
        )
        return client

    async def disconnect(self, ws: WebSocket) -> None:
        """Remove a WebSocket from the active set."""
        async with self._lock:
            self._clients = [c for c in self._clients if c.ws is not ws]
        log.info("ws_client_disconnected", total=len(self._clients))

    # ── Broadcast API ──────────────────────────────────────────────────────────

    async def broadcast(
        self,
        event_type: str,
        data: dict[str, Any],
        episode_id: str | None = None,
    ) -> None:
        """
        Broadcast a typed event to all matching clients.

        Args:
            event_type: Event identifier string
            data: Event payload dict
            episode_id: If set, only send to clients subscribed to this episode
        """
        envelope = self._make_envelope(event_type, data)
        payload = json.dumps(envelope)
        dead: list[WSClient] = []

        async with self._lock:
            targets = list(self._clients)

        for client in targets:
            # Episode scope filter
            if episode_id and client.episode_filter and client.episode_filter != episode_id:
                continue
            # Subscription filter (empty set = all events)
            if client.subscriptions and event_type not in client.subscriptions:
                continue
            try:
                if client.ws.client_state == WebSocketState.CONNECTED:
                    await client.ws.send_text(payload)
                else:
                    dead.append(client)
            except Exception as e:
                log.warning("ws_broadcast_error", client_id=client.client_id, error=str(e))
                dead.append(client)

        if dead:
            async with self._lock:
                for d in dead:
                    try:
                        self._clients.remove(d)
                    except ValueError:
                        pass
            log.info("ws_pruned_dead_clients", count=len(dead))

    async def send_to(
        self,
        ws: WebSocket,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Send a typed event to a single client."""
        try:
            envelope = self._make_envelope(event_type, data)
            await ws.send_text(json.dumps(envelope))
        except Exception as e:
            log.warning("ws_send_error", error=str(e))

    # ── Typed event helpers ────────────────────────────────────────────────────

    async def emit_step(
        self,
        episode_id: str,
        step: int,
        agent: str,
        action_type: str,
        reward: float,
        terminated: bool,
        truncated: bool,
        cumulative_reward: float,
    ) -> None:
        await self.broadcast(EVT_STEP_COMPLETE, {
            "episode_id": episode_id,
            "step": step,
            "agent": agent,
            "action_type": action_type,
            "reward": reward,
            "cumulative_reward": cumulative_reward,
            "terminated": terminated,
            "truncated": truncated,
        }, episode_id=episode_id)

    async def emit_agent_message(
        self,
        episode_id: str,
        sender: str,
        recipient: str | None,
        message_type: str,
        finding: str,
        confidence: float,
    ) -> None:
        await self.broadcast(EVT_AGENT_MESSAGE, {
            "episode_id": episode_id,
            "sender": sender,
            "recipient": recipient,
            "message_type": message_type,
            "finding": finding,
            "confidence": confidence,
            "timestamp": time.time(),
        }, episode_id=episode_id)

    async def emit_cluster_snapshot(
        self,
        episode_id: str,
        cluster_dict: dict,
        active_incidents: list[dict],
    ) -> None:
        await self.broadcast(EVT_CLUSTER_SNAPSHOT, {
            "episode_id": episode_id,
            "cluster": cluster_dict,
            "active_incidents": active_incidents,
        }, episode_id=episode_id)

    async def emit_reward_update(
        self,
        episode_id: str,
        step: int,
        breakdown: dict,
        cumulative: float,
    ) -> None:
        await self.broadcast(EVT_REWARD_UPDATE, {
            "episode_id": episode_id,
            "step": step,
            "breakdown": breakdown,
            "cumulative": cumulative,
        }, episode_id=episode_id)

    async def emit_level_advanced(
        self,
        from_level: int,
        to_level: int,
        episode_id: str,
    ) -> None:
        await self.broadcast(EVT_LEVEL_ADVANCED, {
            "from_level": from_level,
            "to_level": to_level,
            "episode_id": episode_id,
        })

    async def emit_belief_update(
        self,
        episode_id: str,
        agent: str,
        hypothesis: str,
        confidence: float,
    ) -> None:
        await self.broadcast(EVT_BELIEF_UPDATE, {
            "episode_id": episode_id,
            "agent": agent,
            "hypothesis": hypothesis[:300],
            "confidence": confidence,
        }, episode_id=episode_id)

    async def emit_chaos_mutation(
        self,
        episode_id: str,
        mutation_type: str,
        description: str,
    ) -> None:
        await self.broadcast(EVT_CHAOS_MUTATION, {
            "episode_id": episode_id,
            "mutation_type": mutation_type,
            "description": description,
        }, episode_id=episode_id)

    async def emit_incident(
        self,
        episode_id: str,
        incident_id: str,
        title: str,
        level: int,
        affected: list[str],
        description: str,
    ) -> None:
        await self.broadcast(EVT_INCIDENT_INJECTED, {
            "episode_id": episode_id,
            "incident_id": incident_id,
            "title": title,
            "level": level,
            "affected_components": affected,
            "description": description,
        }, episode_id=episode_id)

    # ── Utility ────────────────────────────────────────────────────────────────

    @property
    def connection_count(self) -> int:
        return len(self._clients)

    def get_clients_for_episode(self, episode_id: str) -> list[str]:
        """Return client IDs subscribed to a specific episode."""
        return [
            c.client_id for c in self._clients
            if c.episode_filter is None or c.episode_filter == episode_id
        ]

    @staticmethod
    def _make_envelope(event_type: str, data: dict) -> dict:
        """Wrap data in a standard event envelope with timestamp."""
        return {
            "event": event_type,
            "ts": time.time(),
            "data": data,
        }


# Singleton — imported across the server
ws_manager = ConnectionManager()
