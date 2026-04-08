"""
ChaosMesh Arena — Incident Template Registry (Tasks 2.8–2.12)

Central registry mapping IncidentLevel → list of injectable incident templates.
Provides:
- Seeded random selection for reproducible episodes
- Rich metadata per template (difficulty, tags, expected agents)
- Extended L4/L5 seed templates with realistic compound/dynamic scenarios
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

import structlog

from chaosmesh_arena.models import IncidentLevel

if TYPE_CHECKING:
    from chaosmesh_arena.sim.failure_injector import FailureInjector, InjectionResult

log = structlog.get_logger(__name__)


@dataclass
class IncidentTemplate:
    """Metadata wrapper for an incident injection function."""
    name: str
    level: IncidentLevel
    description: str
    tags: list[str]                           # e.g. ["oom", "pod", "memory"]
    expected_agents: list[str]                # agents needed to resolve
    target_mttr_minutes: float                # expected resolution time
    inject_fn_name: str                       # name of method on FailureInjector
    inject_kwargs: dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# Level 1 — Single-Point Failures (5 templates, Task 2.8)
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_1_TEMPLATES: list[IncidentTemplate] = [
    IncidentTemplate(
        name="pod_oom_crash",
        level=IncidentLevel.LEVEL_1,
        description="Pod exceeds memory limits → OOMKilled → CrashLoopBackOff",
        tags=["oom", "pod", "memory", "crash"],
        expected_agents=["diagnostics", "remediation"],
        target_mttr_minutes=3.0,
        inject_fn_name="inject_pod_crash",
    ),
    IncidentTemplate(
        name="memory_leak_gradual",
        level=IncidentLevel.LEVEL_1,
        description="Slow memory leak — gradual climb toward OOM threshold",
        tags=["memory_leak", "pod", "memory", "gradual"],
        expected_agents=["diagnostics", "remediation"],
        target_mttr_minutes=5.0,
        inject_fn_name="inject_memory_leak",
    ),
    IncidentTemplate(
        name="service_network_timeout",
        level=IncidentLevel.LEVEL_1,
        description="Single service intermittent timeouts from upstream degradation",
        tags=["timeout", "network", "service", "latency"],
        expected_agents=["diagnostics"],
        target_mttr_minutes=4.0,
        inject_fn_name="inject_network_timeout",
    ),
    IncidentTemplate(
        name="node_disk_pressure",
        level=IncidentLevel.LEVEL_1,
        description="Node DiskPressure condition — log rotation failure fills /var/log",
        tags=["disk", "node", "pressure", "eviction"],
        expected_agents=["diagnostics", "remediation"],
        target_mttr_minutes=4.0,
        inject_fn_name="inject_disk_pressure",
    ),
    IncidentTemplate(
        name="image_pull_failure",
        level=IncidentLevel.LEVEL_1,
        description="Pod stuck in Pending — container image tag 404 in registry",
        tags=["image", "registry", "pending", "deployment"],
        expected_agents=["diagnostics"],
        target_mttr_minutes=2.0,
        inject_fn_name="inject_image_pull_failure",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Level 2 — Correlated Failures (3 templates, Task 2.9)
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_2_TEMPLATES: list[IncidentTemplate] = [
    IncidentTemplate(
        name="cascading_db_timeout",
        level=IncidentLevel.LEVEL_2,
        description="Network partition → DB unreachable → API cascade failure",
        tags=["network_partition", "db", "cascade", "api", "zone"],
        expected_agents=["diagnostics", "remediation", "database"],
        target_mttr_minutes=6.0,
        inject_fn_name="inject_cascading_db_timeout",
    ),
    IncidentTemplate(
        name="node_failure_cascade",
        level=IncidentLevel.LEVEL_2,
        description="Node goes NotReady → pods evicted → resource contention on survivor node",
        tags=["node_failure", "eviction", "rescheduling", "resource_contention"],
        expected_agents=["diagnostics", "remediation"],
        target_mttr_minutes=7.0,
        inject_fn_name="inject_node_failure_cascade",
    ),
    IncidentTemplate(
        name="rolling_restart_failure",
        level=IncidentLevel.LEVEL_2,
        description="Config update → CrashLoopBackOff → partial service outage",
        tags=["config", "rolling_restart", "crash_loop", "partial_outage"],
        expected_agents=["diagnostics", "remediation"],
        target_mttr_minutes=5.0,
        inject_fn_name="inject_rolling_restart_failure",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Level 3 — Ambiguous Scenarios (2 templates, Task 2.10)
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_3_TEMPLATES: list[IncidentTemplate] = [
    IncidentTemplate(
        name="attack_vs_misconfig",
        level=IncidentLevel.LEVEL_3,
        description="Auth anomalies that could be credential stuffing OR rate limiter misconfiguration",
        tags=["security", "ambiguous", "auth", "rate_limit", "attack", "misconfig"],
        expected_agents=["diagnostics", "security", "incident_commander"],
        target_mttr_minutes=8.0,
        inject_fn_name="inject_ambiguous_attack_vs_misconfig",
    ),
    IncidentTemplate(
        name="perf_degradation_ambiguous",
        level=IncidentLevel.LEVEL_3,
        description="P99 latency climbing — capacity issue vs. N+1 query code regression",
        tags=["performance", "ambiguous", "capacity", "n+1", "code_regression"],
        expected_agents=["diagnostics", "database", "incident_commander"],
        target_mttr_minutes=10.0,
        inject_fn_name="inject_performance_degradation_ambiguous",
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Level 4 — Dynamic Failures: Seed Templates (2 stubs, Task 2.11)
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_4_TEMPLATES: list[IncidentTemplate] = [
    IncidentTemplate(
        name="remediation_secondary_failure",
        level=IncidentLevel.LEVEL_4,
        description=(
            "[Seed] Restarting pod-api triggers OOM on pod-cache due to connection pool surge. "
            "Fix one thing, break another. Agents must anticipate second-order effects."
        ),
        tags=["dynamic", "second_order", "connection_pool", "oom", "cascade"],
        expected_agents=["diagnostics", "remediation", "database", "incident_commander"],
        target_mttr_minutes=12.0,
        inject_fn_name="inject_level4_dynamic_failure",
        inject_kwargs={"template": "remediation_secondary"},
    ),
    IncidentTemplate(
        name="autoscaling_loop",
        level=IncidentLevel.LEVEL_4,
        description=(
            "[Seed] HPA scaling event triggers resource contention on the node, "
            "which causes pods to OOM, which triggers more scaling, creating a loop. "
            "Standard restart/scale actions make the situation worse."
        ),
        tags=["dynamic", "autoscaling", "hpa", "resource_contention", "loop"],
        expected_agents=["diagnostics", "remediation", "incident_commander"],
        target_mttr_minutes=15.0,
        inject_fn_name="inject_level4_dynamic_failure",
        inject_kwargs={"template": "autoscaling_loop"},
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Level 5 — Compound Chaos: Seed Templates (2 stubs, Task 2.12)
# ═══════════════════════════════════════════════════════════════════════════════

LEVEL_5_TEMPLATES: list[IncidentTemplate] = [
    IncidentTemplate(
        name="db_lag_plus_gateway_saturation",
        level=IncidentLevel.LEVEL_5,
        description=(
            "[Seed] Simultaneous: DB replication lag (replica 2 min behind WAL) "
            "AND API gateway CPU saturated from unrelated load test hitting production. "
            "Agents must triage both independently and coordinate resolution order."
        ),
        tags=["compound", "db_replication", "gateway", "saturation", "multi_incident"],
        expected_agents=["diagnostics", "database", "security", "remediation", "incident_commander"],
        target_mttr_minutes=20.0,
        inject_fn_name="inject_level5_compound_chaos",
        inject_kwargs={"template": "db_plus_gateway"},
    ),
    IncidentTemplate(
        name="security_breach_plus_node_failure",
        level=IncidentLevel.LEVEL_5,
        description=(
            "[Seed] Active credential stuffing attack on auth service "
            "SIMULTANEOUSLY with node-01 hardware failure. "
            "Security team focuses on containment while ops team handles evacuation. "
            "Agents must split attention and avoid stepping on each other."
        ),
        tags=["compound", "security_breach", "node_failure", "simultaneous", "coordination"],
        expected_agents=["diagnostics", "security", "remediation", "incident_commander"],
        target_mttr_minutes=25.0,
        inject_fn_name="inject_level5_compound_chaos",
        inject_kwargs={"template": "security_plus_node"},
    ),
]

# ═══════════════════════════════════════════════════════════════════════════════
# Registry
# ═══════════════════════════════════════════════════════════════════════════════

_REGISTRY: dict[IncidentLevel, list[IncidentTemplate]] = {
    IncidentLevel.LEVEL_1: LEVEL_1_TEMPLATES,
    IncidentLevel.LEVEL_2: LEVEL_2_TEMPLATES,
    IncidentLevel.LEVEL_3: LEVEL_3_TEMPLATES,
    IncidentLevel.LEVEL_4: LEVEL_4_TEMPLATES,
    IncidentLevel.LEVEL_5: LEVEL_5_TEMPLATES,
}


class IncidentRegistry:
    """
    Central registry for incident templates across all difficulty levels.

    Provides deterministic (seeded) or random template selection.
    Wraps FailureInjector for clean injection calls.
    """

    def __init__(self, injector: "FailureInjector") -> None:
        self._injector = injector
        self._rng = random.Random()

    def seed(self, s: int) -> None:
        """Set the random seed for reproducible episode selection."""
        self._rng.seed(s)

    def select(
        self,
        level: IncidentLevel,
        template_name: Optional[str] = None,
    ) -> IncidentTemplate:
        """
        Select an incident template for the given level.

        Args:
            level: Difficulty level
            template_name: If provided, select this specific template by name.
                           Otherwise, select randomly.
        """
        templates = _REGISTRY.get(level, _REGISTRY[IncidentLevel.LEVEL_1])

        if template_name:
            for t in templates:
                if t.name == template_name:
                    return t
            log.warning("template_not_found", name=template_name, level=level)

        return self._rng.choice(templates)

    def inject(
        self,
        level: IncidentLevel,
        template_name: Optional[str] = None,
    ) -> "InjectionResult":
        """
        Select and inject an incident for the given level.
        Returns the InjectionResult from the FailureInjector.
        """
        template = self.select(level, template_name)

        inject_method = getattr(self._injector, template.inject_fn_name, None)
        if inject_method is None:
            log.error(
                "inject_method_not_found",
                method=template.inject_fn_name,
                template=template.name,
            )
            # Fallback to level 1 pod crash
            return self._injector.inject_pod_crash()

        result = inject_method(**template.inject_kwargs)
        log.info(
            "incident_injected",
            template=template.name,
            level=level.value,
            incident_id=result.incident.incident_id,
            target_mttr=template.target_mttr_minutes,
        )
        return result

    def list_templates(self, level: Optional[IncidentLevel] = None) -> list[IncidentTemplate]:
        """List all templates, optionally filtered by level."""
        if level is not None:
            return list(_REGISTRY.get(level, []))
        all_templates = []
        for templates in _REGISTRY.values():
            all_templates.extend(templates)
        return all_templates

    def get_template_metadata(self, level: IncidentLevel) -> list[dict]:
        """Return template metadata dicts suitable for API responses."""
        return [
            {
                "name": t.name,
                "level": t.level.value,
                "description": t.description,
                "tags": t.tags,
                "expected_agents": t.expected_agents,
                "target_mttr_minutes": t.target_mttr_minutes,
            }
            for t in _REGISTRY.get(level, [])
        ]
