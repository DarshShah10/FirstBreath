"""
Data models for VahanAI Emergency Response Dispatch Simulation.

Core concept: When a distress signal arrives, simulate the ENTIRE response chain
to identify where it will break, then output specific interventions.
"""

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class UnitConfig:
    """Configuration for a single emergency response unit."""

    agent_id: int
    entity_uuid: str
    entity_name: str
    entity_type: str  # ambulance, doctor, hospital, blood_bank, ot, dispatcher

    # Current status (from hospital graph)
    is_available: bool = True
    current_location: str = ""
    distance_km: float = 0.0

    # Response capability
    response_time_min: int = 5  # minutes to reach scene
    prep_time_min: int = 0  # prep time (for OT, blood bank)

    # Dependencies
    requires: List[str] = field(default_factory=list)  # e.g., ["ot", "blood"]
    provides: List[str] = field(default_factory=list)  # e.g., ["surgery", "blood"]

    # Influence on outcome
    criticality: float = 1.0  # 0.5 = can substitute, 1.0 = single point of failure


@dataclass
class CityCondition:
    """Current city conditions affecting response."""

    # Traffic
    traffic_level: str = "normal"  # normal, heavy, blocked
    blocked_routes: List[str] = field(default_factory=list)
    traffic_delay_min: int = 0

    # Special conditions
    is_festival: bool = False
    festival_name: str = ""
    weather: str = "clear"  # clear, rain, storm

    # Impact on response time
    effective_delay_min: int = 0


@dataclass
class DistressSignal:
    """Emergency distress signal that triggers simulation."""

    signal_type: str  # A (FirstBreath), B (108 call), C (nurse flag), D (mass casualty)
    severity: int = 8  # 1-10, 10 = most severe
    time_window_min: int = 20  # Golden Hour or window before outcome degrades
    location: str = ""
    patient_condition: str = ""

    # Resources needed
    needs_ambulance: bool = True
    needs_blood: bool = False
    blood_type: str = ""
    needs_ot: bool = False
    needs_specialist: str = ""  # e.g., "cardiologist", "neurosurgeon"


@dataclass
class SimulationConfig:
    """Configuration for a single dispatch simulation run."""

    # What we're simulating
    distress_signal: DistressSignal

    # Available units (from hospital graph)
    available_units: List[UnitConfig] = field(default_factory=list)

    # Current city conditions
    city_condition: CityCondition = field(default_factory=CityCondition)

    # Simulation parameters
    simulation_id: str = ""
    project_id: str = ""
    graph_id: str = ""


@dataclass
class SimulationResult:
    """Result of a single simulation run."""

    # Did resources reach in time?
    success: bool = False
    time_to_scene_min: float = 0.0
    time_to_hospital_min: float = 0.0

    # Where did it fail?
    failure_point: str = ""  # "dispatch", "en_route", "handoff", "ot_prep", "blood"
    failure_reason: str = ""

    # Bottleneck identified
    bottleneck_unit: str = ""
    bottleneck_type: str = ""  # "unavailable", "delayed", "occupied", "missing"

    # Time saved if bottleneck resolved
    time_saved_min: float = 0.0


@dataclass
class AggregatedResult:
    """Aggregated results from multiple simulation runs."""

    # Success probability
    success_probability: float = 0.0  # 0.0 to 1.0

    # Primary bottleneck (most common failure point)
    primary_bottleneck: str = ""
    bottleneck_frequency: float = 0.0  # How often this bottleneck appeared

    # Recommended intervention
    intervention_action: str = ""
    intervention_trigger: str = ""  # "now", "T+5", "if X fails"
    expected_time_saved: float = 0.0

    # Cascade risk
    cascade_risk: List[str] = field(default_factory=list)  # Other emergencies affected


@dataclass
class SimulationParameters:
    """Complete simulation parameter configuration."""

    # Basic info
    simulation_id: str
    project_id: str
    graph_id: str
    simulation_requirement: str

    # Unit configurations
    unit_configs: List[UnitConfig] = field(default_factory=list)

    # City conditions
    city_condition: CityCondition = field(default_factory=CityCondition)

    # Distress signal
    distress_signal: DistressSignal = field(default_factory=DistressSignal)

    # LLM config
    llm_model: str = ""
    llm_base_url: str = ""

    # Metadata
    generated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "simulation_id": self.simulation_id,
            "project_id": self.project_id,
            "graph_id": self.graph_id,
            "simulation_requirement": self.simulation_requirement,
            "unit_configs": [asdict(u) for u in self.unit_configs],
            "city_condition": asdict(self.city_condition),
            "distress_signal": asdict(self.distress_signal),
            "llm_model": self.llm_model,
            "llm_base_url": self.llm_base_url,
            "generated_at": self.generated_at,
        }

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=indent)


# Backward compatibility aliases
AgentActivityConfig = UnitConfig
TimeSimulationConfig = SimulationConfig
EventConfig = DistressSignal
