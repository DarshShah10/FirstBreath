"""
Emergency Case Models.

Data models for medical emergency response simulation.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class EmergencySeverity(Enum):
    """Emergency severity levels."""
    CRITICAL = "critical"          # Immediate life threat
    SEVERE = "severe"              # High urgency
    MODERATE = "moderate"          # Standard urgency
    LOW = "low"                    # Non-urgent

    @property
    def priority_score(self) -> int:
        """Priority score for sorting (higher = more urgent)."""
        scores = {
            EmergencySeverity.CRITICAL: 4,
            EmergencySeverity.SEVERE: 3,
            EmergencySeverity.MODERATE: 2,
            EmergencySeverity.LOW: 1
        }
        return scores[self]


class EmergencyType(Enum):
    """Types of obstetric emergencies."""
    FETAL_DISTRESS = "fetal_distress"
    MATERNAL_HEMORRHAGE = "maternal_hemorrhage"
    UTERINE_RUPTURE = "uterine_rupture"
    CORD_PROLAPSE = "cord_prolapse"
    PLACENTAL_ABRUPTION = "placental_abruption"
    ECLAMPSIA = "eclampsia"
    SHOULDER_DYSTOCIA = "shoulder_dystocia"
    PREMATURE_LABOR = "premature_labor"
    OTHER = "other"


@dataclass
class Location:
    """Patient location."""
    lat: float
    lng: float
    address: str = ""
    district: str = ""

    def distance_to(self, other: 'Location') -> float:
        """Calculate approximate distance in kilometers using Haversine formula."""
        import math
        R = 6371  # Earth's radius in km

        lat1, lon1 = math.radians(self.lat), math.radians(self.lng)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lng)

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))

        return R * c

    def to_dict(self) -> Dict[str, Any]:
        return {
            "lat": self.lat,
            "lng": self.lng,
            "address": self.address,
            "district": self.district
        }


@dataclass
class PatientInfo:
    """Patient information."""
    gestational_age_weeks: int
    blood_type: str = "O_positive"
    complications: List[str] = field(default_factory=list)
    previous_cesarean: bool = False
    multiple_gestation: bool = False
    maternal_age: int = 0
    maternal_conditions: List[str] = field(default_factory=list)


@dataclass
class DistressSignal:
    """
    Structured distress signal from FirstBreath or manual input.

    This is the primary input to the MiroFish simulation engine.
    """
    case_id: str
    severity: EmergencySeverity
    emergency_type: EmergencyType
    location: Location
    patient: PatientInfo
    time_window_minutes: int = 30  # Golden hour for obstetric emergencies
    preferred_hospital_id: Optional[str] = None
    transport_mode: str = "ambulance"  # ambulance, helicopter, private_vehicle
    caller_info: str = ""
    notes: str = ""
    source: str = "manual"  # "firstbreath", "manual", "emergency_call"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "severity": self.severity.value,
            "emergency_type": self.emergency_type.value,
            "location": self.location.to_dict(),
            "patient": {
                "gestational_age_weeks": self.patient.gestational_age_weeks,
                "blood_type": self.patient.blood_type,
                "complications": self.patient.complications,
                "previous_cesarean": self.patient.previous_cesarean,
                "multiple_gestation": self.patient.multiple_gestation,
                "maternal_age": self.patient.maternal_age,
                "maternal_conditions": self.patient.maternal_conditions
            },
            "time_window_minutes": self.time_window_minutes,
            "preferred_hospital_id": self.preferred_hospital_id,
            "transport_mode": self.transport_mode,
            "caller_info": self.caller_info,
            "notes": self.notes,
            "source": self.source,
            "created_at": self.created_at
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DistressSignal':
        """Create DistressSignal from dictionary."""
        location_data = data.get("location", {})
        patient_data = data.get("patient", {})

        return cls(
            case_id=data.get("case_id", ""),
            severity=EmergencySeverity(data.get("severity", "moderate")),
            emergency_type=EmergencyType(data.get("emergency_type", "other")),
            location=Location(
                lat=location_data.get("lat", 0.0),
                lng=location_data.get("lng", 0.0),
                address=location_data.get("address", ""),
                district=location_data.get("district", "")
            ),
            patient=PatientInfo(
                gestational_age_weeks=patient_data.get("gestational_age_weeks", 38),
                blood_type=patient_data.get("blood_type", "O_positive"),
                complications=patient_data.get("complications", []),
                previous_cesarean=patient_data.get("previous_cesarean", False),
                multiple_gestation=patient_data.get("multiple_gestation", False),
                maternal_age=patient_data.get("maternal_age", 0),
                maternal_conditions=patient_data.get("maternal_conditions", [])
            ),
            time_window_minutes=data.get("time_window_minutes", 30),
            preferred_hospital_id=data.get("preferred_hospital_id"),
            transport_mode=data.get("transport_mode", "ambulance"),
            caller_info=data.get("caller_info", ""),
            notes=data.get("notes", ""),
            source=data.get("source", "manual"),
            created_at=data.get("created_at", datetime.now().isoformat())
        )

    def validate(self) -> List[str]:
        """Validate the distress signal. Returns list of validation errors."""
        errors = []

        if not self.case_id:
            errors.append("case_id is required")

        if self.location.lat == 0 and self.location.lng == 0:
            errors.append("Valid location coordinates are required")

        if self.patient.gestational_age_weeks < 20 or self.patient.gestational_age_weeks > 45:
            errors.append("Gestational age must be between 20 and 45 weeks")

        if self.time_window_minutes <= 0:
            errors.append("Time window must be positive")

        return errors


@dataclass
class EmergencyCase:
    """
    Complete emergency case with simulation results.
    """
    distress_signal: DistressSignal
    status: str = "pending"  # pending, simulating, completed, failed
    simulation_id: Optional[str] = None
    primary_ambulance_id: Optional[str] = None
    assigned_hospital_id: Optional[str] = None
    estimated_response_time_minutes: Optional[float] = None
    failure_risk: Optional[float] = None  # 0.0 to 1.0
    bottlenecks: List[str] = field(default_factory=list)
    interventions: List['Intervention'] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.distress_signal.case_id,
            "status": self.status,
            "severity": self.distress_signal.severity.value,
            "emergency_type": self.distress_signal.emergency_type.value,
            "simulation_id": self.simulation_id,
            "primary_ambulance_id": self.primary_ambulance_id,
            "assigned_hospital_id": self.assigned_hospital_id,
            "estimated_response_time_minutes": self.estimated_response_time_minutes,
            "failure_risk": self.failure_risk,
            "bottlenecks": self.bottlenecks,
            "interventions": [i.to_dict() for i in self.interventions],
            "time_window_minutes": self.distress_signal.time_window_minutes,
            "created_at": self.created_at,
            "completed_at": self.completed_at
        }


@dataclass
class Intervention:
    """
    A recommended intervention option.
    """
    intervention_id: str
    name: str
    description: str
    success_probability: float  # 0.0 to 1.0
    estimated_time_minutes: float
    actions: List['InterventionAction'] = field(default_factory=list)
    is_recommended: bool = False
    risk_level: str = "moderate"  # low, moderate, high
    alternative_routes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "name": self.name,
            "description": self.description,
            "success_probability": self.success_probability,
            "estimated_time_minutes": self.estimated_time_minutes,
            "actions": [a.to_dict() for a in self.actions],
            "is_recommended": self.is_recommended,
            "risk_level": self.risk_level,
            "alternative_routes": self.alternative_routes
        }


@dataclass
class InterventionAction:
    """
    A single action within an intervention.
    """
    action_id: str
    priority: str  # immediate, within_2_min, within_5_min, contingency
    responsible: str  # who performs this action
    description: str
    time_limit_minutes: Optional[float] = None
    status: str = "pending"  # pending, completed, failed

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "priority": self.priority,
            "responsible": self.responsible,
            "description": self.description,
            "time_limit_minutes": self.time_limit_minutes,
            "status": self.status
        }
