"""Run five full demo rehearsals (levels 1-5) and write a report.

Usage:
    python scripts/demo_day_rehearsal.py
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from chaosmesh_arena.config import get_settings
from server.main import app

OUTPUT_JSON = Path("data/sqlite/demo_day_rehearsal.json")
OUTPUT_MD = Path("DEMO_DAY_REHEARSAL.md")


def _count_unhealthy_pods(observation: dict[str, Any]) -> int:
    pods = observation.get("cluster_state", {}).get("pods", {})
    return sum(1 for pod in pods.values() if not pod.get("ready", True))


def _run_single_level(client: TestClient, headers: dict[str, str], level: int, max_steps: int = 25) -> dict[str, Any]:
    reset_resp = client.post("/env/reset", json={"level": level}, headers=headers)
    reset_resp.raise_for_status()

    payload = reset_resp.json()
    episode_id = payload["episode_id"]
    observation = payload["observation"]
    initial_unhealthy = _count_unhealthy_pods(observation)

    last_result: dict[str, Any] | None = None
    for _ in range(max_steps):
        step_resp = client.post(
            "/env/step",
            json={
                "episode_id": episode_id,
                "action": {
                    "agent": "diagnostics",
                    "action_type": "query_metrics",
                    "target": "svc-api",
                },
            },
            headers=headers,
        )
        step_resp.raise_for_status()
        last_result = step_resp.json()
        if last_result["terminated"] or last_result["truncated"]:
            break

    state_resp = client.get("/env/state", headers=headers)
    state_resp.raise_for_status()
    state = state_resp.json()

    final_observation = last_result["observation"] if last_result else observation
    final_unhealthy = _count_unhealthy_pods(final_observation)

    return {
        "level": level,
        "episode_id": episode_id,
        "steps": state["step"],
        "episode_status": state["episode_status"],
        "terminated": bool(last_result and last_result["terminated"]),
        "truncated": bool(last_result and last_result["truncated"]),
        "cumulative_reward": state["cumulative_reward"],
        "active_incidents": len(state["active_incidents"]),
        "initial_unhealthy_pods": initial_unhealthy,
        "final_unhealthy_pods": final_unhealthy,
    }


def _write_markdown(results: list[dict[str, Any]]) -> None:
    lines = [
        "# Demo Day Rehearsal Report",
        "",
        f"Generated: {datetime.now(timezone.utc).isoformat()}",
        "",
        "## Run Summary",
        "",
        "| Level | Episode ID | Steps | Status | Terminated | Truncated | Reward | Active Incidents | Initial Unhealthy Pods | Final Unhealthy Pods |",
        "|---|---|---:|---|---|---|---:|---:|---:|---:|",
    ]

    for row in results:
        lines.append(
            "| {level} | {episode_id} | {steps} | {episode_status} | {terminated} | {truncated} | {cumulative_reward:.3f} | {active_incidents} | {initial_unhealthy_pods} | {final_unhealthy_pods} |".format(**row)
        )

    completed = sum(1 for r in results if r["terminated"] or r["truncated"])
    lines.extend(
        [
            "",
            "## Acceptance Check",
            "",
            f"- Total runs: {len(results)}",
            f"- Completed runs (terminated or truncated): {completed}/{len(results)}",
            f"- Levels covered: {', '.join(str(r['level']) for r in results)}",
        ]
    )

    OUTPUT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    settings = get_settings()
    headers = {"X-API-Key": settings.chaosmesh_api_key}

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, Any]] = []
    with TestClient(app) as client:
        for level in range(1, 6):
            results.append(_run_single_level(client, headers, level))

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "results": results,
    }
    OUTPUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    _write_markdown(results)

    print(f"Wrote {OUTPUT_JSON}")
    print(f"Wrote {OUTPUT_MD}")


if __name__ == "__main__":
    main()
