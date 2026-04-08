"""
ChaosMesh Arena — DatabaseAgent (Task 2.6)

The Database Agent:
- Specializes in PostgreSQL / Redis performance diagnosis
- Uses query_db_stats, query_metrics, get_logs, describe_pod
- Threshold activation: only acts when DB-related issues are detected
- Reports DB root causes: slow queries, connection pool exhaustion,
  replication lag, lock contention, OOM in DB pod
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

# Threshold: only activate when DB error rate or latency crosses these
DB_ERROR_THRESHOLD_PCT = 5.0
DB_LATENCY_THRESHOLD_MS = 100.0

# Keywords that indicate a DB-related problem
_DB_KEYWORDS = [
    "psql", "postgres", "pg_", "SELECT", "INSERT", "UPDATE", "DELETE",
    "slow query", "connection", "db", "redis", "cache", "replication",
    "WAL", "vacuum", "checkpoint", "lock", "transaction", "connection pool",
    "ECONNREFUSED", "timeout", "connection refused",
]


def _is_db_relevant(obs: ObservationModel) -> bool:
    """Check if the DB agent should activate for this observation."""
    # Check DB service degradation
    for name, svc in obs.cluster_state.services.items():
        if "db" in name.lower() or "postgres" in name.lower() or "redis" in name.lower():
            if svc.error_rate_percent > DB_ERROR_THRESHOLD_PCT:
                return True
            if svc.p99_latency_ms > DB_LATENCY_THRESHOLD_MS:
                return True

    # Check DB pod health
    for name, pod in obs.cluster_state.pods.items():
        labels = pod.labels
        if any(kw in labels.get("app", "") for kw in ["postgres", "redis", "mysql", "mongo"]):
            if not pod.ready:
                return True

    # Check DB-related log lines
    if obs.recent_logs:
        for line in obs.recent_logs[-10:]:
            if any(kw.lower() in line.lower() for kw in _DB_KEYWORDS):
                return True

    # Check metrics
    for m in obs.recent_metrics:
        if any(kw in m.name for kw in ["db", "query", "connection", "replication"]):
            if m.value > 0:
                return True

    return False


class DatabaseAgent(BaseAgent):
    """
    Database Agent — the DB performance expert of the SRE swarm.

    Investigation logic:
    1. Check if DB issues are present (threshold activation)
    2. If not relevant: NOOP
    3. If relevant: investigate DB pod, service metrics, and logs
    4. Build hypothesis: slow queries / connection pool / OOM / replication lag
    5. Report FINDING when confidence ≥ 0.6
    """

    @property
    def role(self) -> AgentRole:
        return AgentRole.DATABASE

    @property
    def system_prompt(self) -> str:
        return (
            "You are the Database Agent in a Kubernetes SRE swarm. "
            "You ONLY activate when database-related issues are detected. "
            "Your job is to diagnose DB performance problems.\n\n"
            "## Your Tools\n"
            "- query_db_stats: Get connection count, active queries, replication lag, "
            "lock waits, table sizes\n"
            "- query_metrics: Get DB-specific Prometheus metrics\n"
            "- get_logs: Read PostgreSQL/Redis logs for slow queries, errors\n"
            "- describe_pod: Check DB pod resource usage (OOM risk)\n"
            "- send_message: Report FINDING to Commander\n"
            "- noop: Not my problem — DB looks healthy\n\n"
            "## Investigation Strategy\n"
            "1. Check connection count vs. pool size (connection exhaustion)\n"
            "2. Look for slow queries > 1000ms in logs\n"
            "3. Check replication lag (> 30s is critical)\n"
            "4. Check pod memory usage (OOM kills DB = data loss risk)\n"
            "5. Look for lock contention or vacuum issues\n\n"
            "## Issue Severity Guide\n"
            "CRITICAL: DB pod OOMKilled, replication lag > 5min, connection pool exhausted\n"
            "HIGH: Slow queries > 5s, error_rate > 10%\n"
            "MEDIUM: Latency > 100ms, autovacuum running\n\n"
            "## Output Format (JSON only)\n"
            "{\n"
            "  \"action_type\": \"query_db_stats|query_metrics|get_logs|"
            "describe_pod|send_message|noop\",\n"
            "  \"target\": \"<db_pod_name|db_service_name>\",\n"
            "  \"db_issue_type\": \"slow_query|connection_exhaustion|oom|"
            "replication_lag|lock_contention|healthy\",\n"
            "  \"hypothesis\": \"<DB root cause theory>\",\n"
            "  \"confidence\": 0.0-1.0,\n"
            "  \"severity\": \"critical|high|medium|low\",\n"
            "  \"reasoning\": \"<evidence summary>\",\n"
            "  \"finding\": \"<key observation to report, or empty>\"\n"
            "}"
        )

    @property
    def available_tools(self) -> list[ActionType]:
        return [
            ActionType.QUERY_DB_STATS,
            ActionType.QUERY_METRICS,
            ActionType.GET_LOGS,
            ActionType.DESCRIBE_POD,
            ActionType.SEND_MESSAGE,
            ActionType.NOOP,
        ]

    def _reason(self, obs: ObservationModel) -> str:
        """Build DB agent reasoning prompt."""
        # Threshold activation check
        is_relevant = _is_db_relevant(obs)

        lines = [
            f"## Step {obs.step} | Level {obs.current_level.value} Incident",
            f"## DB Agent Activation: {'✅ ACTIVE — DB issues detected' if is_relevant else '⏸️  STANDBY — No DB issues visible'}",
            "",
        ]

        if not is_relevant:
            lines.append("No database-related problems detected. Use noop unless you have specific DB findings.")
            lines.append("\n## Output\nRespond with: {\"action_type\": \"noop\", \"target\": \"\", \"hypothesis\": \"No DB issues\", \"confidence\": 0.9, \"reasoning\": \"DB metrics within normal thresholds\", \"finding\": \"\"}")
            return "\n".join(lines)

        # Active incident context
        lines += ["## Active Incidents (DB-relevant)"]
        for inc in obs.active_incidents:
            desc_lower = inc.description.lower()
            if any(kw.lower() in desc_lower for kw in _DB_KEYWORDS):
                lines.append(f"- {inc.title}: {inc.description[:200]}")

        # DB service metrics
        lines += ["", "## Database Service Metrics"]
        for name, svc in obs.cluster_state.services.items():
            if "db" in name.lower() or "postgres" in name.lower() or "redis" in name.lower():
                lines.append(
                    f"- {name}: error={svc.error_rate_percent:.1f}%, "
                    f"P99={svc.p99_latency_ms:.0f}ms, "
                    f"RPS={svc.request_rate_rps:.0f}, "
                    f"endpoints={svc.healthy_endpoints}/{svc.total_endpoints}"
                )

        # DB pod health
        lines += ["", "## Database Pod Status"]
        for name, pod in obs.cluster_state.pods.items():
            is_db = any(kw in pod.labels.get("app", "") for kw in ["postgres", "redis", "mysql"])
            if is_db or "db" in name.lower() or "cache" in name.lower():
                lines.append(
                    f"- {name} (app={pod.labels.get('app', '?')}): "
                    f"phase={pod.phase.value}, ready={pod.ready}, "
                    f"cpu={pod.resources.cpu_millicores}m/"
                    f"{pod.resources.cpu_limit_millicores}m, "
                    f"mem={pod.resources.memory_mib}MiB/"
                    f"{pod.resources.memory_limit_mib}MiB, "
                    f"restarts={pod.restart_count}"
                )

        # DB-relevant logs
        db_logs = [
            line for line in obs.recent_logs[-20:]
            if any(kw.lower() in line.lower() for kw in _DB_KEYWORDS)
        ]
        if db_logs:
            lines += ["", "## DB-Relevant Log Lines"]
            for line in db_logs[-8:]:
                lines.append(f"  {line[:160]}")

        # DB-relevant metrics
        db_metrics = [
            m for m in obs.recent_metrics
            if any(kw in m.name for kw in ["db", "query", "connection", "replication", "cache"])
        ]
        if db_metrics:
            lines += ["", "## DB Metrics"]
            for m in db_metrics[:8]:
                lines.append(f"  {m.name}={m.value:.2f}{m.unit}")

        # Messages from other agents
        pending = self.flush_messages()
        if pending:
            lines += ["", "## Messages from Other Agents"]
            for msg in pending:
                lines.append(f"  [{msg.sender.value}] {msg.content.finding[:150]}")

        lines += [
            "",
            "## DB Diagnosis Required",
            "Identify the root cause, report your finding if confidence ≥ 0.6. "
            "Choose the most valuable next tool call. Output ONLY valid JSON.",
        ]
        return "\n".join(lines)

    def _parse_action(self, llm_output: str, obs: ObservationModel) -> ActionModel:
        data = self._safe_parse_json(llm_output)

        action_str = data.get("action_type", "noop").lower().strip()
        target = str(data.get("target", ""))
        reasoning = str(data.get("reasoning", llm_output[:300]))
        finding = str(data.get("finding", ""))
        confidence = float(data.get("confidence", 0.5))
        severity = str(data.get("severity", "medium"))

        action_map = {
            "query_db_stats": ActionType.QUERY_DB_STATS,
            "query_metrics": ActionType.QUERY_METRICS,
            "get_logs": ActionType.GET_LOGS,
            "describe_pod": ActionType.DESCRIBE_POD,
            "send_message": ActionType.SEND_MESSAGE,
            "noop": ActionType.NOOP,
        }
        action_type = action_map.get(action_str, ActionType.NOOP)

        # Default target: first DB pod
        if not target:
            for name, pod in obs.cluster_state.pods.items():
                if "db" in name.lower() or "cache" in name.lower():
                    target = name
                    break
            if not target:
                for name in obs.cluster_state.services:
                    if "db" in name.lower():
                        target = name
                        break

        params: dict = {}
        if finding:
            params["finding"] = finding
        if confidence:
            params["confidence"] = confidence
        if severity:
            params["severity"] = severity

        # Auto-promote to send_message for high-confidence findings
        if confidence >= 0.65 and action_type not in (
            ActionType.SEND_MESSAGE, ActionType.NOOP
        ) and finding:
            action_type = ActionType.SEND_MESSAGE

        return ActionModel(
            agent=self.role,
            action_type=action_type,
            target=target,
            parameters=params,
            reasoning=reasoning,
        )
