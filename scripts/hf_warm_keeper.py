#!/usr/bin/env python3
"""
HF Space warm-keeper (Phase 4.4).

Pings key endpoints periodically to reduce cold starts on free-tier Spaces.
Usage:
  python scripts/hf_warm_keeper.py --once
  python scripts/hf_warm_keeper.py --loop

Environment:
  HF_SPACE_BASE_URL=https://<user>-<space>.hf.space
  CHAOSMESH_API_KEY=cm_demo_change_me
  HF_WARM_KEEPER_INTERVAL_SECONDS=240
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import datetime, timezone

import httpx


def _base_url() -> str:
    return os.getenv("HF_SPACE_BASE_URL", "").rstrip("/")


def _headers() -> dict[str, str]:
    return {"X-API-Key": os.getenv("CHAOSMESH_API_KEY", "cm_demo_change_me")}


async def _ping_once() -> None:
    base = _base_url()
    if not base:
        raise RuntimeError("HF_SPACE_BASE_URL is required")

    urls = [
        f"{base}/health",
        f"{base}/demo/scenarios",
    ]

    async with httpx.AsyncClient(timeout=15.0) as client:
        for url in urls:
            try:
                response = await client.get(url, headers=_headers())
                print(
                    f"[{datetime.now(timezone.utc).isoformat()}] {url} -> "
                    f"{response.status_code}"
                )
            except Exception as exc:
                print(f"[{datetime.now(timezone.utc).isoformat()}] {url} -> ERROR: {exc}")


async def _run_loop() -> None:
    interval = int(os.getenv("HF_WARM_KEEPER_INTERVAL_SECONDS", "240"))
    while True:
        await _ping_once()
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Keep HF Space warm by periodic endpoint pings")
    parser.add_argument("--once", action="store_true", help="Run one warm-up cycle and exit")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    args = parser.parse_args()

    if args.once:
        asyncio.run(_ping_once())
        return

    if args.loop:
        asyncio.run(_run_loop())
        return

    parser.error("Choose --once or --loop")


if __name__ == "__main__":
    main()
