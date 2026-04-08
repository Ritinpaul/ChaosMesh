"""
ChaosMesh Arena — RemediationAgent (Task 2.4)

The Remediation Agent:
- Executes cluster fixes: restart_pod, scale_deployment, rollback_deployment,
  isolate_pod, drain_node, update_config
- MUST request IC authorization for dangerous actions
- Integrates with K8s state machine via ActionModel
- Tracks outcomes and learns from past remediation patterns in ChromaDB
"""

from __future__ import annotations

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

# Actions that REQUIRE Incident Commander authorization before execution
DANGEROUS_ACTIONS = {
    ActionType.ROLLBACK_DEPLOYMENT,
    ActionType.DRAIN_NODE,
    ActionType.SCALE_DEPLOYMENT,
    ActionType.ISOLATE_POD,
}


class RemediationAgent(BaseAgent):
    """
    Remediation Agent — the hands of the SRE swarm.

    Execution logic:
    1. Check current cluster state for actionable problems
    2. Identify the correct remediation action from IC broadcasts + agent findings
    3. Request authorization for dangerous actions (drain, rollback, isolate)
    4. Execute approved actions and report outcomes
    5. Store successful remediation patterns in ChromaDB for future episodes
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._authorized_actions: set[str] = set()  # Tracks IC-granted authorizations

    @property
    def role(self) -> AgentRole:
        return AgentRole.REMEDIATION

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Remediation Agent in a Kubernetes SRE swarm. "
            "Your job is to FIX incidents by executing the correct cluster action.\n\n"
            "## Authorization Rules\n"
            "- restart_pod, update_config: NO authorization needed — execute directly\n"
            "- scale_deployment, rollback_deployment, isolate_pod, drain_node: "
            "REQUIRE Incident Commander authorization first\n"
            "- If authorization is NOT granted, use request_authorization instead\n\n"
            "## Remediation Playbook\n"
            "- OOMKilled pod → restart_pod\n"
            "- CrashLoopBackOff → restart_pod, then update_config if it repeats\n"
            "- Service degradation (error_rate > 20%) → scale_deployment or rollback_deployment\n"
            "- Node pressure → drain_node (requires auth)\n"
            "- Security compromise → isolate_pod (requires auth)\n"
            "- Network partition → restart affected services\n\n"
            "## Output Format (JSON only)\n"
            "{\n"
            "  \"action_type\": \"restart_pod|scale_deployment|rollback_deployment|"
            "isolate_pod|drain_node|update_config|request_authorization|send_message|noop\",\n"
            "  \"target\": \"<pod_name|service_name|node_name>\",\n"
            "  \"reasoning\": \"<why this action fixes the incident>\",\n"
            "  \"hypothesis\": \"<what you believe is causing the issue>\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"needs_authorization\": true|false,\n"
            "  \"expected_outcome\": \"<what should happen after this action>\"\n"
            "}"
        )

    @property
    def available_tools(self) -> list[ActionType]:
        return [
            ActionType.RESTART_POD,
            ActionType.SCALE_DEPLOYMENT,
            ActionType.ROLLBACK_DEPLOYMENT,
            ActionType.ISOLATE_POD,
            ActionType.DRAIN_NODE,
            ActionType.UPDATE_CONFIG,
            ActionType.REQUEST_AUTHORIZATION,
            ActionType.SEND_MESSAGE,
            ActionType.NOOP,
        ]

    def _reason(self, obs: ObservationModel) -> str:
        """Build remediation prompt — focus on what to fix and whether auth is needed."""
        lines = [
            f"## Step {obs.step} | Level {obs.current_level.value} Incident",
            "",
            "## Active Incidents",
        ]
        for inc in obs.active_incidents:
            lines.append(
                f"- [{inc.level.value}] {inc.title}"
                f" | Status: {inc.status.value}"
                f" | Affected: {', '.join(inc.affected_components)}"
            )
        if not obs.active_incidents:
            lines.append("- None")

        # Unhealthy pods (primary remediation targets)
        unhealthy = [
            (name, pod)
            for name, pod in obs.cluster_state.pods.items()
            if not pod.ready
        ]
        lines += ["", "## Unhealthy Pods (Remediation Targets)"]
        if unhealthy:
            for name, pod in unhealthy:
                lines.append(
                    f"- {name}: phase={pod.phase.value}, "
                    f"restarts={pod.restart_count}, "
                    f"ready={pod.ready}"
                )
        else:
            lines.append("- All pods Ready ✓")

        # Degraded services
        degraded_svcs = [
            (name, svc)
            for name, svc in obs.cluster_state.services.items()
            if svc.error_rate_percent > 5.0
        ]
        if degraded_svcs:
            lines += ["", "## Degraded Services"]
            for name, svc in degraded_svcs:
                lines.append(
                    f"- {name}: error={svc.error_rate_percent:.1f}%, "
                    f"P99={svc.p99_latency_ms:.0f}ms, "
                    f"endpoints={svc.healthy_endpoints}/{svc.total_endpoints}"
                )

        # Node conditions
        problem_nodes = [
            (name, node)
            for name, node in obs.cluster_state.nodes.items()
            if node.condition.value != "Ready"
        ]
        if problem_nodes:
            lines += ["", "## Problem Nodes"]
            for name, node in problem_nodes:
                lines.append(f"- {name}: condition={node.condition.value}")

        # Messages from Commander / Diagnostics
        pending = self.flush_messages()
        if pending:
            lines += ["", "## Instructions from Commander / Diagnostics"]
            for msg in pending:
                tag = "⚡ AUTH GRANTED" if msg.message_type == MessageType.AUTHORIZATION else ""
                lines.append(
                    f"  [{msg.sender.value}] {tag} {msg.content.finding[:200]}"
                )
                # Track authorization grants
                if msg.message_type == MessageType.AUTHORIZATION:
                    self._authorized_actions.add(msg.content.recommended_action)

        # Authorization status
        if self._authorized_actions:
            lines += ["", "## Authorization Already Granted For"]
            lines.append(f"  {', '.join(self._authorized_actions)}")

        lines += [
            "",
            "## Your Remediation Decision",
            "Pick the SINGLE best action to take right now. "
            "If the action needs auth and is not granted, use request_authorization. "
            "Output ONLY valid JSON.",
        ]
        return "\n".join(lines)

    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        data = self._safe_parse_json(llm_output)

        action_str = data.get("action_type", "noop").lower().strip()
        target = str(data.get("target", ""))
        reasoning = str(data.get("reasoning", llm_output[:300]))
        confidence = float(data.get("confidence", 0.5))
        needs_auth = bool(data.get("needs_authorization", False))

        action_map = {
            "restart_pod": ActionType.RESTART_POD,
            "scale_deployment": ActionType.SCALE_DEPLOYMENT,
            "rollback_deployment": ActionType.ROLLBACK_DEPLOYMENT,
            "isolate_pod": ActionType.ISOLATE_POD,
            "drain_node": ActionType.DRAIN_NODE,
            "update_config": ActionType.UPDATE_CONFIG,
            "request_authorization": ActionType.REQUEST_AUTHORIZATION,
            "send_message": ActionType.SEND_MESSAGE,
            "noop": ActionType.NOOP,
        }
        action_type = action_map.get(action_str, ActionType.NOOP)

        # If the action is dangerous and not yet authorized → force request_authorization
        if action_type in DANGEROUS_ACTIONS:
            action_name = action_type.value
            if action_name not in self._authorized_actions:
                log.info(
                    "remediation_requires_auth",
                    action=action_type.value,
                    target=target,
                )
                return ActionModel(
                    agent=self.role,
                    action_type=ActionType.REQUEST_AUTHORIZATION,
                    target=target,
                    parameters={
                        "requested_action": action_type.value,
                        "confidence": confidence,
                    },
                    reasoning=(
                        f"Requesting authorization for {action_type.value} on {target}. "
                        f"Confidence: {confidence:.0%}. {reasoning}"
                    ),
                )
            else:
                # Clear the authorization after use
                self._authorized_actions.discard(action_name)

        # Default target resolution — pick the first unhealthy pod
        if not target:
            for name, pod in obs.cluster_state.pods.items():
                if not pod.ready:
                    target = name
                    break
            # Fallback to first degraded service
            if not target:
                for name, svc in obs.cluster_state.services.items():
                    if svc.error_rate_percent > 5.0:
                        target = name
                        break

        params: dict = {}
        expected = data.get("expected_outcome", "")
        if expected:
            params["expected_outcome"] = expected

        return ActionModel(
            agent=self.role,
            action_type=action_type,
            target=target,
            parameters=params,
            reasoning=reasoning,
        )
