"""
ChaosMesh Arena — Core Pydantic Models (RFC 001/002/003 compliant).

All I/O types used by the Gymnasium environment, FastAPI endpoints,
and inter-agent messages are defined here.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


# Shared config that serializes datetimes as ISO strings
_API_CONFIG = ConfigDict(json_encoders={__import__('datetime').datetime: lambda v: v.isoformat()})


# ═══════════════════════════════════════════════════════════════════════════════
# Enumerations
# ═══════════════════════════════════════════════════════════════════════════════


class PodPhase(str, Enum):
    PENDING = "Pending"
    RUNNING = "Running"
    TERMINATING = "Terminating"
    FAILED = "Failed"
    SUCCEEDED = "Succeeded"
    EVICTED = "Evicted"


class NodeCondition(str, Enum):
    READY = "Ready"
    NOT_READY = "NotReady"
    DISK_PRESSURE = "DiskPressure"
    MEMORY_PRESSURE = "MemoryPressure"


class AgentRole(str, Enum):
    INCIDENT_COMMANDER = "incident_commander"
    DIAGNOSTICS = "diagnostics"
    REMEDIATION = "remediation"
    SECURITY = "security"
    DATABASE = "database"


class MessageType(str, Enum):
    FINDING = "FINDING"
    REQUEST = "REQUEST"
    DEBATE = "DEBATE"
    NOTIFICATION = "NOTIFICATION"
    AUTHORIZATION = "AUTHORIZATION"
    RESOLUTION = "RESOLUTION"


class Urgency(str, Enum):
    P0 = "P0"  # Critical — system down
    P1 = "P1"  # High — degraded
    P2 = "P2"  # Medium — warning


class IncidentLevel(int, Enum):
    LEVEL_1 = 1  # Single-point failures (fully implemented)
    LEVEL_2 = 2  # Correlated failures (fully implemented)
    LEVEL_3 = 3  # Ambiguous scenarios (fully implemented)
    LEVEL_4 = 4  # Dynamic failures (stub)
    LEVEL_5 = 5  # Compound chaos (stub)


class IncidentStatus(str, Enum):
    ACTIVE = "active"
    INVESTIGATING = "investigating"
    MITIGATING = "mitigating"
    RESOLVED = "resolved"
    TIMED_OUT = "timed_out"


class ActionType(str, Enum):
    # Observation tools
    GET_LOGS = "get_logs"
    QUERY_METRICS = "query_metrics"
    DESCRIBE_POD = "describe_pod"
    DESCRIBE_NODE = "describe_node"
    QUERY_TRACES = "query_traces"
    SCAN_TRAFFIC = "scan_traffic"
    QUERY_DB_STATS = "query_db_stats"
    # Remediation actions
    RESTART_POD = "restart_pod"
    SCALE_DEPLOYMENT = "scale_deployment"
    UPDATE_CONFIG = "update_config"
    ROLLBACK_DEPLOYMENT = "rollback_deployment"
    ISOLATE_POD = "isolate_pod"
    DRAIN_NODE = "drain_node"
    # Coordination tools
    SEND_MESSAGE = "send_message"
    REQUEST_AUTHORIZATION = "request_authorization"
    GRANT_AUTHORIZATION = "grant_authorization"
    ESCALATE = "escalate"
    BROADCAST_STATUS = "broadcast_status"
    DECLARE_RESOLVED = "declare_resolved"
    NOOP = "noop"


# ═══════════════════════════════════════════════════════════════════════════════
# Cluster State Models
# ═══════════════════════════════════════════════════════════════════════════════


class ResourceUsage(BaseModel):
    model_config = ConfigDict(strict=True)

    cpu_millicores: int = Field(ge=0, description="CPU usage in millicores")
    memory_mib: int = Field(ge=0, description="Memory usage in MiB")
    cpu_limit_millicores: int = Field(ge=0, default=1000)
    memory_limit_mib: int = Field(ge=0, default=512)

    @property
    def cpu_percent(self) -> float:
        return (self.cpu_millicores / self.cpu_limit_millicores) * 100

    @property
    def memory_percent(self) -> float:
        return (self.memory_mib / self.memory_limit_mib) * 100


class PodModel(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    namespace: str = "default"
    phase: PodPhase = PodPhase.RUNNING
    node_name: str
    labels: dict[str, str] = Field(default_factory=dict)
    resources: ResourceUsage
    restart_count: int = Field(ge=0, default=0)
    ready: bool = True
    start_time: datetime = Field(default_factory=datetime.utcnow)
    conditions: dict[str, bool] = Field(default_factory=lambda: {"Ready": True})


class ServiceModel(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    namespace: str = "default"
    selector: dict[str, str] = Field(default_factory=dict)
    port: int = Field(gt=0, lt=65536, default=80)
    target_port: int = Field(gt=0, lt=65536, default=8080)
    healthy_endpoints: int = Field(ge=0, default=3)
    total_endpoints: int = Field(ge=0, default=3)
    request_rate_rps: float = Field(ge=0, default=100.0)
    error_rate_percent: float = Field(ge=0, le=100, default=0.0)
    p99_latency_ms: float = Field(ge=0, default=50.0)


class NodeModel(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    condition: NodeCondition = NodeCondition.READY
    allocatable_cpu_millicores: int = Field(ge=0, default=4000)
    allocatable_memory_mib: int = Field(ge=0, default=8192)
    used_cpu_millicores: int = Field(ge=0, default=0)
    used_memory_mib: int = Field(ge=0, default=0)
    pod_count: int = Field(ge=0, default=0)
    max_pods: int = Field(ge=0, default=110)
    zone: str = "us-east-1a"

    @property
    def cpu_pressure(self) -> bool:
        return self.used_cpu_millicores > self.allocatable_cpu_millicores * 0.85

    @property
    def memory_pressure(self) -> bool:
        return self.used_memory_mib > self.allocatable_memory_mib * 0.85


class ClusterStateModel(BaseModel):
    """Complete snapshot of the simulated Kubernetes cluster."""

    model_config = ConfigDict(strict=True)

    cluster_name: str = "chaosmesh-sim"
    sim_time_minutes: float = Field(ge=0, default=0.0)
    pods: dict[str, PodModel] = Field(default_factory=dict)
    services: dict[str, ServiceModel] = Field(default_factory=dict)
    nodes: dict[str, NodeModel] = Field(default_factory=dict)
    network_partitions: list[tuple[str, str]] = Field(default_factory=list)
    active_incidents: list[str] = Field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Incident Models
# ═══════════════════════════════════════════════════════════════════════════════


class IncidentModel(BaseModel):
    model_config = ConfigDict(strict=True)

    incident_id: str = Field(default_factory=lambda: f"inc-{uuid.uuid4().hex[:8]}")
    title: str
    description: str
    level: IncidentLevel
    status: IncidentStatus = IncidentStatus.ACTIVE
    affected_components: list[str] = Field(default_factory=list)
    root_cause: str = ""               # Hidden from agents — ground truth for scoring
    false_lead: str = ""               # Optional red herring
    symptoms: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: datetime | None = None
    mttr_simulated_minutes: float | None = None


# ═══════════════════════════════════════════════════════════════════════════════
# Agent Communication Models (RFC §2.2)
# ═══════════════════════════════════════════════════════════════════════════════


class AgentMessageContent(BaseModel):
    model_config = ConfigDict(strict=True)

    finding: str = ""
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    evidence: list[str] = Field(default_factory=list)
    recommended_action: str = ""
    reasoning: str = ""


class AgentMessage(BaseModel):
    """Structured inter-agent message (per spec §2.2)."""

    model_config = ConfigDict(strict=True)

    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    sender: AgentRole
    recipient: AgentRole | None = None     # None = broadcast
    message_type: MessageType
    urgency: Urgency = Urgency.P2
    content: AgentMessageContent
    requires_response: bool = False
    in_reply_to: str | None = None         # message_id of parent


class AgentBeliefModel(BaseModel):
    """An agent's current hypothesis about the incident."""

    model_config = ConfigDict(strict=True)

    agent: AgentRole
    hypothesis: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ═══════════════════════════════════════════════════════════════════════════════
# Action Models (RFC 002)
# ═══════════════════════════════════════════════════════════════════════════════


class ActionModel(BaseModel):
    """Agent action submitted to env.step() — RFC 002 compliant."""

    model_config = ConfigDict()

    action_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent: AgentRole
    action_type: ActionType
    target: str = Field(default="", max_length=128)
    parameters: dict[str, Any] = Field(default_factory=dict)
    message: AgentMessage | None = None  # For SEND_MESSAGE actions
    reasoning: str = Field(default="", max_length=1000)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    # Safety — block unsafe actions at model level
    UNSAFE_ACTIONS: frozenset[str] = frozenset({
        "delete_namespace", "drop_database", "truncate_table",
        "delete_pvc", "force_delete_node",
    })

    @field_validator("target", mode="before")
    @classmethod
    def validate_target(cls, v: str) -> str:
        """
        Allowlist: Kubernetes resource names only.
        Accepts: lowercase letters, digits, hyphens, dots, forward-slash (namespace/name).
        Rejects: null bytes, path traversal, shell metacharacters, CRLF.
        """
        import re
        if v is None:
            return ""
        v = str(v)
        # Reject dangerous characters outright
        DANGEROUS = ["\x00", "\n", "\r", "..", "%00", "`", "$", ";", "&", "|", ">", "<"]
        for bad in DANGEROUS:
            if bad in v:
                raise ValueError(f"target contains forbidden sequence: {bad!r}")
        # Allow empty string (not all actions need a target)
        if v == "":
            return v
        # Kubernetes naming: lowercase alphanum, hyphens, dots, optional namespace prefix
        if not re.fullmatch(r"[a-z0-9][a-z0-9\-\.\/]{0,127}", v):
            raise ValueError(
                "target must be a valid Kubernetes resource name "
                "(lowercase letters, digits, hyphens, dots only)"
            )
        return v

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v: dict) -> dict:
        """Limit parameter keys to known allowlist."""
        ALLOWED_KEYS = {
            "replicas", "image", "config_key", "config_value",
            "timeout_seconds", "reason", "namespace",
        }
        if not isinstance(v, dict):
            return {}
        unknown = set(v.keys()) - ALLOWED_KEYS
        if unknown:
            raise ValueError(f"Unknown parameter keys: {unknown}")
        return v

    def is_safe(self) -> bool:
        target_lower = self.target.lower()
        return not any(u in target_lower for u in self.UNSAFE_ACTIONS)


# ═══════════════════════════════════════════════════════════════════════════════
# Observation Model (RFC 001)
# ═══════════════════════════════════════════════════════════════════════════════


class MetricSnapshot(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    value: float
    unit: str
    labels: dict[str, str] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ObservationModel(BaseModel):
    """
    Environment observation returned by reset() and step() — RFC 001.

    Agents observe this snapshot each step.
    """

    model_config = ConfigDict()

    episode_id: str
    step: int
    sim_time_minutes: float
    cluster_state: ClusterStateModel
    active_incidents: list[IncidentModel]
    recent_metrics: list[MetricSnapshot] = Field(default_factory=list)
    recent_logs: list[str] = Field(default_factory=list)  # last 20 log lines
    agent_messages: list[AgentMessage] = Field(default_factory=list)
    agent_beliefs: dict[str, AgentBeliefModel] = Field(default_factory=dict)
    available_tools: list[ActionType] = Field(default_factory=list)
    current_level: IncidentLevel = IncidentLevel.LEVEL_1


# ═══════════════════════════════════════════════════════════════════════════════
# Reward Model
# ═══════════════════════════════════════════════════════════════════════════════


class RewardBreakdown(BaseModel):
    model_config = ConfigDict()

    individual: float = 0.0    # Agent-specific reward
    coordination: float = 0.0  # Team communication quality
    efficiency: float = 0.0    # MTTR vs. target
    resolution: float = 0.0    # Incident resolution quality
    total: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Step Result & Full State (RFC 002/003)
# ═══════════════════════════════════════════════════════════════════════════════


class StepResult(BaseModel):
    """Return type of env.step() — RFC 002 compliant."""

    model_config = ConfigDict()

    observation: ObservationModel
    reward: RewardBreakdown
    terminated: bool
    truncated: bool
    info: dict[str, Any] = Field(default_factory=dict)


class FullStateModel(BaseModel):
    """
    Complete internal environment state returned by state() — RFC 003.

    Includes hidden ground truth (root causes) for post-mortem analysis.
    """

    model_config = ConfigDict()

    episode_id: str
    step: int
    sim_time_minutes: float
    wall_time_seconds: float
    cluster_state: ClusterStateModel
    active_incidents: list[IncidentModel]
    all_messages: list[AgentMessage] = Field(default_factory=list)
    all_beliefs: dict[str, AgentBeliefModel] = Field(default_factory=dict)
    action_history: list[ActionModel] = Field(default_factory=list)
    reward_history: list[RewardBreakdown] = Field(default_factory=list)
    current_level: IncidentLevel = IncidentLevel.LEVEL_1
    episode_status: IncidentStatus = IncidentStatus.ACTIVE
    cumulative_reward: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# API Request/Response Models
# ═══════════════════════════════════════════════════════════════════════════════


class ResetRequest(BaseModel):
    model_config = ConfigDict()

    level: IncidentLevel = IncidentLevel.LEVEL_1
    seed: int | None = None
    demo_scenario: str | None = None


class ResetResponse(BaseModel):
    model_config = ConfigDict()

    episode_id: str
    observation: ObservationModel


class StepRequest(BaseModel):
    model_config = ConfigDict()

    episode_id: str
    action: ActionModel


class InjectRequest(BaseModel):
    model_config = ConfigDict()

    scenario_key: str | None = None
    description: str = Field(max_length=500)
    level: IncidentLevel = IncidentLevel.LEVEL_1
    urgency: Urgency = Urgency.P1


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "0.1.0"
    uptime_seconds: float = 0.0
    ollama_available: bool = False
    openrouter_available: bool = False
    redis_connected: bool = False
    active_episode: str | None = None
