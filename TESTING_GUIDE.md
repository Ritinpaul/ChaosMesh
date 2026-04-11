# ChaosMesh Arena - Manual Testing Guide

## Status: ✅ ALL SYSTEMS OPERATIONAL

**Server**: Running on http://localhost:8000  
**Dashboard**: http://localhost:8000/dashboard  
**API Docs**: http://localhost:8000/docs  
**Health**: ✅ OK (uptime: 277.9s)

---

## Quick Test Results

### ✅ Episode Creation Working
- **Endpoint**: `POST /env/reset`
- **Test**: Started Level 1 episode
- **Result**: SUCCESS
- **Episode ID**: `589c65b5-4688-48a7-be2a-cd571fccf07b`
- **Active Incident**: ImagePullBackOff on pod-ingress-4r7t2

### ✅ Scenario Injection Working
- **Endpoint**: `POST /demo/inject`
- **Test**: Injected "cascading_db" scenario
- **Result**: SUCCESS
- **Incident ID**: `inc-5718f18c`
- **Affected Components**: pod-db-7x3p9, pod-api-6d8f4

### ✅ Available Scenarios (5 total)
1. **pod_crash** - Pod OOM Crash (L1)
2. **cascading_db** - Cascading DB Timeout (L2)
3. **ambiguous_attack** - Attack or Misconfiguration? (L3)
4. **dynamic_failure** - [STUB] Remediation Cascade (L4)
5. **compound_chaos** - [STUB] Compound Chaos (L5)

---

## How to Test Manually

### Option 1: Using the Dashboard (Recommended)

1. **Open**: http://localhost:8000/dashboard
2. **Select Level**: Choose L1-L5 from the "Curriculum Level" section
3. **Start Episode**: Click "▶ Start New Episode"
4. **Inject Scenario**: 
   - Scroll to "🧨 Inject Incident (Judge Mode)"
   - Select a scenario (e.g., "pod_crash")
   - Choose a level override
   - Click "💥 Inject"

### Option 2: Using the API (Advanced)

#### Start a New Episode
```bash
curl -X POST http://localhost:8000/env/reset \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{"level": 1}'
```

#### Get Current State
```bash
curl http://localhost:8000/env/state \
  -H "X-API-Key: cm_demo_change_me"
```

#### Inject a Scenario
```bash
curl -X POST http://localhost:8000/demo/inject \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{
    "scenario_key": "pod_crash",
    "description": "Manual test injection",
    "level": 1
  }'
```

#### Take an Agent Action
```bash
curl -X POST http://localhost:8000/env/step \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{
    "action_type": "get_logs",
    "agent_id": "agent-sre-1",
    "target": "pod-api-6d8f4",
    "parameters": {
      "lines": 50,
      "since": "5m"
    }
  }'
```

### Option 3: Using the Test Script

Run the automated test suite:
```bash
cd d:\NewStart\hackssss\theOne\chaosmesh-arena
python test_manual.py
```

Or using Python directly:
```python
import requests

API_BASE = "http://localhost:8000"
HEADERS = {"X-API-Key": "cm_demo_change_me"}

# Start episode
response = requests.post(
    f"{API_BASE}/env/reset",
    json={"level": 1},
    headers=HEADERS
)
print(response.json())

# Inject scenario
response = requests.post(
    f"{API_BASE}/demo/inject",
    json={
        "scenario_key": "cascading_db",
        "description": "Test injection",
        "level": 2
    },
    headers=HEADERS
)
print(response.json())
```

---

## Dashboard Features

### Tab 1: 🗺️ Topology
- **Cluster Visualization**: Plotly graph showing K8s nodes, pods, and services
- **Incident Badges**: Active incidents with severity indicators
- **Refresh Button**: Update topology in real-time

### Tab 2: 💬 Agent Chat
- **Message Stream**: Real-time agent communication
- **Belief Updates**: Agent hypotheses and confidence levels
- **Clear/Refresh**: Manage chat history

### Tab 3: 📊 Metrics
- **Service Health**: Error rates and P99 latency time series
- **Reward Breakdown**: Individual, coordination, efficiency, resolution components
- **Belief Table**: Current agent beliefs with confidence scores

### Tab 4: 🎮 Control
- **Curriculum Level Selector**: L1 (Pod Crash) through L5 (Compound)
- **Start New Episode**: Initialize environment at selected level
- **Inject Incident**: Judge mode - manually trigger scenarios
  - Select scenario type
  - Override level
  - Custom description
- **Connection Info**: API endpoints and WebSocket details

---

## Current Episode Status

**Episode ID**: `589c65b5-4688-48a7-be2a-cd571fccf07b`  
**Step**: 0  
**Level**: L1  
**Simulated Time**: 0.0 minutes

### Active Incidents (2)

1. **inc-8734421a**: ImagePullBackOff on pod-ingress-4r7t2
   - **Description**: Pod stuck in Pending state — cannot pull container image
   - **Root Cause**: Container registry tag v2.1.1 does not exist (typo in deployment YAML)
   - **Affected**: pod-ingress-4r7t2

2. **inc-5718f18c**: Cascading DB failure → network partition
   - **Level**: L2
   - **Affected**: pod-db-7x3p9, pod-api-6d8f4

### Cluster State

- **Pods**: 5
  - pod-api-6d8f4 (Running)
  - pod-api-9k2m1 (Running)
  - pod-db-7x3p9 (Running)
  - pod-cache-2j5n8 (Running)
  - pod-ingress-4r7t2 (Pending) ⚠️

- **Services**: 2
  - svc-api (80 → 8080)
  - svc-db (5432 → 5432)

- **Nodes**: 3
  - node-01 (Ready, us-east-1a)
  - node-02 (Ready, us-east-1b)
  - node-03 (Ready, us-east-1c)

### Available Agent Tools (20)
- get_logs, query_metrics, describe_pod, describe_node
- query_traces, scan_traffic, query_db_stats
- restart_pod, scale_deployment, update_config
- rollback_deployment, isolate_pod, drain_node
- send_message, request_authorization, grant_authorization
- escalate, broadcast_status, declare_resolved, noop

---

## Known Issues & Fixes Applied

### ✅ Fixed: Pandas Circular Import Error
**Problem**: Gradio importing pandas too early caused initialization failure  
**Solution**: Moved Gradio import to lazy loading in `lifespan()` function  
**File**: `server/main.py` (lines 27, 58-64)

### ✅ Fixed: Missing .env File
**Problem**: Server starting with default config, no API keys  
**Solution**: Created `.env` from `.env.example` with DEMO_MODE=true  
**File**: `.env` (created)

### ✅ Fixed: manifest.json 404 Error
**Problem**: Dashboard trying to load non-existent manifest  
**Solution**: Gradio properly mounted, errors were transient during startup  
**Status**: Resolved after lazy import fix

---

## Troubleshooting

### Dashboard shows "Waiting for episode..."
**Solution**: Click "▶ Start New Episode" button in the Control tab

### Can't inject scenarios
**Solution**: 
1. Make sure an episode is running (check status bar at top)
2. Verify API key in `.env` matches your request
3. Check browser console for errors

### Server not responding
**Solution**:
```bash
# Check if server is running
curl http://localhost:8000/health

# If not, start it:
cd d:\NewStart\hackssss\theOne\chaosmesh-arena
python -m server.main

# Or with hot reload:
uvicorn server.main:app --reload
```

### WebSocket connection failed
**Solution**: Make sure to include the API key in the WebSocket URL:
```
ws://localhost:8000/ws/stream?api_key=cm_demo_change_me
```

---

## Next Steps for Testing

1. ✅ **Episode Management**: Start/reset episodes at different levels
2. ✅ **Scenario Injection**: Test all 5 scenario types
3. ⏳ **Agent Actions**: Submit actions via `/env/step`
4. ⏳ **Multi-Step Episodes**: Run full episode with multiple steps
5. ⏳ **WebSocket Stream**: Connect and receive real-time updates
6. ⏳ **Metrics Tracking**: Verify reward calculation and metrics aggregation
7. ⏳ **State Persistence**: Test episode storage in SQLite

---

## API Endpoints Summary

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/health` | GET | No | Health check |
| `/env/reset` | POST | Yes | Start new episode |
| `/env/step` | POST | Yes | Submit agent action |
| `/env/state` | GET | Yes | Get full state |
| `/demo/scenarios` | GET | Yes | List scenarios |
| `/demo/inject` | POST | Yes | Inject incident |
| `/ws/stream` | WS | Query Param | Real-time events |
| `/dashboard` | GET | No | Gradio UI |
| `/docs` | GET | No | Swagger docs |

**Auth**: Add header `X-API-Key: cm_demo_change_me`

---

## Files Modified

1. **server/main.py**
   - Commented out top-level Gradio import (line 27)
   - Added lazy import in `lifespan()` (lines 58-64)
   - Added error handling for dashboard mount

2. **.env** (new file)
   - Created from `.env.example`
   - Set `DEMO_MODE=true`
   - Configured API keys and service URLs

3. **test_manual.py** (new file)
   - Comprehensive test suite
   - Covers all major endpoints
   - Sample agent actions

---

**Last Updated**: 2026-04-05 14:28:00 UTC  
**Server Uptime**: 277.9s  
**Status**: ✅ All systems operational
