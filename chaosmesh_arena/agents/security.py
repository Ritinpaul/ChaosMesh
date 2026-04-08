"""
ChaosMesh Arena — SecurityAgent (Task 2.5)

The Security Agent:
- Specializes in distinguishing attacks from misconfigurations
- Uses scan_traffic, query_metrics (auth anomaly signals), get_logs
- Integrates with MetricsEngine to check auth anomaly indicators
- Reports high-confidence threat assessments to the Commander
- Can recommend pod isolation for confirmed security threats
"""

from __future__ import annotations

import structlog

from chaosmesh_arena.agents.base_agent import BaseAgent
from chaosmesh_arena.models import (
    ActionModel,
    ActionType,
    AgentRole,
    ObservationModel,
)

log = structlog.get_logger(__name__)

# Keywords in logs that suggest security events
_SECURITY_KEYWORDS = [
    "auth_anomaly", "credential stuffing", "JWT", "401 Unauthorized",
    "unusual auth pattern", "unexpected origin", "possible credential",
    "brute force", "rate limit", "injection", "XSS", "traversal",
]

# Keywords suggesting misconfiguration (not attack)
_MISCONFIG_KEYWORDS = [
    "misconfigured", "invalid config", "ConfigMap", "rate limiter",
    "threshold", "timeout", "connection refused", "deploy", "rollback",
]


class SecurityAgent(BaseAgent):
    """
    Security Agent — the threat analyst of the SRE swarm.

    Investigation logic:
    1. Analyze auth anomalies and traffic patterns first
    2. Cross-reference with recent logs for attack signatures vs. misconfig signals
    3. Build threat hypothesis with attack/misconfig probability
    4. When confidence ≥ 0.65 — report FINDING with recommendation
    5. Only recommend pod isolation for confirmed attacks (not misconfiguration)
    """

    @property
    def role(self) -> AgentRole:
        return AgentRole.SECURITY

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Security Agent in a Kubernetes SRE swarm. "
            "Your ONLY job is to determine whether elevated error rates are caused by "
            "a SECURITY ATTACK or a MISCONFIGURATION.\n\n"
            "## Your Tools\n"
            "- scan_traffic: Analyze network traffic for attack patterns "
            "(DDoS, credential stuffing, injection)\n"
            "- query_metrics: Check auth failure rates, request anomalies\n"
            "- get_logs: Look for attack signatures vs. config error messages\n"
            "- isolate_pod: Emergency isolation (REQUIRES IC authorization)\n"
            "- send_message: Report threat assessment to Commander\n"
            "- noop: Wait / observe\n\n"
            "## Threat Assessment Guide\n"
            "Attack indicators: multiple source IPs, failed auth with pattern, "
            "unusual endpoints, payload anomalies, credential stuffing pattern\n"
            "Misconfig indicators: consistent error pattern, recent deploy, "
            "config change correlated with errors, single error type\n\n"
            "## Decision Rule\n"
            "- If attack confidence ≥ 0.7: recommend isolate_pod + alert Commander\n"
            "- If misconfig confidence ≥ 0.7: report FINDING to Commander + Diagnostics\n"
            "- If ambiguous: report both hypotheses with confidence scores\n\n"
            "## Output Format (JSON only)\n"
            "{\n"
            "  \"action_type\": \"scan_traffic|query_metrics|get_logs|"
            "isolate_pod|send_message|noop\",\n"
            "  \"target\": \"<pod_name|service_name|IP>\",\n"
            "  \"attack_probability\": 0.0-1.0,\n"
            "  \"misconfig_probability\": 0.0-1.0,\n"
            "  \"hypothesis\": \"<your threat assessment>\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"reasoning\": \"<evidence-based rationale>\",\n"
            "  \"finding\": \"<key observation to report, or empty>\"\n"
            "}"
        )

    @property
    def available_tools(self) -> list[ActionType]:
        return [
            ActionType.SCAN_TRAFFIC,
            ActionType.QUERY_METRICS,
            ActionType.GET_LOGS,
            ActionType.ISOLATE_POD,
            ActionType.SEND_MESSAGE,
            ActionType.NOOP,
        ]

    def _reason(self, obs: ObservationModel) -> str:
        """Build security analysis prompt — focus on attack vs. misconfig signals."""
        lines = [
            f"## Step {obs.step} | Level {obs.current_level.value} Incident",
            "",
            "## Active Incidents",
        ]
        for inc in obs.active_incidents:
            lines.append(f"- {inc.title}: {inc.description[:200]}")
            if inc.symptoms:
                lines.append(f"  Symptoms: {', '.join(inc.symptoms[:5])}")

        # Service anomalies — security focus
        lines += ["", "## Service Error Analysis"]
        for name, svc in obs.cluster_state.services.items():
            if svc.error_rate_percent > 5.0:
                lines.append(
                    f"- {name}: error_rate={svc.error_rate_percent:.1f}%, "
                    f"P99={svc.p99_latency_ms:.0f}ms, "
                    f"RPS={svc.request_rate_rps:.0f}"
                )

        # Log analysis — look for security signals
        security_signals: list[str] = []
        misconfig_signals: list[str] = []
        if obs.recent_logs:
            lines += ["", "## Security-Relevant Log Lines"]
            for line in obs.recent_logs[-20:]:
                line_lower = line.lower()
                is_security = any(kw.lower() in line_lower for kw in _SECURITY_KEYWORDS)
                is_misconfig = any(kw.lower() in line_lower for kw in _MISCONFIG_KEYWORDS)
                if is_security:
                    security_signals.append(line)
                    lines.append(f"  🔴 [ATTACK?] {line[:150]}")
                elif is_misconfig:
                    misconfig_signals.append(line)
                    lines.append(f"  🟡 [MISCONFIG?] {line[:150]}")

        # Metrics — auth anomaly focus
        if obs.recent_metrics:
            auth_metrics = [
                m for m in obs.recent_metrics
                if any(kw in m.name for kw in ["error", "request", "auth"])
            ]
            if auth_metrics:
                lines += ["", "## Auth/Request Metrics"]
                for m in auth_metrics[:6]:
                    lines.append(f"  {m.name}={m.value:.2f}{m.unit} labels={m.labels}")

        # Running tally
        lines += ["", "## Signal Count"]
        lines.append(f"  Attack signals: {len(security_signals)}")
        lines.append(f"  Misconfig signals: {len(misconfig_signals)}")

        # Messages from other agents
        pending = self.flush_messages()
        if pending:
            lines += ["", "## Messages from Other Agents"]
            for msg in pending:
                lines.append(f"  [{msg.sender.value}] {msg.content.finding[:150]}")

        lines += [
            "",
            "## Your Security Assessment",
            "Based on the signals above, classify this as ATTACK or MISCONFIG (or both). "
            "If confidence ≥ 0.65, send your finding. "
            "Output ONLY valid JSON.",
        ]
        return "\n".join(lines)

    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        data = self._safe_parse_json(llm_output)

        action_str = data.get("action_type", "noop").lower().strip()
        target = str(data.get("target", ""))
        reasoning = str(data.get("reasoning", llm_output[:300]))
        finding = str(data.get("finding", ""))
        confidence = float(data.get("confidence", 0.5))
        attack_prob = float(data.get("attack_probability", 0.0))
        misconfig_prob = float(data.get("misconfig_probability", 0.0))

        action_map = {
            "scan_traffic": ActionType.SCAN_TRAFFIC,
            "query_metrics": ActionType.QUERY_METRICS,
            "get_logs": ActionType.GET_LOGS,
            "isolate_pod": ActionType.ISOLATE_POD,
            "send_message": ActionType.SEND_MESSAGE,
            "noop": ActionType.NOOP,
        }
        action_type = action_map.get(action_str, ActionType.SCAN_TRAFFIC)

        # Default target — first affected service or pod
        if not target:
            for inc in obs.active_incidents:
                if inc.affected_components:
                    target = inc.affected_components[0]
                    break
            if not target:
                for name, svc in obs.cluster_state.services.items():
                    if svc.error_rate_percent > 5.0:
                        target = name
                        break

        params: dict = {
            "attack_probability": attack_prob,
            "misconfig_probability": misconfig_prob,
        }
        if finding:
            params["finding"] = finding
        if confidence:
            params["confidence"] = confidence

        # Auto-promote to send_message when confidence is high
        if confidence >= 0.65 and action_type not in (
            ActionType.SEND_MESSAGE, ActionType.ISOLATE_POD, ActionType.NOOP
        ):
            action_type = ActionType.SEND_MESSAGE
            params["finding"] = finding or (
                f"Security assessment: attack_prob={attack_prob:.0%}, "
                f"misconfig_prob={misconfig_prob:.0%}. {reasoning[:200]}"
            )

        return ActionModel(
            agent=self.role,
            action_type=action_type,
            target=target,
            parameters=params,
            reasoning=reasoning,
        )
