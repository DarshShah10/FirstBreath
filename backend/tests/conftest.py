"""Shared fixtures: a small registry + signals for fast, focused tests."""

import copy
import pytest

REGISTRY = {
    "hospitals": [
        {"hospital_id": "h1", "name": "Central Hospital", "level": "tertiary",
         "location": {"lat": 28.6139, "lng": 77.2090, "address": "Sector 12"},
         "ot_count": 2, "nicu_beds": 4, "obgyn_beds": 10,
         "contact_phone": "+91-120-000"},
        {"hospital_id": "h2", "name": "District Hospital", "level": "secondary",
         "location": {"lat": 28.6300, "lng": 77.2300, "address": "Sector 22"},
         "ot_count": 1, "nicu_beds": 2, "obgyn_beds": 5},
    ],
    "ambulances": [
        {"ambulance_id": "amb_1", "name": "Unit 1", "type": "ALS",
         "base_location": {"lat": 28.6100, "lng": 77.2000},
         "equipped_for": ["neonatal_resuscitation", "emergency_delivery"],
         "has_paramedic": True},
        {"ambulance_id": "amb_2", "name": "Unit 2", "type": "BLS",
         "base_location": {"lat": 28.6200, "lng": 77.2100},
         "equipped_for": ["emergency_delivery"],
         "has_paramedic": False},
    ],
    "staff": [
        {"staff_id": "s_ob_1", "name": "Dr. A", "specialization": "obstetrician",
         "hospital_id": "h1", "on_call": True, "response_time_minutes": 5},
        {"staff_id": "s_an_1", "name": "Dr. B", "specialization": "anesthesiologist",
         "hospital_id": "h1", "on_call": True, "response_time_minutes": 6},
    ],
    "blood_banks": [
        {"blood_bank_id": "bb_1", "name": "Central Bank",
         "hospital_id": "h1",
         "inventory": {"o_negative": 4, "o_positive": 10}},
    ],
    "routes": [
        {"route_id": "r_main", "name": "Main Road",
         "from_location": {"lat": 28.6100, "lng": 77.2000},
         "to_location": {"lat": 28.6139, "lng": 77.2090},
         "distance_km": 1.5, "typical_duration_minutes": 5,
         "current_status": "clear", "alternate_route_id": "r_alt"},
        {"route_id": "r_alt", "name": "Ring Bypass",
         "from_location": {"lat": 28.6100, "lng": 77.2000},
         "to_location": {"lat": 28.6139, "lng": 77.2090},
         "distance_km": 3.0, "typical_duration_minutes": 9,
         "current_status": "clear"},
        {"route_id": "r_h2", "name": "District Road",
         "from_location": {"lat": 28.6100, "lng": 77.2000},
         "to_location": {"lat": 28.6300, "lng": 77.2300},
         "distance_km": 4.0, "typical_duration_minutes": 12,
         "current_status": "clear"},
    ],
}

SIGNAL = {
    "case_id": "case_test",
    "severity": "critical",
    "emergency_type": "fetal_distress",
    "location": {"lat": 28.6100, "lng": 77.2000, "address": "Sector 12"},
    "patient": {"gestational_age_weeks": 36, "blood_type": "O_negative",
                "complications": ["late_decelerations"]},
    "time_window_minutes": 30,
}


@pytest.fixture
def registry():
    return copy.deepcopy(REGISTRY)


@pytest.fixture
def signal():
    return copy.deepcopy(SIGNAL)


def make_world(registry, signals=None, seed="test-seed", horizon=90.0):
    from app.world.state import build_world
    return build_world("run_test", registry, signals or [dict(SIGNAL)],
                       seed=seed, horizon_minutes=horizon)
