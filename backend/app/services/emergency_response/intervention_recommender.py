"""
Intervention Recommendation Engine.

Transforms simulation outcomes into actionable intervention recommendations:
- Identifies bottlenecks in the response chain
- Suggests specific corrective actions
- Recommends alternative routes/resources
- Prioritizes interventions by impact
- Provides real-time recommendations during simulation
"""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import uuid

from ...models.emergency_case import EmergencySeverity, EmergencyType
from ...models.response_resource import ResourceLocation
from .base_agent import BaseAgent, AgentEvent, AgentEventType
from .ambulance_agent import AmbulanceAgent
from .hospital_agent import HospitalAgent
from .staff_agent import StaffAgent, StaffState
from .blood_bank_agent import BloodBankAgent
from .road_network_agent import RoadNetworkAgent, RoadCondition
from .case_queue import CaseQueue, CasePriority, QueuedCase
from ...utils.logger import get_logger

logger = get_logger('mirofish.intervention')


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


class InterventionPriority(Enum):
    """Intervention priority levels."""
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


class InterventionStatus(Enum):
    """Status of an intervention."""
    RECOMMENDED = "recommended"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    NOT_FEASIBLE = "not_feasible"


@dataclass
class InterventionRecommendation:
    """A single intervention recommendation."""
    intervention_id: str
    intervention_type: InterventionType
    priority: InterventionPriority
    target_resource_id: Optional[str]
    target_resource_name: Optional[str]
    action_description: str
    expected_outcome: str
    estimated_time_saved_minutes: float
    confidence_score: float  # 0.0 - 1.0
    preconditions: List[str] = field(default_factory=list)
    alternatives: List[str] = field(default_factory=list)
    status: InterventionStatus = InterventionStatus.RECOMMENDED
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intervention_id": self.intervention_id,
            "type": self.intervention_type.value,
            "priority": self.priority.name,
            "target_resource_id": self.target_resource_id,
            "target_resource_name": self.target_resource_name,
            "action_description": self.action_description,
            "expected_outcome": self.expected_outcome,
            "estimated_time_saved_minutes": self.estimated_time_saved_minutes,
            "confidence_score": self.confidence_score,
            "status": self.status.value,
            "created_at": self.created_at
        }


@dataclass
class BottleneckAnalysis:
    """Analysis of a response chain bottleneck."""
    bottleneck_id: str
    location_type: str  # "ambulance", "hospital", "staff", "blood", "road"
    resource_id: str
    resource_name: str
    issue_description: str
    current_status: str
    estimated_delay_minutes: float
    impact_on_patient: str
    related_interventions: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "bottleneck_id": self.bottleneck_id,
            "location_type": self.location_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "issue_description": self.issue_description,
            "current_status": self.current_status,
            "estimated_delay_minutes": self.estimated_delay_minutes,
            "impact_on_patient": self.impact_on_patient,
            "related_interventions": self.related_interventions
        }


@dataclass
class ResponseChainAnalysis:
    """Complete analysis of a response chain."""
    case_id: str
    severity: EmergencySeverity
    emergency_type: EmergencyType
    time_remaining_minutes: float
    estimated_response_time_minutes: float
    is_feasible: bool
    bottlenecks: List[BottleneckAnalysis] = field(default_factory=list)
    recommendations: List[InterventionRecommendation] = field(default_factory=list)
    alternative_routes: List[Dict[str, Any]] = field(default_factory=list)
    risk_factors: List[str] = field(default_factory=list)
    success_probability: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "case_id": self.case_id,
            "severity": self.severity.value,
            "emergency_type": self.emergency_type.value,
            "time_remaining_minutes": self.time_remaining_minutes,
            "estimated_response_time_minutes": self.estimated_response_time_minutes,
            "is_feasible": self.is_feasible,
            "success_probability": self.success_probability,
            "bottlenecks": [b.to_dict() for b in self.bottlenecks],
            "recommendations": [r.to_dict() for r in self.recommendations],
            "alternative_routes": self.alternative_routes,
            "risk_factors": self.risk_factors,
            "timestamp": self.timestamp
        }


class InterventionRecommender:
    """
    Generates actionable intervention recommendations for emergency response.

    Features:
    - Real-time bottleneck detection
    - Priority-based intervention ranking
    - Multi-option alternatives
    - Success probability estimation
    - Time-saved calculations
    """

    # Time thresholds (in minutes)
    CRITICAL_THRESHOLD = 10
    URGENT_THRESHOLD = 20
    STANDARD_THRESHOLD = 30

    # Emergency type response requirements
    RESPONSE_REQUIREMENTS = {
        EmergencyType.CORD_PROLAPSE: {"max_response": 15, "required_staff": ["obstetrician"], "required_blood": True},
        EmergencyType.UTERINE_RUPTURE: {"max_response": 15, "required_staff": ["obstetrician", "anesthesiologist"], "required_blood": True},
        EmergencyType.PLACENTAL_ABRUPTION: {"max_response": 20, "required_staff": ["obstetrician"], "required_blood": True},
        EmergencyType.ECLAMPSIA: {"max_response": 30, "required_staff": ["obstetrician", "neonatologist"], "required_blood": False},
        EmergencyType.FETAL_DISTRESS: {"max_response": 30, "required_staff": ["obstetrician"], "required_blood": False},
        EmergencyType.MATERNAL_HEMORRHAGE: {"max_response": 20, "required_staff": ["obstetrician", "anesthesiologist"], "required_blood": True},
        EmergencyType.SHOULDER_DYSTOCIA: {"max_response": 15, "required_staff": ["obstetrician"], "required_blood": False},
        EmergencyType.PREMATURE_LABOR: {"max_response": 45, "required_staff": ["obstetrician", "neonatologist"], "required_blood": False},
        EmergencyType.OTHER: {"max_response": 30, "required_staff": ["obstetrician"], "required_blood": False}
    }

    def __init__(self):
        self._intervention_counter = 0
        self._bottleneck_counter = 0

    def analyze_response_chain(
        self,
        case_id: str,
        severity: EmergencySeverity,
        emergency_type: EmergencyType,
        time_remaining_minutes: float,
        current_status: Dict[str, Any]
    ) -> ResponseChainAnalysis:
        """
        Analyze the response chain and generate recommendations.

        Args:
            case_id: Case identifier
            severity: Emergency severity
            emergency_type: Type of emergency
            time_remaining_minutes: Time until critical threshold
            current_status: Current status of all resources

        Returns:
            ResponseChainAnalysis with bottlenecks and recommendations
        """
        logger.info(f"Analyzing response chain for case: {case_id}")

        # Get requirements for this emergency type
        requirements = self.RESPONSE_REQUIREMENTS.get(
            emergency_type,
            self.RESPONSE_REQUIREMENTS[EmergencyType.OTHER]
        )

        # Analyze bottlenecks
        bottlenecks = self._identify_bottlenecks(
            current_status,
            requirements,
            time_remaining_minutes
        )

        # Calculate estimated response time
        estimated_time = self._calculate_estimated_response_time(current_status, bottlenecks)

        # Determine feasibility
        is_feasible = estimated_time <= time_remaining_minutes

        # Calculate success probability
        success_prob = self._calculate_success_probability(
            severity, time_remaining_minutes, estimated_time, bottlenecks
        )

        # Generate recommendations
        recommendations = self._generate_recommendations(
            bottlenecks,
            current_status,
            requirements,
            time_remaining_minutes
        )

        # Sort recommendations by priority
        recommendations.sort(key=lambda r: (r.priority.value, -r.confidence_score))

        analysis = ResponseChainAnalysis(
            case_id=case_id,
            severity=severity,
            emergency_type=emergency_type,
            time_remaining_minutes=time_remaining_minutes,
            estimated_response_time_minutes=estimated_time,
            is_feasible=is_feasible,
            bottlenecks=bottlenecks,
            recommendations=recommendations,
            success_probability=success_prob,
            risk_factors=self._identify_risk_factors(current_status, bottlenecks)
        )

        logger.info(
            f"Analysis complete for {case_id}: "
            f"feasible={is_feasible}, success_prob={success_prob:.2%}, "
            f"recommendations={len(recommendations)}"
        )

        return analysis

    def _identify_bottlenecks(
        self,
        status: Dict[str, Any],
        requirements: Dict[str, Any],
        time_remaining: float
    ) -> List[BottleneckAnalysis]:
        """Identify bottlenecks in the response chain."""
        bottlenecks = []

        # Check ambulance availability
        if status.get("ambulances"):
            for amb_id, amb_status in status["ambulances"].items():
                if amb_status.get("state") == "busy" or amb_status.get("eta_minutes", 0) > time_remaining:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="ambulance",
                        resource_id=amb_id,
                        resource_name=amb_status.get("name", amb_id),
                        issue_description="Ambulance not available or too far",
                        current_status=amb_status.get("state", "unknown"),
                        estimated_delay_minutes=amb_status.get("eta_minutes", 15),
                        impact_on_patient="Delayed transport to hospital",
                        related_interventions=["request_backup_ambulance", "reroute"]
                    ))

        # Check hospital capacity
        if status.get("hospitals"):
            for hosp_id, hosp_status in status["hospitals"].items():
                if hosp_status.get("capacity_utilization", 0) > 0.8:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="hospital",
                        resource_id=hosp_id,
                        resource_name=hosp_status.get("name", hosp_id),
                        issue_description="Hospital at high capacity",
                        current_status=f"{hosp_status.get('capacity_utilization', 0)*100:.0f}% full",
                        estimated_delay_minutes=10,
                        impact_on_patient="Delayed admission and treatment",
                        related_interventions=["activate_nearby_hospital", "alert_hospital"]
                    ))

                # Check OR availability
                if not hosp_status.get("or_available", True):
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="hospital_or",
                        resource_id=hosp_id,
                        resource_name=f"{hosp_status.get('name', hosp_id)} OR",
                        issue_description="Operating room not available",
                        current_status="occupied",
                        estimated_delay_minutes=hosp_status.get("or_eta_minutes", 30),
                        impact_on_patient="Cannot perform emergency surgery",
                        related_interventions=["prepare_or", "activate_nearby_hospital"]
                    ))

        # Check staff availability
        if status.get("staff"):
            required_staff = requirements.get("required_staff", [])
            for spec in required_staff:
                staff_available = any(
                    s.get("specialization") == spec and s.get("is_available", False)
                    for s in status["staff"].values()
                )
                if not staff_available:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="staff",
                        resource_id=f"staff_{spec}",
                        resource_name=f"{spec.title()} (any available)",
                        issue_description=f"No {spec} available",
                        current_status="unavailable",
                        estimated_delay_minutes=15,
                        impact_on_patient="Cannot perform required procedure",
                        related_interventions=["request_specialist", "prepare_staff"]
                    ))

        # Check blood availability (if required)
        if requirements.get("required_blood"):
            blood_status = status.get("blood_banks", {})
            if blood_status:
                blood_available = any(
                    bb.get("total_units", 0) > 0
                    for bb in blood_status.values()
                )
                if not blood_available:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="blood_bank",
                        resource_id="any_blood_bank",
                        resource_name="Blood Supply",
                        issue_description="No compatible blood available",
                        current_status="critical",
                        estimated_delay_minutes=20,
                        impact_on_patient="Cannot perform transfusion if needed",
                        related_interventions=["secure_blood", "mobilize_blood_bank"]
                    ))

        # Check road conditions
        if status.get("road_conditions"):
            for route_id, route_status in status["road_conditions"].items():
                if route_status.get("condition") in ["heavy", "blocked"]:
                    self._bottleneck_counter += 1
                    bottlenecks.append(BottleneckAnalysis(
                        bottleneck_id=f"bn_{self._bottleneck_counter:04d}",
                        location_type="road",
                        resource_id=route_id,
                        resource_name=route_status.get("name", route_id),
                        issue_description=f"Road condition: {route_status.get('condition')}",
                        current_status=route_status.get("condition"),
                        estimated_delay_minutes=route_status.get("delay_minutes", 15),
                        impact_on_patient="Increased transport time",
                        related_interventions=["reroute", "traffic_clearance"]
                    ))

        return bottlenecks

    def _calculate_estimated_response_time(
        self,
        status: Dict[str, Any],
        bottlenecks: List[BottleneckAnalysis]
    ) -> float:
        """Calculate estimated total response time."""
        base_time = status.get("estimated_transport_time", 20)
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
        # Base probability from time
        if time_remaining <= 0:
            return 0.0

        time_ratio = estimated_time / time_remaining if time_remaining > 0 else 1.0

        if time_ratio <= 0.5:
            base_prob = 0.9
        elif time_ratio <= 1.0:
            base_prob = 0.7
        else:
            base_prob = max(0.1, 1.0 - (time_ratio - 1.0) * 0.3)

        # Adjust for severity
        severity_factor = {
            EmergencySeverity.CRITICAL: 0.7,
            EmergencySeverity.SEVERE: 0.85,
            EmergencySeverity.MODERATE: 0.95,
            EmergencySeverity.LOW: 1.0
        }.get(severity, 0.85)

        # Adjust for bottlenecks
        bottleneck_factor = 1.0 - (len(bottlenecks) * 0.1)

        return max(0.0, min(1.0, base_prob * severity_factor * max(0.5, bottleneck_factor)))

    def _generate_recommendations(
        self,
        bottlenecks: List[BottleneckAnalysis],
        status: Dict[str, Any],
        requirements: Dict[str, Any],
        time_remaining: float
    ) -> List[InterventionRecommendation]:
        """Generate intervention recommendations for bottlenecks."""
        recommendations = []

        for bottleneck in bottlenecks:
            recs = self._recommend_for_bottleneck(bottleneck, status, time_remaining)
            recommendations.extend(recs)

        return recommendations

    def _recommend_for_bottleneck(
        self,
        bottleneck: BottleneckAnalysis,
        status: Dict[str, Any],
        time_remaining: float
    ) -> List[InterventionRecommendation]:
        """Generate recommendations for a specific bottleneck."""
        recommendations = []

        if bottleneck.location_type == "ambulance":
            # Recommendation 1: Request backup ambulance
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.REQUEST_BACKUP_AMBULANCE,
                priority=InterventionPriority.HIGH if bottleneck.estimated_delay_minutes > 10 else InterventionPriority.MEDIUM,
                target_resource_id=bottleneck.resource_id,
                target_resource_name="Dispatch Center",
                action_description=f"Dispatch additional ambulance immediately",
                expected_outcome="Reduced transport delay",
                estimated_time_saved_minutes=min(bottleneck.estimated_delay_minutes, 10),
                confidence_score=0.85,
                alternatives=["Consider patient self-transport if close to hospital"]
            ))

            # Recommendation 2: Reroute if road issue
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.REROUTE,
                priority=InterventionPriority.HIGH,
                target_resource_id=bottleneck.resource_id,
                target_resource_name="Navigation System",
                action_description="Find alternative route avoiding congestion",
                expected_outcome="Reduced travel time",
                estimated_time_saved_minutes=min(bottleneck.estimated_delay_minutes, 15),
                confidence_score=0.75,
                alternatives=["Use secondary roads", "Request police escort for traffic clearance"]
            ))

        elif bottleneck.location_type == "hospital":
            # Recommendation 1: Alert hospital
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.ALERT_HOSPITAL,
                priority=InterventionPriority.HIGH,
                target_resource_id=bottleneck.resource_id,
                target_resource_name=bottleneck.resource_name,
                action_description="Pre-alert hospital of incoming critical case",
                expected_outcome="Faster triage and admission",
                estimated_time_saved_minutes=5,
                confidence_score=0.9
            ))

            # Recommendation 2: Activate nearby hospital
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.ACTIVATE_NEARBY_HOSPITAL,
                priority=InterventionPriority.MEDIUM,
                target_resource_id=None,
                target_resource_name="Nearby Hospital",
                action_description="Transfer to alternative hospital with capacity",
                expected_outcome="Patient admitted without delay",
                estimated_time_saved_minutes=10,
                confidence_score=0.7,
                alternatives=["Wait for current hospital capacity"]
            ))

        elif bottleneck.location_type == "hospital_or":
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.PREPARE_OR,
                priority=InterventionPriority.CRITICAL,
                target_resource_id=bottleneck.resource_id,
                target_resource_name=bottleneck.resource_name,
                action_description="Prepare operating room for emergency case",
                expected_outcome="OR ready on patient arrival",
                estimated_time_saved_minutes=min(bottleneck.estimated_delay_minutes, 15),
                confidence_score=0.8
            ))

            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.ACTIVATE_NEARBY_HOSPITAL,
                priority=InterventionPriority.HIGH,
                target_resource_id=None,
                target_resource_name="Alternative Hospital with OR",
                action_description="Divert to hospital with available operating room",
                expected_outcome="Immediate surgical intervention",
                estimated_time_saved_minutes=20,
                confidence_score=0.75,
                alternatives=["Wait for current OR"]
            ))

        elif bottleneck.location_type == "staff":
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.REQUEST_SPECIALIST,
                priority=InterventionPriority.CRITICAL,
                target_resource_id=bottleneck.resource_id,
                target_resource_name=bottleneck.resource_name,
                action_description="Call in specialist from off-duty or nearby facility",
                expected_outcome="Required specialist available",
                estimated_time_saved_minutes=15,
                confidence_score=0.7,
                preconditions=["Verify specialist location", "Arrange transport if needed"]
            ))

            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.PREPARE_STAFF,
                priority=InterventionPriority.HIGH,
                target_resource_id=bottleneck.resource_id,
                target_resource_name=bottleneck.resource_name,
                action_description="Alert available staff to prepare for case",
                expected_outcome="Staff ready on arrival",
                estimated_time_saved_minutes=5,
                confidence_score=0.9
            ))

        elif bottleneck.location_type == "blood_bank":
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.SECURE_BLOOD,
                priority=InterventionPriority.CRITICAL,
                target_resource_id="any_blood_bank",
                target_resource_name="Blood Supply Network",
                action_description="Secure blood products from regional blood bank",
                expected_outcome="Blood available if transfusion needed",
                estimated_time_saved_minutes=15,
                confidence_score=0.8,
                preconditions=["Confirm patient blood type", "Check regional blood bank inventory"]
            ))

            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.MOBILIZE_BLOOD_BANK,
                priority=InterventionPriority.HIGH,
                target_resource_id=None,
                target_resource_name="Mobile Blood Unit",
                action_description="Dispatch mobile blood bank unit to hospital",
                expected_outcome="On-site blood availability",
                estimated_time_saved_minutes=10,
                confidence_score=0.75
            ))

        elif bottleneck.location_type == "road":
            self._intervention_counter += 1
            recommendations.append(InterventionRecommendation(
                intervention_id=f"int_{self._intervention_counter:04d}",
                intervention_type=InterventionType.REROUTE,
                priority=InterventionPriority.CRITICAL,
                target_resource_id=bottleneck.resource_id,
                target_resource_name="Navigation",
                action_description="Re-route ambulance through clear roads",
                expected_outcome="Reduced transport time",
                estimated_time_saved_minutes=bottleneck.estimated_delay_minutes,
                confidence_score=0.85,
                alternatives=["Request traffic police for road clearance"]
            ))

            if time_remaining < 15:
                self._intervention_counter += 1
                recommendations.append(InterventionRecommendation(
                    intervention_id=f"int_{self._intervention_counter:04d}",
                    intervention_type=InterventionType.TRAFFIC_CLEARANCE,
                    priority=InterventionPriority.HIGH,
                    target_resource_id=None,
                    target_resource_name="Traffic Control",
                    action_description="Request emergency traffic clearance on route",
                    expected_outcome="Faster transit with traffic control",
                    estimated_time_saved_minutes=bottleneck.estimated_delay_minutes * 0.5,
                    confidence_score=0.7,
                    preconditions=["Coordinate with traffic police"]
                ))

        return recommendations

    def _identify_risk_factors(
        self,
        status: Dict[str, Any],
        bottlenecks: List[BottleneckAnalysis]
    ) -> List[str]:
        """Identify risk factors for the response."""
        risk_factors = []

        # Time-based risks
        if status.get("time_remaining_minutes", 30) < 15:
            risk_factors.append("Critical time pressure - intervention window closing")

        if status.get("estimated_transport_time", 20) > 30:
            risk_factors.append("Long transport time due to distance or conditions")

        # Resource-based risks
        if len(bottlenecks) >= 3:
            risk_factors.append("Multiple bottlenecks - high failure risk")

        if any(b.location_type == "staff" for b in bottlenecks):
            risk_factors.append("Specialist unavailable - may need transfer")

        if any(b.location_type == "blood_bank" for b in bottlenecks):
            risk_factors.append("Blood supply issue - prepare for complications")

        # Condition-based risks
        if status.get("patient_condition") == "deteriorating":
            risk_factors.append("Patient condition deteriorating - time critical")

        return risk_factors

    def get_priority_interventions(
        self,
        analysis: ResponseChainAnalysis,
        max_count: int = 3
    ) -> List[InterventionRecommendation]:
        """Get the most important interventions to execute."""
        critical = [r for r in analysis.recommendations if r.priority == InterventionPriority.CRITICAL]
        high = [r for r in analysis.recommendations if r.priority == InterventionPriority.HIGH]
        medium = [r for r in analysis.recommendations if r.priority == InterventionPriority.MEDIUM]

        result = critical[:max_count]
        if len(result) < max_count:
            result.extend(high[:max_count - len(result)])
        if len(result) < max_count:
            result.extend(medium[:max_count - len(result)])

        return result


def generate_intervention_report(analysis: ResponseChainAnalysis) -> str:
    """Generate a human-readable intervention report."""
    lines = [
        f"=== INTERVENTION REPORT: Case {analysis.case_id} ===",
        f"",
        f"Status: {'FEASIBLE' if analysis.is_feasible else 'CRITICAL - INTERVENTION REQUIRED'}",
        f"Success Probability: {analysis.success_probability:.0%}",
        f"",
        f"Time Analysis:",
        f"  - Time Remaining: {analysis.time_remaining_minutes:.1f} minutes",
        f"  - Estimated Response: {analysis.estimated_response_time_minutes:.1f} minutes",
        f"  - Margin: {analysis.time_remaining_minutes - analysis.estimated_response_time_minutes:.1f} minutes",
        f"",
    ]

    if analysis.bottlenecks:
        lines.append(f"Bottlenecks Identified ({len(analysis.bottlenecks)}):")
        for i, bn in enumerate(analysis.bottlenecks, 1):
            lines.append(f"  {i}. {bn.resource_name} ({bn.location_type})")
            lines.append(f"     Issue: {bn.issue_description}")
            lines.append(f"     Delay: {bn.estimated_delay_minutes:.1f} minutes")
        lines.append("")

    if analysis.recommendations:
        lines.append(f"Priority Interventions ({len(analysis.recommendations)}):")
        for i, rec in enumerate(analysis.recommendations[:5], 1):
            lines.append(f"  {i}. [{rec.priority.name}] {rec.action_description}")
            lines.append(f"     Target: {rec.target_resource_name or 'System'}")
            lines.append(f"     Time Saved: ~{rec.estimated_time_saved_minutes:.0f} minutes")
            lines.append(f"     Confidence: {rec.confidence_score:.0%}")
        lines.append("")

    if analysis.risk_factors:
        lines.append("Risk Factors:")
        for rf in analysis.risk_factors:
            lines.append(f"  - {rf}")
        lines.append("")

    if not analysis.is_feasible:
        lines.append("!!! IMMEDIATE ACTION REQUIRED !!!")
        lines.append("Recommended: Execute top 3 interventions immediately")
        lines.append(f"Current success probability: {analysis.success_probability:.0%}")

    return "\n".join(lines)
