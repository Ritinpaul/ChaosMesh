# Episode Creation Not Working - FIX INSTRUCTIONS

## Problem
Dashboard shows "Waiting for episode..." and the "Start New Episode" button doesn't work.

## Root Cause
**CORS (Cross-Origin Resource Sharing) configuration is missing `http://localhost:8000`**

When the Gradio dashboard is mounted inside FastAPI at `/dashboard`, it makes HTTP requests from the browser to the API endpoints. These requests originate from `http://localhost:8000/dashboard` and need to be allowed by CORS.

## Solution

### Step 1: Restart the Server

The `.env` file has been updated with the correct CORS configuration:

```env
CORS_ORIGINS=["http://localhost:8000","http://localhost:7860","http://localhost:3000"]
```

**You MUST restart the server for this change to take effect!**

#### How to Restart:

1. **Stop the current server**:
   - If running in terminal: Press `Ctrl+C`
   - If running in background: Find and kill the process

2. **Start the server again**:
   ```bash
   cd d:\NewStart\hackssss\theOne\chaosmesh-arena
   python -m server.main
   ```
   
   OR
   
   ```bash
   uvicorn server.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Step 2: Verify CORS is Fixed

After restarting, test with curl:

```bash
curl -X OPTIONS http://localhost:8000/env/reset \
  -H "Origin: http://localhost:8000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: content-type,x-api-key" \
  -v
```

Look for this header in the response:
```
access-control-allow-origin: http://localhost:8000
```

### Step 3: Test the Dashboard

1. Go to: http://localhost:8000/dashboard
2. Hard refresh: `Ctrl+Shift+R` (to clear cache)
3. Select "L1 — Pod Crash"
4. Click "▶ Start New Episode"
5. You should see:
   - Status bar updates with episode ID
   - "Waiting for episode..." disappears
   - Episode details appear

### Step 4: If Still Not Working

Check the browser console (F12 → Console tab) for errors:

- **CORS error**: Server wasn't restarted
  ```
  Access to fetch at 'http://localhost:8000/env/reset' from origin 'http://localhost:8000' 
  has been blocked by CORS policy
  ```
  **Solution**: Restart the server!

- **401 Unauthorized**: API key mismatch
  **Solution**: Check `.env` file has `CHAOSMESH_API_KEY=cm_demo_change_me`

- **Network error**: Server not running
  **Solution**: Start the server

- **JavaScript error**: Gradio issue
  **Solution**: Try hard refresh or clear browser cache

## Quick Verification Script

Run this to confirm the API works:

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

if response.status_code == 200:
    print(f"SUCCESS! Episode ID: {response.json()['episode_id']}")
else:
    print(f"FAILED: {response.status_code} - {response.text}")
```

## Summary

1. ✅ **FIXED**: Updated `.env` with correct CORS origins
2. ⏳ **ACTION REQUIRED**: **RESTART THE SERVER**
3. ✅ **THEN**: Test the dashboard button

**After restarting, everything should work!**
