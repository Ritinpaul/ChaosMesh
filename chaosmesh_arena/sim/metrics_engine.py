"""
ChaosMesh Arena — Prometheus-style Metrics Engine.

Generates realistic time-series metrics for simulated K8s components.
Agents query this via get_logs / query_metrics tool actions.
"""

from __future__ import annotations

import math
import random
import time
from collections import deque
from datetime import datetime
from typing import Optional

from chaosmesh_arena.models import MetricSnapshot, PodModel, ServiceModel


class MetricsEngine:
    """
    Generates Prometheus-compatible metrics for the simulated cluster.

    Maintains a rolling 15-minute buffer of metric time-series.
    Supports PromQL-like label filtering for agent queries.
    """

    BUFFER_SECONDS = 900  # 15 minutes of history

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        # metric_name -> deque of (timestamp, value, labels)
        self._series: dict[str, deque[tuple[float, float, dict[str, str]]]] = {}
        self._anomalies: dict[str, dict] = {}   # active anomaly injections
        self._start_ts = time.time()

    # ── Public API ────────────────────────────────────────────────────────────

    def record(
        self,
        name: str,
        value: float,
        labels: Optional[dict[str, str]] = None,
    ) -> MetricSnapshot:
        """Record a metric data point."""
        labels = labels or {}
        ts = time.time()
        if name not in self._series:
            self._series[name] = deque(maxlen=self.BUFFER_SECONDS)
        self._series[name].append((ts, value, labels))
        return MetricSnapshot(name=name, value=value, unit=self._unit_for(name), labels=labels)

    def query(
        self,
        metric_name: str,
        label_filter: Optional[dict[str, str]] = None,
        last_n: int = 10,
    ) -> list[MetricSnapshot]:
        """
        PromQL-style point-in-time query.
        Returns the last_n data points matching label_filter.
        """
        series = self._series.get(metric_name, deque())
        results = []
        for ts, value, labels in reversed(series):
            if label_filter and not all(labels.get(k) == v for k, v in label_filter.items()):
                continue
            results.append(MetricSnapshot(
                name=metric_name,
                value=round(value, 4),
                unit=self._unit_for(metric_name),
                labels=labels,
                timestamp=datetime.fromtimestamp(ts),
            ))
            if len(results) >= last_n:
                break
        return list(reversed(results))

    def latest(self, metric_name: str, labels: Optional[dict[str, str]] = None) -> Optional[float]:
        """Get the most recent value for a metric."""
        points = self.query(metric_name, labels, last_n=1)
        return points[0].value if points else None

    def inject_anomaly(
        self,
        metric_name: str,
        anomaly_type: str,       # "spike", "slow_climb", "sawtooth", "flatline"
        labels: dict[str, str],
        intensity: float = 1.0,  # 0.0–1.0
        duration_seconds: float = 60.0,
    ) -> None:
        """
        Schedule an anomaly pattern to be applied during snapshot generation.
        Called by the failure injector when an incident is triggered.
        """
        key = f"{metric_name}:{':'.join(f'{k}={v}' for k,v in sorted(labels.items()))}"
        self._anomalies[key] = {
            "metric_name": metric_name,
            "anomaly_type": anomaly_type,
            "labels": labels,
            "intensity": intensity,
            "start_ts": time.time(),
            "duration_seconds": duration_seconds,
        }

    def clear_anomaly(self, metric_name: str, labels: dict[str, str]) -> None:
        """Remove an active anomaly (called on remediation)."""
        key = f"{metric_name}:{':'.join(f'{k}={v}' for k,v in sorted(labels.items()))}"
        self._anomalies.pop(key, None)

    def snapshot_pod(self, pod: PodModel) -> list[MetricSnapshot]:
        """Generate a full metric snapshot for a single pod."""
        labels = {"pod": pod.name, "node": pod.node_name, **pod.labels}
        metrics = []

        # Base values from pod state
        cpu_base = pod.resources.cpu_millicores / pod.resources.cpu_limit_millicores
        mem_base = pod.resources.memory_mib / pod.resources.memory_limit_mib

        # Apply noise
        cpu = self._apply_noise(cpu_base, noise=0.03) * 100
        mem = self._apply_noise(mem_base, noise=0.01) * 100

        # Apply any active anomalies
        cpu = self._apply_anomaly("pod_cpu_usage_percent", labels, cpu)
        mem = self._apply_anomaly("pod_memory_usage_percent", labels, mem)

        metrics.append(self.record("pod_cpu_usage_percent", round(cpu, 2), labels))
        metrics.append(self.record("pod_memory_usage_percent", round(mem, 2), labels))
        metrics.append(self.record("pod_restart_count", float(pod.restart_count), labels))
        metrics.append(self.record(
            "pod_ready",
            1.0 if pod.ready else 0.0,
            labels,
        ))
        return metrics

    def snapshot_service(self, svc: ServiceModel) -> list[MetricSnapshot]:
        """Generate a full metric snapshot for a service."""
        labels = {"service": svc.name}
        metrics = []

        rps = self._apply_anomaly(
            "service_request_rate_rps", labels,
            self._apply_noise(svc.request_rate_rps, noise=0.05),
        )
        err = self._apply_anomaly(
            "service_error_rate_percent", labels,
            self._apply_noise(svc.error_rate_percent, noise=0.1),
        )
        lat = self._apply_anomaly(
            "service_p99_latency_ms", labels,
            self._apply_noise(svc.p99_latency_ms, noise=0.08),
        )

        metrics.append(self.record("service_request_rate_rps", round(rps, 2), labels))
        metrics.append(self.record("service_error_rate_percent", round(max(0, err), 4), labels))
        metrics.append(self.record("service_p99_latency_ms", round(max(0, lat), 2), labels))
        metrics.append(self.record(
            "service_healthy_endpoints",
            float(svc.healthy_endpoints),
            labels,
        ))
        return metrics

    def get_recent_snapshots(self, last_n: int = 20) -> list[MetricSnapshot]:
        """Collect the most recent data point for every tracked metric."""
        snapshots = []
        for metric_name, series in self._series.items():
            if not series:
                continue
            ts, value, labels = series[-1]
            snapshots.append(MetricSnapshot(
                name=metric_name,
                value=round(value, 4),
                unit=self._unit_for(metric_name),
                labels=labels,
                timestamp=datetime.fromtimestamp(ts),
            ))
        # Sort most recent first, limit
        return snapshots[:last_n]

    def reset(self) -> None:
        self._series.clear()
        self._anomalies.clear()
        self._start_ts = time.time()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _apply_noise(self, base: float, noise: float = 0.05) -> float:
        """Add Gaussian noise to a base value."""
        return base * (1 + self._rng.gauss(0, noise))

    def _apply_anomaly(
        self,
        metric_name: str,
        labels: dict[str, str],
        base_value: float,
    ) -> float:
        """Apply anomaly pattern to a base metric value if active."""
        key = f"{metric_name}:{':'.join(f'{k}={v}' for k,v in sorted(labels.items()))}"
        anomaly = self._anomalies.get(key)
        if not anomaly:
            return base_value

        elapsed = time.time() - anomaly["start_ts"]
        if elapsed > anomaly["duration_seconds"]:
            del self._anomalies[key]
            return base_value

        progress = elapsed / anomaly["duration_seconds"]  # 0.0 → 1.0
        intensity = anomaly["intensity"]
        atype = anomaly["anomaly_type"]

        if atype == "spike":
            # Instant spike that decays
            multiplier = 1.0 + (intensity * 10.0 * math.exp(-5 * progress))
        elif atype == "slow_climb":
            # Gradual ramp up
            multiplier = 1.0 + (intensity * 8.0 * progress)
        elif atype == "sawtooth":
            # Oscillating spikes (simulates retry storms)
            period = 0.1
            multiplier = 1.0 + intensity * 5.0 * abs(math.sin(progress * math.pi / period))
        elif atype == "flatline":
            # Metric drops to 0 (service down)
            multiplier = 0.0
        else:
            multiplier = 1.0

        return base_value * multiplier

    @staticmethod
    def _unit_for(metric_name: str) -> str:
        if "percent" in metric_name:
            return "%"
        if "latency" in metric_name or "duration" in metric_name:
            return "ms"
        if "rps" in metric_name or "rate" in metric_name:
            return "req/s"
        if "count" in metric_name:
            return "count"
        if "bytes" in metric_name:
            return "bytes"
        return "value"
