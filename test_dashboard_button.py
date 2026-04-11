"""
Quick diagnostic to test if the dashboard button is working
"""
import httpx
import os

API_BASE = os.environ.get("CHAOSMESH_API_BASE", "http://localhost:8000")
API_KEY = os.environ.get("CHAOSMESH_API_KEY", "cm_demo_change_me")
_HEADERS = {"X-API-Key": API_KEY}

print("=" * 70)
print("DASHBOARD BUTTON DIAGNOSTIC")
print("=" * 70)

print(f"\nConfiguration:")
print(f"  API_BASE: {API_BASE}")
print(f"  API_KEY: {API_KEY}")
print(f"  Headers: {_HEADERS}")

# Simulate what the dashboard does when you click "Start New Episode"
print("\n" + "=" * 70)
print("Simulating 'Start New Episode' button click (Level 1)")
print("=" * 70)

def _api_post(path: str, body: dict) -> dict:
    try:
        r = httpx.post(f"{API_BASE}{path}", json=body, headers=_HEADERS, timeout=10.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

# This is what happens when you click the button
def do_reset(level_int: int):
    print(f"\nCalling: POST {API_BASE}/env/reset")
    print(f"Body: {{'level': {level_int}}}")
    print(f"Headers: {_HEADERS}")
    
    resp = _api_post("/env/reset", {"level": level_int})
    
    if "error" in resp:
        result = f"❌ Reset failed: {resp['error']}"
    else:
        ep_id = resp.get("episode_id", "?")
        result = f"✅ Episode started: `{ep_id}` at Level {level_int}"
    
    print(f"\nResult: {result}")
    return result

# Test it
result = do_reset(1)

print("\n" + "=" * 70)
print("Now checking /env/state (what the status bar polls)")
print("=" * 70)

def _api_get(path: str) -> dict:
    try:
        r = httpx.get(f"{API_BASE}{path}", headers=_HEADERS, timeout=5.0)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"error": str(e)}

state = _api_get("/env/state")

if "error" in state:
    print(f"ERROR getting state: {state['error']}")
else:
    print(f"Episode ID: {state.get('episode_id')}")
    print(f"Step: {state.get('step')}")
    print(f"Level: {state.get('current_level')}")
    print(f"Active Incidents: {len(state.get('active_incidents', []))}")
    
print("\n" + "=" * 70)
print("CONCLUSION:")
print("=" * 70)

if "error" not in state and state.get('episode_id'):
    print("✅ The API is working correctly!")
    print("✅ Episode was created successfully!")
    print("\nIf the dashboard still shows 'Waiting for episode...', the issue is:")
    print("  1. The button click handler is not firing")
    print("  2. Gradio is not updating the UI after the click")
    print("  3. CORS is blocking the request from the browser")
    print("\nTry:")
    print("  1. Hard refresh the page (Ctrl+Shift+R)")
    print("  2. Check browser console for JavaScript errors")
    print("  3. Restart the server to pick up new CORS config")
else:
    print("❌ The API call failed!")
    print("This means the dashboard button WOULD fail too.")
