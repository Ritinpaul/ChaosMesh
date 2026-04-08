"""Pre-submission validator for ChaosMesh Arena hackathon checklist.

Run:
    python scripts/pre_submission_validate.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def _fail(msg: str) -> None:
    print(f"[FAIL] {msg}")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check_required_files() -> list[str]:
    errs: list[str] = []
    required = [
        ROOT / "Dockerfile",
        ROOT / "inference.py",
        ROOT / "openenv.yaml",
        ROOT / "server" / "routes" / "openenv_compat.py",
        ROOT / "chaosmesh_arena" / "models.py",
    ]
    for p in required:
        if not p.exists():
            errs.append(f"Missing required file: {p.relative_to(ROOT)}")
    if not errs:
        _ok("Required files present")
    return errs


def check_inference_contract() -> list[str]:
    errs: list[str] = []
    path = ROOT / "inference.py"
    text = _read(path)

    required_snippets = [
        "from openai import OpenAI",
        "HF_TOKEN",
        "API_BASE_URL",
        "MODEL_NAME",
        "[START]",
        "[STEP]",
        "[END]",
    ]
    for needle in required_snippets:
        if needle not in text:
            errs.append(f"inference.py missing required token: {needle}")

    if "score = min(max(score, 0.0), 1.0)" not in text:
        errs.append("inference.py does not clamp score to [0,1]")

    if not errs:
        _ok("inference.py includes OpenAI client, env vars, and structured logs")
    return errs


def check_env_template() -> list[str]:
    errs: list[str] = []
    env_example = ROOT / ".env.example"
    text = _read(env_example)
    for var in ("API_BASE_URL", "MODEL_NAME", "HF_TOKEN"):
        if re.search(rf"^{re.escape(var)}=", text, flags=re.MULTILINE) is None:
            errs.append(f".env.example missing {var}")
    if not errs:
        _ok(".env.example defines API_BASE_URL, MODEL_NAME, HF_TOKEN")
    return errs


def check_openenv_manifest() -> list[str]:
    errs: list[str] = []
    text = _read(ROOT / "openenv.yaml")

    for route in ("path: /reset", "path: /step", "path: /state"):
        if route not in text:
            errs.append(f"openenv.yaml missing endpoint: {route}")

    for model_ref in (
        "chaosmesh_arena.models.ActionModel",
        "chaosmesh_arena.models.ObservationModel",
        "chaosmesh_arena.models.StepResult",
        "chaosmesh_arena.models.FullStateModel",
    ):
        if model_ref not in text:
            errs.append(f"openenv.yaml missing model reference: {model_ref}")

    task_count = len(re.findall(r"^\s*-\s+id:\s+", text, flags=re.MULTILINE))
    if task_count < 3:
        errs.append(f"openenv.yaml has only {task_count} tasks (<3)")

    if "min: 0.0" not in text or "max: 1.0" not in text:
        errs.append("openenv.yaml grader score range is not 0.0..1.0")

    if "max_runtime_minutes: 20" not in text:
        errs.append("openenv.yaml missing max_runtime_minutes: 20")

    if not errs:
        _ok("openenv.yaml covers endpoints, typed models, tasks>=3, grader range, runtime cap")
    return errs


def check_route_aliases() -> list[str]:
    errs: list[str] = []
    text = _read(ROOT / "server" / "routes" / "openenv_compat.py")
    required_aliases = [
        '@router.post("/reset"',
        '@router.post("/step"',
        '@router.get("/state"',
    ]
    for alias in required_aliases:
        if alias not in text:
            errs.append(f"Missing route alias in openenv_compat.py: {alias}")

    if "validator_compat" not in text:
        errs.append("openenv_compat.py is not configured for validator compatibility user")

    if not errs:
        _ok("OpenEnv compatibility routes present for reset/step/state")
    return errs


def main() -> int:
    print("== ChaosMesh Arena Pre-Submission Validation ==")
    checks = [
        check_required_files,
        check_inference_contract,
        check_env_template,
        check_openenv_manifest,
        check_route_aliases,
    ]

    errors: list[str] = []
    for fn in checks:
        errors.extend(fn())

    if errors:
        print("\nValidation failed:\n")
        for e in errors:
            _fail(e)
        return 1

    print("\nAll pre-submission checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
