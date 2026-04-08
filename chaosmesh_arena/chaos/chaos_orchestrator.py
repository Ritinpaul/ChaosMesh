"""
ChaosMesh Arena — Adversarial LLM Chaos Orchestrator (Task 2.13)

Dual-LLM adversarial controller that generates novel incidents and
adapts them based on agent progress.

Architecture:
  Primary LLM (higher temp / creative): generates novel incident mutations
  Secondary LLM (lower temp / critical): validates mutations for realism

Flow:
  1. generate_incident(level, obs) → novel IncidentTemplate
  2. mutate_active_incident(incident, agent_actions) → Mutation
  3. validate_mutation(mutation) → bool (secondary LLM red-team check)
  4. If valid → inject mutation into cluster
  5. Fallback to IncidentRegistry if LLMs unavailable
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from typing import TYPE_CHECKING, Optional

import structlog

from chaosmesh_arena.models import IncidentLevel, IncidentModel, ObservationModel

if TYPE_CHECKING:
    from chaosmesh_arena.llm.router import LLMRouter
    from chaosmesh_arena.templates.incident_registry import IncidentRegistry

log = structlog.get_logger(__name__)

# Creativity temperature for the adversarial generator
_GENERATOR_TEMP = 0.85
# Critical temperature for the validator (more conservative)
_VALIDATOR_TEMP = 0.2

# Max tokens for chaos generation prompts
_CHAOS_MAX_TOKENS = 600


@dataclass
class ChaosIncidentProposal:
    """A proposed novel incident from the chaos generator LLM."""
    title: str
    description: str
    symptoms: list[str]
    root_cause: str
    false_lead: str
    affected_components: list[str]
    inject_sequence: list[str]  # ordered list of injector method names
    difficulty_justification: str
    confidence: float


@dataclass
class ChaosMutation:
    """A mutation to an in-progress incident to increase difficulty."""
    mutation_type: str          # "secondary_failure", "red_herring", "escalation", "adaptation"
    description: str
    new_symptoms: list[str]
    inject_method: str          # FailureInjector method to call
    inject_kwargs: dict
    validated: bool = False


_GENERATOR_SYSTEM = """\
You are an adversarial Chaos Engineer AI. Your goal is to design realistic but tricky
Kubernetes infrastructure incidents that are difficult for an SRE swarm to resolve.

Rules:
- Incidents must be physically realistic (real K8s failure modes)
- Each incident must have at least one false lead / red herring to confuse agents
- Match the difficulty to the requested level (L1=simple, L5=compound chaos)
- Output strictly valid JSON only — no markdown, no explanation outside JSON
"""

_VALIDATOR_SYSTEM = """\
You are a skeptical SRE reviewing a proposed chaos incident for realism.
Your job is to reject unrealistic or self-contradictory scenarios.

Validation criteria:
1. Is this a realistic Kubernetes failure mode?
2. Are the symptoms consistent with the root cause?
3. Is the false lead plausibly confusing (not obviously wrong)?
4. Is the difficulty appropriate for the stated level?

Output JSON: {"valid": true/false, "reason": "...", "confidence": 0.0-1.0}
"""


class ChaosOrchestrator:
    """
    Adversarial LLM Chaos Orchestrator.

    Uses two LLM calls (primary + validator) to generate and validate
    novel incident scenarios beyond the static template registry.

    Degrades gracefully: if both LLMs fail, uses the static registry.
    """

    def __init__(
        self,
        llm_router: "LLMRouter",
        incident_registry: "IncidentRegistry",
    ) -> None:
        self._llm = llm_router
        self._registry = incident_registry
        self._rng = random.Random()
        self._proposal_cache: list[ChaosIncidentProposal] = []

    async def generate_incident(
        self,
        level: IncidentLevel,
        obs: Optional[ObservationModel] = None,
        seed: Optional[int] = None,
    ) -> ChaosIncidentProposal | None:
        """
        Use primary LLM to generate a novel incident for the given level.
        Returns None if LLM fails (caller should fall back to registry).
        """
        if seed is not None:
            self._rng.seed(seed)

        prompt = self._build_generator_prompt(level, obs)

        try:
            raw = await self._llm.infer(
                system=_GENERATOR_SYSTEM,
                prompt=prompt,
                max_tokens=_CHAOS_MAX_TOKENS,
                temperature=_GENERATOR_TEMP,
                agent_role="chaos_generator",
            )
            proposal = self._parse_proposal(raw, level)
            if proposal:
                log.info(
                    "chaos_incident_generated",
                    level=level.value,
                    title=proposal.title[:60],
                    confidence=proposal.confidence,
                )
            return proposal

        except Exception as e:
            log.warning("chaos_generator_failed", error=str(e), level=level.value)
            return None

    async def validate_mutation(self, mutation: ChaosMutation) -> bool:
        """
        Use secondary LLM (with lower temperature) to validate a mutation for realism.
        Returns True if the mutation is valid and should be injected.
        """
        prompt = (
            f"Proposed chaos mutation:\n"
            f"Type: {mutation.mutation_type}\n"
            f"Description: {mutation.description}\n"
            f"New symptoms: {', '.join(mutation.new_symptoms)}\n"
            f"Injection method: {mutation.inject_method}\n\n"
            f"Is this a realistic scenario that would genuinely confuse SRE agents? "
            f"Output JSON only."
        )

        try:
            raw = await self._llm.infer(
                system=_VALIDATOR_SYSTEM,
                prompt=prompt,
                max_tokens=200,
                temperature=_VALIDATOR_TEMP,
                agent_role="chaos_validator",
            )
            data = self._safe_json(raw)
            valid = bool(data.get("valid", False))
            confidence = float(data.get("confidence", 0.5))
            reason = str(data.get("reason", ""))

            log.info(
                "chaos_mutation_validated",
                valid=valid,
                confidence=confidence,
                reason=reason[:80],
            )
            mutation.validated = valid
            return valid and confidence >= 0.5

        except Exception as e:
            log.warning("chaos_validator_failed", error=str(e))
            # If validator fails, optimistically accept
            mutation.validated = True
            return True

    async def mutate_active_incident(
        self,
        incident: IncidentModel,
        agent_actions: list[str],
        step: int,
    ) -> ChaosMutation | None:
        """
        Generate a mutation to an in-progress incident based on agent actions.
        Called when agents are making too-easy progress.

        Args:
            incident: Current active incident
            agent_actions: Recent action types taken by agents
            step: Current simulation step

        Returns:
            ChaosMutation if a valid mutation was generated, None otherwise.
        """
        prompt = self._build_mutation_prompt(incident, agent_actions, step)

        try:
            raw = await self._llm.infer(
                system=_GENERATOR_SYSTEM,
                prompt=prompt,
                max_tokens=400,
                temperature=_GENERATOR_TEMP,
                agent_role="chaos_mutator",
            )
            mutation = self._parse_mutation(raw)
            if mutation:
                # Validate with secondary LLM
                if await self.validate_mutation(mutation):
                    log.info(
                        "chaos_mutation_accepted",
                        type=mutation.mutation_type,
                        method=mutation.inject_method,
                    )
                    return mutation
                else:
                    log.info("chaos_mutation_rejected_by_validator")
                    return None
        except Exception as e:
            log.warning("chaos_mutation_failed", error=str(e))
            return None

    def fallback_registry_inject(self, level: IncidentLevel) -> None:
        """
        Fallback: use static registry when LLMs are unavailable.
        Called by env when generate_incident returns None.
        """
        log.info("chaos_fallback_registry", level=level.value)
        return self._registry.inject(level)

    # ── Prompt Builders ───────────────────────────────────────────────────────

    def _build_generator_prompt(
        self,
        level: IncidentLevel,
        obs: Optional[ObservationModel],
    ) -> str:
        cluster_ctx = ""
        if obs:
            pods = list(obs.cluster_state.pods.keys())[:5]
            svcs = list(obs.cluster_state.services.keys())
            cluster_ctx = (
                f"\nCluster context:\n"
                f"  Running pods: {pods}\n"
                f"  Services: {svcs}\n"
                f"  Network partitions: {obs.cluster_state.network_partitions}\n"
            )

        level_guide = {
            IncidentLevel.LEVEL_1: "Single-component failure. Obvious root cause. One false lead.",
            IncidentLevel.LEVEL_2: "Two correlated failures. Cascading effect. Requires multi-step diagnosis.",
            IncidentLevel.LEVEL_3: "Ambiguous — two plausible root causes. Security vs ops disagreement.",
            IncidentLevel.LEVEL_4: "Dynamic — remediation of first issue triggers second issue. Time-sensitive.",
            IncidentLevel.LEVEL_5: "Compound — 2+ simultaneous unrelated incidents. Agents must split attention.",
        }

        return (
            f"Design a Level {level.value} Kubernetes incident.\n"
            f"Difficulty: {level_guide.get(level, 'Unknown')}\n"
            f"{cluster_ctx}\n"
            "Output JSON with this exact schema:\n"
            "{\n"
            '  "title": "Short incident title",\n'
            '  "description": "2-3 sentence description",\n'
            '  "symptoms": ["symptom1", "symptom2", "symptom3"],\n'
            '  "root_cause": "True root cause (hidden from agents)",\n'
            '  "false_lead": "Red herring that will mislead agents",\n'
            '  "affected_components": ["pod-name", "svc-name"],\n'
            '  "inject_sequence": ["inject_pod_crash", "inject_network_timeout"],\n'
            '  "difficulty_justification": "Why this is appropriate for the level",\n'
            '  "confidence": 0.0-1.0\n'
            "}"
        )

    def _build_mutation_prompt(
        self,
        incident: IncidentModel,
        agent_actions: list[str],
        step: int,
    ) -> str:
        return (
            f"Active incident (step {step}):\n"
            f"  Title: {incident.title}\n"
            f"  Description: {incident.description[:200]}\n"
            f"  Level: {incident.level.value}\n\n"
            f"Agent actions taken so far: {agent_actions[-8:]}\n\n"
            "The agents are making progress. Generate a realistic mutation to increase difficulty.\n"
            "Mutation types: secondary_failure, red_herring, escalation, adaptation\n\n"
            "Output JSON:\n"
            "{\n"
            '  "mutation_type": "secondary_failure|red_herring|escalation|adaptation",\n'
            '  "description": "What changes",\n'
            '  "new_symptoms": ["new symptom 1", "new symptom 2"],\n'
            '  "inject_method": "inject_pod_crash|inject_memory_leak|inject_network_timeout|'
            'inject_disk_pressure",\n'
            '  "inject_kwargs": {}\n'
            "}"
        )

    # ── Parsers ───────────────────────────────────────────────────────────────

    def _parse_proposal(
        self, raw: str, level: IncidentLevel
    ) -> ChaosIncidentProposal | None:
        data = self._safe_json(raw)
        if not data or "title" not in data:
            return None
        try:
            return ChaosIncidentProposal(
                title=str(data.get("title", "Unnamed Incident")),
                description=str(data.get("description", "")),
                symptoms=list(data.get("symptoms", [])),
                root_cause=str(data.get("root_cause", "")),
                false_lead=str(data.get("false_lead", "")),
                affected_components=list(data.get("affected_components", [])),
                inject_sequence=list(data.get("inject_sequence", ["inject_pod_crash"])),
                difficulty_justification=str(data.get("difficulty_justification", "")),
                confidence=float(data.get("confidence", 0.6)),
            )
        except Exception as e:
            log.warning("chaos_proposal_parse_error", error=str(e))
            return None

    def _parse_mutation(self, raw: str) -> ChaosMutation | None:
        data = self._safe_json(raw)
        if not data or "mutation_type" not in data:
            return None
        try:
            # Validate inject_method is a known method
            valid_methods = {
                "inject_pod_crash", "inject_memory_leak", "inject_network_timeout",
                "inject_disk_pressure", "inject_image_pull_failure",
                "inject_cascading_db_timeout", "inject_node_failure_cascade",
                "inject_rolling_restart_failure",
            }
            method = str(data.get("inject_method", "inject_pod_crash"))
            if method not in valid_methods:
                method = "inject_pod_crash"

            return ChaosMutation(
                mutation_type=str(data.get("mutation_type", "secondary_failure")),
                description=str(data.get("description", "")),
                new_symptoms=list(data.get("new_symptoms", [])),
                inject_method=method,
                inject_kwargs=dict(data.get("inject_kwargs", {})),
            )
        except Exception as e:
            log.warning("chaos_mutation_parse_error", error=str(e))
            return None

    @staticmethod
    def _safe_json(text: str) -> dict:
        """Try to extract JSON from LLM output."""
        import re
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try JSON block in markdown
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try first { ... }
        m = re.search(r"\{[\s\S]+\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {}
