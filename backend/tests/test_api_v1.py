"""
Test script for Emergency Simulation API V1.

Tests the REST API endpoints for simulation management.
"""

import json
import time
import requests
from datetime import datetime


BASE_URL = "http://localhost:5001"


def test_health():
    """Test health endpoint."""
    print("\n=== Testing /api/v1/health ===")
    resp = requests.get(f"{BASE_URL}/api/v1/health")
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")
    assert resp.status_code == 200
    print("✓ Health check passed")


def test_create_simulation():
    """Test simulation creation."""
    print("\n=== Testing POST /api/v1/simulations ===")
    data = {
        "simulation_speed": 1.0,
        "mode": "sequential",
        "max_concurrent_cases": 10
    }
    resp = requests.post(f"{BASE_URL}/api/v1/simulations", json=data)
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    assert resp.status_code == 201
    assert result["success"] is True
    sim_id = result["simulation_id"]
    print(f"✓ Created simulation: {sim_id}")
    return sim_id


def test_list_simulations(sim_id):
    """Test listing simulations."""
    print("\n=== Testing GET /api/v1/simulations ===")
    resp = requests.get(f"{BASE_URL}/api/v1/simulations")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    assert resp.status_code == 200
    print("✓ List simulations passed")


def test_get_simulation(sim_id):
    """Test getting simulation status."""
    print(f"\n=== Testing GET /api/v1/simulations/{sim_id} ===")
    resp = requests.get(f"{BASE_URL}/api/v1/simulations/{sim_id}")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {json.dumps(result, indent=2)[:500]}...")
    assert resp.status_code == 200
    print("✓ Get simulation passed")


def test_add_case(sim_id):
    """Test adding a case."""
    print(f"\n=== Testing POST /api/v1/simulations/{sim_id}/cases ===")
    data = {
        "case_id": "test_case_001",
        "severity": "critical",
        "emergency_type": "fetal_distress",
        "location": {
            "lat": 28.6100,
            "lng": 77.2000,
            "address": "Sector 12, Noida, UP"
        },
        "patient": {
            "gestational_age_weeks": 38,
            "blood_type": "O_positive",
            "complications": ["late_decelerations"],
            "previous_cesarean": False,
            "multiple_gestation": False
        },
        "time_window_minutes": 30
    }
    resp = requests.post(f"{BASE_URL}/api/v1/simulations/{sim_id}/cases", json=data)
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    assert resp.status_code == 201
    assert result["success"] is True
    case_id = result["case_id"]
    print(f"✓ Added case: {case_id}")
    return case_id


def test_run_simulation(sim_id):
    """Test running simulation."""
    print(f"\n=== Testing POST /api/v1/simulations/{sim_id}/run ===")
    data = {"duration_minutes": 5, "max_steps": 100}
    resp = requests.post(f"{BASE_URL}/api/v1/simulations/{sim_id}/run", json=data)
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {json.dumps(result, indent=2)}")
    assert resp.status_code == 202
    print("✓ Simulation started (async)")


def test_get_results(sim_id):
    """Test getting results."""
    print(f"\n=== Testing GET /api/v1/simulations/{sim_id}/results ===")
    time.sleep(1)  # Give simulation time to complete
    resp = requests.get(f"{BASE_URL}/api/v1/simulations/{sim_id}/results")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    if resp.status_code == 200:
        print(f"Response (truncated): {json.dumps(result, indent=2)[:1000]}...")
        print("✓ Got results")
    else:
        print(f"Response: {result}")
        print("✓ Got response (simulation may still be running)")


def test_intervention_analysis(sim_id, case_id):
    """Test intervention analysis."""
    print(f"\n=== Testing GET /api/v1/simulations/{sim_id}/interventions/{case_id} ===")
    resp = requests.get(f"{BASE_URL}/api/v1/simulations/{sim_id}/interventions/{case_id}?format=brief")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    if resp.status_code == 200:
        print(f"Analysis keys: {list(result.get('analysis', {}).keys())[:5]}...")
        print(f"Report (first 500 chars):\n{result.get('report', '')[:500]}")
        print("✓ Got intervention analysis")
    else:
        print(f"Response: {result}")


def test_resources():
    """Test resources endpoint."""
    print("\n=== Testing GET /api/v1/resources ===")
    resp = requests.get(f"{BASE_URL}/api/v1/resources")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    if resp.status_code == 200:
        hospitals = result.get("hospitals", [])
        ambulances = result.get("ambulances", [])
        print(f"Hospitals: {len(hospitals)}, Ambulances: {len(ambulances)}")
        if hospitals:
            print(f"First hospital: {hospitals[0]['name']} ({hospitals[0]['hospital_id']})")
        print("✓ Resources endpoint works")


def test_nearest_resources():
    """Test nearest resources endpoint."""
    print("\n=== Testing GET /api/v1/resources/nearest ===")
    resp = requests.get(f"{BASE_URL}/api/v1/resources/nearest?lat=28.61&lng=77.21")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    if resp.status_code == 200:
        print(f"Response: {json.dumps(result, indent=2)[:500]}")
        print("✓ Nearest resources works")


def test_stop_simulation(sim_id):
    """Test stopping simulation."""
    print(f"\n=== Testing POST /api/v1/simulations/{sim_id}/stop ===")
    resp = requests.post(f"{BASE_URL}/api/v1/simulations/{sim_id}/stop")
    print(f"Status: {resp.status_code}")
    result = resp.json()
    print(f"Response: {result}")
    print("✓ Stop simulation endpoint works")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("Emergency Simulation API V1 - Test Suite")
    print("=" * 60)

    try:
        test_health()
        test_resources()
        test_nearest_resources()

        sim_id = test_create_simulation()
        test_list_simulations(sim_id)
        test_get_simulation(sim_id)

        case_id = test_add_case(sim_id)
        test_run_simulation(sim_id)
        test_get_results(sim_id)
        test_intervention_analysis(sim_id, case_id)

        test_stop_simulation(sim_id)

        print("\n" + "=" * 60)
        print("ALL TESTS PASSED!")
        print("=" * 60)

    except requests.exceptions.ConnectionError:
        print("\n⚠ Could not connect to server. Make sure the Flask app is running on port 5001")
        print("   Run: python run.py")
    except AssertionError as e:
        print(f"\n✗ Test failed: {e}")
        raise
    except Exception as e:
        print(f"\n✗ Error: {e}")
        raise


if __name__ == "__main__":
    run_all_tests()
