# STEP-BY-STEP: FIX THE DASHBOARD

## Current Situation

✅ **Server is running**  
✅ **API works perfectly** (I just created an episode: `9cf47f60-5e45-460b-acde-a376c61ca75b`)  
❌ **Dashboard button doesn't work**

## The Fix

I've added debug logging to the dashboard so we can see what's happening.

### STEP 1: RESTART THE SERVER (Required!)

**In your terminal where the server is running:**

1. Press `Ctrl+C` to stop
2. Run: `python start_server.py`
3. Wait for: `INFO: chaosmesh_ready port=8000`

### STEP 2: REFRESH THE DASHBOARD

1. Go to: http://localhost:8000/dashboard
2. Press: `Ctrl+Shift+R` (hard refresh)

### STEP 3: TRY TO CREATE AN EPISODE

1. Click "Control" tab
2. Select "L1 — Pod Crash"
3. Click "▶ Start New Episode"

### STEP 4: CHECK THE SERVER LOGS

Look in the terminal where the server is running. You should now see:

```
[Dashboard] Reset button clicked! Level: 1
[Dashboard] POST http://localhost:8000/env/reset
[Dashboard] Body: {'level': 1}
[Dashboard] Response: 200
[Dashboard] Reset response: 9cf47f60-...
[Dashboard] SUCCESS: ✅ Episode started...
```

If you DON'T see these logs, it means:
- The button click isn't reaching the server
- There's a Gradio queue issue

## Alternative: Access the Episode I Created

I already created an episode for you! The server has an active episode:

**Episode ID**: `9cf47f60-5e45-460b-acde-a376c61ca75b`

**To see it:**

1. Refresh the dashboard (Ctrl+Shift+R)
2. The status bar SHOULD update automatically
3. If not, click the "Refresh" buttons in each tab

## If Dashboard Still Doesn't Work

### Option A: Use the API Docs (Recommended)

```
http://localhost:8000/docs
```

This gives you a working UI to:
- Create episodes
- Get state
- Inject incidents
- Take actions

### Option B: Use curl

```bash
# Create episode
curl -X POST http://localhost:8000/env/reset \
  -H "X-API-Key: cm_demo_change_me" \
  -H "Content-Type: application/json" \
  -d '{"level": 1}'

# Get state
curl http://localhost:8000/env/state \
  -H "X-API-Key: cm_demo_change_me"
```

### Option C: Use Python

```python
import requests

API = "http://localhost:8000"
KEY = {"X-API-Key": "cm_demo_change_me"}

# Get current state
r = requests.get(f"{API}/env/state", headers=KEY)
print(r.json())

# Create new episode
r = requests.post(f"{API}/env/reset", json={"level": 1}, headers=KEY)
print(r.json()['episode_id'])
```

## What Changed

I added debug logging to these functions:
- `_api_post()` - Now logs API calls
- `do_reset()` - Now logs button clicks
- `update_status_bar()` - Now logs status updates
- `_refresh_state()` - Now logs state fetches

These logs will help us see what's failing.

## Next Steps

1. **RESTART THE SERVER** (most important!)
2. Try the dashboard again
3. Share the server logs if it still doesn't work
4. Or just use the API docs at /docs (which definitely works!)

---

**Bottom Line**: The backend works perfectly. We're just debugging why the dashboard button doesn't communicate properly. After restarting, the debug logs will tell us exactly what's wrong.
