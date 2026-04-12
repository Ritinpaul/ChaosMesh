"""
ChaosMesh Arena — Hackathon Inference Script
============================================

Follows the mandatory submission specification exactly:
  - OpenAI client for all LLM calls
  - [START] / [STEP] / [END] stdout format
  - Score normalised to [0, 1]
  - HF_TOKEN has NO default (required env var)
  - API_BASE_URL and MODEL_NAME have safe defaults
"""

from __future__ import annotations

import json
import os
import textwrap
import traceback
from typing import List, Optional

from openai import OpenAI

# ── Mandatory env vars (spec §1) ───────────────────────────────────────────────
API_KEY = os.getenv("HF_TOKEN")  # NO default — must be supplied externally
API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "Qwen/Qwen2.5-72B-Instruct")

# ── Episode config ─────────────────────────────────────────────────────────────
TASK_NAME = os.getenv("CHAOSMESH_TASK", "sre-pod-crashloop")
BENCHMARK = os.getenv("CHAOSMESH_BENCHMARK", "chaosmesh_arena")
MAX_STEPS = int(os.getenv("MAX_STEPS", "8"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.7"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "512"))
SUCCESS_SCORE_THRESHOLD = 0.1  # score ∈ [0, 1]

# Map task_id → incident level (multi-task evaluator support)
TASK_LEVEL_MAP = {
    "sre-pod-crashloop": 1,
    "sre-db-timeout": 2,
    "sre-high-latency": 2,
    "sre-node-pressure": 3,
    "sre-security-anomaly": 3,
    "sre-compound-chaos": 5,
    # Legacy task IDs (backward-compat)
    "level-1-pod-failure": 1,
    "level_1_pod_failure": 1,
    "level-2-cascading-failure": 2,
    "level_2_cascading_failure": 2,
    "level-3-ambiguous-root-cause": 3,
    "level_3_ambiguous_root_cause": 3,
}

# Maximum possible reward per episode (used for normalisation)
# RewardCalculator gives up to +5 per step for a perfect response
_MAX_REWARD_PER_STEP = 5.0
MAX_TOTAL_REWARD = MAX_STEPS * _MAX_REWARD_PER_STEP



# ── Logging helpers (MANDATORY stdout format) ──────────────────────────────────

def log_start(task: str, env: str, model: str) -> None:
    print(f"[START] task={task} env={env} model={model}", flush=True)


def log_step(step: int, action: str, reward: float, done: bool, error: Optional[str]) -> None:
    error_val = error if error else "null"
    done_val = str(done).lower()
    # action must be single-line — strip newlines
    action_safe = action.replace("\n", " ").replace("\r", "")[:200]
    print(
        f"[STEP] step={step} action={action_safe} "
        f"reward={reward:.2f} done={done_val} error={error_val}",
        flush=True,
    )


def log_end(success: bool, steps: int, score: float, rewards: List[float]) -> None:
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(
        f"[END] success={str(success).lower()} steps={steps} "
        f"score={score:.3f} rewards={rewards_str}",
        flush=True,
    )


# ── System prompt for the SRE commander ───────────────────────────────────────

SYSTEM_PROMPT = textwrap.dedent("""
    You are an expert Site Reliability Engineer (SRE) incident commander.

    You are operating inside ChaosMesh Arena: a simulated Kubernetes cluster
    experiencing one or more injected failures.  Each turn you receive an
    observation JSON describing:
      - active_incidents: list of incidents with title, description, symptoms
      - cluster_state: pods (with phases/readiness), services (error rates,
        latency), nodes (conditions)
      - recent_logs: last 20 log lines from the cluster
      - recent_metrics: key Prometheus-style metrics

    Your job is to decide the single best action to diagnose or remediate the
    incident.  Respond with a JSON object on ONE line (no markdown, no newlines):

    {"action_type": "<type>", "agent": "<role>", "target": "<name>", "reasoning": "<why>"}

    action_type must be one of:
      get_logs | query_metrics | describe_pod | describe_node | query_traces |
      scan_traffic | query_db_stats | restart_pod | scale_deployment |
      update_config | rollback_deployment | isolate_pod | drain_node |
      send_message | declare_resolved | noop

    agent must be one of:
      incident_commander | diagnostics | remediation | security | database

    target: the specific pod / service / node name (empty string if not applicable).
    reasoning: concise explanation (≤ 80 chars).

    Priority: resolve ALL active incidents within the step budget.
    When all incidents are resolved, use action_type=declare_resolved.
""").strip()


def _obs_to_prompt(obs_dict: dict, step: int, last_reward: float, history: List[str]) -> str:
    """Build a concise user prompt from the raw observation dict."""
    incidents = obs_dict.get("active_incidents", [])
    cluster = obs_dict.get("cluster_state", {})
    logs = obs_dict.get("recent_logs", [])[-5:]
    metrics = obs_dict.get("recent_metrics", [])[:6]

    incident_summary = json.dumps(
        [{"title": i.get("title"), "symptoms": i.get("symptoms", [])[:3]} for i in incidents],
        separators=(",", ":"),
    )
    pod_summary = {
        k: {"phase": v.get("phase"), "ready": v.get("ready")}
        for k, v in list(cluster.get("pods", {}).items())[:8]
    }
    history_block = "\n".join(history[-4:]) if history else "None"

    return textwrap.dedent(f"""
        Step {step} | Last reward: {last_reward:.2f}

        Active incidents: {incident_summary}
        Pods (sample): {json.dumps(pod_summary, separators=(',', ':'))}
        Recent logs: {json.dumps(logs, separators=(',', ':'))}
        Metrics: {json.dumps(metrics, separators=(',', ':'))}

        Previous actions:
        {history_block}

        Reply with ONE JSON line (action_type, agent, target, reasoning).
    """).strip()


def _get_llm_action(client: OpenAI, step: int, obs_dict: dict, last_reward: float, history: List[str]) -> dict:
    """Call the LLM and parse its JSON action response.  Falls back to safe noop."""
    user_prompt = _obs_to_prompt(obs_dict, step, last_reward, history)
    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            stream=False,
        )
        raw = (completion.choices[0].message.content or "").strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as exc:
        print(f"[DEBUG] LLM call failed: {exc}", flush=True)
        return {"action_type": "noop", "agent": "incident_commander", "target": "", "reasoning": "fallback"}


def main() -> None:
    """
    Main episode loop — fully synchronous since ChaosMeshArenaEnv is gymnasium-based
    (no async needed).
    """
    from chaosmesh_arena.env import ChaosMeshArenaEnv
    from chaosmesh_arena.models import ActionModel, ActionType, AgentRole, IncidentLevel

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Determine incident level from task_id (multi-task evaluator support)
    level_int = TASK_LEVEL_MAP.get(TASK_NAME, 1)
    env = ChaosMeshArenaEnv(level=IncidentLevel(level_int), demo_mode=True)

    history: List[str] = []
    rewards: List[float] = []
    steps_taken = 0
    score = 0.0
    success = False

    log_start(task=TASK_NAME, env=BENCHMARK, model=MODEL_NAME)

    try:
        obs, _info = env.reset(options={"level": level_int})
        obs_dict = obs.model_dump(mode="json")
        last_reward = 0.0

        for step in range(1, MAX_STEPS + 1):
            # ── Ask LLM for next action ────────────────────────────────────────
            raw_action = _get_llm_action(client, step, obs_dict, last_reward, history)

            # ── Map LLM output → ActionModel ───────────────────────────────────
            try:
                action_type = ActionType(raw_action.get("action_type", "noop"))
            except ValueError:
                action_type = ActionType.NOOP

            try:
                agent_role = AgentRole(raw_action.get("agent", "incident_commander"))
            except ValueError:
                agent_role = AgentRole.INCIDENT_COMMANDER

            action = ActionModel(
                agent=agent_role,
                action_type=action_type,
                target=str(raw_action.get("target", "")),
                reasoning=str(raw_action.get("reasoning", ""))[:200],
            )

            # ── Step environment ───────────────────────────────────────────────
            error_msg: Optional[str] = None
            try:
                obs, reward_obj, terminated, truncated, info = env.step(action)
                reward = float(reward_obj.total) if hasattr(reward_obj, "total") else float(reward_obj)
                done = terminated or truncated
                obs_dict = obs.model_dump(mode="json")
            except Exception as exc:
                error_msg = str(exc)[:120]
                reward = 0.0
                done = False
                print(f"[DEBUG] env.step error: {exc}", flush=True)

            rewards.append(reward)
            steps_taken = step
            last_reward = reward

            # Action string for the log line — compact JSON
            action_str = json.dumps({
                "type": action_type.value,
                "agent": agent_role.value,
                "target": action.target,
            }, separators=(",", ":"))

            log_step(step=step, action=action_str, reward=reward, done=done, error=error_msg)

            history.append(
                f"Step {step}: {action_type.value}({action.target}) → reward {reward:+.2f}"
            )

            if done:
                break

        # ── Compute normalised score ───────────────────────────────────────────
        total_reward = sum(rewards)
        score = total_reward / MAX_TOTAL_REWARD if MAX_TOTAL_REWARD > 0 else 0.0
        if score != score:  # NaN-safe guard
            score = 0.0
        score = min(max(score, 0.0), 1.0)   # clamp to [0, 1]
        success = score >= SUCCESS_SCORE_THRESHOLD

    except Exception:
        print(f"[DEBUG] Episode exception:\n{traceback.format_exc()}", flush=True)

    finally:
        try:
            env.close()
        except Exception as exc:
            print(f"[DEBUG] env.close() error: {exc}", flush=True)

        log_end(success=success, steps=steps_taken, score=score, rewards=rewards)


if __name__ == "__main__":
    main()
