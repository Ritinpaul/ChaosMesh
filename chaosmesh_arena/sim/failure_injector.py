"""
ChaosMesh Arena — Failure Injector.

Orchestrates incident injection into the K8s state machine and metrics/log
engines. Each incident template maps to concrete state mutations.
"""

from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING, Optional

from chaosmesh_arena.models import IncidentLevel, IncidentModel, IncidentStatus

if TYPE_CHECKING:
    from chaosmesh_arena.sim.cluster_state import ClusterStateMachine
    from chaosmesh_arena.sim.log_synthesizer import LogSynthesizer
    from chaosmesh_arena.sim.metrics_engine import MetricsEngine


@dataclasses.dataclass
class InjectionResult:
    incident: IncidentModel
    affected_pods: list[str]
    affected_services: list[str]
    initial_logs: list[str]


class FailureInjector:
    """
    Translates incident templates into concrete cluster state mutations,
    metric anomalies, and log injections.

    Supports rollback (remediation) per incident.
    """

    def __init__(
        self,
        cluster: "ClusterStateMachine",
        metrics: "MetricsEngine",
        logs: "LogSynthesizer",
    ) -> None:
        self._cluster = cluster
        self._metrics = metrics
        self._logs = logs
        self._active: dict[str, InjectionResult] = {}  # incident_id → result

    # ── Level 1 — Single-Point Failures ──────────────────────────────────────

    def inject_pod_crash(self, pod_name: Optional[str] = None) -> InjectionResult:
        """Level 1: Pod OOMKilled crash."""
        pods = list(self._cluster._pods.keys())
        target = pod_name or next(
            (p for p in pods if "api" in p), pods[0] if pods else None
        )
        if not target:
            raise ValueError("No pods available to crash")

        pod = self._cluster._pods[target]
        self._cluster.oom_pod(target)

        # Inject correlated metrics and logs
        self._metrics.inject_anomaly(
            "pod_memory_usage_percent",
            "spike",
            {"pod": target},
            intensity=1.0,
            duration_seconds=120,
        )
        self._metrics.inject_anomaly(
            "pod_restart_count",
            "slow_climb",
            {"pod": target},
            intensity=0.5,
            duration_seconds=300,
        )
        logs = self._logs.inject_error(pod, "oom", count=4)
        logs += self._logs.inject_error(pod, "crash_loop", count=2)

        incident = IncidentModel(
            title=f"Pod {target} OOMKilled",
            description=f"Pod {target} exceeded memory limits and was killed by the OOM handler.",
            level=IncidentLevel.LEVEL_1,
            affected_components=[target],
            root_cause="Memory limit too low for workload; container consumed all available memory.",
            symptoms=["pod_restart_count increasing", "pod_memory_usage_percent at 100%",
                      "OOMKilled in pod logs"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[target],
            affected_services=[],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_memory_leak(self, pod_name: Optional[str] = None) -> InjectionResult:
        """Level 1: Slow memory leak — gradual climb to OOM."""
        pods = list(self._cluster._pods.keys())
        target = pod_name or next(
            (p for p in pods if "api" in p), pods[0] if pods else None
        )
        if not target:
            raise ValueError("No pods available")

        pod = self._cluster._pods[target]
        self._metrics.inject_anomaly(
            "pod_memory_usage_percent",
            "slow_climb",
            {"pod": target},
            intensity=0.8,
            duration_seconds=600,
        )
        logs = self._logs.inject_error(pod, "oom", count=1)

        incident = IncidentModel(
            title=f"Memory leak detected in {target}",
            description="Pod memory usage is climbing steadily. No OOM yet but trajectory is critical.",
            level=IncidentLevel.LEVEL_1,
            affected_components=[target],
            root_cause="Application memory leak — objects allocated but not garbage collected.",
            false_lead="High request rate suggests traffic spike (but it's a leak, not load).",
            symptoms=["pod_memory_usage_percent slowly climbing", "GC pause logs increasing"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[target],
            affected_services=[],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_network_timeout(self, svc_name: Optional[str] = None) -> InjectionResult:
        """Level 1: Single service intermittent timeouts."""
        svcs = list(self._cluster._services.keys())
        target_svc = svc_name or (svcs[0] if svcs else None)
        if not target_svc:
            raise ValueError("No services available")

        self._cluster.degrade_service(target_svc, error_rate=15.0, latency_multiplier=8.0, healthy_frac=1.0)
        self._metrics.inject_anomaly(
            "service_p99_latency_ms",
            "sawtooth",
            {"service": target_svc},
            intensity=0.8,
            duration_seconds=300,
        )
        self._metrics.inject_anomaly(
            "service_error_rate_percent",
            "spike",
            {"service": target_svc},
            intensity=0.5,
            duration_seconds=300,
        )

        # Fake a representative pod for log injection
        pod = next(iter(self._cluster._pods.values()))
        logs = self._logs.inject_error(pod, "timeout", count=5)

        incident = IncidentModel(
            title=f"Service {target_svc} intermittent timeouts",
            description="Clients experiencing periodic timeouts on the service. Error rate elevated.",
            level=IncidentLevel.LEVEL_1,
            affected_components=[target_svc],
            root_cause="Upstream dependency (external API) degraded; timeouts propagating.",
            symptoms=["service_error_rate_percent > 10%", "service_p99_latency_ms spikes",
                      "timeout errors in logs"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[],
            affected_services=[target_svc],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_disk_pressure(self, node_name: Optional[str] = None) -> InjectionResult:
        """Level 1: Node disk pressure."""
        nodes = list(self._cluster._nodes.keys())
        target_node = node_name or nodes[0]
        node = self._cluster._nodes[target_node]
        from chaosmesh_arena.models import NodeCondition
        self._cluster._nodes[target_node] = node.model_copy(
            update={"condition": NodeCondition.DISK_PRESSURE}
        )

        pod = next(iter(self._cluster._pods.values()))
        logs = self._logs.inject_error(pod, "disk_pressure", count=4)

        incident = IncidentModel(
            title=f"Node {target_node} disk pressure",
            description="Node is reporting DiskPressure condition. Kubelet may evict pods.",
            level=IncidentLevel.LEVEL_1,
            affected_components=[target_node],
            root_cause="Log files filled /var/log partition. No log rotation configured.",
            symptoms=["node.condition = DiskPressure", "ENOSPC errors in pod logs",
                      "pod evictions imminent"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[],
            affected_services=[],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_image_pull_failure(self, pod_name: Optional[str] = None) -> InjectionResult:
        """Level 1: Container image pull failure."""
        pods = list(self._cluster._pods.keys())
        target = pod_name or pods[-1]
        pod = self._cluster._pods[target]
        from chaosmesh_arena.models import PodPhase
        self._cluster._pods[target] = pod.model_copy(
            update={"phase": PodPhase.PENDING, "ready": False}
        )

        logs = [
            f"[{self._logs._sim_ts()}] ERROR Failed to pull image \"myapp:v2.1.1\": "
            f"rpc error: code = Unknown desc = failed to pull and unpack image: "
            f"failed to resolve reference: unexpected status code 404",
            f"[{self._logs._sim_ts()}] WARNING  Back-off pulling image \"myapp:v2.1.1\" "
            f"pod={target}",
        ]
        self._logs._buffer.extend(logs)

        incident = IncidentModel(
            title=f"ImagePullBackOff on {target}",
            description="Pod stuck in Pending state — cannot pull container image.",
            level=IncidentLevel.LEVEL_1,
            affected_components=[target],
            root_cause="Container registry tag v2.1.1 does not exist (typo in deployment YAML).",
            symptoms=["pod.phase = Pending", "ImagePullBackOff event", "pod not ready"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[target],
            affected_services=[],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    # ── Level 2 — Correlated Failures ─────────────────────────────────────────

    def inject_cascading_db_timeout(self) -> InjectionResult:
        """Level 2: Network partition → DB timeouts → API service degradation."""
        self._cluster.apply_network_partition("us-east-1a", "us-east-1b")
        svc = "svc-db"
        api_svc = "svc-api"
        if svc in self._cluster._services:
            self._cluster.degrade_service(svc, error_rate=80.0, latency_multiplier=20.0, healthy_frac=0.0)
        if api_svc in self._cluster._services:
            self._cluster.degrade_service(api_svc, error_rate=45.0, latency_multiplier=12.0, healthy_frac=0.5)

        self._metrics.inject_anomaly(
            "service_error_rate_percent", "spike",
            {"service": "svc-db"}, intensity=1.0, duration_seconds=300,
        )
        self._metrics.inject_anomaly(
            "service_p99_latency_ms", "spike",
            {"service": "svc-api"}, intensity=0.9, duration_seconds=300,
        )

        db_pod = next((p for n, p in self._cluster._pods.items() if "db" in n), None)
        api_pod = next((p for n, p in self._cluster._pods.items() if "api" in n), None)
        logs = []
        if db_pod:
            logs += self._logs.inject_error(db_pod, "connection_refused", count=3)
        if api_pod:
            logs += self._logs.inject_error(api_pod, "timeout", count=4)

        incident = IncidentModel(
            title="Cascading DB failure — network partition",
            description="Network partition between zones a and b caused DB to become unreachable. "
                        "API service is timing out on all DB-backed endpoints.",
            level=IncidentLevel.LEVEL_2,
            affected_components=["us-east-1a", "us-east-1b", "svc-db", "svc-api"],
            root_cause="Network partition between availability zones. DB pod is in zone-a, "
                       "API pods in zone-b cannot reach it.",
            symptoms=["svc-db error rate 80%", "svc-api error rate 45%",
                      "connection refused to DB", "inter-zone connectivity loss"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[db_pod.name if db_pod else "", api_pod.name if api_pod else ""],
            affected_services=["svc-db", "svc-api"],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_node_failure_cascade(self) -> InjectionResult:
        """Level 2: Node failure → pod rescheduling → resource contention."""
        from chaosmesh_arena.models import NodeCondition, PodPhase
        node = self._cluster._nodes.get("node-01")
        if node:
            self._cluster._nodes["node-01"] = node.model_copy(
                update={"condition": NodeCondition.NOT_READY}
            )
            # Evict all pods on node-01
            for pod_name, pod in list(self._cluster._pods.items()):
                if pod.node_name == "node-01":
                    self._cluster.evict_pod(pod_name, "NodeNotReady")

        # Overload node-02 with all evicted pods
        node2 = self._cluster._nodes.get("node-02")
        if node2:
            self._cluster._nodes["node-02"] = node2.model_copy(update={
                "used_cpu_millicores": int(node2.allocatable_cpu_millicores * 0.95),
                "used_memory_mib": int(node2.allocatable_memory_mib * 0.92),
            })

        pod = next(iter(self._cluster._pods.values()))
        logs = self._logs.inject_error(pod, "connection_refused", count=2)
        logs += self._logs.inject_error(pod, "crash_loop", count=2)

        incident = IncidentModel(
            title="Node failure causing pod rescheduling cascade",
            description="node-01 became NotReady. All 3 pods evicted and rescheduled onto "
                        "node-02, causing severe resource contention.",
            level=IncidentLevel.LEVEL_2,
            affected_components=["node-01", "node-02"],
            root_cause="node-01 lost network connectivity (simulated NIC failure). "
                       "node-02 overloaded by rescheduled pods.",
            symptoms=["node-01 NotReady", "multiple pods in Pending/Evicted",
                      "node-02 CPU/memory at 95%+", "pod restarts increasing"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=list(self._cluster._pods.keys()),
            affected_services=list(self._cluster._services.keys()),
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_rolling_restart_failure(self) -> InjectionResult:
        """Level 2: Config change → rolling restart fails → partial outage."""
        api_pods = [n for n in self._cluster._pods if "api" in n]
        for pod_name in api_pods[:1]:  # First pod restart fails
            self._cluster.evict_pod(pod_name, "ConfigChange")

        if "svc-api" in self._cluster._services:
            self._cluster.degrade_service("svc-api", error_rate=30.0, latency_multiplier=3.0, healthy_frac=0.5)

        pod = next(iter(self._cluster._pods.values()))
        logs = self._logs.inject_error(pod, "crash_loop", count=3)

        incident = IncidentModel(
            title="Rolling restart failure — config update",
            description="Deploying config change with invalid env var. "
                        "Pods crash on startup, creating partial outage.",
            level=IncidentLevel.LEVEL_2,
            affected_components=["pod-api-6d8f4", "svc-api"],
            root_cause="ConfigMap update introduced invalid DATABASE_URL format. "
                       "Pods fail readiness probe on startup.",
            symptoms=["pod CrashLoopBackOff", "svc-api 50% endpoints healthy",
                      "30% error rate on API"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=api_pods[:1],
            affected_services=["svc-api"],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    # ── Level 3 — Ambiguous Scenarios ─────────────────────────────────────────

    def inject_ambiguous_attack_vs_misconfig(self) -> InjectionResult:
        """Level 3: Security attack indicators AND misconfiguration indicators present simultaneously."""
        # Auth anomaly metrics (looks like attack)
        self._metrics.inject_anomaly(
            "service_error_rate_percent", "spike",
            {"service": "svc-api"}, intensity=0.7, duration_seconds=400,
        )
        if "svc-api" in self._cluster._services:
            self._cluster.degrade_service("svc-api", error_rate=25.0, latency_multiplier=5.0, healthy_frac=1.0)

        api_pod = next((p for n, p in self._cluster._pods.items() if "api" in n), None)
        logs = []
        if api_pod:
            # Auth anomaly logs (security indicator)
            logs += self._logs.inject_error(api_pod, "auth_anomaly", count=4)
            # Timeout logs (misconfiguration indicator)
            logs += self._logs.inject_error(api_pod, "timeout", count=3)

        incident = IncidentModel(
            title="Elevated error rate — attack or misconfiguration?",
            description="API service showing 25% error rate and auth anomalies. "
                        "Could be credential stuffing attack OR rate limiter misconfiguration "
                        "causing false 401s. Security and Diagnostics agents will disagree.",
            level=IncidentLevel.LEVEL_3,
            affected_components=["svc-api"],
            root_cause="Rate limiter misconfiguration — threshold set too low after recent "
                       "config update; legitimate users hitting limit and being flagged.",
            false_lead="Auth anomaly logs look exactly like credential stuffing pattern.",
            symptoms=["401 errors from multiple IPs", "auth anomaly warnings",
                      "service_error_rate_percent 25%", "timeout errors in same logs"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[api_pod.name if api_pod else ""],
            affected_services=["svc-api"],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    def inject_performance_degradation_ambiguous(self) -> InjectionResult:
        """Level 3: Capacity issue vs code regression — requires multi-agent debate."""
        for pod_name in self._cluster._pods:
            self._metrics.inject_anomaly(
                "pod_cpu_usage_percent", "slow_climb",
                {"pod": pod_name}, intensity=0.6, duration_seconds=500,
            )

        if "svc-api" in self._cluster._services:
            self._cluster.degrade_service("svc-api", error_rate=8.0, latency_multiplier=6.0, healthy_frac=1.0)

        self._metrics.inject_anomaly(
            "service_p99_latency_ms", "slow_climb",
            {"service": "svc-api"}, intensity=0.7, duration_seconds=500,
        )

        db_pod = next((p for n, p in self._cluster._pods.items() if "db" in n), None)
        api_pod = next((p for n, p in self._cluster._pods.items() if "api" in n), None)
        logs = []
        if db_pod:
            logs += self._logs.inject_error(db_pod, "timeout", count=2)
        if api_pod:
            logs += self._logs.inject_error(api_pod, "timeout", count=3)

        incident = IncidentModel(
            title="Gradual performance degradation",
            description="P99 latency climbing over last 10 minutes. CPU rising across all pods. "
                        "Could be capacity (traffic growth) or code regression (N+1 query introduced).",
            level=IncidentLevel.LEVEL_3,
            affected_components=["svc-api", "pod-db-7x3p9"],
            root_cause="N+1 query introduced in recent deployment — each API call now makes "
                       "O(n) DB queries instead of 1 batched query.",
            false_lead="Traffic increased 40% this week, suggesting capacity issue.",
            symptoms=["pod_cpu_usage_percent climbing all pods", "service_p99_latency_ms 6x normal",
                      "slow DB queries in logs", "traffic volume looks higher"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=[p.name for p in self._cluster._pods.values()],
            affected_services=["svc-api"],
            initial_logs=logs,
        )
        self._active[incident.incident_id] = result
        return result

    # ── Level 4 Stubs ─────────────────────────────────────────────────────────

    def inject_level4_dynamic_failure(self, template: str = "remediation_secondary") -> InjectionResult:
        """
        Level 4 — STUB: Dynamic failures where remediation triggers secondary failure.

        NOTE: Full dynamic generation not yet implemented. Uses seed template.
        Future: DynamicFailureEngine.generate() will create these adaptively.
        """
        # Use Level 1 pod crash as seed template for now
        incident = IncidentModel(
            title="[STUB] Remediation-triggered secondary failure",
            description="[Level 4 Stub] Restarting pod-api triggers OOM on pod-cache "
                        "due to connection pool surge. Fix one thing, break another.",
            level=IncidentLevel.LEVEL_4,
            affected_components=["pod-api-6d8f4", "pod-cache-2j5n8"],
            root_cause="[Stub] Connection pool not properly drained before pod restart. "
                       "Surge of reconnections overwhelms cache pod.",
            symptoms=["[Stub] pod-api restarted successfully",
                      "[Stub] pod-cache OOMKilled 30s later"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=["pod-api-6d8f4", "pod-cache-2j5n8"],
            affected_services=[],
            initial_logs=["[STUB] Level 4 incident injected via seed template"],
        )
        self._active[incident.incident_id] = result
        return result

    def inject_level5_compound_chaos(self, template: str = "db_plus_gateway") -> InjectionResult:
        """
        Level 5 — STUB: Multiple simultaneous unrelated incidents.

        NOTE: Full compound generation not yet implemented. Uses seed template.
        Future: CompoundChaosEngine.generate() will create adaptive multi-incident scenarios.
        """
        incident = IncidentModel(
            title="[STUB] Compound chaos — DB lag + API gateway saturation",
            description="[Level 5 Stub] Simultaneous: DB replication lag (replica 2 min behind) "
                        "AND API gateway CPU saturated from unrelated load test.",
            level=IncidentLevel.LEVEL_5,
            affected_components=["pod-db-7x3p9", "pod-ingress-4r7t2"],
            root_cause="[Stub] Two independent issues: (1) long-running analytics query blocking "
                       "replication WAL. (2) Load test misconfigured to hit production gateway.",
            symptoms=["[Stub] DB replica lag > 2min", "[Stub] ingress CPU 95%",
                      "[Stub] split-brain read concerns"],
        )
        result = InjectionResult(
            incident=incident,
            affected_pods=["pod-db-7x3p9", "pod-ingress-4r7t2"],
            affected_services=["svc-db", "svc-api"],
            initial_logs=["[STUB] Level 5 compound incident injected via seed template"],
        )
        self._active[incident.incident_id] = result
        return result

    # ── Remediation ────────────────────────────────────────────────────────────

    def remediate(self, incident_id: str, action_pod: Optional[str] = None) -> bool:
        """
        Apply remediation for an incident — reverses cluster mutations.
        Returns True if incident was found and remediated.
        """
        result = self._active.pop(incident_id, None)
        if not result:
            return False

        # Restore pods
        for pod_name in result.affected_pods:
            if pod_name:
                self._cluster.restore_pod(pod_name)

        # Restore services
        for svc_name in result.affected_services:
            self._cluster.restore_service(svc_name)

        # Clear metric anomalies
        self._metrics.reset()

        # Heal any network partitions
        self._cluster._network_partitions.clear()

        # Restore node conditions
        from chaosmesh_arena.models import NodeCondition
        for node_name, node in self._cluster._nodes.items():
            if node.condition != NodeCondition.READY:
                self._cluster._nodes[node_name] = node.model_copy(
                    update={"condition": NodeCondition.READY}
                )

        # Log remediation success
        if action_pod and action_pod in self._cluster._pods:
            self._logs.inject_remediation(self._cluster._pods[action_pod])

        return True

    def get_active_incidents(self) -> list[IncidentModel]:
        return [r.incident for r in self._active.values()]

    def is_all_resolved(self) -> bool:
        return len(self._active) == 0
