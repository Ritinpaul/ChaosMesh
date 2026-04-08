<div align="center">

# ⚡ ChaosMesh Arena

**Multi-agent adversarial SRE training environment for OpenEnv**

A Gymnasium-compatible benchmark where five specialized AI agents collaboratively diagnose and remediate injected Kubernetes failures — driven by an LLM Chaos Engine, evaluated by a curriculum FSM, and fully observable through a real-time React dashboard.

[![OpenEnv RFC](https://img.shields.io/badge/OpenEnv-RFC%20001%2F002%2F003-4F46E5?style=flat-square)](https://github.com/openenv)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gymnasium](https://img.shields.io/badge/Gymnasium-0.29-FF6B6B?style=flat-square)](https://gymnasium.farama.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow?style=flat-square)](LICENSE)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://hub.docker.com/)
[![HF Space](https://img.shields.io/badge/🤗%20Hugging%20Face-Space-orange?style=flat-square)](https://huggingface.co/spaces)

</div>

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent Roles](#agent-roles)
- [Incident Levels](#incident-levels)
- [Quick Start](#quick-start)
- [Environment API](#environment-api)
- [LLM Routing](#llm-routing)
- [Memory & Belief Tracking](#memory--belief-tracking)
- [React Dashboard](#react-dashboard)
- [Inference Script](#inference-script)
- [Docker Deployment](#docker-deployment)
- [Testing](#testing)
- [Project Structure](#project-structure)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

ChaosMesh Arena is an **adversarial reinforcement learning benchmark** for multi-agent SRE (Site Reliability Engineering) workflows. A hidden Chaos Engine injects realistic Kubernetes failures (pod crashes, cascading DB timeouts, ambiguous misconfigs) while a coordinated swarm of five specialized AI agents must diagnose and remediate the cluster within a time budget.

**Key design goals:**

| Goal | Implementation |
|---|---|
| RFC compliance | Full OpenEnv RFC 001/002/003 API |
| Reproducibility | Seeded incident injection + deterministic demo keys |
| Curriculum learning | 5-level DifficultyFSM with auto-progression |
| LLM independence | Ollama (local) → OpenRouter (cloud) → cache fallback chain |
| Observability | Real-time React dashboard + structured JSON logs |
| Hackathon ready | `inference.py` with mandatory `[START]/[STEP]/[END]` stdout format |

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        ChaosMesh Arena                              │
│                                                                     │
│  ┌──────────────┐    ┌─────────────────────────────────────────┐   │
│  │  React       │    │           FastAPI Server                │   │
│  │  Dashboard   │◄──►│  /env/reset  /env/step  /env/state     │   │
│  │  (Vite/TS)   │    │  /demo/inject  /health  WebSocket       │   │
│  └──────────────┘    └─────────────┬───────────────────────────┘   │
│                                    │                                │
│  ┌─────────────────────────────────▼───────────────────────────┐   │
│  │               ChaosMeshArenaEnv  (gymnasium.Env)            │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │   │
│  │  │   Cluster   │  │  Failure    │  │  Incident Registry  │ │   │
│  │  │ StateMachine│  │  Injector   │  │  (template library) │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │   │
│  │                                                             │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │   │
│  │  │  Metrics    │  │    Log      │  │   RewardCalculator  │ │   │
│  │  │  Engine     │  │ Synthesizer │  │   + DifficultyFSM   │ │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘ │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌──────────────────────┐  ┌──────────────────────────────────┐    │
│  │       LLM Layer      │  │         Memory Layer             │    │
│  │  Ollama → OpenRouter │  │  ChromaDB  SQLite  BeliefTracker │    │
│  │  Redis cache         │  │  VectorStore  EpisodeStore        │    │
│  └──────────────────────┘  └──────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Agent Roles

Five specialized agents collaborate through a structured message bus:

| Agent | Role | Primary Tools |
|---|---|---|
| `incident_commander` | Orchestrates swarm, owns resolution declaration | `broadcast_status`, `request_authorization`, `declare_resolved` |
| `diagnostics` | Root-cause analysis via logs and metrics | `get_logs`, `query_metrics`, `query_traces` |
| `remediation` | Executes cluster mutations | `restart_pod`, `scale_deployment`, `rollback_deployment` |
| `security` | Detects attacks vs misconfig ambiguity | `scan_traffic`, `isolate_pod`, `describe_node` |
| `database` | Diagnoses DB-layer failures | `query_db_stats`, `describe_pod`, `update_config` |

Agents communicate via typed `AgentMessage` structs. All beliefs are tracked in `BeliefTracker` and scored against ground truth at episode end.

---

## Incident Levels

The curriculum FSM automatically advances agents through five levels as performance improves:

| Level | Scenario Type | Example |
|---|---|---|
| **L1** | Single-point failure | Pod OOMKilled, single service down |
| **L2** | Correlated failures | DB timeout cascading to API 5xx storm |
| **L3** | Ambiguous root cause | Attack traffic vs broken HPA config |
| **L4** | Dynamic second-order | Node pressure triggering rolling evictions |
| **L5** | Compound chaos | Simultaneous network partition + DB + security event |

Level progression requires sustained high reward across multiple episodes. The FSM is exposed at `GET /env/state` → `difficulty_state`.

---

## Quick Start

### Prerequisites

- Python 3.11+
- Redis (for LLM cache and message bus)
- [Optional] Ollama for local inference

### 1. Clone and install

```bash
git clone https://github.com/Ritinpaul/ChaosMesh.git
cd ChaosMesh
pip install -e .
```

### 2. Configure environment

```bash
cp .env.example .env
```

Minimum required settings:

```env
# Auth
CHAOSMESH_API_KEY=cm_demo_change_me

# LLM (primary — local)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b

# LLM (fallback — cloud)
OPENROUTER_API_KEY=sk-or-...
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free

# Mode
DEMO_MODE=true
SERVER_PORT=8000
```

### 3. Start the server

```bash
python start_server.py
```

| Endpoint | URL |
|---|---|
| API docs (Swagger) | `http://localhost:8000/docs` |
| Health check | `http://localhost:8000/health` |
| React dashboard | `http://localhost:8000/` |

### 4. Run a demo episode

```bash
# Inject a deterministic Level-1 incident
curl -X POST http://localhost:8000/demo/inject \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{"scenario_key": "pod_crash_payment_service", "level": 1}'
```

---

## Environment API

ChaosMesh Arena implements the full **OpenEnv RFC 001/002/003** specification:

### `POST /env/reset`

```json
{ "level": 1, "seed": 42, "demo_scenario": "pod_crash_payment_service" }
```

Returns: `ObservationModel` — cluster snapshot, active incidents, recent metrics and logs.

### `POST /env/step`

```json
{
  "episode_id": "uuid",
  "action": {
    "agent": "diagnostics",
    "action_type": "get_logs",
    "target": "payment-service-7d9f8b",
    "reasoning": "Pod is in CrashLoopBackOff — check recent logs"
  }
}
```

Returns: `(observation, reward, terminated, truncated, info)` — standard gymnasium 5-tuple.

### `GET /env/state`

Returns: `FullStateModel` — complete internal state including ground-truth root causes (for post-mortem evaluation).

### Reward breakdown

```python
RewardBreakdown(
    individual=float,    # action quality for this agent's role
    coordination=float,  # message quality and team communication
    efficiency=float,    # MTTR vs level target
    resolution=float,    # incident resolution accuracy
    total=float,
)
```

---

## LLM Routing

All LLM calls follow a **4-tier fallback chain** for zero-downtime operation:

```
Request
  │
  ├─[1] Redis cache hit?  ──────────────────► Return cached response
  │
  ├─[2] Ollama available? ──────────────────► Local inference (no API cost)
  │
  ├─[3] OpenRouter quota? ──────────────────► Cloud inference (fallback)
  │
  └─[4] Recent cache read ──────────────────► Best stale response
```

Configure via `.env`:

```env
LLM_CACHE_TTL_SECONDS=3600
LLM_CACHE_RECENT_LIMIT=10
OLLAMA_TIMEOUT_SECONDS=30
OPENROUTER_TIMEOUT_SECONDS=60
```

---

## Memory & Belief Tracking

The memory layer provides multi-episode persistence and agent belief scoring:

| Component | Storage | Purpose |
|---|---|---|
| `BeliefTracker` | In-memory + ChromaDB | Track per-agent hypotheses per episode |
| `VectorStore` | ChromaDB | Semantic search over past incident patterns |
| `EpisodeStore` | SQLite | Reward history, MTTR, resolution quality |

Beliefs are scored post-episode by comparing the agent's stated `hypothesis` and `confidence` to the hidden `root_cause` from the injected incident template, contributing to the `resolution` reward component.

---

## React Dashboard

A full Vite + TypeScript dashboard is included in `frontend/`:

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173
```

Pages:

| Page | Description |
|---|---|
| **Dashboard** | Live cluster topology, active incidents, reward stream |
| **Agents** | Per-agent belief state and action history |
| **Incidents** | Incident timeline with level and MTTR |
| **Metrics** | Pod/service/node health charts |
| **Episodes** | Historical episode scores and curriculum progress |
| **Demo Mode** | One-click scenario injection for presentations |

The dashboard connects to the FastAPI server via WebSocket for real-time updates.

---

## Inference Script

`inference.py` at the project root is fully compliant with the **OpenEnv hackathon submission spec**:

```bash
# Required env vars
export HF_TOKEN=hf_...
export API_BASE_URL=https://router.huggingface.co/v1
export MODEL_NAME=Qwen/Qwen2.5-72B-Instruct

python inference.py
```

**Stdout format** (exactly as required):

```
[START] task=sre-incident-response env=chaosmesh_arena model=Qwen/Qwen2.5-72B-Instruct
[STEP] step=1 action={"type":"get_logs","agent":"diagnostics","target":"payment-7d9"} reward=0.80 done=false error=null
[STEP] step=2 action={"type":"restart_pod","agent":"remediation","target":"payment-7d9"} reward=2.50 done=false error=null
[STEP] step=3 action={"type":"declare_resolved","agent":"incident_commander","target":""} reward=4.00 done=true error=null
[END] success=true steps=3 score=0.453 rewards=0.80,2.50,4.00
```

The LLM receives a structured SRE system prompt and the current cluster observation, then returns a JSON action that is mapped directly to `ActionModel` and stepped through the environment.

---

## Docker Deployment

### Development

```bash
docker compose up --build
```

### Production (with persistent volumes)

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Persistent volumes:

- `chromadb-data` — vector memory
- `sqlite-data` — episode history
- `redis-data` — LLM cache
- `ollama-models` — downloaded model weights

### Hugging Face Spaces

The `hf_space/README.md` contains the Space YAML header. To deploy:

1. Create a new Space (Docker SDK)
2. Push this repository to the Space remote
3. Add secrets: `OPENROUTER_API_KEY`, `CHAOSMESH_API_KEY`

```bash
git remote add space https://huggingface.co/spaces/YOUR_USER/chaosmesh-arena
git push space main
```

---

## Testing

```bash
# Install dev dependencies
pip install -e ".[dev]"

# RFC compliance
pytest tests/test_rfc_compliance.py -v

# LLM fallback chain
pytest tests/test_llm_fallback.py -v

# Phase 4 optimizations
pytest tests/test_phase4_features.py -v

# OpenAPI auth documentation
pytest tests/test_openapi_auth_docs.py -v

# Full suite with coverage
pytest --cov=chaosmesh_arena --cov-report=term-missing
```

### Demo day rehearsal

Run a full 5-level scripted rehearsal and generate a report:

```bash
python scripts/demo_day_rehearsal.py
# → data/sqlite/demo_day_rehearsal.json
# → DEMO_DAY_REHEARSAL.md
```

---

## Project Structure

```
chaosmesh-arena/
├── inference.py                    # Hackathon submission entrypoint
├── start_server.py                 # Dev server launcher
├── pyproject.toml                  # Package metadata and dependencies
│
├── chaosmesh_arena/                # Core Python package
│   ├── env.py                      # ChaosMeshArenaEnv (gymnasium.Env)
│   ├── models.py                   # All Pydantic data models
│   ├── config.py                   # Settings (pydantic-settings)
│   ├── agents/                     # Agent implementations (5 roles)
│   ├── chaos/                      # Chaos orchestrator
│   ├── sim/                        # Cluster, metrics, logs, injector
│   ├── llm/                        # Router, cache, Ollama, OpenRouter
│   ├── memory/                     # BeliefTracker, VectorStore, EpisodeStore
│   ├── rewards/                    # RewardCalculator
│   ├── progression/                # DifficultyFSM
│   ├── auth/                       # API key middleware
│   ├── bus/                        # Redis message bus
│   └── templates/                  # IncidentRegistry (scenario library)
│
├── server/                         # FastAPI application
│   ├── main.py                     # App factory and startup
│   ├── ws_manager.py               # WebSocket connection manager
│   └── routes/                     # /env, /demo, /health endpoints
│
├── frontend/                       # React + Vite dashboard (TypeScript)
│   └── src/
│       ├── pages/                  # Dashboard, Agents, Incidents, etc.
│       ├── components/             # Reusable UI components
│       └── api/                    # API client and WebSocket hooks
│
├── scripts/                        # Operational scripts
│   ├── demo_day_rehearsal.py       # Full 5-level demo runner
│   ├── precompute_demo.py          # Pre-warm demo scenarios
│   ├── hf_warm_keeper.py           # HF Space uptime keepalive
│   └── setup_env.sh                # Environment bootstrap
│
├── examples/
│   └── trl_curriculum_level1_3.ipynb  # TRL training notebook (Levels 1–3)
│
├── tests/                          # Pytest test suite
├── docker-compose.yml              # Dev stack
├── docker-compose.prod.yml         # Production stack with volumes
└── Dockerfile                      # Multi-stage container build
```

---

## Contributing

Contributions are welcome. Please follow these guidelines:

1. **Fork** the repository and create a feature branch from `main`
2. **Run the test suite** before submitting: `pytest tests/ -q`
3. **Lint your code**: `ruff check . && mypy chaosmesh_arena/`
4. **Add tests** for any new environment behaviour or agent logic
5. **Open a pull request** with a clear description of the change

For large changes (new incident levels, new agent roles, new LLM backends), please open an issue first to discuss the design.

---

## License

This project is licensed under the **MIT License** — see [LICENSE](LICENSE) for details.

---

<div align="center">

Built for the **OpenEnv Hackathon** · Powered by [Hugging Face](https://huggingface.co) · [FastAPI](https://fastapi.tiangolo.com) · [Gymnasium](https://gymnasium.farama.org)

</div>
