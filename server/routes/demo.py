"""
ChaosMesh Arena — Demo Routes.

POST /demo/inject — Manually inject a scenario for judges
GET  /demo/scenarios — List available pre-built scenarios
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from chaosmesh_arena.auth.middleware import require_api_key
from chaosmesh_arena.models import IncidentLevel, InjectRequest
from chaosmesh_arena.templates.incident_registry import IncidentRegistry
from server.routes.env import get_env
from server.ws_manager import ws_manager

router = APIRouter(prefix="/demo", tags=["demo"])
_PRECOMPUTED_MANIFEST = Path("data/sqlite/precomputed_scenarios.json")


def _scenario_catalog() -> dict[str, dict]:
    """Return deterministic demo scenarios (one recommended per level + full list metadata)."""
    env = get_env()
    registry = getattr(env, "_registry", None)
    if registry is None:
        registry = IncidentRegistry(env._injector)

    catalog: dict[str, dict] = {}
    recommended: dict[str, dict] = {}

    for level in IncidentLevel:
        templates = registry.list_templates(level)
        if not templates:
            continue

        for t in templates:
            catalog[t.name] = {
                "name": t.name,
                "description": t.description,
                "level": t.level.value,
                "tags": t.tags,
                "expected_agents": t.expected_agents,
                "target_mttr_minutes": t.target_mttr_minutes,
            }

        # One pre-selected scenario per level (deterministic first template)
        first = templates[0]
        recommended[f"level_{level.value}"] = {
            "scenario_key": first.name,
            "name": first.name,
            "description": first.description,
            "level": first.level.value,
        }

    # Backward compatible flat map expected by existing tests/UI.
    flat = {
        item["scenario_key"]: {
            "name": item["name"],
            "description": item["description"],
            "level": item["level"],
        }
        for item in recommended.values()
    }

    return {
        "recommended": recommended,
        "all": catalog,
        "flat": flat,
    }


@router.post(
    "/inject",
    summary="Manually inject a scenario (for judges)",
    dependencies=[Depends(require_api_key)],
)
async def inject_scenario(request: InjectRequest) -> dict:
    """
    Inject a custom or pre-built incident scenario.
    The description is used to match the best template.
    """
    env = get_env()
    if not env._episode_id:
        raise HTTPException(status_code=400, detail="No active episode. Call /env/reset first.")

    # Deterministic path: scenario_key maps directly to template name in registry.
    if request.scenario_key:
        result = env._registry.inject(request.level, template_name=request.scenario_key)
    else:
        # Backward-compatible path: infer by description keywords.
        desc_lower = request.description.lower()
        if any(k in desc_lower for k in ["oom", "crash", "memory", "kill"]):
            result = env._injector.inject_pod_crash()
        elif any(k in desc_lower for k in ["db", "database", "cascade", "partition", "network"]):
            result = env._injector.inject_cascading_db_timeout()
        elif any(k in desc_lower for k in ["attack", "security", "auth", "credential", "dns"]):
            result = env._injector.inject_ambiguous_attack_vs_misconfig()
        elif any(k in desc_lower for k in ["disk", "space", "storage"]):
            result = env._injector.inject_disk_pressure()
        elif any(k in desc_lower for k in ["timeout", "slow", "latency"]):
            result = env._injector.inject_network_timeout()
        elif request.level == IncidentLevel.LEVEL_4:
            result = env._injector.inject_level4_dynamic_failure()
        elif request.level == IncidentLevel.LEVEL_5:
            result = env._injector.inject_level5_compound_chaos()
        else:
            result = env._injector.inject_pod_crash()

    await ws_manager.broadcast("incident_injected", {
        "incident_id": result.incident.incident_id,
        "title": result.incident.title,
        "level": result.incident.level.value,
        "affected_components": result.incident.affected_components,
        "description": result.incident.description,
    })

    return {
        "success": True,
        "incident_id": result.incident.incident_id,
        "title": result.incident.title,
        "level": result.incident.level.value,
        "affected_pods": result.affected_pods,
        "affected_services": result.affected_services,
        "initial_logs": result.initial_logs[:5],
    }


@router.get(
    "/scenarios",
    summary="List available demo scenarios",
    dependencies=[Depends(require_api_key)],
)
async def list_scenarios() -> dict:
    """Return all pre-built scenarios available for judge injection."""
    catalog = _scenario_catalog()
    return {
        "scenarios": catalog["flat"],
        "recommended": catalog["recommended"],
        "all_scenarios": catalog["all"],
    }


@router.get(
    "/precomputed",
    summary="Get precomputed scenario manifest",
    dependencies=[Depends(require_api_key)],
)
async def precomputed_manifest() -> dict:
    if not _PRECOMPUTED_MANIFEST.exists():
        return {"available": False, "message": "Run scripts/precompute_demo.py first."}
    try:
        data = json.loads(_PRECOMPUTED_MANIFEST.read_text(encoding="utf-8"))
        return {"available": True, "manifest": data}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to read manifest: {exc}")
