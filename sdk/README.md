# chaosmesh-sdk

Python SDK for the **ChaosMesh Arena** — a multi-agent adversarial SRE training environment.

## Install

```bash
pip install chaosmesh-sdk           # Core (sync + async HTTP client)
pip install "chaosmesh-sdk[gym]"    # + Gymnasium env wrapper for RL
```

## Quickstart

### 1. Register and get an API key

```bash
curl -X POST http://localhost:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "you@example.com"}'
# → {"api_key": "cm_live_..."}  ← Save this!
```

### 2. Run an episode (sync)

```python
from chaosmesh_sdk import ChaosMeshClient, Episode

client = ChaosMeshClient(api_key="cm_live_...")

with client.episode(level=1) as ep:
    while not ep.done:
        # Build your action (see action schema below)
        action = {
            "agent": "incident_commander",
            "action_type": "diagnose",
            "target": "payment-svc",
            "parameters": {},
            "reasoning": "Checking pod status",
        }
        result = ep.step(action)
        print(f"Step {ep.step_count}: reward={result.reward.total:.3f}")

print(f"Episode complete! Score: {ep.score:.3f}")
```

> **Note:** `client.episode()` is a convenience factory that returns an `Episode` context manager.

### 3. Run with Gymnasium / Stable-Baselines3

```python
from chaosmesh_sdk import ChaosMeshGymEnv
from stable_baselines3 import PPO

env = ChaosMeshGymEnv(api_key="cm_live_...", level=1)

model = PPO("MlpPolicy", env, verbose=1)
model.learn(total_timesteps=10_000)

obs, info = env.reset()
for _ in range(50):
    action, _ = model.predict(obs)
    obs, reward, terminated, truncated, info = env.step(action)
    if terminated or truncated:
        break
```

### 4. Async usage

```python
import asyncio
from chaosmesh_sdk import ChaosMeshClient

async def main():
    async with ChaosMeshClient(api_key="cm_live_...") as client:
        obs, info = await client.async_reset(level=2)
        episode_id = info["episode_id"]
        result = await client.async_step(episode_id, {
            "agent": "diagnostician",
            "action_type": "collect_logs",
            "target": "auth-service",
        })
        print(f"Reward: {result.reward.total}")

asyncio.run(main())
```

## Action Schema

```python
{
    "agent": "incident_commander" | "diagnostician" | "remediator" | "security_analyst",
    "action_type": "diagnose" | "scale_up" | "rollback" | "forward_traffic" | ...,
    "target": "<kubernetes-resource-name>",   # e.g. "payment-svc"
    "parameters": {"replicas": 3},            # optional
    "reasoning": "Why this action?",          # shown in post-mortem report
}
```

## API Reference

| Method | Description |
|---|---|
| `client.reset(level=1)` | Start new episode |
| `client.step(episode_id, action)` | Submit action → `StepResult` |
| `client.get_leaderboard(level, period)` | Get rankings |
| `client.list_episodes(limit)` | Your episode history |
| `client.get_profile()` | Your account info |
| `client.health()` | Server health check |

See the full [API docs](https://chaosmesh.io/docs/sdk).

## License

MIT — see [LICENSE](../LICENSE)
