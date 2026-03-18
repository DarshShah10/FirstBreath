"""
Hospital Agent for Emergency Response Simulation.

Models hospital behavior including:
- Receiving emergency alerts
- Coordinating staff
- Preparing OT
- Managing blood bank
- Patient reception
- Capacity management
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from collections import defaultdict

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage, AgentStates
)
from ...models.response_resource import (
    Hospital, MedicalStaff, BloodBank, ResourceLocation,
    HospitalLevel, StaffSpecialization, ResourceStatus
)
from .base_agent import BaseAgent
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.hospital')


class HospitalAgent(BaseAgent):
    """
    Hospital agent modeling healthcare facility behavior.

    State Machine:
    - ready -> alerted -> preparing -> ot_preparing -> ot_ready -> receiving -> ready

    Key Behaviors:
    - Receives alerts from ambulances
    - Alerts on-call staff
    - Prepares operating room
    - Coordinates blood products
    - Receives and admits patients
    - Manages capacity constraints
    """

    # Time estimates (in minutes)
    STAFF_ALERT_TIME = 2.0        # Time to page staff
    STAFF_RESPONSE_TIME = 3.0      # Time for staff to confirm
    OT_PREP_TIME = 10.0           # Time to prepare OT
    BLOOD_PREP_TIME = 5.0         # Time to prepare blood
    RECEIVE_PATIENT_TIME = 3.0     # Time to receive patient

    def __init__(
        self,
        hospital: Hospital,
        staff_list: Optional[List[MedicalStaff]] = None,
        blood_bank: Optional[BloodBank] = None,
        simulation_speed: float = 1.0
    ):
        super().__init__(
            agent_id=hospital.hospital_id,
            agent_type=AgentType.HOSPITAL,
            name=hospital.name,
            location=hospital.location
        )

        self.hospital = hospital
        self.simulation_speed = simulation_speed

        # Resources
        self.staff: Dict[str, MedicalStaff] = {}
        if staff_list:
            for s in staff_list:
                self.staff[s.staff_id] = s

        self.blood_bank = blood_bank

        # OT state
        self._ot_available: int = hospital.ot_count
        self._ot_reserved: int = 0

        # Current operations
        self._pending_alerts: Dict[str, Dict] = {}  # ambulance_id -> alert data
        self._staff_notified: List[str] = []  # staff_ids
        self._staff_confirmed: List[str] = []  # staff_ids who confirmed
        self._ot_prep_started: Optional[float] = None
        self._ot_ready_time: Optional[float] = None
        self._blood_prep_started: Optional[float] = None

        # Current patient
        self._current_patient_id: Optional[str] = None
        self._incoming_ambulances: List[str] = []  # ambulance_ids

        # Capacity tracking
        self._capacity_queue: List[Dict] = []
        self._bed_occupancy: int = 0  # Currently occupied beds
        self._total_beds: int = hospital.obgyn_beds + hospital.nicu_beds  # Total bed capacity

        # Level-based capabilities
        self.is_tertiary = hospital.level == HospitalLevel.TERTIARY
        self.is_secondary = hospital.level == HospitalLevel.SECONDARY

        # Set initial state
        self._current_state = "ready"
        logger.info(f"HospitalAgent initialized: {self.name} ({hospital.level.value})")

    def get_valid_states(self) -> List[str]:
        """Valid states for hospital."""
        return list(AgentStates.HOSPITAL_STATES.keys())

    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Valid state transitions."""
        return {
            "ready": ["alerted"],
            "alerted": ["preparing", "ready"],  # Can cancel if false alarm
            "preparing": ["ot_preparing", "ready"],
            "ot_preparing": ["ot_ready", "preparing"],
            "ot_ready": ["receiving", "ready"],
            "receiving": ["ready"],
            "at_capacity": ["ready"]  # When bed frees up
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        """Actions this agent can perform."""
        return [
            ResponseActionType.RECEIVE_ALERT,
            ResponseActionType.ALERT_STAFF,
            ResponseActionType.STAFF_CONFIRM,
            ResponseActionType.PREPARE_OT,
            ResponseActionType.PREPARE_BLOOD,
            ResponseActionType.OT_READY,
            ResponseActionType.RECEIVE_PATIENT,
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
        if self.current_state == "alerted":
            messages.extend(self._handle_alerted(simulation_time))
        elif self.current_state == "preparing":
            messages.extend(self._handle_preparing(simulation_time))
        elif self.current_state == "ot_preparing":
            messages.extend(self._handle_ot_preparing(simulation_time))
        elif self.current_state == "receiving":
            messages.extend(self._handle_receiving(simulation_time))

        return messages

    def _process_inbox(self) -> None:
        """Process incoming messages."""
        for message in self._inbox:
            if message.action_type == ResponseActionType.RECEIVE_ALERT:
                self._handle_alert(message)
            elif message.action_type == ResponseActionType.STAFF_CONFIRM:
                self._handle_staff_confirm(message)
            elif message.action_type == ResponseActionType.OT_READY:
                self._handle_ot_ready_message(message)
            elif message.action_type == ResponseActionType.UPDATE_STATUS:
                self._handle_status_update(message)
            elif message.action_type == ResponseActionType.REQUEST_BLOOD:
                self._handle_blood_request(message)

        self.clear_inbox()

    def _handle_alert(self, message: ActionMessage) -> None:
        """Handle incoming emergency alert."""
        content = message.content

        ambulance_id = content.get("ambulance_id", message.from_agent)
        patient_id = content.get("patient_id")
        eta = content.get("eta_minutes", 20)
        patient_status = content.get("patient_status", "unknown")
        emergency_type = content.get("emergency_type", "unknown")

        # Store alert
        self._pending_alerts[ambulance_id] = {
            "patient_id": patient_id,
            "eta": eta,
            "patient_status": patient_status,
            "emergency_type": emergency_type,
            "received_at": datetime.now().isoformat()
        }

        if ambulance_id not in self._incoming_ambulances:
            self._incoming_ambulances.append(ambulance_id)

        # Transition to alerted
        self.set_state("alerted", ResponseActionType.RECEIVE_ALERT)

        # Log
        self.log_action(
            ResponseActionType.RECEIVE_ALERT,
            {
                "ambulance_id": ambulance_id,
                "patient_id": patient_id,
                "eta": eta,
                "emergency_type": emergency_type
            },
            outcome="alert_received"
        )

        logger.info(
            f"Hospital {self.name} received alert: "
            f"patient {patient_id}, ETA {eta} min"
        )

    def _handle_staff_confirm(self, message: ActionMessage) -> None:
        """Handle staff confirmation."""
        staff_id = message.from_agent
        available = message.content.get("available", True)

        if available and staff_id not in self._staff_confirmed:
            self._staff_confirmed.append(staff_id)

            self.log_action(
                ResponseActionType.STAFF_CONFIRM,
                {"staff_id": staff_id, "available": True},
                outcome="confirmed"
            )

    def _handle_ot_ready_message(self, message: ActionMessage) -> None:
        """Handle OT ready notification."""
        self._ot_ready_time = message.content.get("time")
        self.log_action(
            ResponseActionType.OT_READY,
            {"ot_ready_at": self._ot_ready_time},
            outcome="ot_ready"
        )

    def _handle_status_update(self, message: ActionMessage) -> None:
        """Handle status updates from ambulances."""
        content = message.content
        status = content.get("status")

        if status == "delayed":
            # Update ETA for incoming ambulance
            ambulance_id = content.get("ambulance_id")
            if ambulance_id in self._pending_alerts:
                self._pending_alerts[ambulance_id]["eta"] = content.get("new_eta_minutes")
                logger.info(
                    f"Hospital {self.name}: ETA updated for {ambulance_id} "
                    f"to {content.get('new_eta_minutes')} min"
                )

    def _handle_blood_request(self, message: ActionMessage) -> None:
        """Handle blood request from another hospital."""
        # This would coordinate with blood bank
        blood_type = message.content.get("blood_type")
        units_needed = message.content.get("units_needed", 2)

        logger.info(
            f"Hospital {self.name} received blood request: "
            f"{units_needed} units {blood_type}"
        )

    def _handle_alerted(self, sim_time: float) -> List[ActionMessage]:
        """Handle alerted state - begin staff notification."""
        messages = []

        # Alert on-call staff
        if not self._staff_notified:
            self._staff_notified = self._alert_staff()

            for staff_id in self._staff_notified:
                messages.append(self.send_message(
                    to_agent=staff_id,
                    action_type=ResponseActionType.ALERT_STAFF,
                    content={
                        "hospital_id": self.agent_id,
                        "emergency_type": "obstetric_emergency",
                        "urgent": True
                    }
                ))

            self.log_action(
                ResponseActionType.ALERT_STAFF,
                {"staff_notified": self._staff_notified},
                outcome="staff_alerted"
            )

        # Check if staff has confirmed
        # In real system, this would be async - staff responds when available
        # For simulation, we assume positive response after response time

        # Transition to preparing after alerting
        self.set_state("preparing", ResponseActionType.COORDINATE)

        return messages

    def _handle_preparing(self, sim_time: float) -> List[ActionMessage]:
        """Handle preparing state - prepare OT and blood."""
        messages = []

        # Check if enough staff confirmed
        min_staff_required = 2  # At least OBGYN + anesthesiologist or midwife

        if len(self._staff_confirmed) >= min_staff_required or len(self._staff_notified) > 0:
            # Start OT preparation
            if self._ot_prep_started is None:
                self._ot_prep_started = sim_time
                self._ot_reserved = 1  # Reserve one OT
                self._ot_available -= 1

                self.log_action(
                    ResponseActionType.PREPARE_OT,
                    {"ot_reserved": 1, "remaining_ot": self._ot_available},
                    outcome="ot_prep_started"
                )

                # Notify ambulance
                if self._incoming_ambulances:
                    amb_id = self._incoming_ambulances[0]
                    eta = self._pending_alerts.get(amb_id, {}).get("eta", 20)
                    messages.append(self.send_message(
                        to_agent=amb_id,
                        action_type=ResponseActionType.UPDATE_STATUS,
                        content={
                            "status": "ot_preparing",
                            "eta_update": "on_time" if eta >= self.OT_PREP_TIME else "may_be_delayed"
                        }
                    ))

            # Check if OT prep complete
            elapsed = sim_time - self._ot_prep_started
            if elapsed >= self.OT_PREP_TIME:
                self.set_state("ot_preparing", ResponseActionType.PREPARE_OT)

        return messages

    def _handle_ot_preparing(self, sim_time: float) -> List[ActionMessage]:
        """Handle OT preparing state."""
        messages = []

        # Check if OT is ready
        elapsed = sim_time - (self._ot_prep_started or sim_time)
        if elapsed >= self.OT_PREP_TIME:
            self.set_state("ot_ready", ResponseActionType.OT_READY)
            self._ot_ready_time = sim_time

            self.log_action(
                ResponseActionType.OT_READY,
                {"ot_ready_at": sim_time},
                outcome="ot_ready"
            )

            # Notify dispatch
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.OT_READY,
                content={
                    "hospital_id": self.agent_id,
                    "ot_ready_at": sim_time,
                    "staff_confirmed": self._staff_confirmed
                }
            ))

        return messages

    def _handle_receiving(self, sim_time: float) -> List[ActionMessage]:
        """Handle receiving patient state."""
        messages = []

        # After receiving patient, return to ready
        if self._current_patient_id:
            self.set_state("ready", ResponseActionType.RECEIVE_PATIENT)

            # Release OT
            self._ot_reserved = max(0, self._ot_reserved - 1)
            self._ot_available += 1

            # Clear current operation
            self._current_patient_id = None
            self._pending_alerts.clear()
            self._staff_confirmed.clear()
            self._staff_notified.clear()
            self._incoming_ambulances.clear()

        return messages

    def receive_patient(
        self,
        patient_id: str,
        ambulance_id: str,
        sim_time: float
    ) -> bool:
        """
        Receive a patient from ambulance.

        Args:
            patient_id: ID of patient
            ambulance_id: ID of arriving ambulance
            sim_time: Current simulation time

        Returns:
            True if patient can be received
        """
        if self.current_state not in ("ot_ready", "receiving"):
            logger.warning(
                f"Hospital {self.name} cannot receive patient - "
                f"not ready (state: {self.current_state})"
            )
            return False

        if self._ot_available <= 0:
            logger.warning(
                f"Hospital {self.name} cannot receive patient - no OT available"
            )
            return False

        self._current_patient_id = patient_id
        self.set_state("receiving", ResponseActionType.RECEIVE_PATIENT)

        self.log_action(
            ResponseActionType.RECEIVE_PATIENT,
            {
                "patient_id": patient_id,
                "ambulance_id": ambulance_id,
                "arrival_time": sim_time
            },
            outcome="patient_received"
        )

        return True

    def _alert_staff(self) -> List[str]:
        """Alert on-call staff. Returns list of alerted staff IDs."""
        alerted = []

        # Get on-call staff by specialization
        obgyns = self._get_on_call_obgyns()
        anesthetists = self._get_on_call_anesthesiologists()

        # Alert at least one of each
        if obgyns:
            alerted.append(obgyns[0].staff_id)
        if anesthetists:
            alerted.append(anesthetists[0].staff_id)

        # Also alert NICU staff if hospital has NICU
        if self.hospital.nicu_beds > 0:
            nicu_staff = self._get_on_call_by_specialization(StaffSpecialization.NEONATOLOGIST)
            if nicu_staff:
                alerted.append(nicu_staff[0].staff_id)

        return alerted

    def _get_on_call_obgyns(self) -> List[MedicalStaff]:
        """Get on-call OBGYNs."""
        return self._get_on_call_by_specialization(StaffSpecialization.OBSTETRICIAN)

    def _get_on_call_anesthesiologists(self) -> List[MedicalStaff]:
        """Get on-call anesthesiologists."""
        return self._get_on_call_by_specialization(StaffSpecialization.ANESTHESIOLOGIST)

    def _get_on_call_by_specialization(
        self,
        specialization: StaffSpecialization
    ) -> List[MedicalStaff]:
        """Get on-call staff by specialization."""
        return [
            s for s in self.staff.values()
            if s.specialization == specialization and s.on_call
        ]

    def can_handle_emergency(self, emergency_type: str) -> bool:
        """Check if hospital can handle emergency type."""
        return self.hospital.can_handle_emergency(emergency_type)

    def get_availability_report(self) -> Dict[str, Any]:
        """Get hospital availability report."""
        return {
            "hospital_id": self.agent_id,
            "hospital_name": self.name,
            "current_state": self.current_state,
            "level": self.hospital.level.value,
            "ot_available": self._ot_available,
            "ot_reserved": self._ot_reserved,
            "ot_total": self.hospital.ot_count,
            "staff_on_call": len(self._staff_notified),
            "staff_confirmed": len(self._staff_confirmed),
            "incoming_ambulances": len(self._incoming_ambulances),
            "can_receive": self._ot_available > 0 and self.current_state in ("ready", "alerted", "preparing", "ot_preparing", "ot_ready"),
            "ot_ready_time": self._ot_ready_time
        }

    def check_blood_availability(self, blood_type: str, units_needed: int = 2) -> bool:
        """Check if required blood is available."""
        if not self.blood_bank:
            return True  # Assume available if no blood bank modeled

        return self.blood_bank.has_blood_type(blood_type, units_needed)

    def request_blood(
        self,
        blood_type: str,
        units_needed: int = 2,
        from_central: bool = True
    ) -> Optional[ActionMessage]:
        """Request blood from central blood bank."""
        if not self.blood_bank or not self.blood_bank.has_blood_type(blood_type, units_needed):
            # Need to request from central
            return self.send_message(
                to_agent="blood_bank_central" if from_central else "ems_dispatch",
                action_type=ResponseActionType.REQUEST_BLOOD,
                content={
                    "blood_type": blood_type,
                    "units_needed": units_needed,
                    "requesting_hospital": self.agent_id
                }
            )
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Export hospital agent state."""
        base = super().to_dict()
        base.update({
            "hospital_id": self.hospital.hospital_id,
            "level": self.hospital.level.value,
            "ot_available": self._ot_available,
            "ot_reserved": self._ot_reserved,
            "staff_notified": self._staff_notified,
            "staff_confirmed": self._staff_confirmed,
            "incoming_ambulances": self._incoming_ambulances,
            "availability_report": self.get_availability_report()
        })
        return base
