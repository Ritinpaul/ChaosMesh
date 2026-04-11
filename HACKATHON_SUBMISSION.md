# Hackathon Submission Form

## 1) Project Information

- Project Name: ChaosMesh Arena
- Tagline: Multi-agent SRE training under realistic Kubernetes chaos scenarios.
- Team Name: TheOne
- Submission Date: 2026-04-05

## 2) Problem Statement

Modern incident response training is often static, shallow, and not reproducible. Teams need realistic, escalating, and measurable practice environments that mirror production pressure.

## 3) Solution Summary

ChaosMesh Arena is a curriculum-driven adversarial environment where multiple specialist agents collaborate to detect, triage, and remediate incidents from Level 1 to Level 5 complexity.

What it delivers:

- deterministic scenario injection for demos and benchmarking
- dual LLM execution path (local-first with cloud fallback)
- memory-backed belief tracking and resolution analytics
- RFC-compliant API surface for controlled training loops

## 4) Key Features

- Curriculum progression engine (Level 1 -> Level 5)
- Incident registry with difficulty-scoped templates
- FastAPI APIs with OpenAPI docs and API-key security
- Redis-backed LLM cache and fallback behavior
- ChromaDB-backed memory optimization
- React dashboard and demo tooling

## 5) Technical Stack

- Backend: FastAPI, Pydantic, Uvicorn
- Environment Core: custom gym-like simulation in Python
- LLM Layer: Ollama + OpenRouter with routing/fallback
- Data/State: Redis, SQLite, ChromaDB
- Frontend: React + Vite
- Deployment: Docker Compose

## 6) Innovation Highlights

- Multi-agent incident gameplay with measurable rewards and progression
- Deterministic scenario replay for fair evaluations
- Hybrid LLM architecture for resilience and cost/performance control
- Memory-aware incident reasoning loop (belief tracking + accuracy paths)

## 7) Demo Plan

A full five-level rehearsal is automated via:

- `python scripts/demo_day_rehearsal.py`

Artifacts generated:

- `data/sqlite/demo_day_rehearsal.json`
- `DEMO_DAY_REHEARSAL.md`

## 8) Setup Instructions

### Local

1. `pip install -e .`
2. `copy .env.example .env`
3. `python start_server.py`
4. Open `http://localhost:8000/docs`

### Production-like

1. `docker compose -f docker-compose.prod.yml up -d --build`

## 9) API and Docs

- Swagger: `http://localhost:8000/docs`
- OpenAPI JSON: `http://localhost:8000/openapi.json`
- Health: `http://localhost:8000/health`

## 10) What was completed in finalization phase

- TRL notebook for Levels 1-3
- Production Docker Compose with Chroma/SQLite persistent volumes and Ollama preload service
- OpenAPI auth documentation validation tests
- README and badges refresh
- Five-level demo rehearsal automation and report generation

## 11) Repository

- Repo Root: `chaosmesh-arena`
- Main README: `README.md`

## 12) Contact

- Primary Contact: [Add name/email]
- Team Members: [Add team list]

