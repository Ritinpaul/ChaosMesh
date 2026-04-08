#!/usr/bin/env python3
"""
Pre-compute Demo Scenarios (Task 4.3).

This script cycles through Level 1 to Level 5 incidents using the actual
FastAPI ChaosMesh Arena environment and agents, forcing the LLM responses
to be queried and stored directly into Redis. In a live Hackathon Demo,
if responses are cached, the LLM will fall back gracefully and render
insanely fast.
"""

import asyncio
import json
from pathlib import Path

import structlog

from chaosmesh_arena.agents.commander import CommanderAgent
from chaosmesh_arena.agents.database import DatabaseAgent
from chaosmesh_arena.agents.diagnostics import DiagnosticsAgent
from chaosmesh_arena.agents.remediation import RemediationAgent
from chaosmesh_arena.agents.security import SecurityAgent
from chaosmesh_arena.config import get_settings
from chaosmesh_arena.env import ChaosMeshArenaEnv
from chaosmesh_arena.llm.cache import LLMCache
from chaosmesh_arena.models import IncidentLevel
from chaosmesh_arena.llm.router import LLMRouter
from chaosmesh_arena.memory.vector_store import VectorStore

log = structlog.get_logger(__name__)

MANIFEST_PATH = Path("data/sqlite/precomputed_scenarios.json")


async def run_scenario(level: IncidentLevel, template_name: str) -> dict:
    log.info("start_precompute", level=level.value, template_name=template_name)

    env = ChaosMeshArenaEnv(level=level, demo_mode=True)
    obs, _ = env.reset(seed=1337 + level.value)
    # Force the exact scenario for deterministic demos.
    result = env._registry.inject(level, template_name=template_name)
    
    router = LLMRouter()
    vector = VectorStore()
    
    # Init swarm
    swarm = [
        DiagnosticsAgent(router, vector, obs.episode_id),
        CommanderAgent(router, vector, obs.episode_id),
        SecurityAgent(router, vector, obs.episode_id),
        DatabaseAgent(router, vector, obs.episode_id),
        RemediationAgent(router, vector, obs.episode_id),
    ]

    for step in range(3):
        # We just act a few times to fill cache
        obs_copy = env._build_observation()
        # Have diagnostics and commander act sequentially to fill logical branches
        for agent in swarm[:2]:
            log.info("agent_acting", role=agent.role.value, step=step)
            action = await agent.act(obs_copy)
            env.step(action)

    log.info(
        "precompute_success",
        level=level.value,
        incident_id=result.incident.incident_id,
    )
    return {
        "level": level.value,
        "scenario_key": template_name,
        "incident_id": result.incident.incident_id,
        "title": result.incident.title,
        "description": result.incident.description,
    }


def _pick_one_per_level(env: ChaosMeshArenaEnv) -> dict[IncidentLevel, str]:
    picks: dict[IncidentLevel, str] = {}
    for lvl in IncidentLevel:
        templates = env._registry.list_templates(lvl)
        if not templates:
            continue
        picks[lvl] = templates[0].name
    return picks


async def main():
    _ = get_settings()
    cache = LLMCache()
    await cache.flush()

    selector_env = ChaosMeshArenaEnv(level=IncidentLevel.LEVEL_1, demo_mode=True)
    picks = _pick_one_per_level(selector_env)

    log.info("precomputing_cache", levels=len(picks))
    manifest_rows: list[dict] = []

    for lvl, template_name in picks.items():
        try:
            row = await run_scenario(lvl, template_name)
            manifest_rows.append(row)
        except Exception as e:
            log.error("precompute_failed", level=lvl.value, error=str(e))

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(
            {
                "generated_count": len(manifest_rows),
                "scenarios": manifest_rows,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    log.info("all_scenarios_cached_successfully")


if __name__ == "__main__":
    asyncio.run(main())
