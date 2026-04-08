"""
ChaosMesh Arena — IncidentCommanderAgent (Task 2.2)

The Incident Commander:
- Orchestrates all other agents
- Issues authorization for dangerous actions (drain_node, rollback_deployment)
- Resolves conflicts between agent hypotheses
- Makes the final DECLARE_RESOLVED call
- Assigns work to specialized agents via broadcast messages
"""

from __future__ import annotations

import json

import structlog

from chaosmesh_arena.agents.base_agent import BaseAgent
from chaosmesh_arena.models import (
    ActionModel,
    ActionType,
    AgentRole,
    MessageType,
    ObservationModel,
    Urgency,
)

log = structlog.get_logger(__name__)

# Actions that require IC authorization before execution
REQUIRES_IC_AUTH = {
    ActionType.ROLLBACK_DEPLOYMENT,
    ActionType.DRAIN_NODE,
    ActionType.SCALE_DEPLOYMENT,
    ActionType.ISOLATE_POD,
}


class IncidentCommanderAgent(BaseAgent):
    """
    Incident Commander — coordinates the SRE swarm.

    Decision logic:
    1. Assess incident severity from observation
    2. Delegate investigation work to specialized agents (broadcast)
    3. Authorize dangerous remediation actions
    4. Resolve agent conflicts by confidence-weighting their beliefs
    5. Declare resolution when evidence is sufficient
    """

    @property
    def role(self) -> AgentRole:
        return AgentRole.INCIDENT_COMMANDER

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Incident Commander in a Kubernetes SRE swarm. "
            "Your job is to orchestrate 4 specialized agents (Diagnostics, Remediation, Security, Database).\n\n"
            "## Your Responsibilities\n"
            "1. Assess incident severity and assign tasks via BROADCAST_STATUS\n"
            "2. Authorize dangerous actions (drain_node, rollback_deployment, isolate_pod, scale_deployment)\n"
            "3. Resolve conflicts between agent hypotheses using confidence scores\n"
            "4. Declare the incident RESOLVED only when high-confidence evidence supports it\n"
            "5. Escalate if no progress within 5 steps\n\n"
            "## Decision Rules\n"
            "- Do NOT authorize actions below 60% confidence\n"
            "- If Security and Diagnostics disagree, request more evidence before acting\n"
            "- DECLARE_RESOLVED only when ≥2 agents confirm the fix worked\n"
            "- Always explain your decisions for the incident post-mortem\n\n"
            "## Output Format (JSON only)\n"
            "{\n"
            "  \"action_type\": \"broadcast_status|grant_authorization|declare_resolved|escalate|noop\",\n"
            "  \"target\": \"<pod/service/agent name>\",\n"
            "  \"reasoning\": \"<your decision rationale>\",\n"
            "  \"hypothesis\": \"<current incident theory>\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"delegate_to\": \"diagnostics|remediation|security|database|null\",\n"
            "  \"authorize\": true|false\n"
            "}"
        )

    @property
    def available_tools(self) -> list[ActionType]:
        return [
            ActionType.BROADCAST_STATUS,
            ActionType.GRANT_AUTHORIZATION,
            ActionType.DECLARE_RESOLVED,
            ActionType.ESCALATE,
            ActionType.SEND_MESSAGE,
            ActionType.REQUEST_AUTHORIZATION,
            ActionType.NOOP,
        ]

    def _reason(self, obs: ObservationModel) -> str:
        """Build IC's reasoning prompt from cluster state + agent beliefs."""
        lines = [
            f"## Episode: {obs.episode_id} | Step: {obs.step} | Level: {obs.current_level.value}",
            "",
            "## Active Incidents",
        ]
        for inc in obs.active_incidents:
            lines.append(
                f"- [{inc.level.value}] {inc.title} | Status: {inc.status.value} | "
                f"Affected: {', '.join(inc.affected_components)}"
            )
        if not obs.active_incidents:
            lines.append("- None detected")

        lines += ["", "## Cluster Health"]
        unhealthy_pods = [
            name for name, pod in obs.cluster_state.pods.items()
            if not pod.ready
        ]
        unhealthy_svc = [
            name for name, svc in obs.cluster_state.services.items()
            if svc.error_rate_percent > 5.0
        ]
        lines.append(f"Unhealthy pods: {unhealthy_pods or 'none'}")
        lines.append(f"Degraded services: {unhealthy_svc or 'none'}")

        if obs.agent_beliefs:
            lines += ["", "## Agent Beliefs (current hypotheses)"]
            for agent_name, belief in obs.agent_beliefs.items():
                lines.append(
                    f"- {agent_name}: {belief.hypothesis[:120]} "
                    f"(confidence: {belief.confidence:.0%})"
                )

        if obs.agent_messages:
            lines += ["", "## Recent Agent Messages (last 5)"]
            for msg in obs.agent_messages[-5:]:
                lines.append(
                    f"- FROM {msg.sender.value}: [{msg.message_type.value}] "
                    f"{msg.content.finding[:150]}"
                )

        # Check if any agent requested authorization
        pending_auth = [
            msg for msg in obs.agent_messages
            if msg.message_type == MessageType.REQUEST_AUTHORIZATION
        ]
        if pending_auth:
            lines += ["", "## ⚠️  Authorization Requests Pending"]
            for req in pending_auth:
                lines.append(
                    f"- {req.sender.value} requests: {req.content.finding[:200]}"
                )

        lines += [
            "",
            "## Your Decision",
            "Based on the above, what is your next command as Incident Commander? "
            "Output ONLY valid JSON.",
        ]
        return "\n".join(lines)

    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        """Parse IC LLM output into an ActionModel."""
        data = self._safe_parse_json(llm_output)

        action_str = data.get("action_type", "noop").lower().strip()
        target = str(data.get("target", ""))
        reasoning = str(data.get("reasoning", llm_output[:300]))

        # Map to valid ActionType
        action_map = {
            "broadcast_status": ActionType.BROADCAST_STATUS,
            "grant_authorization": ActionType.GRANT_AUTHORIZATION,
            "declare_resolved": ActionType.DECLARE_RESOLVED,
            "escalate": ActionType.ESCALATE,
            "send_message": ActionType.SEND_MESSAGE,
            "request_authorization": ActionType.REQUEST_AUTHORIZATION,
            "noop": ActionType.NOOP,
        }
        action_type = action_map.get(action_str, ActionType.BROADCAST_STATUS)

        # Build broadcast message if delegating
        params: dict = {}
        delegate = data.get("delegate_to")
        if delegate:
            params["delegate_to"] = delegate
        if data.get("authorize"):
            params["authorized"] = True

        return ActionModel(
            agent=self.role,
            action_type=action_type,
            target=target,
            parameters=params,
            reasoning=reasoning,
        )

    def should_authorize(self, requested_action: ActionType, confidence: float) -> bool:
        """
        IC authorization gate — called by swarm before dangerous actions.
        Requires ≥60% confidence and a valid pending request.
        """
        if requested_action not in REQUIRES_IC_AUTH:
            return True  # Low-risk actions don't need authorization
        return confidence >= 0.60
