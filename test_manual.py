#!/usr/bin/env python3
"""
ChaosMesh Arena - Manual Testing Script
========================================

This script performs comprehensive API testing including:
1. Health check
2. Starting a new episode
3. Listing available scenarios
4. Injecting incidents
5. Checking state
6. Taking agent actions

Run: python test_manual.py
"""

import requests
import json
import sys
from typing import Dict, Any

API_BASE = "http://localhost:8000"
API_KEY = "cm_demo_change_me"
HEADERS = {"X-API-Key": API_KEY}


def print_section(title: str):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def test_health() -> bool:
    """Test the health endpoint."""
    print_section("TEST 1: Health Check")
    try:
        response = requests.get(f"{API_BASE}/health", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        print(f"Status: {data['status']}")
        print(f"Version: {data['version']}")
        print(f"Uptime: {data['uptime_seconds']:.1f}s")
        print(f"Ollama Available: {data['ollama_available']}")
        print(f"OpenRouter Available: {data['openrouter_available']}")
        print(f"Active Episode: {data.get('active_episode') or 'None'}")
        return True
    except Exception as e:
        print(f"FAILED: {e}")
        return False


def test_reset(level: int = 1) -> str:
    """Start a new episode."""
    print_section(f"TEST 2: Reset Environment (Level {level})")
    try:
        response = requests.post(
            f"{API_BASE}/env/reset",
            json={"level": level},
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        episode_id = data["episode_id"]
        obs = data["observation"]
        
        print(f"Episode ID: {episode_id}")
        print(f"Step: {obs['step']}")
        print(f"Simulated Time: {obs['sim_time_minutes']:.1f} minutes")
        print(f"Active Incidents: {len(obs['active_incidents'])}")
        
        for inc in obs['active_incidents']:
            print(f"  - [{inc['incident_id']}] {inc['title']}")
            print(f"    Description: {inc['description']}")
            print(f"    Affected: {', '.join(inc['affected_components'])}")
        
        print(f"\nCluster State:")
        print(f"  Pods: {len(obs['cluster_state']['pods'])}")
        print(f"  Services: {len(obs['cluster_state']['services'])}")
        print(f"  Nodes: {len(obs['cluster_state']['nodes'])}")
        print(f"  Available Tools: {len(obs['available_tools'])}")
        
        return episode_id
    except Exception as e:
        print(f"FAILED: {e}")
        return ""


def test_scenarios() -> Dict[str, Any]:
    """List available scenarios."""
    print_section("TEST 3: Available Scenarios")
    try:
        response = requests.get(
            f"{API_BASE}/demo/scenarios",
            headers=HEADERS,
            timeout=5
        )
        response.raise_for_status()
        scenarios = response.json()["scenarios"]
        
        print(f"Total Scenarios: {len(scenarios)}\n")
        for key, details in scenarios.items():
            print(f"  {key}")
            print(f"    Name: {details['name']}")
            print(f"    Level: L{details['level']}")
            print(f"    Description: {details['description']}")
            print()
        
        return scenarios
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def test_inject(scenario_key: str, level: int = 1) -> str:
    """Inject a scenario."""
    print_section(f"TEST 4: Inject Scenario '{scenario_key}'")
    try:
        response = requests.post(
            f"{API_BASE}/demo/inject",
            json={
                "scenario_key": scenario_key,
                "description": f"Manual test injection of {scenario_key}",
                "level": level
            },
            headers=HEADERS,
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"Injected: {data['title']}")
        print(f"Incident ID: {data['incident_id']}")
        print(f"Level: L{data['level']}")
        print(f"Affected Components: {', '.join(data.get('affected_pods', []))}")
        
        return data['incident_id']
    except Exception as e:
        print(f"FAILED: {e}")
        return ""


def test_state() -> Dict[str, Any]:
    """Check current state."""
    print_section("TEST 5: Current State")
    try:
        response = requests.get(
            f"{API_BASE}/env/state",
            headers=HEADERS,
            timeout=5
        )
        response.raise_for_status()
        state = response.json()
        
        print(f"Episode ID: {state['episode_id']}")
        print(f"Step: {state['step']}")
        print(f"Simulated Time: {state['sim_time_minutes']:.1f} minutes")
        print(f"Current Level: {state['current_level']}")
        print(f"\nActive Incidents: {len(state['active_incidents'])}")
        
        for inc in state['active_incidents']:
            print(f"  - [{inc['incident_id']}] {inc['title']}")
            print(f"    Status: {inc['status']}")
            print(f"    Level: {inc['level']}")
        
        print(f"\nAgent Messages: {len(state.get('all_messages', []))}")
        print(f"Agent Beliefs: {len(state.get('all_beliefs', {}))}")
        print(f"Cumulative Reward: {state.get('cumulative_reward', 0):.2f}")
        
        return state
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def test_step(action: Dict[str, Any]):
    """Take an agent action."""
    print_section("TEST 6: Take Agent Step")
    try:
        response = requests.post(
            f"{API_BASE}/env/step",
            json=action,
            headers=HEADERS,
            timeout=15
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"Action: {action.get('action_type')}")
        print(f"Agent: {action.get('agent_id')}")
        print(f"\nResult:")
        print(f"  Reward: {data.get('reward', 0):.2f}")
        print(f"  Done: {data.get('done', False)}")
        print(f"  New Step: {data.get('observation', {}).get('step', 0)}")
        
        return data
    except Exception as e:
        print(f"FAILED: {e}")
        return {}


def main():
    """Run all tests."""
    print("\n")
    print("=" * 70)
    print(" " * 15 + "ChaosMesh Arena - Manual Test Suite")
    print("=" * 70)
    
    # Test 1: Health
    if not test_health():
        print("\nServer is not running! Start it with:")
        print("  python -m server.main")
        print("  OR")
        print("  uvicorn server.main:app --reload")
        sys.exit(1)
    
    # Test 2: Reset
    episode_id = test_reset(level=1)
    if not episode_id:
        print("\nFailed to start episode!")
        sys.exit(1)
    
    # Test 3: Scenarios
    scenarios = test_scenarios()
    if not scenarios:
        print("\nFailed to get scenarios!")
        sys.exit(1)
    
    # Test 4: Inject
    incident_id = test_inject("pod_crash", level=1)
    if not incident_id:
        print("\nFailed to inject scenario!")
        sys.exit(1)
    
    # Test 5: State
    state = test_state()
    if not state:
        print("\nFailed to get state!")
        sys.exit(1)
    
    # Test 6: Agent Action (example)
    sample_action = {
        "action_type": "get_logs",
        "agent_id": "agent-sre-1",
        "target": "pod-ingress-4r7t2",
        "parameters": {
            "lines": 50,
            "since": "5m"
        }
    }
    test_step(sample_action)
    
    print_section("ALL TESTS PASSED")
    print("\nDashboard: http://localhost:8000/dashboard")
    print("API Docs: http://localhost:8000/docs")
    print("WebSocket: ws://localhost:8000/ws/stream?api_key=cm_demo_change_me")
    print()


if __name__ == "__main__":
    main()
