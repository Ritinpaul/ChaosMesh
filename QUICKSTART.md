# 🚀 ChaosMesh Arena - Quick Start

## ✅ System Status
- **Server**: RUNNING on http://localhost:8000
- **Dashboard**: http://localhost:8000/dashboard  
- **Health**: OK (tested and verified)

---

## 🎮 Manual Testing - Quick Commands

### Start a New Episode (via Dashboard)
1. Open: http://localhost:8000/dashboard
2. Go to "Control" tab (🎮)
3. Select level (L1-L5)
4. Click "▶ Start New Episode"

### Inject a Scenario
1. In "Control" tab, scroll to "🧨 Inject Incident"
2. Choose scenario: `pod_crash`, `cascading_db`, `ambiguous_attack`, etc.
3. Set level override (1-5)
4. Click "💥 Inject"

### Via Python (Quick Test)
```python
import requests

API = "http://localhost:8000"
KEY = {"X-API-Key": "cm_demo_change_me"}

# Start episode
r = requests.post(f"{API}/env/reset", json={"level": 1}, headers=KEY)
print(f"Episode: {r.json()['episode_id']}")

# Inject scenario
r = requests.post(f"{API}/demo/inject", 
    json={"scenario_key": "pod_crash", "level": 1}, headers=KEY)
print(f"Incident: {r.json()['incident_id']}")

# Check state
r = requests.get(f"{API}/env/state", headers=KEY)
print(f"Active incidents: {len(r.json()['active_incidents'])}")
```

### Via curl
```bash
# Health check
curl http://localhost:8000/health

# Start episode
curl -X POST http://localhost:8000/env/reset \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{"level": 1}'

# Inject scenario
curl -X POST http://localhost:8000/demo/inject \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{"scenario_key": "cascading_db", "level": 2}'
```

---

## 📊 Current Episode Info

**Episode ID**: `589c65b5-4688-48a7-be2a-cd571fccf07b`  
**Level**: L1  
**Active Incidents**: 2

1. **ImagePullBackOff** on pod-ingress-4r7t2
2. **Cascading DB failure** (pod-db-7x3p9, pod-api-6d8f4)

**Available Scenarios**:
- `pod_crash` (L1) - Pod OOM crash
- `cascading_db` (L2) - Network partition → DB timeout
- `ambiguous_attack` (L3) - Attack vs misconfiguration
- `dynamic_failure` (L4) - Remediation cascade [STUB]
- `compound_chaos` (L5) - Multiple simultaneous failures [STUB]

---

## 🔧 Fixes Applied

1. ✅ **Pandas import error** - Fixed via lazy Gradio import
2. ✅ **Missing .env** - Created from template
3. ✅ **Connection errors** - Server now properly mounted

---

## 📖 Documentation

- **Full Guide**: `TESTING_GUIDE.md`
- **Test Script**: `test_manual.py`
- **API Docs**: http://localhost:8000/docs
- **Server Logs**: Check console where you started the server

---

## 🎯 What to Test

- [x] Health endpoint
- [x] Start episode at L1-L5
- [x] List scenarios
- [x] Inject incidents
- [x] Check state
- [ ] Submit agent actions
- [ ] Multi-step episodes
- [ ] WebSocket real-time updates
- [ ] Metrics/rewards tracking

---

**Need help?** See `TESTING_GUIDE.md` for detailed instructions.
