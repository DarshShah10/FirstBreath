"""
Actionable Intervention Recommendation Engine.

Transforms simulation outcomes into mission-briefing style recommendations:
- WHO does it, WHAT they do, HOW they do it, WHEN by
- Real-time bottleneck detection with actual simulation data
- Specific action steps with contact information
- Alternative scenarios for decision making
- Printable execution checklists
- Before/after outcome projections
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

from ...models.emergency_case import EmergencySeverity, EmergencyType, Location, PatientInfo, DistressSignal
from ...models.response_resource import ResourceLocation, Hospital, Ambulance, MedicalStaff, BloodBank, StaffSpecialization
from .base_agent import BaseAgent
from .ambulance_agent import AmbulanceAgent
from .hospital_agent import HospitalAgent
from .staff_agent import StaffAgent
from .blood_bank_agent import BloodBankAgent
from .road_network_agent import RoadNetworkAgent, RoadCondition
from ...utils.logger import get_logger

logger = get_logger('mirofish.actionable_intervention')


class InterventionType(Enum):
    """Types of interventions."""
    REROUTE = "reroute"
    PREPARE_STAFF = "prepare_staff"
    SECURE_BLOOD = "secure_blood"
    ALERT_HOSPITAL = "alert_hospital"
    REQUEST_BACKUP_AMBULANCE = "request_backup_ambulance"
    ACTIVATE_NEARBY_HOSPITAL = "activate_nearby_hospital"
    ESCALATE_TO_DISPATCH = "escalate_to_dispatch"
    REQUEST_SPECIALIST = "request_specialist"
    PREPARE_OR = "prepare_or"
    MOBILIZE_BLOOD_BANK = "mobilize_blood_bank"
    TRAFFIC_CLEARANCE = "traffic_clearance"
    EMERGENCY_LANE = "emergency_lane"
    CANCEL_NON_EMERGENCY = "cancel_non_emergency"
    CALL_STAFF = "call_staff"


class InterventionPriority(Enum):
    """Intervention priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class BottleneckSeverity(Enum):
    """Severity of bottleneck impact."""
    CRITICAL = "critical"      # Blocks intervention entirely
    HIGH = "high"             # Significant delay
    MEDIUM = "medium"         # Manageable delay
    LOW = "low"               # Minor impact


class ReportFormat(Enum):
    """Output format for reports."""
    BRIEF = "brief"           # Terminal-friendly one-liners
    DETAILED = "detailed"     # Full mission-briefing style
    JSON = "json"             # Structured data for API/UI
    MARKDOWN = "markdown"     # Documentation format
    HTML = "html"             # Dashboard format


@dataclass
class ContactInfo:
    """Contact information for a person or resource."""
    name: str
    role: str
    phone: str = ""
    email: str = ""
    location: str = ""
    availability: str = "on_duty"

    def format_phone(self) -> str:
        """Format phone for dialing."""
        if self.phone:
            return f"Call: {self.phone}"
        return "No phone available"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "role": self.role,
            "phone": self.phone,
            "email": self.email,
            "location": self.location,
            "availability": self.availability
        }


@dataclass
class ActionStep:
    """A single actionable step in an intervention."""
    step_number: int
    action: str                           # What to do
    actor: str                           # WHO does this
    method: str = ""                     # HOW to do it
    contacts: List[ContactInfo] = field(default_factory=list)
    estimated_time_minutes: float = 0.0
    dependencies: List[str] = field(default_factory=list)
    checklist_items: List[str] = field(default_factory=list)
    alternative_if_failed: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_number": self.step_number,
            "action": self.action,
            "actor": self.actor,
            "method": self.method,
            "contacts": [c.to_dict() for c in self.contacts],
            "estimated_time_minutes": self.estimated_time_minutes,
            "dependencies": self.dependencies,
            "checklist_items": self.checklist_items,
            "alternative_if_failed": self.alternative_if_failed
        }


@dataclass
class ActionableRecommendation:
    """A complete intervention recommendation with actionable steps."""
    recommendation_id: str
    intervention_type: InterventionType
    priority: InterventionPriority
    title: str                            # e.g., "OR Clearance Protocol"
    summary: str                          # One-line summary
    action_steps: List[ActionStep] = field(default_factory=list)
    target_resource_id: Optional[str] = None
    target_resource_name: Optional[str] = None
    expected_outcome: str = ""
    time_saved_minutes: float = 0.0
    confidence_score: float = 0.0        # 0.0 - 1.0
    alternatives: List[str] = field(default_factory=list)
    success_probability_before: float = 0.0
    success_probability_after: float = 0.0

    def get_total_time(self) -> float:
        """Get total estimated time for all steps."""
        return sum(step.estimated_time_minutes for step in self.action_steps)

    def get_checklist_items(self) -> List[str]:
        """Get flattened checklist items."""
        items = []
        for step in self.action_steps:
            for item in step.checklist_items:
                items.append(f"[ ] {step.step_number}.{step.checklist_items.index(item)+1}. {item}")
        return items

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_id": self.recommendation_id,
            "type": self.intervention_type.value,
            "priority": self.priority.name,
            "title": self.title,
            "summary": self.summary,
            "action_steps": [s.to_dict() for s in self.action_steps],
            "target_resource_id": self.target_resource_id,
            "target_resource_name": self.target_resource_name,
            "expected_outcome": self.expected_outcome,
            "time_saved_minutes": self.time_saved_minutes,
            "confidence_score": self.confidence_score,
            "success_probability_before": self.success_probability_before,
            "success_probability_after": self.success_probability_after
        }


@dataclass
class ResourceStatus:
    """Real-time status of a resource from simulation."""
    resource_id: str
    resource_name: str
    resource_type: str                   # ambulance, hospital, staff, blood, road
    current_state: str = ""
    location: Optional[Dict[str, float]] = None
    eta_minutes: Optional[float] = None
    availability: str = "unknown"
    details: Dict[str, Any] = field(default_factory=dict)
    contact: Optional[ContactInfo] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "resource_type": self.resource_type,
            "current_state": self.current_state,
            "location": self.location,
            "eta_minutes": self.eta_minutes,
            "availability": self.availability,
            "details": self.details,
            "contact": self.contact.to_dict() if self.contact else None
        }


@dataclass
class BottleneckAnalysis:
    """Analysis of a response chain bottleneck with real data."""
    bottleneck_id: str
    severity: BottleneckSeverity
    location_type: str                   # ambulance, hospital, staff, blood, road
    resource_id: str
    resource_name: str
    issue_description: str
    current_status: str
    estimated_delay_minutes: float
    impact_on_patient: str
    affected_resources: List[str] = field(default_factory=list)
    resolution_options: List[str] = field(default_factory=list)
    urgency_reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bottleneck_id": self.bottleneck_id,
            "severity": self.severity.value,
            "location_type": self.location_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "issue_description": self.issue_description,
            "current_status": self.current_status,
            "estimated_delay_minutes": self.estimated_delay_minutes,
            "impact_on_patient": self.impact_on_patient,
            "affected_resources": self.affected_resources,
            "resolution_options": self.resolution_options,
            "urgency_reason": self.urgency_reason
        }


@dataclass
class InterventionScenario:
    """Alternative intervention scenario for comparison."""
    scenario_id: str
    scenario_name: str                    # e.g., "OR Clearance", "Hospital Diversion"
    description: str
    interventions: List[ActionableRecommendation] = field(default_factory=list)
    success_probability: float = 0.0
    time_to_implement_minutes: float = 0.0
    risks: List[str] = field(default_factory=list)
    pros: List[str] = field(default_factory=list)
    cons: List[str] = field(default_factory=list)
    recommended: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "scenario_name": self.scenario_name,
            "description": self.description,
            "interventions": [i.to_dict() for i in self.interventions],
            "success_probability": self.success_probability,
            "time_to_implement_minutes": self.time_to_implement_minutes,
            "risks": self.risks,
            "pros": self.pros,
            "cons": self.cons,
            "recommended": self.recommended
        }


@dataclass
class ResponseChainStatus:
    """Real-time status of the response chain."""
    ambulance: Optional[ResourceStatus] = None
    hospital: Optional[ResourceStatus] = None
    blood_bank: Optional[ResourceStatus] = None
    road_network: Optional[ResourceStatus] = None
    staff: List[ResourceStatus] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ambulance": self.ambulance.to_dict() if self.ambulance else None,
            "hospital": self.hospital.to_dict() if self.hospital else None,
            "blood_bank": self.blood_bank.to_dict() if self.blood_bank else None,
            "road_network": self.road_network.to_dict() if self.road_network else None,
            "staff": [s.to_dict() for s in self.staff]
        }


@dataclass
class OutcomeProjection:
    """Projected outcomes with and without interventions."""
    baseline_probability: float
    with_current_interventions: float
    with_recommended_actions: float
    time_saved_minutes: float
    risk_factors: List[str] = field(default_factory=list)
    critical_time_points: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "baseline_probability": self.baseline_probability,
            "with_current_interventions": self.with_current_interventions,
            "with_recommended_actions": self.with_recommended_actions,
            "time_saved_minutes": self.time_saved_minutes,
            "risk_factors": self.risk_factors,
            "critical_time_points": self.critical_time_points
        }


@dataclass
class ActionableResponseAnalysis:
    """Complete analysis with actionable recommendations."""
    case_id: str
    severity: EmergencySeverity
    emergency_type: EmergencyType
    patient_info: Dict[str, Any]
    location: Dict[str, float]
    time_window_minutes: float
    time_remaining_minutes: float
    estimated_response_time_minutes: float
    is_feasible: bool

    # Real-time status
    response_chain_status: ResponseChainStatus = None

    # Analysis components
    bottlenecks: List[BottleneckAnalysis] = field(default_factory=list)
    recommendations: List[ActionableRecommendation] = field(default_factory=list)
    scenarios: List[InterventionScenario] = field(default_factory=list)

    # Outcome projections
    outcome_projection: Optional[OutcomeProjection] = None

    # Risk assessment
    risk_factors: List[str] = field(default_factory=list)
    critical_warnings: List[str] = field(default_factory=list)

    # Metadata
    success_probability: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    simulation_time_minutes: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "severity": self.severity.value,
            "emergency_type": self.emergency_type.value,
            "patient_info": self.patient_info,
            "location": self.location,
            "time_window_minutes": self.time_window_minutes,
            "time_remaining_minutes": self.time_remaining_minutes,
            "estimated_response_time_minutes": self.estimated_response_time_minutes,
            "is_feasible": self.is_feasible,
            "response_chain_status": self.response_chain_status.to_dict() if self.response_chain_status else None,
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "scenarios": [s.to_dict() for s in self.scenarios],
            "outcome_projection": self.outcome_projection.to_dict() if self.outcome_projection else None,
            "risk_factors": self.risk_factors,
            "critical_warnings": self.critical_warnings,
            "success_probability": self.success_probability,
            "timestamp": self.timestamp,
            "simulation_time_minutes": self.simulation_time_minutes
        }


class ActionableInterventionRecommender:
    """
    Generates mission-briefing style intervention recommendations.

    Features:
    - Real-time bottleneck detection with actual simulation data
    - Actionable recommendations with WHO/HOW/WHEN/Contacts
    - Alternative scenarios for decision making
    - Printable execution checklists
    - Before/after outcome projections
    """

    # Time thresholds (in minutes)
    CRITICAL_THRESHOLD = 10
    URGENT_THRESHOLD = 20
    STANDARD_THRESHOLD = 30

    # Emergency type response requirements
    RESPONSE_REQUIREMENTS = {
        EmergencyType.CORD_PROLAPSE: {
            "max_response": 15,
            "required_staff": ["obstetrician"],
            "required_blood": True,
            "critical_actions": ["emergency_delivery_setup", "transport_to_or"]
        },
        EmergencyType.UTERINE_RUPTURE: {
            "max_response": 15,
            "required_staff": ["obstetrician", "anesthesiologist"],
            "required_blood": True,
            "critical_actions": ["immediate_surgery", "blood_products"]
        },
        EmergencyType.PLACENTAL_ABRUPTION: {
            "max_response": 20,
            "required_staff": ["obstetrician"],
            "required_blood": True,
            "critical_actions": ["stabilization", "emergency_delivery"]
        },
        EmergencyType.ECLAMPSIA: {
            "max_response": 30,
            "required_staff": ["obstetrician", "neonatologist"],
            "required_blood": False,
            "critical_actions": ["seizure_management", "blood_pressure_control"]
        },
        EmergencyType.FETAL_DISTRESS: {
            "max_response": 30,
            "required_staff": ["obstetrician"],
            "required_blood": False,
            "critical_actions": ["fetal_monitoring", "emergency_csection"]
        },
        EmergencyType.MATERNAL_HEMORRHAGE: {
            "max_response": 20,
            "required_staff": ["obstetrician", "anesthesiologist"],
            "required_blood": True,
            "critical_actions": ["hemorrhage_control", "fluid_resuscitation", "blood_transfusion"]
        },
        EmergencyType.SHOULDER_DYSTOCIA: {
            "max_response": 15,
            "required_staff": ["obstetrician"],
            "required_blood": False,
            "critical_actions": ["mcroberts_maneuver", "episiotomy"]
        },
        EmergencyType.PREMATURE_LABOR: {
            "max_response": 45,
            "required_staff": ["obstetrician", "neonatologist"],
            "required_blood": False,
            "critical_actions": ["tocolysis", "corticosteroids", "nicu_prep"]
        },
        EmergencyType.OTHER: {
            "max_response": 30,
            "required_staff": ["obstetrician"],
            "required_blood": False,
            "critical_actions": ["stabilization", "transport"]
        }
    }

    # Role-based actors for different actions
    ACTION_ACTORS = {
        "or_clearance": ["Hospital Administrator", "OR Manager", "Chief of Surgery"],
        "staff_alert": ["Nursing Supervisor", "Department Head", "On-call Coordinator"],
        "blood_bank": ["Blood Bank Manager", "Transfusion Officer", "Laboratory Technician"],
        "ambulance_dispatch": ["EMS Dispatch Supervisor", "Ambulance Coordinator"],
        "traffic": ["Traffic Control Center", "Police Dispatch"],
        "hospital_alert": ["Emergency Department Director", "Charge Nurse"],
        "specialist_call": ["Medical Director", "Chief of Staff", "Department Secretary"]
    }

    def __init__(self):
        self._bottleneck_counter = 0
        self._recommendation_counter = 0
        self._scenario_counter = 0

    def analyze(
        self,
        case_id: str,
        signal: DistressSignal,
        time_remaining_minutes: float,
        simulation_time_minutes: float,
        ambulance_agent: Optional[AmbulanceAgent] = None,
        hospital_agent: Optional[HospitalAgent] = None,
        staff_agents: Optional[List[StaffAgent]] = None,
        blood_bank_agent: Optional[BloodBankAgent] = None,
        road_network_agent: Optional[RoadNetworkAgent] = None,
        alternative_hospitals: Optional[List[Tuple[Hospital, HospitalAgent]]] = None
    ) -> ActionableResponseAnalysis:
        """
        Perform comprehensive analysis and generate actionable recommendations.

        Args:
            case_id: Case identifier
            signal: The distress signal with patient details
            time_remaining_minutes: Time until critical threshold
            simulation_time_minutes: Current simulation time
            ambulance_agent: Active ambulance agent (if dispatched)
            hospital_agent: Target hospital agent
            staff_agents: Available staff agents
            blood_bank_agent: Associated blood bank agent
            road_network_agent: Road network for routing info
            alternative_hospitals: List of (hospital, agent) tuples for diversion options

        Returns:
            ActionableResponseAnalysis with all recommendations
        """
        logger.info(f"Analyzing actionable interventions for case: {case_id}")

        # Get requirements for this emergency type
        requirements = self.RESPONSE_REQUIREMENTS.get(
            signal.emergency_type,
            self.RESPONSE_REQUIREMENTS[EmergencyType.OTHER]
        )

        # Build real-time status from simulation data
        status = self._build_response_chain_status(
            ambulance_agent, hospital_agent, staff_agents,
            blood_bank_agent, road_network_agent
        )

        # Identify bottlenecks with real data
        bottlenecks = self._identify_bottlenecks(
            status, requirements, time_remaining_minutes,
            ambulance_agent, hospital_agent, blood_bank_agent
        )

        # Calculate estimated response time
        estimated_time = self._calculate_estimated_response_time(status, bottlenecks)

        # Determine feasibility
        is_feasible = estimated_time <= time_remaining_minutes

        # Calculate success probability
        base_prob = self._calculate_success_probability(
            signal.severity, time_remaining_minutes, estimated_time, bottlenecks
        )

        # Generate actionable recommendations
        recommendations = self._generate_actionable_recommendations(
            bottlenecks, status, requirements, time_remaining_minutes,
            base_prob, ambulance_agent, hospital_agent,
            alternative_hospitals, blood_bank_agent, staff_agents
        )

        # Generate alternative scenarios
        scenarios = self._generate_scenarios(
            recommendations, base_prob, time_remaining_minutes, bottlenecks
        )

        # Calculate outcome projections
        outcome_projection = self._calculate_outcome_projection(
            base_prob, recommendations, time_remaining_minutes, bottlenecks
        )

        # Identify risk factors and critical warnings
        risk_factors = self._identify_risk_factors(status, bottlenecks, time_remaining_minutes)
        critical_warnings = self._generate_critical_warnings(
            bottlenecks, time_remaining_minutes, is_feasible
        )

        analysis = ActionableResponseAnalysis(
            case_id=case_id,
            severity=signal.severity,
            emergency_type=signal.emergency_type,
            patient_info={
                "gestational_age_weeks": signal.patient.gestational_age_weeks if signal.patient else None,
                "blood_type": getattr(signal.patient, 'blood_type', 'Unknown') if signal.patient else 'Unknown',
                "conditions": getattr(signal.patient, 'conditions', []) if signal.patient else []
            },
            location={"lat": signal.location.lat, "lng": signal.location.lng},
            time_window_minutes=signal.time_window_minutes,
            time_remaining_minutes=time_remaining_minutes,
            estimated_response_time_minutes=estimated_time,
            is_feasible=is_feasible,
            response_chain_status=status,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            scenarios=scenarios,
            outcome_projection=outcome_projection,
            risk_factors=risk_factors,
            critical_warnings=critical_warnings,
            success_probability=base_prob,
            simulation_time_minutes=simulation_time_minutes
        )

        logger.info(
            f"Actionable analysis complete for {case_id}: "
            f"feasible={is_feasible}, success={base_prob:.0%}, "
            f"bottlenecks={len(bottlenecks)}, recommendations={len(recommendations)}"
        )

        return analysis

    def _build_response_chain_status(
        self,
        ambulance_agent: Optional[AmbulanceAgent],
        hospital_agent: Optional[HospitalAgent],
        staff_agents: Optional[List[StaffAgent]],
        blood_bank_agent: Optional[BloodBankAgent],
        road_network_agent: Optional[RoadNetworkAgent]
    ) -> ResponseChainStatus:
        """Build real-time status from simulation agents."""
        status = ResponseChainStatus()

        # Ambulance status
        if ambulance_agent:
            eta_report = ambulance_agent.get_eta_report()
            location = eta_report.get("current_location")
            status.ambulance = ResourceStatus(
                resource_id=ambulance_agent.agent_id,
                resource_name=ambulance_agent.name,
                resource_type="ambulance",
                current_state=eta_report.get("current_state", "unknown"),
                location=location,
                eta_minutes=eta_report.get("eta_to_patient") or eta_report.get("eta_to_hospital"),
                availability="busy" if ambulance_agent.current_state != "available" else "available",
                details={
                    "patient_id": eta_report.get("patient_id"),
                    "hospital_id": eta_report.get("hospital_id"),
                    "route_status": eta_report.get("route_status"),
                    "reroute_count": eta_report.get("reroute_count", 0),
                    "has_paramedic": eta_report.get("has_paramedic", False)
                }
            )

        # Hospital status
        if hospital_agent:
            avail_report = hospital_agent.get_availability_report()
            hosp = hospital_agent.hospital
            status.hospital = ResourceStatus(
                resource_id=hospital_agent.agent_id,
                resource_name=hospital_agent.name,
                resource_type="hospital",
                current_state=avail_report.get("current_state", "unknown"),
                availability="available" if avail_report.get("can_receive", False) else "limited",
                details={
                    "level": avail_report.get("level"),
                    "ot_available": avail_report.get("ot_available"),
                    "ot_reserved": avail_report.get("ot_reserved"),
                    "ot_total": avail_report.get("ot_total"),
                    "staff_on_call": avail_report.get("staff_on_call", 0),
                    "staff_confirmed": avail_report.get("staff_confirmed", 0),
                    "incoming_ambulances": avail_report.get("incoming_ambulances", 0),
                    "ot_ready_time": avail_report.get("ot_ready_time")
                },
                contact=ContactInfo(
                    name=hosp.name,
                    role="Receiving Hospital",
                    phone=hosp.contact_phone,
                    location=hosp.location.address
                )
            )

        # Blood bank status
        if blood_bank_agent:
            bb = blood_bank_agent.blood_bank
            status.blood_bank = ResourceStatus(
                resource_id=blood_bank_agent.agent_id,
                resource_name=blood_bank_agent.name,
                resource_type="blood_bank",
                current_state=blood_bank_agent.current_state,
                availability="available" if blood_bank_agent.current_state == "available" else "limited",
                details={
                    "inventory": bb.inventory,
                    "status": bb.status.value
                }
            )

        # Staff status
        if staff_agents:
            for staff in staff_agents:
                s = staff.staff
                status.staff.append(ResourceStatus(
                    resource_id=staff.agent_id,
                    resource_name=s.name,
                    resource_type="staff",
                    current_state=staff.current_state,
                    availability="on_call" if s.on_call else "off_duty",
                    details={
                        "specialization": s.specialization.value,
                        "hospital_id": s.hospital_id,
                        "response_time_minutes": s.response_time_minutes
                    },
                    contact=ContactInfo(
                        name=s.name,
                        role=s.specialization.value.title(),
                        phone=s.contact_phone,
                        location=s.hospital_id or ""
                    )
                ))

        # Road network status
        if road_network_agent:
            route_conditions = []
            if hasattr(road_network_agent, '_routes'):
                for route_id, route in road_network_agent._routes.items():
                    condition = getattr(route, 'worst_condition', RoadCondition.CLEAR)
                    route_conditions.append({
                        "route_id": route_id,
                        "name": getattr(route, 'name', route_id),
                        "condition": condition.value
                    })

            status.road_network = ResourceStatus(
                resource_id="road_network",
                resource_name="City Road Network",
                resource_type="road",
                current_state="active",
                details={"routes": route_conditions}
            )

        return status

    def _identify_bottlenecks(
        self,
        status: ResponseChainStatus,
        requirements: Dict[str, Any],
        time_remaining: float,
        ambulance_agent: Optional[AmbulanceAgent],
        hospital_agent: Optional[HospitalAgent],
        blood_bank_agent: Optional[BloodBankAgent]
    ) -> List[BottleneckAnalysis]:
        """Identify bottlenecks with real simulation data."""
        bottlenecks = []

        # Check ambulance availability and ETA
        if status.ambulance:
            amb = status.ambulance
            if amb.current_state != "available" and amb.current_state != "returning":
                # Ambulance is busy
                eta = amb.eta_minutes or 20
                if eta > time_remaining:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        severity=BottleneckSeverity.CRITICAL,
                        location_type="ambulance",
                        resource_id=amb.resource_id,
                        resource_name=amb.resource_name,
                        issue_description=f"Ambulance {amb.resource_name} will not reach patient in time",
                        current_status=f"State: {amb.current_state}, ETA: {eta:.1f} min",
                        estimated_delay_minutes=max(0, eta - time_remaining),
                        impact_on_patient="Transport to hospital will be delayed beyond critical window",
                        affected_resources=["patient", "hospital"],
                        resolution_options=[
                            "Request backup ambulance",
                            "Divert from current mission"
                        ],
                        urgency_reason=f"Only {time_remaining:.1f} minutes remaining before critical threshold"
                    ))

        # Check hospital OR availability
        if status.hospital:
            hosp = status.hospital
            ot_available = hosp.details.get("ot_available", 0)
            ot_reserved = hosp.details.get("ot_reserved", 0)

            if ot_available <= 0:
                self._bottleneck_counter += 1
                ot_ready_time = hosp.details.get("ot_ready_time")
                delay_reason = "OR occupied" if ot_reserved > 0 else "No OR available"

                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                    severity=BottleneckSeverity.CRITICAL,
                    location_type="hospital_or",
                    resource_id=hosp.resource_id,
                    resource_name=f"{hosp.resource_name} Operating Room",
                    issue_description=f"Operating room not available - {delay_reason}",
                    current_status=f"OT Available: {ot_available}, Reserved: {ot_reserved}",
                    estimated_delay_minutes=15 if ot_reserved > 0 else 30,
                    impact_on_patient="Emergency surgery cannot be performed on arrival",
                    affected_resources=["patient", "ambulance"],
                    resolution_options=[
                        "Clear OR for emergency",
                        "Divert to alternative hospital",
                        "Wait for current surgery to complete"
                    ],
                    urgency_reason="C-section requires immediate OR availability"
                ))

            # Check hospital capacity
            if hosp.details.get("incoming_ambulances", 0) > 2:
                self._bottleneck_counter += 1
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                    severity=BottleneckSeverity.HIGH,
                    location_type="hospital",
                    resource_id=hosp.resource_id,
                    resource_name=hosp.resource_name,
                    issue_description="High volume of incoming emergencies",
                    current_status=f"{hosp.details.get('incoming_ambulances')} ambulances en route",
                    estimated_delay_minutes=10,
                    impact_on_patient="Extended wait time for triage and admission",
                    affected_resources=["patient"],
                    resolution_options=["Alert additional staff", "Prepare overflow area"],
                    urgency_reason="Multiple concurrent emergencies strain resources"
                ))

        # Check staff availability
        if status.staff:
            required_specializations = [s.lower() for s in requirements.get("required_staff", [])]
            for spec in required_specializations:
                matching_staff = [s for s in status.staff if spec in s.details.get("specialization", "").lower()]
                available_staff = [s for s in matching_staff if s.availability == "on_call"]

                if not available_staff:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        severity=BottleneckSeverity.HIGH,
                        location_type="staff",
                        resource_id=f"staff_{spec}",
                        resource_name=f"{spec.title()} (any available)",
                        issue_description=f"No {spec} available - all on-call staff busy or off-duty",
                        current_status=f"Required: {spec}, Available: {len(available_staff)}",
                        estimated_delay_minutes=15,
                        impact_on_patient=f"Required {spec} procedure cannot be performed",
                        affected_resources=["patient", "hospital"],
                        resolution_options=[
                            f"Call in off-duty {spec}",
                            f"Transfer to hospital with available {spec}",
                            "Escalate to medical director"
                        ],
                        urgency_reason=f"Emergency requires {spec} for life-saving procedure"
                    ))

        # Check blood availability
        if requirements.get("required_blood") and status.blood_bank:
            blood = status.blood_bank
            inventory = blood.details.get("inventory", {})

            # Check for critical blood types
            critical_types = ["o_negative", "o_positive"]
            has_sufficient = any(inventory.get(bt, 0) >= 2 for bt in critical_types)

            if not has_sufficient:
                self._bottleneck_counter += 1
                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                    severity=BottleneckSeverity.HIGH,
                    location_type="blood_bank",
                    resource_id=blood.resource_id,
                    resource_name=blood.resource_name or "Regional Blood Bank",
                    issue_description="Insufficient blood products for hemorrhage emergency",
                    current_status=f"O-negative: {inventory.get('o_negative', 0)}, O-positive: {inventory.get('o_positive', 0)}",
                    estimated_delay_minutes=20,
                    impact_on_patient="Transfusion cannot be performed if needed",
                    affected_resources=["patient"],
                    resolution_options=[
                        "Request from regional blood bank",
                        "Divert to hospital with blood supply",
                        "Request emergency blood delivery"
                    ],
                    urgency_reason="Maternal hemorrhage requires blood products within minutes"
                ))

        # Check road conditions
        if status.road_network:
            routes = status.road_network.details.get("routes", [])
            problematic_routes = [r for r in routes if r.get("condition") in ["heavy", "blocked", "moderate"]]

            for route in problematic_routes:
                self._bottleneck_counter += 1
                condition = route.get("condition", "unknown")
                delay = 15 if condition == "blocked" else (10 if condition == "heavy" else 5)

                bottlenecks.append(BottleneckAnalysis(
                    bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                    severity=BottleneckSeverity.MEDIUM if condition != "blocked" else BottleneckSeverity.HIGH,
                    location_type="road",
                    resource_id=route.get("route_id", "unknown"),
                    resource_name=route.get("name", "Route"),
                    issue_description=f"Road condition: {condition.title()}",
                    current_status=condition,
                    estimated_delay_minutes=delay,
                    impact_on_patient="Increased transport time to hospital",
                    affected_resources=["ambulance", "patient"],
                    resolution_options=[
                        "Use alternate route",
                        "Request traffic police clearance",
                        "Activate emergency vehicle priority"
                    ],
                    urgency_reason="Every minute of delay reduces success probability"
                ))

        return bottlenecks

    def _calculate_estimated_response_time(
        self,
        status: ResponseChainStatus,
        bottlenecks: List[BottleneckAnalysis]
    ) -> float:
        """Calculate estimated total response time."""
        base_time = 0.0

        # Add ambulance ETA if available
        if status.ambulance and status.ambulance.eta_minutes:
            base_time += status.ambulance.eta_minutes

        # Add hospital preparation time if OR not ready
        if status.hospital:
            ot_ready = status.hospital.details.get("ot_ready_time")
            if ot_ready is None and status.hospital.details.get("ot_available", 1) <= 0:
                base_time += 10  # OT prep time

        # Add bottleneck delays
        bottleneck_delay = sum(b.estimated_delay_minutes for b in bottlenecks)

        return base_time + bottleneck_delay

    def _calculate_success_probability(
        self,
        severity: EmergencySeverity,
        time_remaining: float,
        estimated_time: float,
        bottlenecks: List[BottleneckAnalysis]
    ) -> float:
        """Calculate probability of successful intervention."""
        if time_remaining <= 0:
            return 0.0

        time_ratio = estimated_time / time_remaining if time_remaining > 0 else 1.0

        # Base probability from time
        if time_ratio <= 0.5:
            base_prob = 0.9
        elif time_ratio <= 1.0:
            base_prob = 0.7
        else:
            base_prob = max(0.05, 1.0 - (time_ratio - 1.0) * 0.4)

        # Adjust for severity
        severity_factor = {
            EmergencySeverity.CRITICAL: 0.6,
            EmergencySeverity.SEVERE: 0.8,
            EmergencySeverity.MODERATE: 0.95,
            EmergencySeverity.LOW: 1.0
        }.get(severity, 0.8)

        # Adjust for bottlenecks
        critical_bottlenecks = [b for b in bottlenecks if b.severity == BottleneckSeverity.CRITICAL]
        bottleneck_factor = 1.0 - (len(critical_bottlenecks) * 0.25) - (len(bottlenecks) * 0.05)

        return max(0.0, min(1.0, base_prob * severity_factor * max(0.3, bottleneck_factor)))

    def _generate_actionable_recommendations(
        self,
        bottlenecks: List[BottleneckAnalysis],
        status: ResponseChainStatus,
        requirements: Dict[str, Any],
        time_remaining: float,
        base_prob: float,
        ambulance_agent: Optional[AmbulanceAgent],
        hospital_agent: Optional[HospitalAgent],
        alternative_hospitals: Optional[List[Tuple[Hospital, HospitalAgent]]],
        blood_bank_agent: Optional[BloodBankAgent],
        staff_agents: Optional[List[StaffAgent]]
    ) -> List[ActionableRecommendation]:
        """Generate actionable recommendations with specific steps."""
        recommendations = []

        for bottleneck in bottlenecks:
            rec = self._create_recommendation_for_bottleneck(
                bottleneck, status, time_remaining, base_prob,
                ambulance_agent, hospital_agent, alternative_hospitals,
                blood_bank_agent, staff_agents
            )
            if rec:
                recommendations.append(rec)

        # Sort by priority
        recommendations.sort(key=lambda r: r.priority.value)

        return recommendations

    def _create_recommendation_for_bottleneck(
        self,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        time_remaining: float,
        base_prob: float,
        ambulance_agent: Optional[AmbulanceAgent],
        hospital_agent: Optional[HospitalAgent],
        alternative_hospitals: Optional[List[Tuple[Hospital, HospitalAgent]]],
        blood_bank_agent: Optional[BloodBankAgent],
        staff_agents: Optional[List[StaffAgent]]
    ) -> Optional[ActionableRecommendation]:
        """Create detailed recommendation for a specific bottleneck."""
        self._recommendation_counter += 1
        rec_id = f"rec_{self._recommendation_counter:04d}"

        if bottleneck.location_type == "hospital_or":
            return self._create_or_clearance_recommendation(
                rec_id, bottleneck, status, hospital_agent, alternative_hospitals, time_remaining, base_prob
            )

        elif bottleneck.location_type == "ambulance":
            return self._create_ambulance_recommendation(
                rec_id, bottleneck, status, ambulance_agent, time_remaining, base_prob
            )

        elif bottleneck.location_type == "staff":
            return self._create_staff_recommendation(
                rec_id, bottleneck, status, staff_agents, time_remaining, base_prob
            )

        elif bottleneck.location_type == "blood_bank":
            return self._create_blood_recommendation(
                rec_id, bottleneck, status, blood_bank_agent, time_remaining, base_prob
            )

        elif bottleneck.location_type == "road":
            return self._create_traffic_recommendation(
                rec_id, bottleneck, status, ambulance_agent, time_remaining, base_prob
            )

        return None

    def _create_or_clearance_recommendation(
        self,
        rec_id: str,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        hospital_agent: Optional[HospitalAgent],
        alternative_hospitals: Optional[List[Tuple[Hospital, HospitalAgent]]],
        time_remaining: float,
        base_prob: float
    ) -> ActionableRecommendation:
        """Create OR clearance or diversion recommendation."""
        hosp = status.hospital
        hosp_name = hosp.resource_name if hosp else "Target Hospital"

        steps = []

        # Step 1: Contact hospital administrator
        steps.append(ActionStep(
            step_number=1,
            action="Call Hospital Administrator NOW",
            actor="EMS Dispatch / On-call Coordinator",
            method="Use emergency contact line to reach hospital administration immediately",
            estimated_time_minutes=2,
            checklist_items=[
                "Dial emergency hospital line",
                "Request immediate connection to Hospital Administrator",
                "State: 'Critical obstetric emergency, OR clearance needed'"
            ],
            contacts=[ContactInfo(
                name="Hospital Administrator",
                role="Decision Maker",
                phone=hosp.details.get("contact", {}).get("phone", "") if hosp else "",
                availability="on_duty"
            )]
        ))

        # Step 2: Identify alternative hospital
        alt_options = []
        if alternative_hospitals:
            for alt_hosp, _ in alternative_hospitals[:2]:
                alt_options.append(f"{alt_hosp.name}: {alt_hosp.contact_phone}")

        # Step 3: Decision tree
        steps.append(ActionStep(
            step_number=2,
            action="Assess OR availability and make decision",
            actor="Hospital Administrator / Medical Director",
            method="Check current OR schedule and patient status to determine if clearance is feasible",
            estimated_time_minutes=3,
            dependencies=["Step 1"],
            checklist_items=[
                "Check current surgeries in progress",
                "Identify non-emergency cases that can be postponed",
                "Estimate time to clear OR"
            ]
        ))

        # Calculate improvement
        time_saved = min(bottleneck.estimated_delay_minutes, 15)
        improved_prob = min(0.95, base_prob + 0.3)

        recommendation = ActionableRecommendation(
            recommendation_id=rec_id,
            intervention_type=InterventionType.PREPARE_OR,
            priority=InterventionPriority.CRITICAL,
            title="OR CLEARANCE PROTOCOL",
            summary=f"Clear operating room at {hosp_name} for emergency C-section",
            action_steps=steps,
            target_resource_id=hosp.resource_id if hosp else None,
            target_resource_name=hosp_name,
            expected_outcome="Operating room ready for emergency surgery on patient arrival",
            time_saved_minutes=time_saved,
            confidence_score=0.8,
            success_probability_before=base_prob,
            success_probability_after=improved_prob,
            alternatives=[
                f"Diversion to alternative: {alt_options[0]}" if alt_options else "No alternative available",
                "Wait for current surgery completion (may exceed time window)"
            ]
        )

        return recommendation

    def _create_ambulance_recommendation(
        self,
        rec_id: str,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        ambulance_agent: Optional[AmbulanceAgent],
        time_remaining: float,
        base_prob: float
    ) -> ActionableRecommendation:
        """Create ambulance backup/diversion recommendation."""
        amb = status.ambulance
        steps = []

        steps.append(ActionStep(
            step_number=1,
            action="Dispatch backup ambulance immediately",
            actor="EMS Dispatch Supervisor",
            method="Use secondary ambulance fleet or mutual aid from neighboring zone",
            estimated_time_minutes=1,
            checklist_items=[
                "Check available ambulance inventory",
                "Dispatch nearest available unit",
                "Update original ambulance to stand down if needed"
            ]
        ))

        steps.append(ActionStep(
            step_number=2,
            action="Radio current ambulance crew",
            actor="EMS Dispatch",
            method="Communicate backup dispatch and update ETA to patient",
            estimated_time_minutes=1,
            dependencies=["Step 1"],
            checklist_items=[
                "Contact ambulance via radio",
                "Confirm new ETA with backup unit",
                "Update hospital with new timeline"
            ]
        ))

        time_saved = min(bottleneck.estimated_delay_minutes, 10)
        improved_prob = min(0.85, base_prob + 0.25)

        return ActionableRecommendation(
            recommendation_id=rec_id,
            intervention_type=InterventionType.REQUEST_BACKUP_AMBULANCE,
            priority=InterventionPriority.HIGH,
            title="BACKUP AMBULANCE DISPATCH",
            summary=f"Request additional ambulance due to ETA delay",
            action_steps=steps,
            target_resource_id=amb.resource_id if amb else "ems_dispatch",
            target_resource_name=amb.resource_name if amb else "EMS Dispatch",
            expected_outcome="Second ambulance en route to patient",
            time_saved_minutes=time_saved,
            confidence_score=0.85,
            success_probability_before=base_prob,
            success_probability_after=improved_prob
        )

    def _create_staff_recommendation(
        self,
        rec_id: str,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        staff_agents: Optional[List[StaffAgent]],
        time_remaining: float,
        base_prob: float
    ) -> ActionableRecommendation:
        """Create staff call-in recommendation."""
        spec = bottleneck.resource_name.replace(" (any available)", "")

        steps = []

        # Find matching staff contacts
        matching_staff = [s for s in (status.staff or []) if spec.lower() in s.resource_name.lower()]
        staff_contacts = [
            ContactInfo(
                name=s.resource_name,
                role=s.details.get("specialization", spec).title(),
                phone=s.contact.phone if s.contact else "",
                location=s.contact.location if s.contact else ""
            )
            for s in matching_staff[:3]
        ]

        steps.append(ActionStep(
            step_number=1,
            action=f"Call in {spec} from off-duty roster",
            actor="Department Secretary / Medical Director",
            method="Contact off-duty staff and request immediate response",
            estimated_time_minutes=2,
            contacts=staff_contacts if staff_contacts else [ContactInfo(
                name=f"Any Available {spec}",
                role="Medical Staff"
            )],
            checklist_items=[
                f"Access off-duty {spec} contact list",
                "Call in priority order (nearest first)",
                "Offer transport if staff needs ride"
            ]
        ))

        steps.append(ActionStep(
            step_number=2,
            action=f"Confirm {spec} response and ETA",
            actor="Calling Coordinator",
            method="Get confirmation from staff member and estimated arrival time",
            estimated_time_minutes=2,
            dependencies=["Step 1"],
            checklist_items=[
                "Confirm staff will respond",
                "Get estimated arrival time",
                "Alert hospital of staff ETA"
            ]
        ))

        time_saved = bottleneck.estimated_delay_minutes
        improved_prob = min(0.9, base_prob + 0.2)

        return ActionableRecommendation(
            recommendation_id=rec_id,
            intervention_type=InterventionType.REQUEST_SPECIALIST,
            priority=InterventionPriority.CRITICAL,
            title=f"{spec.upper()} MOBILIZATION",
            summary=f"Call in {spec} for emergency procedure",
            action_steps=steps,
            target_resource_id=bottleneck.resource_id,
            target_resource_name=bottleneck.resource_name,
            expected_outcome=f"Qualified {spec} available for procedure",
            time_saved_minutes=time_saved,
            confidence_score=0.75,
            success_probability_before=base_prob,
            success_probability_after=improved_prob,
            alternatives=[
                "Transfer patient to hospital with available specialist",
                "Use telemedicine guidance from remote specialist"
            ]
        )

    def _create_blood_recommendation(
        self,
        rec_id: str,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        blood_bank_agent: Optional[BloodBankAgent],
        time_remaining: float,
        base_prob: float
    ) -> ActionableRecommendation:
        """Create blood supply recommendation."""
        blood = status.blood_bank
        steps = []

        steps.append(ActionStep(
            step_number=1,
            action="Check current blood inventory and request emergency stock",
            actor="Blood Bank Manager / Transfusion Officer",
            method="Verify current inventory and place emergency order",
            estimated_time_minutes=3,
            checklist_items=[
                "Confirm patient blood type if known",
                "Check O-negative emergency stock",
                "Request 4 units minimum for hemorrhage"
            ]
        ))

        steps.append(ActionStep(
            step_number=2,
            action="Arrange emergency blood delivery",
            actor="Blood Bank Logistics",
            method="Use dedicated courier or hospital drone for rapid delivery",
            estimated_time_minutes=5,
            dependencies=["Step 1"],
            checklist_items=[
                "Dispatch courier immediately",
                "Track delivery ETA",
                "Confirm receipt at hospital"
            ]
        ))

        steps.append(ActionStep(
            step_number=3,
            action="Prepare for bedside transfusion",
            actor="Hospital Blood Bank",
            method="Pre-stage blood products for immediate transfusion on arrival",
            estimated_time_minutes=2,
            dependencies=["Step 2"],
            checklist_items=[
                "Thaw FFP if needed (takes 20-30 min, start NOW)",
                "Prepare transfusion set",
                "Alert nursing station"
            ]
        ))

        time_saved = 10  # Preparedness saves time at critical moment
        improved_prob = min(0.85, base_prob + 0.15)

        return ActionableRecommendation(
            recommendation_id=rec_id,
            intervention_type=InterventionType.SECURE_BLOOD,
            priority=InterventionPriority.HIGH,
            title="EMERGENCY BLOOD MOBILIZATION",
            summary="Secure blood products for hemorrhage response",
            action_steps=steps,
            target_resource_id=blood.resource_id if blood else "blood_bank",
            target_resource_name=blood.resource_name if blood else "Regional Blood Bank",
            expected_outcome="Blood products available within 15 minutes",
            time_saved_minutes=time_saved,
            confidence_score=0.8,
            success_probability_before=base_prob,
            success_probability_after=improved_prob,
            alternatives=[
                "Use cell saver during surgery if available",
                "Request blood from nearby hospital"
            ]
        )

    def _create_traffic_recommendation(
        self,
        rec_id: str,
        bottleneck: BottleneckAnalysis,
        status: ResponseChainStatus,
        ambulance_agent: Optional[AmbulanceAgent],
        time_remaining: float,
        base_prob: float
    ) -> ActionableRecommendation:
        """Create traffic clearance recommendation."""
        steps = []

        steps.append(ActionStep(
            step_number=1,
            action="Request emergency traffic clearance",
            actor="EMS Dispatch",
            method="Contact traffic control center or police dispatch for road clearance",
            estimated_time_minutes=2,
            checklist_items=[
                "Call traffic control: 100 (India) or local emergency number",
                "Provide exact location and route",
                "Request traffic lights to green for ambulance"
            ]
        ))

        steps.append(ActionStep(
            step_number=2,
            action="Activate ambulance priority system",
            actor="Traffic Engineering",
            method="Enable emergency vehicle preemption on traffic signals",
            estimated_time_minutes=1,
            dependencies=["Step 1"],
            checklist_items=[
                "Verify ambulance GPS tracking active",
                "Enable signal preemption",
                "Monitor ambulance progress"
            ]
        ))

        time_saved = bottleneck.estimated_delay_minutes * 0.6
        improved_prob = min(0.85, base_prob + 0.15)

        return ActionableRecommendation(
            recommendation_id=rec_id,
            intervention_type=InterventionType.TRAFFIC_CLEARANCE,
            priority=InterventionPriority.MEDIUM if bottleneck.severity != BottleneckSeverity.HIGH else InterventionPriority.HIGH,
            title="TRAFFIC CLEARANCE FOR AMBULANCE",
            summary=f"Clear congested route: {bottleneck.resource_name}",
            action_steps=steps,
            target_resource_id=bottleneck.resource_id,
            target_resource_name=bottleneck.resource_name,
            expected_outcome="Reduced transit time through cleared route",
            time_saved_minutes=time_saved,
            confidence_score=0.7,
            success_probability_before=base_prob,
            success_probability_after=improved_prob,
            alternatives=[
                "Use alternate route (adds 3-5 minutes)",
                "Police escort through traffic"
            ]
        )

    def _generate_scenarios(
        self,
        recommendations: List[ActionableRecommendation],
        base_prob: float,
        time_remaining: float,
        bottlenecks: List[BottleneckAnalysis]
    ) -> List[InterventionScenario]:
        """Generate alternative intervention scenarios."""
        scenarios = []

        # Scenario 1: No intervention (baseline)
        self._scenario_counter += 1
        scenarios.append(InterventionScenario(
            scenario_id=f"scenario_{self._scenario_counter:03d}",
            scenario_name="NO INTERVENTION (BASELINE)",
            description="Continue current response without additional actions",
            interventions=[],
            success_probability=base_prob,
            time_to_implement_minutes=0,
            pros=["No additional coordination required"],
            cons=[f"Only {base_prob:.0%} success probability", "Patient outcomes depend on current bottlenecks"],
            recommended=False
        ))

        # Scenario 2: Clear OR (if OR bottleneck exists)
        or_bottlenecks = [b for b in bottlenecks if b.location_type == "hospital_or"]
        if or_bottlenecks:
            self._scenario_counter += 1
            or_recs = [r for r in recommendations if r.intervention_type == InterventionType.PREPARE_OR]
            scenarios.append(InterventionScenario(
                scenario_id=f"scenario_{self._scenario_counter:03d}",
                scenario_name="OR CLEARANCE AT TARGET HOSPITAL",
                description="Clear operating room at current destination hospital",
                interventions=or_recs,
                success_probability=max(r.success_probability_after for r in or_recs) if or_recs else base_prob + 0.3,
                time_to_implement_minutes=sum(r.get_total_time() for r in or_recs),
                risks=["May not complete in time", "Requires hospital cooperation"],
                pros=["Avoids transport delay", "Familiar staff and equipment"],
                cons=["Time pressure on hospital staff"],
                recommended=True
            ))

        # Scenario 3: Hospital diversion (if alternatives exist)
        self._scenario_counter += 1
        div_recs = [r for r in recommendations if r.intervention_type == InterventionType.ACTIVATE_NEARBY_HOSPITAL]
        scenarios.append(InterventionScenario(
            scenario_id=f"scenario_{self._scenario_counter:03d}",
            scenario_name="HOSPITAL DIVERSION",
            description="Transfer patient to alternative hospital with available resources",
            interventions=div_recs,
            success_probability=min(0.9, base_prob + 0.4),
            time_to_implement_minutes=15,
            risks=["Longer transport time", "Unknown hospital protocols"],
            pros=["Guaranteed OR availability", "Fresh team"],
            cons=["Transport delay", "Less pre-alert time"],
            recommended=not or_bottlenecks
        ))

        return scenarios

    def _calculate_outcome_projection(
        self,
        base_prob: float,
        recommendations: List[ActionableRecommendation],
        time_remaining: float,
        bottlenecks: List[BottleneckAnalysis]
    ) -> OutcomeProjection:
        """Calculate outcome projections with and without interventions."""
        # Best case with all interventions
        max_improvement = max([r.success_probability_after for r in recommendations], default=0)
        with_all = max(base_prob + 0.3, max_improvement)

        # Calculate time savings
        total_time_saved = sum(r.time_saved_minutes for r in recommendations if r.priority in [InterventionPriority.CRITICAL, InterventionPriority.HIGH])

        # Identify critical time points
        critical_points = []
        if time_remaining < 10:
            critical_points.append({
                "time": f"{time_remaining:.0f} min remaining",
                "warning": "CRITICAL - Intervention window closing",
                "action": "Execute all critical interventions immediately"
            })

        # Add bottleneck-specific warnings
        for bn in bottlenecks:
            if bn.severity == BottleneckSeverity.CRITICAL:
                critical_points.append({
                    "time": f"Now",
                    "warning": f"Critical bottleneck: {bn.resource_name}",
                    "action": bn.urgency_reason
                })

        return OutcomeProjection(
            baseline_probability=base_prob,
            with_current_interventions=base_prob,
            with_recommended_actions=min(0.95, with_all),
            time_saved_minutes=total_time_saved,
            risk_factors=[bn.issue_description for bn in bottlenecks if bn.severity in [BottleneckSeverity.CRITICAL, BottleneckSeverity.HIGH]],
            critical_time_points=critical_points
        )

    def _identify_risk_factors(
        self,
        status: ResponseChainStatus,
        bottlenecks: List[BottleneckAnalysis],
        time_remaining: float
    ) -> List[str]:
        """Identify risk factors for the response."""
        risk_factors = []

        # Time-based risks
        if time_remaining < 10:
            risk_factors.append("CRITICAL: Less than 10 minutes to intervention window")

        if time_remaining < 20:
            risk_factors.append("URGENT: Time pressure on all response activities")

        # Bottleneck-based risks
        critical_count = len([b for b in bottlenecks if b.severity == BottleneckSeverity.CRITICAL])
        if critical_count >= 2:
            risk_factors.append(f"MULTIPLE CRITICAL BOTTLENECKS: {critical_count} critical issues identified")

        # Resource-based risks
        if any(b.location_type == "staff" for b in bottlenecks):
            risk_factors.append("STAFF SHORTAGE: Required specialist unavailable")

        if any(b.location_type == "blood_bank" for b in bottlenecks):
            risk_factors.append("BLOOD SUPPLY: Insufficient blood products for hemorrhage")

        if any(b.location_type == "hospital_or" for b in bottlenecks):
            risk_factors.append("OR CONGESTION: Operating room not available")

        # Patient-specific risks
        if status.hospital and status.hospital.details.get("incoming_ambulances", 0) > 2:
            risk_factors.append("HOSPITAL STRAIN: Multiple concurrent emergencies")

        return risk_factors

    def _generate_critical_warnings(
        self,
        bottlenecks: List[BottleneckAnalysis],
        time_remaining: float,
        is_feasible: bool
    ) -> List[str]:
        """Generate critical warning messages."""
        warnings = []

        if not is_feasible:
            warnings.append("RESPONSE NOT FEASIBLE: Estimated time exceeds intervention window")
            warnings.append("IMMEDIATE ACTION REQUIRED: Execute critical interventions now")

        if time_remaining < 5:
            warnings.append("FINAL WINDOW: Less than 5 minutes - every second counts")

        critical_bottlenecks = [b for b in bottlenecks if b.severity == BottleneckSeverity.CRITICAL]
        if critical_bottlenecks:
            warnings.append(f"CRITICAL ISSUES ({len(critical_bottlenecks)}):")
            for bn in critical_bottlenecks:
                warnings.append(f"  - {bn.resource_name}: {bn.issue_description}")

        return warnings


def generate_actionable_report(
    analysis: ActionableResponseAnalysis,
    format: ReportFormat = ReportFormat.DETAILED
) -> str:
    """
    Generate human-readable actionable intervention report.

    Args:
        analysis: The actionable response analysis
        format: Output format preference

    Returns:
        Formatted report string
    """
    if format == ReportFormat.JSON:
        import json
        return json.dumps(analysis.to_dict(), indent=2)

    elif format == ReportFormat.MARKDOWN:
        return _generate_markdown_report(analysis)

    elif format == ReportFormat.BRIEF:
        return _generate_brief_report(analysis)

    else:  # DETAILED
        return _generate_detailed_report(analysis)


def _generate_header() -> str:
    """Generate report header."""
    return """
╔═══════════════════════════════════════════════════════════════════════════════╗
║          OBSTETRIC EMERGENCY RESPONSE - ACTIONABLE INTERVENTION REPORT       ║
╚═══════════════════════════════════════════════════════════════════════════════╝"""


def _generate_detailed_report(analysis: ActionableResponseAnalysis) -> str:
    """Generate detailed mission-briefing style report."""
    lines = []

    # Header
    lines.append(_generate_header())
    lines.append("")

    # Case ID and Status
    case_tag = f"CASE #{analysis.case_id.upper()}"
    status_emoji = "❌" if not analysis.is_feasible else "⚠️"
    lines.append(f"┌─ {case_tag} {'─' * (76 - len(case_tag))}┐")
    lines.append(f"│ Status: {status_emoji} {'NOT FEASIBLE - INTERVENTION REQUIRED' if not analysis.is_feasible else 'FEASIBLE WITH RISK'} {'─' * (50 - len(analysis.case_id))}│")
    lines.append("└" + "─" * 78 + "┘")
    lines.append("")

    # Patient Context Section
    lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
    lines.append("│ PATIENT CONTEXT                                                              │")
    lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

    patient = analysis.patient_info
    lines.append(f"│ Emergency Type:  {analysis.emergency_type.value.replace('_', ' ').title():<58}│")
    lines.append(f"│ Severity:        {analysis.severity.value.upper():<58}│")
    if patient.get("gestational_age_weeks"):
        lines.append(f"│ Gestational Age: {patient['gestational_age_weeks']} weeks{'':<46}│")
    if patient.get("blood_type"):
        lines.append(f"│ Blood Type:      {patient['blood_type']:<58}│")
    lines.append(f"│ Location:        Lat {analysis.location.get('lat', 0):.4f}, Lng {analysis.location.get('lng', 0):.4f}{'':<28}│")
    lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

    # Time Analysis
    margin = analysis.time_remaining_minutes - analysis.estimated_response_time_minutes
    margin_str = f"{margin:+.1f} min" if margin >= 0 else f"{margin:.1f} min (EXCEEDED)"
    lines.append(f"│ TIME ANALYSIS                                                                │")
    lines.append(f"│   Time Window:      {analysis.time_window_minutes:.0f} minutes{'':<47}│")
    lines.append(f"│   Time Remaining:  {analysis.time_remaining_minutes:.1f} minutes{'':<47}│")
    lines.append(f"│   Est. Response:    {analysis.estimated_response_time_minutes:.1f} minutes{'':<46}│")
    lines.append(f"│   Margin:           {margin_str:<58}│")
    lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

    # Success Probability
    prob_bar = "█" * int(analysis.success_probability * 20) + "░" * (20 - int(analysis.success_probability * 20))
    lines.append(f"│ SUCCESS PROBABILITY: {analysis.success_probability:.0%} [{prob_bar}]   │")
    lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
    lines.append("")

    # Critical Warnings
    if analysis.critical_warnings:
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ ⚠️  CRITICAL WARNINGS                                                        │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")
        for warning in analysis.critical_warnings:
            if warning.startswith("  "):
                lines.append(f"│{warning:<79}│")
            elif warning.endswith(":"):
                lines.append(f"│ {warning:<78}│")
            else:
                lines.append(f"│ ⚠️ {warning:<76}│")
        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Response Chain Status
    if analysis.response_chain_status:
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ RESPONSE CHAIN STATUS                                                        │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

        status = analysis.response_chain_status

        # Ambulance
        if status.ambulance:
            amb = status.ambulance
            state_emoji = "🚑" if amb.current_state == "en_route_patient" else "⏳"
            lines.append(f"│ {state_emoji} AMBULANCE ({amb.resource_name})")
            lines.append(f"│    State: {amb.current_state:<20} ETA: {amb.eta_minutes:.1f} min" if amb.eta_minutes else f"│    State: {amb.current_state}")
            if amb.location:
                lines.append(f"│    Location: {amb.location.get('lat', 0):.4f}, {amb.location.get('lng', 0):.4f}")

        # Hospital
        if status.hospital:
            hosp = status.hospital
            ot_status = f"OT: {hosp.details.get('ot_available', 0)}/{hosp.details.get('ot_total', 0)}"
            lines.append(f"│ 🏥 HOSPITAL ({hosp.resource_name})")
            lines.append(f"│    State: {hosp.current_state:<20} {ot_status}")
            if hosp.contact:
                contact = hosp.contact
                if isinstance(contact, dict):
                    lines.append(f"│    Contact: {contact.get('phone', 'N/A')}")
                else:
                    lines.append(f"│    Contact: {contact.phone or 'N/A'}")

        # Blood Bank
        if status.blood_bank:
            blood = status.blood_bank
            o_neg = blood.details.get("inventory", {}).get("o_negative", 0)
            lines.append(f"│ 🩸 BLOOD BANK")
            lines.append(f"│    O-negative units: {o_neg}")

        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Bottlenecks
    if analysis.bottlenecks:
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ BOTTLENECK ANALYSIS                                                          │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

        for i, bn in enumerate(analysis.bottlenecks, 1):
            severity_indicator = "🔴" if bn.severity == BottleneckSeverity.CRITICAL else ("🟠" if bn.severity == BottleneckSeverity.HIGH else "🟡")
            lines.append(f"│ {severity_indicator} Bottleneck #{i}: {bn.resource_name}")
            lines.append(f"│    Issue: {bn.issue_description}")
            lines.append(f"│    Delay: {bn.estimated_delay_minutes:.0f} min | Impact: {bn.impact_on_patient}")

        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Actionable Recommendations
    if analysis.recommendations:
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ IMMEDIATE ACTIONS REQUIRED                                                   │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

        for i, rec in enumerate(analysis.recommendations, 1):
            priority_emoji = "🔴" if rec.priority == InterventionPriority.CRITICAL else ("🟠" if rec.priority == InterventionPriority.HIGH else "🟡")
            lines.append(f"│")
            lines.append(f"│ {priority_emoji} ACTION #{i}: {rec.title}")
            lines.append(f"│    Summary: {rec.summary}")
            lines.append(f"│    Time Saved: ~{rec.time_saved_minutes:.0f} min | Confidence: {rec.confidence_score:.0%}")
            lines.append(f"│")
            lines.append(f"│    STEPS:")

            for step in rec.action_steps:
                lines.append(f"│      {step.step_number}. {step.action}")
                if step.actor:
                    lines.append(f"│         WHO: {step.actor}")
                if step.method:
                    lines.append(f"│         HOW: {step.method}")
                if step.contacts:
                    for contact in step.contacts:
                        if contact.phone:
                            lines.append(f"│         📞 {contact.name}: {contact.phone}")
                lines.append(f"│         Time: ~{step.estimated_time_minutes:.0f} min")

            if rec.alternatives:
                lines.append(f"│    ALTERNATIVES:")
                for alt in rec.alternatives[:2]:
                    lines.append(f"│      • {alt}")

        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Execution Checklist
    if analysis.recommendations:
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ 📋 EXECUTION CHECKLIST (Print and Use)                                       │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")

        for rec in analysis.recommendations:
            for step_idx, step in enumerate(rec.action_steps, 1):
                for item_idx, item in enumerate(step.checklist_items, 1):
                    lines.append(f"│ [ ] {step.step_number}.{item_idx}. {item}")
                    if step.contacts and step.contacts[0].phone:
                        lines.append(f"│      → Call: {step.contacts[0].phone}")

        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Outcome Projection
    if analysis.outcome_projection:
        proj = analysis.outcome_projection
        lines.append("┌─────────────────────────────────────────────────────────────────────────────┐")
        lines.append("│ OUTCOME PROJECTIONS                                                          │")
        lines.append("├─────────────────────────────────────────────────────────────────────────────┤")
        lines.append(f"│ Without Intervention: {proj.baseline_probability:.0%} success probability")
        lines.append(f"│ With Recommended Actions: {proj.with_recommended_actions:.0%} success probability")
        lines.append(f"│ Potential Time Saved: ~{proj.time_saved_minutes:.0f} minutes")
        lines.append("└─────────────────────────────────────────────────────────────────────────────┘")
        lines.append("")

    # Footer
    lines.append("═" * 80)
    lines.append(f"Report Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Simulation Time: {analysis.simulation_time_minutes:.1f} min")
    lines.append("═" * 80)

    return "\n".join(lines)


def _generate_brief_report(analysis: ActionableResponseAnalysis) -> str:
    """Generate brief terminal-friendly report."""
    lines = []

    # Status line
    status = "NOT FEASIBLE" if not analysis.is_feasible else "FEASIBLE"
    lines.append(f"[{analysis.success_probability:.0%}] {status} | {analysis.time_remaining_minutes:.0f}min remaining")

    # Critical warnings
    for warning in analysis.critical_warnings[:3]:
        if not warning.startswith("  "):
            lines.append(f"  ⚠️ {warning}")

    # Top 3 actions
    lines.append("\nTOP ACTIONS:")
    for i, rec in enumerate(analysis.recommendations[:3], 1):
        emoji = "🔴" if rec.priority == InterventionPriority.CRITICAL else "🟠"
        lines.append(f"  {i}. {emoji} {rec.title}: {rec.summary}")

    return "\n".join(lines)


def _generate_markdown_report(analysis: ActionableResponseAnalysis) -> str:
    """Generate markdown-formatted report."""
    lines = []

    lines.append(f"# Obstetric Emergency Response Report: {analysis.case_id}")
    lines.append("")
    lines.append("## Status")
    lines.append(f"- **Success Probability**: {analysis.success_probability:.0%}")
    lines.append(f"- **Feasibility**: {'❌ NOT FEASIBLE' if not analysis.is_feasible else '✅ Feasible'}")
    lines.append(f"- **Time Remaining**: {analysis.time_remaining_minutes:.1f} minutes")
    lines.append("")

    lines.append("## Patient Context")
    lines.append(f"- **Emergency**: {analysis.emergency_type.value.replace('_', ' ').title()}")
    lines.append(f"- **Severity**: {analysis.severity.value.upper()}")
    lines.append("")

    if analysis.critical_warnings:
        lines.append("## ⚠️ Critical Warnings")
        for warning in analysis.critical_warnings:
            lines.append(f"- {warning}")
        lines.append("")

    if analysis.bottlenecks:
        lines.append("## Bottlenecks")
        for bn in analysis.bottlenecks:
            lines.append(f"### {bn.resource_name}")
            lines.append(f"- **Issue**: {bn.issue_description}")
            lines.append(f"- **Delay**: {bn.estimated_delay_minutes:.0f} minutes")
            lines.append("")
        lines.append("")

    if analysis.recommendations:
        lines.append("## Recommended Actions")
        for i, rec in enumerate(analysis.recommendations, 1):
            lines.append(f"### {i}. {rec.title}")
            lines.append(f"**Priority**: {rec.priority.name}")
            lines.append(f"**Summary**: {rec.summary}")
            lines.append("")
            lines.append("**Steps:**")
            for step in rec.action_steps:
                lines.append(f"{step.step_number}. **{step.action}**")
                if step.actor:
                    lines.append(f"   - WHO: {step.actor}")
                if step.contacts:
                    for c in step.contacts:
                        if c.phone:
                            lines.append(f"   - 📞 {c.phone}")
            lines.append("")
        lines.append("")

    lines.append(f"---\n*Report generated: {datetime.now().isoformat()}*")

    return "\n".join(lines)


# Legacy compatibility function
def generate_intervention_report(analysis: Any) -> str:
    """Generate legacy-style intervention report for backward compatibility."""
    if hasattr(analysis, 'success_probability'):
        # It's the new ActionableResponseAnalysis
        return generate_actionable_report(analysis, ReportFormat.BRIEF)

    # Old ResponseChainAnalysis - convert to brief format
    from .intervention_recommender_old import generate_intervention_report as old_generate
    return old_generate(analysis)
