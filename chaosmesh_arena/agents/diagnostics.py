"""
ChaosMesh Arena — DiagnosticsAgent (Task 2.3)

The Diagnostics Agent:
- Uses get_logs, query_metrics, describe_pod, describe_node, query_traces
- Builds high-confidence hypotheses from observability data
- Reports FINDINGs to the Incident Commander
- Stores diagnostic patterns in ChromaDB for cross-episode learning
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


class DiagnosticsAgent(BaseAgent):
    """
    Diagnostics Agent — the eyes and ears of the SRE swarm.

    Investigates incidents by:
    1. Getting logs from affected pods
    2. Querying Prometheus-style metrics
    3. Describing pod/node state
    4. Flagging anomalies and building root cause hypotheses
    5. Sending FINDINGs to the Commander and Swarm
    """

    @property
    def role(self) -> AgentRole:
        return AgentRole.DIAGNOSTICS

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Diagnostics Agent in a Kubernetes SRE swarm. "
            "Your ONLY job is to investigate incidents using observability tools. "
            "You do NOT fix things — that's Remediation's job.\n\n"
            "## Your Tools\n"
            "- get_logs: Retrieve logs from a specific pod\n"
            "- query_metrics: Query Prometheus-style metrics for a service or pod\n"
            "- describe_pod: Get pod status, conditions, events\n"
            "- describe_node: Get node capacity and conditions\n"
            "- query_traces: Fetch distributed traces for a service\n"
            "- send_message: Report a FINDING to the Commander\n"
            "- noop: Wait for more info\n\n"
            "## Investigation Strategy\n"
            "1. Check unhealthy pods first — run get_logs on the most critical one\n"
            "2. Query metrics for affected services (look for latency/error spikes)\n"
            "3. Cross-reference with recent logs to identify root cause\n"
            "4. Build hypothesis with confidence score (0.0–1.0)\n"
            "5. Send FINDING message when confidence ≥ 0.6\n\n"
            "## Output Format (JSON only)\n"
            "{\n"
            "  \"action_type\": \"get_logs|query_metrics|describe_pod|describe_node|query_traces|send_message|noop\",\n"
            "  \"target\": \"<pod_name|service_name|node_name>\",\n"
            "  \"hypothesis\": \"<current root cause theory>\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"reasoning\": \"<investigation rationale>\",\n"
            "  \"finding\": \"<key observation to report, or empty if not reporting yet>\"\n"
            "}"
        )

    @property
    def available_tools(self) -> list[ActionType]:
        return [
            ActionType.GET_LOGS,
            ActionType.QUERY_METRICS,
            ActionType.DESCRIBE_POD,
            ActionType.DESCRIBE_NODE,
            ActionType.QUERY_TRACES,
            ActionType.SEND_MESSAGE,
            ActionType.NOOP,
        ]

    def _reason(self, obs: ObservationModel) -> str:
        """Build diagnostics prompt — focus on what to investigate next."""
        lines = [
            f"## Step {obs.step} | Level {obs.current_level.value} Incident",
            "",
            "## Active Incidents",
        ]
        for inc in obs.active_incidents:
            lines.append(f"- {inc.title}: {inc.description[:200]}")
            if inc.symptoms:
                lines.append(f"  Symptoms: {', '.join(inc.symptoms[:5])}")

        # Which pods are unhealthy?
        unhealthy = [
            (name, pod)
            for name, pod in obs.cluster_state.pods.items()
            if not pod.ready
        ]
        lines += ["", "## Unhealthy Pods"]
        if unhealthy:
            for name, pod in unhealthy:
                lines.append(
                    f"- {name}: phase={pod.phase.value}, "
                    f"restarts={pod.restart_count}, "
                    f"cpu={pod.resources.cpu_millicores}m, "
                    f"mem={pod.resources.memory_mib}MiB"
                )
        else:
            lines.append("- All pods healthy")

        # Service error rates
        lines += ["", "## Service Error Rates"]
        for name, svc in obs.cluster_state.services.items():
            if svc.error_rate_percent > 0:
                lines.append(
                    f"- {name}: {svc.error_rate_percent:.1f}% errors, "
                    f"P99={svc.p99_latency_ms:.0f}ms, "
                    f"RPS={svc.request_rate_rps:.0f}"
                )

        # Recent logs
        if obs.recent_logs:
            lines += ["", "## Recent Logs (last 10 lines)"]
            lines.extend(f"  {line}" for line in obs.recent_logs[-10:])

        # Recent metrics
        if obs.recent_metrics:
            lines += ["", "## Recent Metrics"]
            for m in obs.recent_metrics[-8:]:
                lines.append(f"  {m.name}={m.value:.2f}{m.unit} labels={m.labels}")

        # Messages from other agents
        pending = self.flush_messages()
        if pending:
            lines += ["", "## Messages From Other Agents"]
            for msg in pending:
                lines.append(f"  [{msg.sender.value}] {msg.content.finding[:150]}")

        lines += [
            "",
            "## Your Next Investigation Step",
            "Which tool do you use next? If you have a high-confidence finding (≥0.6), "
            "send it. Otherwise, keep investigating. Output ONLY valid JSON.",
        ]
        return "\n".join(lines)

    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        data = self._safe_parse_json(llm_output)

        action_str = data.get("action_type", "noop").lower().strip()
        target = str(data.get("target", ""))
        reasoning = str(data.get("reasoning", llm_output[:300]))
        finding = str(data.get("finding", ""))

        # If no specific target, pick the first unhealthy pod
        if not target:
            for name, pod in obs.cluster_state.pods.items():
                if not pod.ready:
                    target = name
                    break
            if not target and obs.cluster_state.pods:
                target = next(iter(obs.cluster_state.pods))

        action_map = {
            "get_logs": ActionType.GET_LOGS,
            "query_metrics": ActionType.QUERY_METRICS,
            "describe_pod": ActionType.DESCRIBE_POD,
            "describe_node": ActionType.DESCRIBE_NODE,
            "query_traces": ActionType.QUERY_TRACES,
            "send_message": ActionType.SEND_MESSAGE,
            "noop": ActionType.NOOP,
        }
        action_type = action_map.get(action_str, ActionType.GET_LOGS)

        # If it's a SEND_MESSAGE, embed the finding in parameters
        params: dict = {}
        if finding:
            params["finding"] = finding
            params["confidence"] = float(data.get("confidence", 0.5))

        # If high confidence — auto-send_message instead of another observation
        confidence = float(data.get("confidence", 0.0))
        if confidence >= 0.65 and action_type not in (ActionType.SEND_MESSAGE, ActionType.NOOP):
            # Prioritize reporting over tool use once confident
            if finding or reasoning:
                action_type = ActionType.SEND_MESSAGE
                params["finding"] = finding or reasoning[:300]
                params["confidence"] = confidence

        return ActionModel(
            agent=self.role,
            action_type=action_type,
            target=target,
            parameters=params,
            reasoning=reasoning,
        )
