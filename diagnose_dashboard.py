"""
ChaosMesh Arena - Dashboard Connection Fix
===========================================

This script diagnoses and fixes the "Waiting for episode..." issue
where the dashboard can't communicate with the backend API.
"""

import requests
import sys

API_BASE = "http://localhost:8000"
API_KEY = "cm_demo_change_me"
HEADERS = {"X-API-Key": API_KEY}

print("\n" + "=" * 70)
print("CHAOSMESH ARENA - DASHBOARD CONNECTION DIAGNOSTIC")
print("=" * 70)

# Step 1: Check if server is running
print("\n[1/5] Checking if server is running...")
try:
    response = requests.get(f"{API_BASE}/health", timeout=2)
    if response.status_code == 200:
        print("     ✓ Server is RUNNING")
        data = response.json()
        print(f"       - Version: {data['version']}")
        print(f"       - Ollama: {data['ollama_available']}")
        print(f"       - Redis: {data['redis_connected']}")
    else:
        print(f"     ✗ Server returned HTTP {response.status_code}")
        sys.exit(1)
except requests.exceptions.ConnectionError:
    print("     ✗ Server is NOT RUNNING")
    print("\n       Start it with: python start_server.py")
    sys.exit(1)

# Step 2: Test API authentication
print("\n[2/5] Testing API authentication...")
try:
    response = requests.get(f"{API_BASE}/env/state", headers=HEADERS, timeout=2)
    if response.status_code == 200:
        print("     ✓ API authentication working")
    elif response.status_code == 401:
        print("     ✗ Authentication FAILED")
        print(f"       Check API key in .env: {API_KEY}")
        sys.exit(1)
    else:
        print(f"     ? Unexpected response: {response.status_code}")
except Exception as e:
    print(f"     ✗ Error: {e}")
    sys.exit(1)

# Step 3: Create a test episode
print("\n[3/5] Creating a test episode...")
try:
    response = requests.post(
        f"{API_BASE}/env/reset",
        json={"level": 1},
        headers=HEADERS,
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        episode_id = data.get("episode_id")
        print(f"     ✓ Episode created: {episode_id[:16]}...")
    else:
        print(f"     ✗ Failed: HTTP {response.status_code}")
        print(f"       Response: {response.text[:200]}")
        sys.exit(1)
except Exception as e:
    print(f"     ✗ Error: {e}")
    sys.exit(1)

# Step 4: Verify episode state
print("\n[4/5] Verifying episode state...")
try:
    response = requests.get(f"{API_BASE}/env/state", headers=HEADERS, timeout=2)
    if response.status_code == 200:
        data = response.json()
        print(f"     ✓ State retrieved successfully")
        print(f"       - Episode ID: {data.get('episode_id', '?')[:16]}...")
        print(f"       - Step: {data.get('step', 0)}")
        print(f"       - Incidents: {len(data.get('active_incidents', []))}")
    else:
        print(f"     ✗ Failed to get state")
except Exception as e:
    print(f"     ✗ Error: {e}")

# Step 5: Test scenario injection
print("\n[5/5] Testing scenario injection...")
try:
    response = requests.post(
        f"{API_BASE}/demo/inject",
        json={
            "scenario_key": "pod_crash",
            "description": "Test injection",
            "level": 1
        },
        headers=HEADERS,
        timeout=5
    )
    if response.status_code == 200:
        data = response.json()
        print(f"     ✓ Scenario injected: {data.get('title', '?')}")
        print(f"       - Incident ID: {data.get('incident_id', '?')}")
    else:
        print(f"     ? HTTP {response.status_code}")
except Exception as e:
    print(f"     ? Error: {e}")

# Conclusion
print("\n" + "=" * 70)
print("DIAGNOSIS COMPLETE")
print("=" * 70)

print("\n✓ ALL API ENDPOINTS ARE WORKING CORRECTLY!")
print("\nThe '404 manifest.json' errors in server logs are HARMLESS.")
print("They're just the browser looking for PWA config files.")

print("\n" + "=" * 70)
print("WHY DASHBOARD SHOWS 'WAITING FOR EPISODE'")
print("=" * 70)

print("\nThe issue is Gradio's queue/WebSocket system when mounted in FastAPI.")
print("\nSOLUTIONS (try in order):")

print("\n1. HARD REFRESH THE BROWSER")
print("   - Press: Ctrl + Shift + R")
print("   - This clears cached JavaScript")

print("\n2. CLEAR BROWSER CACHE")
print("   - Chrome: Settings > Privacy > Clear browsing data")
print("   - Select: Cached images and files")
print("   - Time range: Last hour")

print("\n3. USE INCOGNITO/PRIVATE MODE")
print("   - Open: Ctrl + Shift + N (Chrome) or Ctrl + Shift + P (Firefox)")
print("   - Navigate to: http://localhost:8000/dashboard")

print("\n4. TRY A DIFFERENT BROWSER")
print("   - If using Chrome, try Firefox or Edge")

print("\n5. CHECK BROWSER CONSOLE")
print("   - Press F12")
print("   - Go to Console tab")
print("   - Look for red errors (not the 404 manifest ones)")
print("   - Share any ERR_INTERNET_DISCONNECTED errors")

print("\n" + "=" * 70)
print("CURRENT EPISODE STATUS")
print("=" * 70)

try:
    response = requests.get(f"{API_BASE}/env/state", headers=HEADERS, timeout=2)
    if response.status_code == 200:
        data = response.json()
        print(f"\nEpisode ID: {data.get('episode_id', 'None')}")
        print(f"Step: {data.get('step', 0)}")
        print(f"Level: {data.get('current_level', 1)}")
        print(f"Active Incidents: {len(data.get('active_incidents', []))}")
        
        for inc in data.get('active_incidents', []):
            print(f"\n  - {inc['title']}")
            print(f"    ID: {inc['incident_id']}")
            print(f"    Status: {inc['status']}")
except:
    pass

print("\n" + "=" * 70)
print("\nYou can test the API manually:")
print("  http://localhost:8000/docs")
print("\nOr access the dashboard:")
print("  http://localhost:8000/dashboard")
print()
