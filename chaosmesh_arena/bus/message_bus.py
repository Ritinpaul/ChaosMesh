"""
ChaosMesh Arena — Redis Pub/Sub Message Bus (Task 2.7)

Provides async publish/subscribe inter-agent messaging via Redis.
Graceful fallback to in-process asyncio.Queue when Redis is unavailable.

Channels:
  chaosmesh:broadcast      — all agents receive
  chaosmesh:agent:<role>   — targeted messages
  chaosmesh:events         — environment lifecycle events
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Coroutine

import structlog

from chaosmesh_arena.models import AgentMessage, AgentRole

log = structlog.get_logger(__name__)

# Redis channel names
BROADCAST_CHANNEL = "chaosmesh:broadcast"
EVENTS_CHANNEL = "chaosmesh:events"


def _agent_channel(role: AgentRole) -> str:
    return f"chaosmesh:agent:{role.value}"


class InProcessQueue:
    """
    Fallback in-process queue used when Redis is unavailable.
    Mimics the Redis pub/sub interface at the application level.
    """

    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue] = {}
        self._subscribers: dict[str, list[Callable]] = {}

    def _ensure_channel(self, channel: str) -> None:
        if channel not in self._queues:
            self._queues[channel] = asyncio.Queue(maxsize=200)
        if channel not in self._subscribers:
            self._subscribers[channel] = []

    async def publish(self, channel: str, data: str) -> None:
        self._ensure_channel(channel)
        for callback in self._subscribers[channel]:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(channel, data)
                else:
                    callback(channel, data)
            except Exception as e:
                log.warning("inprocess_callback_error", channel=channel, error=str(e))

    def subscribe(self, channel: str, callback: Callable) -> None:
        self._ensure_channel(channel)
        self._subscribers[channel].append(callback)

    def unsubscribe(self, channel: str, callback: Callable) -> None:
        if channel in self._subscribers:
            try:
                self._subscribers[channel].remove(callback)
            except ValueError:
                pass


class MessageBus:
    """
    Redis-backed pub/sub message bus for inter-agent communication.

    Usage:
        bus = MessageBus()
        await bus.connect()

        # Publish to all agents
        await bus.broadcast(message)

        # Publish to specific agent
        await bus.publish_to(AgentRole.DIAGNOSTICS, message)

        # Subscribe to a channel
        await bus.subscribe(BROADCAST_CHANNEL, my_callback)

        await bus.close()
    """

    def __init__(self, redis_url: str = "redis://localhost:6379") -> None:
        self._redis_url = redis_url
        self._redis: Any = None         # aioredis.Redis when connected
        self._pubsub: Any = None        # aioredis.client.PubSub
        self._fallback = InProcessQueue()
        self._redis_available = False
        self._listeners: list[asyncio.Task] = []
        self._callbacks: dict[str, list[Callable]] = {}

    async def connect(self) -> bool:
        """
        Attempt Redis connection. Returns True if connected, False if falling back.
        Always succeeds — falls back to in-process queue transparently.
        """
        try:
            import redis.asyncio as aioredis  # type: ignore[import]
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=2.0,
            )
            # Ping to verify connection
            await asyncio.wait_for(self._redis.ping(), timeout=3.0)
            self._pubsub = self._redis.pubsub()
            self._redis_available = True
            log.info("message_bus_redis_connected", url=self._redis_url)
            return True
        except Exception as e:
            log.warning(
                "message_bus_redis_unavailable",
                error=str(e),
                fallback="in-process queue",
            )
            self._redis_available = False
            return False

    async def broadcast(self, message: AgentMessage) -> None:
        """Publish a message to all agents."""
        await self._publish(BROADCAST_CHANNEL, message)

    async def publish_to(self, recipient: AgentRole, message: AgentMessage) -> None:
        """Publish a targeted message to a specific agent."""
        await self._publish(_agent_channel(recipient), message)
        # Also publish to broadcast if message is also addressed as broadcast
        if message.recipient is None:
            await self._publish(BROADCAST_CHANNEL, message)

    async def publish_event(self, event_type: str, data: dict) -> None:
        """Publish a lifecycle event (episode_started, incident_injected, etc.)."""
        payload = json.dumps({"event_type": event_type, "data": data})
        if self._redis_available and self._redis:
            try:
                await self._redis.publish(EVENTS_CHANNEL, payload)
                return
            except Exception as e:
                log.warning("bus_redis_publish_error", error=str(e))
        await self._fallback.publish(EVENTS_CHANNEL, payload)

    async def subscribe(
        self,
        channel: str,
        callback: Callable[[str, AgentMessage], Coroutine | None],
    ) -> None:
        """Subscribe to a channel. Callback receives (channel, AgentMessage)."""
        if channel not in self._callbacks:
            self._callbacks[channel] = []
        self._callbacks[channel].append(callback)

        if self._redis_available and self._pubsub:
            try:
                async def _redis_handler(raw_msg: dict) -> None:
                    if raw_msg.get("type") != "message":
                        return
                    await self._dispatch(raw_msg["channel"], raw_msg["data"])

                await self._pubsub.subscribe(**{channel: _redis_handler})
                task = asyncio.create_task(self._redis_listen_loop())
                self._listeners.append(task)
                return
            except Exception as e:
                log.warning("bus_redis_subscribe_error", error=str(e))

        # Fallback: in-process
        async def _fallback_handler(ch: str, data: str) -> None:
            await self._dispatch(ch, data)

        self._fallback.subscribe(channel, _fallback_handler)

    async def subscribe_agent(
        self,
        role: AgentRole,
        callback: Callable,
    ) -> None:
        """Convenience: subscribe to both broadcast and targeted channel."""
        await self.subscribe(BROADCAST_CHANNEL, callback)
        await self.subscribe(_agent_channel(role), callback)

    async def get_messages(
        self,
        role: AgentRole,
        timeout: float = 0.05,
    ) -> list[AgentMessage]:
        """
        Poll for messages for a given agent role.
        Non-blocking pull: returns immediately with whatever is in the queue.
        """
        messages: list[AgentMessage] = []
        channels = [BROADCAST_CHANNEL, _agent_channel(role)]

        if self._redis_available and self._redis:
            try:
                for ch in channels:
                    # LRANGE pattern: we push messages to a list and RPOP here
                    raw = await self._redis.rpop(f"{ch}:queue", count=10)
                    if raw:
                        for item in (raw if isinstance(raw, list) else [raw]):
                            try:
                                msg = AgentMessage.model_validate_json(item)
                                messages.append(msg)
                            except Exception:
                                pass
                return messages
            except Exception:
                pass

        # Fallback: check in-process queues
        for ch in channels:
            q = self._fallback._queues.get(ch)
            if q:
                while not q.empty():
                    try:
                        item = q.get_nowait()
                        if isinstance(item, str):
                            msg = AgentMessage.model_validate_json(item)
                        else:
                            msg = item
                        messages.append(msg)
                    except Exception:
                        break
        return messages

    async def close(self) -> None:
        """Gracefully shut down the message bus."""
        for task in self._listeners:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._listeners.clear()

        if self._pubsub:
            try:
                await self._pubsub.unsubscribe()
                await self._pubsub.close()
            except Exception:
                pass

        if self._redis:
            try:
                await self._redis.aclose()
            except Exception:
                pass

        log.info("message_bus_closed")

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _publish(self, channel: str, message: AgentMessage) -> None:
        """Internal: serialize and dispatch message to channel."""
        payload = message.model_dump_json()

        if self._redis_available and self._redis:
            try:
                # Push to list queue AND publish for real-time sub
                await self._redis.lpush(f"{channel}:queue", payload)
                await self._redis.expire(f"{channel}:queue", 300)  # 5min TTL
                await self._redis.publish(channel, payload)
                log.debug("bus_published_redis", channel=channel, msg_id=message.message_id[:8])
                return
            except Exception as e:
                log.warning("bus_redis_publish_failed", error=str(e))

        # Fallback
        await self._fallback.publish(channel, payload)
        log.debug("bus_published_inprocess", channel=channel, msg_id=message.message_id[:8])

    async def _dispatch(self, channel: str, raw: str) -> None:
        """Parse and dispatch to registered callbacks for this channel."""
        try:
            msg = AgentMessage.model_validate_json(raw)
        except Exception as e:
            log.warning("bus_parse_error", error=str(e))
            return

        callbacks = self._callbacks.get(channel, [])
        for cb in callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(channel, msg)
                else:
                    cb(channel, msg)
            except Exception as e:
                log.warning("bus_callback_error", error=str(e))

    async def _redis_listen_loop(self) -> None:
        """Background task: drive the Redis pubsub listener."""
        if not self._pubsub:
            return
        try:
            async for message in self._pubsub.listen():
                if message.get("type") == "message":
                    await self._dispatch(message["channel"], message["data"])
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.warning("bus_listen_loop_error", error=str(e))

    @property
    def is_redis_connected(self) -> bool:
        return self._redis_available
