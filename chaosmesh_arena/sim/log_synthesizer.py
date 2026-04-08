"""
ChaosMesh Arena — Synthetic Log Generator.

Produces realistic Kubernetes/application log lines correlated
with cluster state and active incidents. Agents use these via
the get_logs tool action.
"""

from __future__ import annotations

import random
import uuid
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

from chaosmesh_arena.models import PodModel, PodPhase


# ── Log Templates ─────────────────────────────────────────────────────────────

_NORMAL_TEMPLATES: dict[str, list[str]] = {
    "api": [
        'level=info msg="GET /api/v1/health 200" latency=12ms pod={pod}',
        'level=info msg="POST /api/v1/users 201" latency=45ms pod={pod}',
        'level=debug msg="cache hit" key="user:1234" pod={pod}',
        'level=info msg="db query completed" duration=8ms rows=12 pod={pod}',
        'level=info msg="request served" method=GET path=/metrics status=200 pod={pod}',
    ],
    "postgres": [
        'LOG:  checkpoint complete: wrote 42 buffers',
        'LOG:  autovacuum: processing {db}',
        'LOG:  connection received: host=10.0.0.{n} port=54{n2}',
        'LOG:  statement: SELECT 1  -- health check',
        'LOG:  database system is ready to accept connections',
    ],
    "redis": [
        "* Ready to accept connections",
        "* 1 changes in 3600 seconds. Saving...",
        "* Background saving started by pid {pid}",
        ". DB saved on disk",
        "* AOF rewrite: 12 MB of memory used by copy-on-write",
    ],
    "nginx-ingress": [
        '10.0.0.{n} - - [{ts}] "GET / HTTP/1.1" 200 612 "-" "kube-probe/1.27"',
        '10.0.0.{n} - - [{ts}] "GET /api/v1/health HTTP/1.1" 200 18',
        'nginx: [notice] signal process started',
        'upstream keepalive: worker_connections not enough',
    ],
}

_ERROR_TEMPLATES: dict[str, list[str]] = {
    "oom": [
        "FATAL: Out of memory: Kill process {pid} ({app}) score {score}",
        "kernel: oom-kill event: memory cgroup out of memory: Killed process {pid}",
        "level=fatal msg=\"OOMKilled\" pod={pod} memory_limit=512Mi",
        "java.lang.OutOfMemoryError: Java heap space\n\tat java.util.Arrays.copyOf",
    ],
    "connection_refused": [
        'level=error msg="dial tcp {ip}:{port}: connect: connection refused" pod={pod}',
        "Error: ECONNREFUSED {ip}:{port}",
        'psql: error: connection to server at "{ip}" port {port} failed: Connection refused',
        'level=warn msg="upstream unavailable" target={ip}:{port} retry=3 pod={pod}',
    ],
    "timeout": [
        'level=error msg="context deadline exceeded" duration=30s pod={pod}',
        'level=warn msg="slow query detected" duration=5200ms threshold=1000ms pod={pod}',
        'level=error msg="read tcp {ip}:{port}: i/o timeout" pod={pod}',
        "ERROR:  canceling statement due to statement timeout",
    ],
    "auth_anomaly": [
        'level=warn msg="unusual auth pattern" source_ip={ip} attempts=47 pod={pod}',
        'level=warn msg="JWT token from unexpected origin" ip={ip} pod={pod}',
        '401 Unauthorized - too many invalid tokens from {ip}',
        'level=error msg="possible credential stuffing" ips=[{ip},{ip2}] pod={pod}',
    ],
    "disk_pressure": [
        'level=error msg="write failed: no space left on device" path=/var/log pod={pod}',
        "lvm: Insufficient free space: 0 extents needed",
        "ENOSPC: no space left on device",
        "eviction manager: volume is above high threshold",
    ],
    "crash_loop": [
        'level=fatal msg="segmentation fault (core dumped)" pod={pod}',
        "panic: runtime error: index out of range [5] with length 3",
        "signal 11 (SIGSEGV), address not mapped to object at 0x0000000000000010",
        'Back-off restarting failed container {app} in pod {pod}',
    ],
}

_REMEDIATION_TEMPLATES = [
    'level=info msg="pod restarted successfully" pod={pod} restart_count={n}',
    'level=info msg="deployment scaled" replicas={n} pod={pod}',
    'level=info msg="config updated and applied" pod={pod}',
    'level=info msg="connection pool reset" pool_size=20 pod={pod}',
    'level=info msg="service recovered" error_rate=0.1% pod={pod}',
]


class LogSynthesizer:
    """
    Generates realistic log lines for the simulated cluster.

    Maintains a rolling buffer of recent logs (last 500 lines).
    Error injection is controlled by the FailureInjector.
    """

    BUFFER_SIZE = 500

    def __init__(self, seed: Optional[int] = None) -> None:
        self._rng = random.Random(seed)
        self._buffer: deque[str] = deque(maxlen=self.BUFFER_SIZE)
        self._error_contexts: dict[str, list[str]] = {}  # pod → active error categories
        self._sim_start = datetime.utcnow()

    # ── Public API ────────────────────────────────────────────────────────────

    def generate_normal(self, pods: list[PodModel], n: int = 5) -> list[str]:
        """Generate n normal log lines for running pods."""
        lines = []
        for _ in range(n):
            pod = self._rng.choice(pods) if pods else None
            if not pod:
                continue
            app = pod.labels.get("app", "unknown")
            templates = _NORMAL_TEMPLATES.get(app, _NORMAL_TEMPLATES["api"])
            line = self._rng.choice(templates)
            line = self._interpolate(line, pod=pod)
            timestamped = f"[{self._sim_ts()}] {line}"
            self._buffer.append(timestamped)
            lines.append(timestamped)
        return lines

    def inject_error(
        self,
        pod: PodModel,
        error_category: str,
        count: int = 3,
    ) -> list[str]:
        """
        Inject error log lines for a specific error category.
        error_category: "oom", "connection_refused", "timeout", "auth_anomaly",
                        "disk_pressure", "crash_loop"
        """
        templates = _ERROR_TEMPLATES.get(error_category, [])
        if not templates:
            return []

        lines = []
        # Track active errors per pod for consistent log generation
        if pod.name not in self._error_contexts:
            self._error_contexts[pod.name] = []
        if error_category not in self._error_contexts[pod.name]:
            self._error_contexts[pod.name].append(error_category)

        for _ in range(count):
            line = self._rng.choice(templates)
            line = self._interpolate(line, pod=pod)
            timestamped = f"[{self._sim_ts()}] ERROR {line}"
            self._buffer.append(timestamped)
            lines.append(timestamped)
        return lines

    def inject_remediation(self, pod: PodModel) -> list[str]:
        """
        Inject remediation success log lines (called when incident resolved).
        Clears active error context for the pod.
        """
        self._error_contexts.pop(pod.name, None)
        lines = []
        line = self._rng.choice(_REMEDIATION_TEMPLATES)
        line = self._interpolate(line, pod=pod)
        timestamped = f"[{self._sim_ts()}] {line}"
        self._buffer.append(timestamped)
        lines.append(timestamped)
        return lines

    def generate_for_pod(self, pod: PodModel, n: int = 5) -> list[str]:
        """
        Generate log lines for a specific pod — mix of normal and error if active.
        """
        lines = []
        errors = self._error_contexts.get(pod.name, [])

        for _ in range(n):
            if errors and self._rng.random() < 0.7:
                # 70% error logs if incident active
                category = self._rng.choice(errors)
                new_lines = self.inject_error(pod, category, count=1)
                lines.extend(new_lines)
            else:
                new_lines = self.generate_normal([pod], n=1)
                lines.extend(new_lines)
        return lines

    def get_recent(self, n: int = 20, pod_filter: Optional[str] = None) -> list[str]:
        """Return n most recent log lines (optionally filtered by pod name)."""
        lines = list(self._buffer)
        if pod_filter:
            lines = [l for l in lines if pod_filter in l]
        return lines[-n:]

    def reset(self) -> None:
        self._buffer.clear()
        self._error_contexts.clear()
        self._sim_start = datetime.utcnow()

    # ── Internal ──────────────────────────────────────────────────────────────

    def _interpolate(self, template: str, pod: Optional[PodModel] = None) -> str:
        """Fill template placeholders with realistic values."""
        app = pod.labels.get("app", "app") if pod else "app"
        replacements = {
            "{pod}": pod.name if pod else "unknown-pod",
            "{app}": app,
            "{pid}": str(self._rng.randint(1000, 65000)),
            "{score}": str(self._rng.randint(100, 999)),
            "{ip}": f"10.0.{self._rng.randint(0,255)}.{self._rng.randint(1,254)}",
            "{ip2}": f"10.0.{self._rng.randint(0,255)}.{self._rng.randint(1,254)}",
            "{port}": str(self._rng.choice([5432, 6379, 8080, 3306, 27017])),
            "{n}": str(self._rng.randint(1, 254)),
            "{n2}": str(self._rng.randint(10, 99)),
            "{db}": self._rng.choice(["appdb", "userdb", "analytics"]),
            "{ts}": datetime.utcnow().strftime("%d/%b/%Y:%H:%M:%S +0000"),
        }
        result = template
        for k, v in replacements.items():
            result = result.replace(k, v)
        return result

    def _sim_ts(self) -> str:
        """Simulated timestamp for log lines."""
        jitter = timedelta(milliseconds=self._rng.randint(0, 999))
        return (datetime.utcnow() + jitter).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
