#!/usr/bin/env python3
"""
Test if episode creation works via API (not dashboard).
This proves the backend is functional.
"""

import requests
import json
import sys

API_BASE = "http://localhost:8000"
API_KEY = "cm_demo_change_me"
HEADERS = {
    "X-API-Key": API_KEY,
    "Content-Type": "application/json"
}

def test_health():
    """Test server health endpoint."""
    print("\n" + "="*70)
    print("TEST 1: Server Health")
    print("="*70)
    
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        data = r.json()
        
        print(f"✓ Status: {data['status']}")
        print(f"✓ Version: {data['version']}")
        print(f"✓ Ollama: {'Available' if data['ollama_available'] else 'Not Available'}")
        print(f"✓ Redis: {'Connected' if data['redis_connected'] else 'Not Connected'}")
        print(f"✓ Active Episode: {data['active_episode'] or 'None'}")
        print(f"✓ Uptime: {data['uptime_seconds']:.1f}s")
        return True
    except requests.exceptions.ConnectionError:
        print("✗ Server not running!")
        print("\nStart the server with:")
        print("  python start_server.py")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def test_create_episode():
    """Test episode creation via API."""
    print("\n" + "="*70)
    print("TEST 2: Create Episode")
    print("="*70)
    
    try:
        payload = {"level": 1}
        print(f"\nSending: POST {API_BASE}/env/reset")
        print(f"Headers: {HEADERS}")
        print(f"Body: {payload}")
        
        r = requests.post(
            f"{API_BASE}/env/reset",
            headers=HEADERS,
            json=payload,
            timeout=30
        )
        
        print(f"\nResponse Status: {r.status_code}")
        
        if r.status_code == 200:
            data = r.json()
            print(f"\n✓ SUCCESS! Episode Created!")
            print(f"  • Episode ID: {data['episode_id']}")
            print(f"  • Level: {payload['level']}")
            print(f"  • Active Incidents: {len(data['observation']['active_incidents'])}")
            
            # Show incident details
            for inc in data['observation']['active_incidents']:
                print(f"    - {inc['title']}")
            
            return data['episode_id']
        else:
            print(f"✗ Failed: {r.status_code}")
            print(f"  Response: {r.text}")
            return None
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return None

def test_get_state(episode_id):
    """Test state retrieval."""
    print("\n" + "="*70)
    print("TEST 3: Get Current State")
    print("="*70)
    
    try:
        r = requests.get(
            f"{API_BASE}/env/state",
            headers=HEADERS,
            timeout=10
        )
        
        if r.status_code == 200:
            data = r.json()
            print(f"\n✓ SUCCESS! State Retrieved!")
            print(f"  • Episode ID: {data['episode_id']}")
            print(f"  • Step: {data['step']}")
            print(f"  • Level: {data['current_level']}")
            print(f"  • Cumulative Reward: {data['cumulative_reward']:.2f}")
            print(f"  • Active Incidents: {len(data['active_incidents'])}")
            print(f"  • Services: {len(data['cluster_state']['services'])}")
            return True
        else:
            print(f"✗ Failed: {r.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error: {e}")
        return False

def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 ChaosMesh Arena - API Functionality Test")
    print("="*70)
    print("\nThis script tests if the backend API works correctly.")
    print("If these tests pass, the issue is in the dashboard UI, not the backend.")
    
    # Test 1: Server Health
    if not test_health():
        print("\n❌ Server is not running. Cannot proceed with tests.")
        print("\nStart the server first:")
        print("  python start_server.py")
        sys.exit(1)
    
    # Test 2: Create Episode
    episode_id = test_create_episode()
    if not episode_id:
        print("\n❌ Failed to create episode. Check server logs.")
        sys.exit(1)
    
    # Test 3: Get State
    if not test_get_state(episode_id):
        print("\n❌ Failed to get state. Check server logs.")
        sys.exit(1)
    
    # Summary
    print("\n" + "="*70)
    print("✅ ALL TESTS PASSED!")
    print("="*70)
    print("\n🎉 The backend API works perfectly!")
    print("\nWhat this means:")
    print("  ✓ Server is running correctly")
    print("  ✓ Episode creation works")
    print("  ✓ State retrieval works")
    print("  ✓ API authentication works")
    print("\nIf the dashboard button doesn't work, it's a Gradio UI issue,")
    print("NOT a backend problem.")
    print("\nWorkarounds:")
    print("  1. Use control_panel.html (simple HTML interface)")
    print("  2. Use http://localhost:8000/docs (Swagger UI)")
    print("  3. Use curl/PowerShell commands")
    print("\nCurrent Episode ID: " + episode_id)
    print("\nYou can now:")
    print("  • Open control_panel.html and click 'Get Current State'")
    print("  • Refresh the Gradio dashboard to see this episode")
    print("  • Continue with manual testing")

if __name__ == "__main__":
    main()
