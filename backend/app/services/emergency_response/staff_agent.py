"""
Staff Agent for Emergency Response Simulation.

Models medical staff behavior:
- On-call availability
- Response time simulation
- Shift management
- Skill matching for emergencies
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import random

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage
)
from ...models.response_resource import MedicalStaff, StaffSpecialization
from .base_agent import BaseAgent, AgentEvent, AgentEventType
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.staff')


class StaffState(Enum):
    """Staff availability states."""
    OFF_DUTY = "off_duty"
    ON_CALL = "on_call"
    RESPONDING = "responding"
    AT_HOSPITAL = "at_hospital"
    BUSY = "busy"
    UNAVAILABLE = "unavailable"


class StaffAgent(BaseAgent):
    """
    Staff agent modeling medical personnel behavior.

    State Machine:
    - off_duty -> on_call -> responding -> at_hospital -> on_call
                  -> busy (in surgery) -> on_call
                  -> unavailable

    Key Behaviors:
    - Responds to hospital alerts
    - Simulates travel/response time
    - Tracks availability for emergency types
    - Manages shift schedules
    """

    # Time estimates (in minutes)
    RESPONSE_TIME_BASE = 5.0      # Base response time
    TRAVEL_TIME_PER_KM = 2.0     # Minutes per km
    SURGERY_TIME_MIN = 30        # Minimum surgery duration
    SURGERY_TIME_MAX = 180       # Maximum surgery duration

    # Specialization requirements by emergency type
    EMERGENCY_SPECIALIZATIONS: Dict[str, List[StaffSpecialization]] = {
        "fetal_distress": [
            StaffSpecialization.OBSTETRICIAN,
            StaffSpecialization.ANESTHESIOLOGIST,
            StaffSpecialization.NURSE
        ],
        "maternal_hemorrhage": [
            StaffSpecialization.OBSTETRICIAN,
            StaffSpecialization.ANESTHESIOLOGIST,
            StaffSpecialization.NURSE
        ],
        "eclampsia": [
            StaffSpecialization.OBSTETRICIAN,
            StaffSpecialization.ANESTHESIOLOGIST,
            StaffSpecialization.NEONATOLOGIST,
            StaffSpecialization.NURSE
        ],
        "cord_prolapse": [
            StaffSpecialization.OBSTETRICIAN,
            StaffSpecialization.ANESTHESIOLOGIST
        ],
        "premature_labor": [
            StaffSpecialization.OBSTETRICIAN,
            StaffSpecialization.NEONATOLOGIST
        ]
    }

    def __init__(
        self,
        staff: MedicalStaff,
        simulation_speed: float = 1.0
    ):
        super().__init__(
            agent_id=staff.staff_id,
            agent_type=AgentType.STAFF,
            name=staff.name,
            location=None  # Staff location varies
        )

        self.staff = staff
        self.simulation_speed = simulation_speed

        # State
        self._staff_state = StaffState.ON_CALL if staff.on_call else StaffState.OFF_DUTY
        self._current_hospital_id: Optional[str] = None
        self._assigned_case_id: Optional[str] = None

        # Timing
        self._alert_time: Optional[float] = None
        self._response_time: Optional[float] = None
        self._arrival_time: Optional[float] = None
        self._surgery_start: Optional[float] = None
        self._surgery_end: Optional[float] = None

        # Performance metrics
        self._total_calls = 0
        self._total_responses = 0
        self._avg_response_time = 0.0

        logger.info(f"StaffAgent initialized: {self.name} ({staff.specialization.value})")

    @property
    def current_state(self) -> str:
        return self._staff_state.value

    def get_valid_states(self) -> List[str]:
        """Valid states for staff."""
        return [s.value for s in StaffState]

    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Valid state transitions."""
        return {
            "off_duty": ["on_call"],
            "on_call": ["responding", "busy", "unavailable"],
            "responding": ["at_hospital", "unavailable"],
            "at_hospital": ["busy", "on_call", "off_duty"],
            "busy": ["on_call"],
            "unavailable": ["on_call"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        """Actions this agent can perform."""
        return [
            ResponseActionType.STAFF_CONFIRM,
            ResponseActionType.COORDINATE,
            ResponseActionType.REQUEST_BLOOD,
            ResponseActionType.ESCALATE
        ]

    def step(self, simulation_time: float) -> List[ActionMessage]:
        """Execute one simulation step."""
        messages = []

        # Process incoming messages
        self._process_inbox()

        # State-based behavior
        if self._staff_state == StaffState.RESPONDING:
            messages.extend(self._handle_responding(simulation_time))
        elif self._staff_state == StaffState.BUSY:
            messages.extend(self._handle_busy(simulation_time))

        return messages

    def _process_inbox(self) -> None:
        """Process incoming messages."""
        for message in self._inbox:
            if message.action_type == ResponseActionType.ALERT_STAFF:
                self._handle_alert(message)
            elif message.action_type == ResponseActionType.REQUEST_BACKUP:
                self._handle_backup_request(message)
            elif message.action_type == ResponseActionType.UPDATE_STATUS:
                self._handle_status_update(message)

        self.clear_inbox()

    def _handle_alert(self, message: ActionMessage) -> None:
        """Handle staff alert from hospital."""
        content = message.content
        hospital_id = content.get("hospital_id")
        case_id = content.get("case_id")
        emergency_type = content.get("emergency_type", "other")

        # Check if this staff can handle the emergency
        required_specs = self.EMERGENCY_SPECIALIZATIONS.get(
            emergency_type,
            [StaffSpecialization.OBSTETRICIAN]
        )

        if self.staff.specialization not in required_specs:
            logger.debug(f"Staff {self.name} not required for {emergency_type}")
            return

        # Check availability
        if self._staff_state not in [StaffState.ON_CALL, StaffState.OFF_DUTY]:
            if self._staff_state == StaffState.BUSY:
                # Decline but suggest when available
                self._send_decline_message(hospital_id, case_id, "in_surgery")
            return

        # Accept the call
        self._staff_state = StaffState.RESPONDING
        self._current_hospital_id = hospital_id
        self._assigned_case_id = case_id
        self._alert_time = datetime.now().timestamp()
        self._total_calls += 1

        # Calculate response time based on specialization and conditions
        self._response_time = self._calculate_response_time()

        logger.info(
            f"Staff {self.name} responding to alert: "
            f"case={case_id}, hospital={hospital_id}, "
            f"ETA={self._response_time:.1f} min"
        )

    def _handle_backup_request(self, message: ActionMessage) -> None:
        """Handle request to serve as backup."""
        content = message.content
        hospital_id = content.get("hospital_id")
        reason = content.get("reason", "unknown")

        if self._staff_state == StaffState.ON_CALL:
            self._send_confirm_message(hospital_id)
            logger.info(f"Staff {self.name} confirmed backup for: {reason}")

    def _handle_status_update(self, message: ActionMessage) -> None:
        """Handle status updates."""
        content = message.content
        status = content.get("status")

        if status == "surgery_complete":
            self._staff_state = StaffState.ON_CALL
            self._assigned_case_id = None
            self._surgery_end = datetime.now().timestamp()
            logger.info(f"Staff {self.name} available after surgery")

    def _handle_responding(self, sim_time: float) -> List[ActionMessage]:
        """Handle responding state - simulate travel."""
        messages = []

        elapsed = sim_time - (self._alert_time or 0)
        if elapsed >= self._response_time:
            # Arrived at hospital
            self._staff_state = StaffState.AT_HOSPITAL
            self._arrival_time = sim_time
            self._total_responses += 1

            # Update average response time
            if self._total_responses > 0:
                self._avg_response_time = (
                    (self._avg_response_time * (self._total_responses - 1) + elapsed)
                    / self._total_responses
                )

            # Confirm arrival to hospital
            if self._current_hospital_id:
                messages.append(self.send_message(
                    to_agent=self._current_hospital_id,
                    action_type=ResponseActionType.STAFF_CONFIRM,
                    content={
                        "staff_id": self.agent_id,
                        "status": "available",
                        "arrival_time": sim_time,
                        "specialization": self.staff.specialization.value,
                        "case_id": self._assigned_case_id
                    }
                ))

            logger.info(
                f"Staff {self.name} arrived at hospital "
                f"{self._current_hospital_id} for case {self._assigned_case_id}"
            )

        return messages

    def _handle_busy(self, sim_time: float) -> List[ActionMessage]:
        """Handle busy state - in surgery."""
        messages = []

        # Check if surgery is complete
        if self._surgery_end and sim_time >= self._surgery_end:
            self._staff_state = StaffState.ON_CALL
            self._assigned_case_id = None

            # Notify hospital
            if self._current_hospital_id:
                messages.append(self.send_message(
                    to_agent=self._current_hospital_id,
                    action_type=ResponseActionType.UPDATE_STATUS,
                    content={
                        "status": "surgery_complete",
                        "staff_id": self.agent_id
                    }
                ))

        return messages

    def _calculate_response_time(self) -> float:
        """Calculate response time based on conditions."""
        # Base response time
        base_time = self.RESPONSE_TIME_BASE

        # Specialization factor (some need more prep time)
        spec_factors = {
            StaffSpecialization.OBSTETRICIAN: 1.0,
            StaffSpecialization.ANESTHESIOLOGIST: 1.2,
            StaffSpecialization.NEONATOLOGIST: 1.1,
            StaffSpecialization.NURSE: 0.8,
            StaffSpecialization.EMERGENCY_MEDIC: 0.7,
            StaffSpecialization.MIDWIFE: 0.9
        }

        spec_mult = spec_factors.get(self.staff.specialization, 1.0)
        base_time *= spec_mult

        # Add randomness (not everyone responds at the same speed)
        variance = random.uniform(0.8, 1.2)
        base_time *= variance

        return base_time

    def _send_confirm_message(self, hospital_id: str) -> None:
        """Send confirmation message to hospital."""
        msg = self.send_message(
            to_agent=hospital_id,
            action_type=ResponseActionType.STAFF_CONFIRM,
            content={
                "staff_id": self.agent_id,
                "name": self.name,
                "specialization": self.staff.specialization.value,
                "status": "confirmed",
                "eta_minutes": self._response_time
            }
        )
        self._inbox.append(msg)

    def _send_decline_message(self, hospital_id: str, case_id: str, reason: str) -> None:
        """Send decline message to hospital."""
        msg = self.send_message(
            to_agent=hospital_id,
            action_type=ResponseActionType.ESCALATE,
            content={
                "staff_id": self.agent_id,
                "status": "unavailable",
                "reason": reason,
                "case_id": case_id
            }
        )
        self._inbox.append(msg)

    def start_surgery(self, sim_time: float, duration_minutes: Optional[float] = None) -> None:
        """Start surgery - called by hospital."""
        if duration_minutes is None:
            duration_minutes = random.uniform(self.SURGERY_TIME_MIN, self.SURGERY_TIME_MAX)

        self._staff_state = StaffState.BUSY
        self._surgery_start = sim_time
        self._surgery_end = sim_time + duration_minutes

        logger.info(
            f"Staff {self.name} started surgery, "
            f"will be available at t={self._surgery_end:.1f}"
        )

    def can_handle_emergency(self, emergency_type: str) -> bool:
        """Check if staff can handle emergency type."""
        required = self.EMERGENCY_SPECIALIZATIONS.get(
            emergency_type,
            [StaffSpecialization.OBSTETRICIAN]
        )
        return self.staff.specialization in required

    def is_available(self) -> bool:
        """Check if staff is available."""
        return self._staff_state in [
            StaffState.ON_CALL,
            StaffState.OFF_DUTY,
            StaffState.AT_HOSPITAL
        ]

    def get_availability_report(self) -> Dict[str, Any]:
        """Get staff availability report."""
        return {
            "staff_id": self.agent_id,
            "name": self.name,
            "specialization": self.staff.specialization.value,
            "current_state": self._staff_state.value,
            "is_available": self.is_available(),
            "assigned_case": self._assigned_case_id,
            "hospital": self._current_hospital_id,
            "avg_response_time": self._avg_response_time,
            "total_calls": self._total_calls,
            "total_responses": self._total_responses,
            "response_rate": (
                self._total_responses / self._total_calls
                if self._total_calls > 0 else 0
            )
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export staff agent state."""
        base = super().to_dict()
        base.update({
            "staff_id": self.staff.staff_id,
            "specialization": self.staff.specialization.value,
            "staff_state": self._staff_state.value,
            "current_hospital": self._current_hospital_id,
            "assigned_case": self._assigned_case_id,
            "availability_report": self.get_availability_report()
        })
        return base


class StaffPool:
    """
    Pool of staff agents for efficient management.

    Provides:
    - Fast lookup by specialization
    - Availability filtering
    - Load balancing across staff
    """

    def __init__(self):
        self._agents: Dict[str, StaffAgent] = {}
        self._by_specialization: Dict[StaffSpecialization, List[str]] = {}

    def add(self, agent: StaffAgent) -> None:
        """Add staff agent to pool."""
        self._agents[agent.agent_id] = agent

        spec = agent.staff.specialization
        if spec not in self._by_specialization:
            self._by_specialization[spec] = []
        self._by_specialization[spec].append(agent.agent_id)

    def get(self, staff_id: str) -> Optional[StaffAgent]:
        """Get staff agent by ID."""
        return self._agents.get(staff_id)

    def get_by_specialization(
        self,
        specialization: StaffSpecialization
    ) -> List[StaffAgent]:
        """Get all staff of a specific specialization."""
        staff_ids = self._by_specialization.get(specialization, [])
        return [self._agents[sid] for sid in staff_ids if sid in self._agents]

    def get_available_for_emergency(
        self,
        emergency_type: str
    ) -> List[StaffAgent]:
        """Get available staff who can handle emergency type."""
        required_specs = StaffAgent.EMERGENCY_SPECIALIZATIONS.get(
            emergency_type,
            [StaffSpecialization.OBSTETRICIAN]
        )

        available = []
        for spec in required_specs:
            for agent in self.get_by_specialization(spec):
                if agent.is_available():
                    available.append(agent)

        return available

    def get_all_agents(self) -> List[StaffAgent]:
        """Get all staff agents."""
        return list(self._agents.values())

    def get_pool_status(self) -> Dict[str, Any]:
        """Get pool status summary."""
        status = {
            "total_staff": len(self._agents),
            "by_specialization": {},
            "availability": {
                "available": 0,
                "busy": 0,
                "off_duty": 0
            }
        }

        for spec in StaffSpecialization:
            agents = self.get_by_specialization(spec)
            status["by_specialization"][spec.value] = len(agents)

        for agent in self._agents.values():
            state = agent.current_state
            if state in ["on_call", "at_hospital"]:
                status["availability"]["available"] += 1
            elif state == "busy":
                status["availability"]["busy"] += 1
            elif state == "off_duty":
                status["availability"]["off_duty"] += 1

        return status
