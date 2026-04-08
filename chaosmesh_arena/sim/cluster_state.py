"""
ChaosMesh Arena — Kubernetes Cluster State Machine.

Simulates a K8s cluster as an in-memory graph (networkx).
Provides realistic state transitions: pod lifecycle, node pressure,
network partitions, and resource contention.

No real K8s cluster required — this is a faithful simulation.
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Optional

import networkx as nx

from chaosmesh_arena.models import (
    ClusterStateModel,
    NodeCondition,
    NodeModel,
    PodModel,
    PodPhase,
    ResourceUsage,
    ServiceModel,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Default Cluster Blueprint
# ═══════════════════════════════════════════════════════════════════════════════

_DEFAULT_NODES = [
    NodeModel(
        name="node-01",
        zone="us-east-1a",
        allocatable_cpu_millicores=4000,
        allocatable_memory_mib=8192,
        used_cpu_millicores=1200,
        used_memory_mib=3200,
        pod_count=3,
    ),
    NodeModel(
        name="node-02",
        zone="us-east-1b",
        allocatable_cpu_millicores=4000,
        allocatable_memory_mib=8192,
        used_cpu_millicores=800,
        used_memory_mib=2048,
        pod_count=2,
    ),
    NodeModel(
        name="node-03",
        zone="us-east-1c",
        allocatable_cpu_millicores=4000,
        allocatable_memory_mib=8192,
        used_cpu_millicores=400,
        used_memory_mib=1024,
        pod_count=0,
    ),
]

_DEFAULT_PODS = [
    PodModel(
        name="pod-api-6d8f4",
        node_name="node-01",
        labels={"app": "api", "version": "v2.1.0"},
        resources=ResourceUsage(
            cpu_millicores=300, memory_mib=256,
            cpu_limit_millicores=500, memory_limit_mib=512,
        ),
    ),
    PodModel(
        name="pod-api-9k2m1",
        node_name="node-02",
        labels={"app": "api", "version": "v2.1.0"},
        resources=ResourceUsage(
            cpu_millicores=280, memory_mib=240,
            cpu_limit_millicores=500, memory_limit_mib=512,
        ),
    ),
    PodModel(
        name="pod-db-7x3p9",
        node_name="node-01",
        labels={"app": "postgres", "role": "primary"},
        resources=ResourceUsage(
            cpu_millicores=600, memory_mib=2048,
            cpu_limit_millicores=2000, memory_limit_mib=4096,
        ),
    ),
    PodModel(
        name="pod-cache-2j5n8",
        node_name="node-02",
        labels={"app": "redis", "tier": "cache"},
        resources=ResourceUsage(
            cpu_millicores=100, memory_mib=512,
            cpu_limit_millicores=500, memory_limit_mib=1024,
        ),
    ),
    PodModel(
        name="pod-ingress-4r7t2",
        node_name="node-01",
        labels={"app": "nginx-ingress", "component": "controller"},
        resources=ResourceUsage(
            cpu_millicores=150, memory_mib=256,
            cpu_limit_millicores=1000, memory_limit_mib=512,
        ),
    ),
]

_DEFAULT_SERVICES = [
    ServiceModel(
        name="svc-api",
        selector={"app": "api"},
        port=80,
        target_port=8080,
        healthy_endpoints=2,
        total_endpoints=2,
        request_rate_rps=150.0,
        error_rate_percent=0.1,
        p99_latency_ms=45.0,
    ),
    ServiceModel(
        name="svc-db",
        selector={"app": "postgres"},
        port=5432,
        target_port=5432,
        healthy_endpoints=1,
        total_endpoints=1,
        request_rate_rps=80.0,
        error_rate_percent=0.0,
        p99_latency_ms=8.0,
    ),
]


# ═══════════════════════════════════════════════════════════════════════════════
# Cluster State Machine
# ═══════════════════════════════════════════════════════════════════════════════


class ClusterStateMachine:
    """
    In-memory simulation of a Kubernetes cluster.

    Maintains a networkx DiGraph where:
    - Nodes = pods, services, k8s-nodes
    - Edges = network connections, scheduling relationships

    State transitions are realistic but happen in simulated time.
    """

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._graph: nx.DiGraph = nx.DiGraph()
        self._pods: dict[str, PodModel] = {}
        self._services: dict[str, ServiceModel] = {}
        self._nodes: dict[str, NodeModel] = {}
        self._network_partitions: list[tuple[str, str]] = []
        self._sim_time_minutes: float = 0.0
        self._init_default_cluster()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_default_cluster(self) -> None:
        """Load the default 5-pod, 2-service, 3-node cluster."""
        for node in _DEFAULT_NODES:
            self.add_node(node)
        for pod in _DEFAULT_PODS:
            self.add_pod(pod)
        for svc in _DEFAULT_SERVICES:
            self.add_service(svc)
        # Wire services → pods (based on label selectors)
        self._refresh_service_endpoints()

    def reset(self, seed: Optional[int] = None) -> None:
        """Full cluster reset — restores default healthy state."""
        if seed is not None:
            self._rng = random.Random(seed)
        self._graph.clear()
        self._pods.clear()
        self._services.clear()
        self._nodes.clear()
        self._network_partitions.clear()
        self._sim_time_minutes = 0.0
        self._init_default_cluster()

    # ── Graph Manipulation ───────────────────────────────────────────────────

    def add_pod(self, pod: PodModel) -> None:
        self._pods[pod.name] = pod
        self._graph.add_node(pod.name, kind="pod", data=pod)
        # Edge: pod → node (scheduled-on)
        if pod.node_name in self._nodes:
            self._graph.add_edge(pod.name, pod.node_name, relation="scheduled-on")

    def add_service(self, svc: ServiceModel) -> None:
        self._services[svc.name] = svc
        self._graph.add_node(svc.name, kind="service", data=svc)

    def add_node(self, node: NodeModel) -> None:
        self._nodes[node.name] = node
        self._graph.add_node(node.name, kind="k8s-node", data=node)

    # ── State Transitions ─────────────────────────────────────────────────────

    def evict_pod(self, pod_name: str, reason: str = "OOMKilled") -> bool:
        """
        Evict a pod — transitions it to EVICTED phase.
        Pod stays NOT READY until an agent explicitly restarts it.
        Returns True if a target node was found.
        """
        if pod_name not in self._pods:
            return False
        pod = self._pods[pod_name]
        pod = pod.model_copy(update={
            "phase": PodPhase.EVICTED,
            "ready": False,
            "restart_count": pod.restart_count + 1,
        })
        self._pods[pod_name] = pod
        self._graph.nodes[pod_name]["data"] = pod
        # Record which node could take it but don't auto-reschedule
        available_node = self._find_schedulable_node(pod)
        return available_node is not None

    def oom_pod(self, pod_name: str) -> None:
        """Simulate an OOM kill — spike memory then evict."""
        if pod_name not in self._pods:
            return
        pod = self._pods[pod_name]
        # Memory spikes to 100% limit and pod goes not-ready immediately
        spiked_resources = pod.resources.model_copy(update={
            "memory_mib": pod.resources.memory_limit_mib,
        })
        pod = pod.model_copy(update={
            "resources": spiked_resources,
            "ready": False,                          # ← mark not-ready before eviction
            "phase": PodPhase.FAILED,
        })
        self._pods[pod_name] = pod
        self.evict_pod(pod_name, "OOMKilled")

    def apply_network_partition(self, zone_a: str, zone_b: str) -> None:
        """Partition network between two zones — all inter-zone traffic blocked."""
        self._network_partitions.append((zone_a, zone_b))
        # Remove graph edges between pods in different zones
        for pod_a_name, pod_a in self._pods.items():
            node_a = self._nodes.get(pod_a.node_name)
            for pod_b_name, pod_b in self._pods.items():
                if pod_a_name == pod_b_name:
                    continue
                node_b = self._nodes.get(pod_b.node_name)
                if node_a and node_b:
                    if (node_a.zone == zone_a and node_b.zone == zone_b) or \
                       (node_a.zone == zone_b and node_b.zone == zone_a):
                        if self._graph.has_edge(pod_a_name, pod_b_name):
                            self._graph.remove_edge(pod_a_name, pod_b_name)

    def heal_network_partition(self, zone_a: str, zone_b: str) -> None:
        """Remove a network partition and restore connectivity."""
        try:
            self._network_partitions.remove((zone_a, zone_b))
        except ValueError:
            pass
        self._refresh_service_endpoints()

    def apply_cpu_throttle(self, pod_name: str, cpu_multiplier: float = 5.0) -> None:
        """Spike CPU usage on a pod (simulates CPU-hungry workload)."""
        if pod_name not in self._pods:
            return
        pod = self._pods[pod_name]
        new_cpu = min(
            int(pod.resources.cpu_millicores * cpu_multiplier),
            pod.resources.cpu_limit_millicores,
        )
        updated = pod.resources.model_copy(update={"cpu_millicores": new_cpu})
        self._pods[pod_name] = pod.model_copy(update={"resources": updated})
        # Update node used CPU
        node = self._nodes.get(pod.node_name)
        if node:
            self._nodes[pod.node_name] = node.model_copy(update={
                "used_cpu_millicores": min(
                    node.used_cpu_millicores + (new_cpu - pod.resources.cpu_millicores),
                    node.allocatable_cpu_millicores,
                )
            })

    def degrade_service(
        self,
        svc_name: str,
        error_rate: float = 50.0,
        latency_multiplier: float = 10.0,
        healthy_frac: float = 0.5,
    ) -> None:
        """Degrade a service's health — increases error rate and latency."""
        if svc_name not in self._services:
            return
        svc = self._services[svc_name]
        healthy = max(0, int(svc.total_endpoints * healthy_frac))
        self._services[svc_name] = svc.model_copy(update={
            "error_rate_percent": error_rate,
            "p99_latency_ms": svc.p99_latency_ms * latency_multiplier,
            "healthy_endpoints": healthy,
        })

    def restore_pod(self, pod_name: str) -> bool:
        """Restore a pod to Running state (remediation action)."""
        if pod_name not in self._pods:
            return False
        pod = self._pods[pod_name]
        healthy_resources = ResourceUsage(
            cpu_millicores=max(50, pod.resources.cpu_millicores // 4),
            memory_mib=max(64, pod.resources.memory_mib // 4),
            cpu_limit_millicores=pod.resources.cpu_limit_millicores,
            memory_limit_mib=pod.resources.memory_limit_mib,
        )
        self._pods[pod_name] = pod.model_copy(update={
            "phase": PodPhase.RUNNING,
            "ready": True,
            "resources": healthy_resources,
            "conditions": {"Ready": True},
        })
        return True

    def restore_service(self, svc_name: str) -> bool:
        """Restore service to healthy state."""
        if svc_name not in self._services:
            return False
        svc = self._services[svc_name]
        self._services[svc_name] = svc.model_copy(update={
            "error_rate_percent": 0.1,
            "p99_latency_ms": 45.0,
            "healthy_endpoints": svc.total_endpoints,
        })
        return True

    # ── Simulated Time ────────────────────────────────────────────────────────

    def tick(self, real_seconds: float = 1.0, time_acceleration: float = 15.0) -> None:
        """
        Advance simulated time.
        Default: 1 real second = 15 simulated seconds.
        """
        self._sim_time_minutes += (real_seconds * time_acceleration) / 60.0
        # Natural drift: small random fluctuations in pod resources
        self._apply_resource_drift()

    def _apply_resource_drift(self) -> None:
        """Add natural random noise to resource metrics (makes metrics more realistic)."""
        for pod_name, pod in self._pods.items():
            if pod.phase != PodPhase.RUNNING:
                continue
            drift_cpu = self._rng.randint(-20, 20)
            drift_mem = self._rng.randint(-10, 10)
            new_cpu = max(10, min(
                pod.resources.cpu_limit_millicores,
                pod.resources.cpu_millicores + drift_cpu,
            ))
            new_mem = max(16, min(
                pod.resources.memory_limit_mib,
                pod.resources.memory_mib + drift_mem,
            ))
            updated = pod.resources.model_copy(update={
                "cpu_millicores": new_cpu,
                "memory_mib": new_mem,
            })
            self._pods[pod_name] = pod.model_copy(update={"resources": updated})

    # ── Internal Helpers ─────────────────────────────────────────────────────

    def _find_schedulable_node(self, pod: PodModel) -> Optional[str]:
        """Find a node with enough resources to place the pod."""
        for node_name, node in self._nodes.items():
            if node.condition != NodeCondition.READY:
                continue
            fits_cpu = (node.used_cpu_millicores + pod.resources.cpu_limit_millicores
                        < node.allocatable_cpu_millicores * 0.9)
            fits_mem = (node.used_memory_mib + pod.resources.memory_limit_mib
                        < node.allocatable_memory_mib * 0.9)
            if fits_cpu and fits_mem:
                return node_name
        return None

    def _reschedule_pod(self, pod_name: str, target_node: str) -> None:
        """Move a pod to a new node."""
        pod = self._pods[pod_name]
        old_node = self._nodes.get(pod.node_name)
        new_node = self._nodes.get(target_node)
        if old_node:
            self._nodes[pod.node_name] = old_node.model_copy(update={
                "pod_count": max(0, old_node.pod_count - 1),
                "used_cpu_millicores": max(0, old_node.used_cpu_millicores - pod.resources.cpu_millicores),
                "used_memory_mib": max(0, old_node.used_memory_mib - pod.resources.memory_mib),
            })
        if new_node:
            self._nodes[target_node] = new_node.model_copy(update={
                "pod_count": new_node.pod_count + 1,
                "used_cpu_millicores": new_node.used_cpu_millicores + pod.resources.cpu_millicores,
                "used_memory_mib": new_node.used_memory_mib + pod.resources.memory_mib,
            })
        self._pods[pod_name] = pod.model_copy(update={
            "node_name": target_node,
            "phase": PodPhase.RUNNING,
            "ready": True,
        })
        # Update graph edges
        if self._graph.has_edge(pod_name, pod.node_name):
            self._graph.remove_edge(pod_name, pod.node_name)
        self._graph.add_edge(pod_name, target_node, relation="scheduled-on")

    def _refresh_service_endpoints(self) -> None:
        """Update service endpoint counts based on pod ready state."""
        for svc_name, svc in self._services.items():
            matching = [
                p for p in self._pods.values()
                if all(svc.selector.get(k) == v for k, v in svc.selector.items())
            ]
            healthy = sum(1 for p in matching if p.ready and p.phase == PodPhase.RUNNING)
            self._services[svc_name] = svc.model_copy(update={
                "total_endpoints": len(matching),
                "healthy_endpoints": healthy,
            })
            # Graph edges: service → pod
            for pod in matching:
                if not self._graph.has_edge(svc_name, pod.name):
                    self._graph.add_edge(svc_name, pod.name, relation="routes-to")

    # ── Snapshot ──────────────────────────────────────────────────────────────

    def snapshot(self) -> ClusterStateModel:
        """Export current cluster state as a Pydantic model."""
        return ClusterStateModel(
            sim_time_minutes=self._sim_time_minutes,
            pods=dict(self._pods),
            services=dict(self._services),
            nodes=dict(self._nodes),
            network_partitions=list(self._network_partitions),
        )

    # ── Query Helpers (used by agents via tool calls) ─────────────────────────

    def get_pod(self, name: str) -> Optional[PodModel]:
        return self._pods.get(name)

    def get_service(self, name: str) -> Optional[ServiceModel]:
        return self._services.get(name)

    def get_node(self, name: str) -> Optional[NodeModel]:
        return self._nodes.get(name)

    def unhealthy_pods(self) -> list[PodModel]:
        return [p for p in self._pods.values() if not p.ready or p.phase != PodPhase.RUNNING]

    def unhealthy_services(self) -> list[ServiceModel]:
        return [s for s in self._services.values()
                if s.error_rate_percent > 5 or s.healthy_endpoints < s.total_endpoints]

    def has_network_partition(self, zone_a: str, zone_b: str) -> bool:
        return (zone_a, zone_b) in self._network_partitions or \
               (zone_b, zone_a) in self._network_partitions

    @property
    def sim_time_minutes(self) -> float:
        return self._sim_time_minutes
