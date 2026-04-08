"""
ChaosMesh Arena — BaseAgent (Task 2.1)

Abstract LLM-powered agent with:
- Dual LLM routing (Ollama primary → OpenRouter fallback → cache)
- ChromaDB persistent memory (per-agent collection)
- Structured message protocol (per RFC §2.2)
- Tool dispatch table
- Async reasoning loop
"""

from __future__ import annotations

import asyncio
import json
from abc import ABC, abstractmethod
from typing import Any

import structlog

from chaosmesh_arena.llm.router import LLMRouter
from chaosmesh_arena.memory.vector_store import VectorStore
from chaosmesh_arena.models import (
    ActionModel,
    ActionType,
    AgentBeliefModel,
    AgentMessage,
    AgentMessageContent,
    AgentRole,
    MessageType,
    ObservationModel,
    Urgency,
)

log = structlog.get_logger(__name__)

# Maximum LLM tokens per reasoning call
MAX_TOKENS = 512
LLM_TIMEOUT = 30.0  # seconds


class BaseAgent(ABC):
    """
    Abstract base for all ChaosMesh Arena agents.

    Each concrete agent must implement:
    - `role` — AgentRole enum value
    - `system_prompt` — LLM system instructions (injected into every call)
    - `available_tools` — list of ActionType this agent can use
    - `_reason(obs)` — build LLM prompt from observation
    - `_parse_action(llm_output, obs)` — parse LLM output into ActionModel
    """

    def __init__(
        self,
        llm_router: LLMRouter,
        vector_store: VectorStore,
        episode_id: str = "no-episode",
    ) -> None:
        self._llm = llm_router
        self._memory = vector_store
        self._episode_id = episode_id
        self._message_queue: list[AgentMessage] = []
        self._last_belief: AgentBeliefModel | None = None
        self._step_count: int = 0

        log.info("agent_initialized", role=self.role.value, episode=episode_id)

    # ── Abstract interface ────────────────────────────────────────────────────

    @property
    @abstractmethod
    def role(self) -> AgentRole:
        """The agent's role identifier."""

    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """System prompt injected into every LLM call."""

    @property
    @abstractmethod
    def available_tools(self) -> list[ActionType]:
        """Which ActionTypes this agent can produce."""

    @abstractmethod
    def _reason(self, obs: ObservationModel) -> str:
        """Build the user-turn LLM prompt from current observation."""

    @abstractmethod
    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        """
        Parse raw LLM output into a valid ActionModel.
        Must always return a valid action — fallback to NOOP on parse failure.
        """

    # ── Core act() loop ───────────────────────────────────────────────────────

    async def act(self, obs: ObservationModel) -> ActionModel:
        """
        Main entry point called by the environment/swarm each step.
        Think → Memory → Decide → Return action.
        """
        self._step_count += 1
        self._episode_id = obs.episode_id

        # 1. Retrieve relevant past patterns from ChromaDB
        context = await self._retrieve_memory(obs)

        # 2. Build prompt with observation + memory context
        prompt = self._reason(obs)
        if context:
            prompt += f"\n\n## Relevant Past Patterns\n{context}"

        # 3. Call LLM (with timeout guard)
        try:
            llm_output = await asyncio.wait_for(
                self._llm.infer(
                    system=self.system_prompt,
                    prompt=prompt,
                    max_tokens=MAX_TOKENS,
                    temperature=0.3,
                ),
                timeout=LLM_TIMEOUT,
            )
        except asyncio.TimeoutError:
            log.warning("agent_llm_timeout", role=self.role.value, step=self._step_count)
            llm_output = json.dumps({"action_type": "noop", "target": "", "reasoning": "LLM timeout"})
        except Exception as e:
            log.error("agent_llm_error", role=self.role.value, error=str(e))
            llm_output = json.dumps({"action_type": "noop", "target": "", "reasoning": str(e)})

        # 4. Parse action (agent-specific)
        action = self._parse_action(llm_output, obs)
        action = action.model_copy(update={"agent": self.role})

        # 5. Update belief state
        self._last_belief = self._extract_belief(llm_output, obs)

        # 6. Store pattern in ChromaDB for cross-episode learning
        await self._store_memory(obs, action, llm_output)

        log.info(
            "agent_acted",
            role=self.role.value,
            action_type=action.action_type.value,
            target=action.target,
            step=self._step_count,
        )
        return action

    # ── Memory helpers ────────────────────────────────────────────────────────

    async def _retrieve_memory(self, obs: ObservationModel) -> str:
        """Query ChromaDB for similar past incidents."""
        if not obs.active_incidents:
            return ""
        try:
            query = " ".join(
                f"{inc.title} {inc.description}"
                for inc in obs.active_incidents[:2]
            )
            results = await self._memory.query(
                collection=self.role.value,
                query_text=query,
                n_results=3,
                episode_filter=None,  # Cross-episode search
            )
            if not results:
                return ""
            return "\n".join(
                f"- [Past] {r['document']} (similarity: {r.get('distance', '?')})"
                for r in results
            )
        except Exception as e:
            log.warning("memory_retrieve_failed", role=self.role.value, error=str(e))
            return ""

    async def _store_memory(
        self, obs: ObservationModel, action: ActionModel, llm_output: str
    ) -> None:
        """Store action + outcome in ChromaDB for future retrieval."""
        if not obs.active_incidents:
            return
        try:
            document = (
                f"Incident: {obs.active_incidents[0].title} | "
                f"Action: {action.action_type.value} on {action.target} | "
                f"Reasoning: {action.reasoning[:200]}"
            )
            metadata = {
                "episode_id": obs.episode_id,
                "step": str(obs.step),
                "agent": self.role.value,
                "action_type": action.action_type.value,
                "level": str(obs.current_level.value),
            }
            await self._memory.add(
                collection=self.role.value,
                document=document,
                metadata=metadata,
                doc_id=f"{obs.episode_id}-{obs.step}-{self.role.value}",
            )
        except Exception as e:
            log.warning("memory_store_failed", role=self.role.value, error=str(e))

    # ── Message bus helpers ───────────────────────────────────────────────────

    def receive_message(self, message: AgentMessage) -> None:
        """Enqueue a message from another agent."""
        self._message_queue.append(message)

    def flush_messages(self) -> list[AgentMessage]:
        """Drain and return all queued messages."""
        msgs = list(self._message_queue)
        self._message_queue.clear()
        return msgs

    def compose_message(
        self,
        content: str,
        message_type: MessageType = MessageType.FINDING,
        recipient: AgentRole | None = None,
        urgency: Urgency = Urgency.P2,
        confidence: float = 0.7,
        evidence: list[str] | None = None,
        requires_response: bool = False,
    ) -> AgentMessage:
        """Helper to build a structured inter-agent message."""
        return AgentMessage(
            sender=self.role,
            recipient=recipient,
            message_type=message_type,
            urgency=urgency,
            content=AgentMessageContent(
                finding=content,
                confidence=confidence,
                evidence=evidence or [],
                recommended_action="",
                reasoning="",
            ),
            requires_response=requires_response,
        )

    def get_belief(self) -> AgentBeliefModel | None:
        return self._last_belief

    # ── Belief extraction ─────────────────────────────────────────────────────

    def _extract_belief(
        self, llm_output: str, obs: ObservationModel
    ) -> AgentBeliefModel:
        """Extract a belief from LLM output. Agents can override."""
        try:
            data = json.loads(llm_output)
            hypothesis = data.get("hypothesis", data.get("reasoning", "Unknown"))
            confidence = float(data.get("confidence", 0.5))
        except (json.JSONDecodeError, ValueError):
            hypothesis = llm_output[:200]
            confidence = 0.4

        return AgentBeliefModel(
            agent=self.role,
            hypothesis=hypothesis,
            confidence=min(max(confidence, 0.0), 1.0),
            supporting_evidence=[],
            contradicting_evidence=[],
        )

    # ── Utility ───────────────────────────────────────────────────────────────

    @staticmethod
    def _safe_parse_json(text: str) -> dict[str, Any]:
        """Try to extract the first JSON object from an LLM response."""
        # Try direct parse
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass
        # Try finding JSON block in markdown
        import re
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try first { ... }
        m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}

    def _make_noop(self, reasoning: str = "Parse failed") -> ActionModel:
        return ActionModel(
            agent=self.role,
            action_type=ActionType.NOOP,
            target="",
            reasoning=reasoning,
        )
