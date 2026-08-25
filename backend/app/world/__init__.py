"""
FirstBreath world model — deterministic simulation substrate.

Agents propose actions; the world disposes. Pure physics, seeded randomness,
no wall-clock in logic, no shared global state.
"""

from .state import WorldState, build_world
from .engine import WorldEngine, load_registry
from .actions import (
    DecisionList, DispatchAmbulance, PreAlertHospital, RerouteAmbulance,
    RequestBlood, PageStaff, UpdateTraffic, Escalate, NoOp, apply_action,
)
from .observation import dispatcher_observation, hospital_observation, ambulance_observation

__all__ = [
    "WorldState", "build_world", "WorldEngine", "load_registry",
    "DecisionList", "DispatchAmbulance",
    "PreAlertHospital", "RerouteAmbulance", "RequestBlood", "PageStaff",
    "UpdateTraffic", "Escalate", "NoOp", "apply_action",
    "dispatcher_observation", "hospital_observation", "ambulance_observation",
]
