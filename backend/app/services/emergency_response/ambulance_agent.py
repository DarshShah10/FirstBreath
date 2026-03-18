"""
Ambulance Agent for Emergency Response Simulation.

Models ambulance behavior including:
- Dispatch response
- Route selection and navigation
- Patient stabilization
- Dynamic rerouting when routes are blocked
- Communication with dispatch and hospital
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import math

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage, AgentStates
)
from ...models.response_resource import (
    Ambulance, ResourceLocation, TransportRoute, ResourceStatus
)
from .base_agent import BaseAgent
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.ambulance')


class AmbulanceAgent(BaseAgent):
    """
    Ambulance agent modeling emergency vehicle behavior.

    State Machine:
    - available -> dispatched -> en_route_patient -> at_patient
      -> stabilizing -> en_route_hospital -> at_hospital -> returning -> available

    Key Behaviors:
    - Responds to dispatch commands
    - Navigates to patient location
    - Stabilizes patient
    - Navigates to hospital
    - Handles route blocks and rerouting
    - Communicates with dispatch and hospital throughout
    """

    # Time estimates (in minutes)
    DEPART_TIME = 1.0           # Time to depart after dispatch
    STABILIZE_TIME = 5.0       # Time to stabilize patient
    HANDOVER_TIME = 2.0        # Time to hand over patient
    RETURN_TIME = 1.0          # Time to return to base

    # Speed and distance constants
    SPEED_KMH = 40.0           # Average ambulance speed in city (km/h)
    ARRIVAL_THRESHOLD_KM = 0.1 # Arrival detection threshold (100 meters)

    def __init__(
        self,
        ambulance: Ambulance,
        simulation_speed: float = 1.0  # 1.0 = real-time
    ):
        super().__init__(
            agent_id=ambulance.ambulance_id,
            agent_type=AgentType.AMBULANCE,
            name=ambulance.name,
            location=ambulance.location
        )

        self.ambulance = ambulance
        self.simulation_speed = simulation_speed

        # Mission state
        self.current_patient_id: Optional[str] = None
        self.current_hospital_id: Optional[str] = None
        self.current_route: Optional[TransportRoute] = None
        self.alternate_route: Optional[TransportRoute] = None

        # Location tracking
        self.current_location = ambulance.location
        self.destination_location: Optional[ResourceLocation] = None
        self.route_progress: float = 0.0  # 0.0 to 1.0

        # Timing
        self.dispatch_time: Optional[float] = None
        self.arrive_patient_time: Optional[float] = None
        self.depart_hospital_time: Optional[float] = None
        self.arrive_hospital_time: Optional[float] = None

        # Route block handling
        self.reroute_count: int = 0
        self.max_reroutes: int = 3
        self.blocked_routes: List[str] = []

        # Equipment check
        self.equipped_capabilities = set(ambulance.equipped_for)
        self.has_paramedic = ambulance.has_paramedic

        # Set initial state
        self._current_state = "available"
        logger.info(f"AmbulanceAgent initialized: {self.name}")

    def get_valid_states(self) -> List[str]:
        """Valid states for ambulance."""
        return list(AgentStates.AMBULANCE_STATES.keys())

    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Valid state transitions."""
        return {
            "available": ["dispatched"],
            "dispatched": ["en_route_patient"],
            "en_route_patient": ["at_patient", "dispatched"],  # Can cancel
            "at_patient": ["stabilizing", "en_route_hospital"],  # Can skip stabilization if critical
            "stabilizing": ["en_route_hospital"],
            "en_route_hospital": ["at_hospital", "en_route_patient"],  # Reroute back to patient
            "at_hospital": ["returning", "en_route_patient"],  # If hospital can't receive
            "returning": ["available"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        """Actions this agent can perform."""
        return [
            ResponseActionType.DEPART,
            ResponseActionType.ARRIVE_PATIENT,
            ResponseActionType.STABILIZE,
            ResponseActionType.DEPART_HOSPITAL,
            ResponseActionType.ARRIVE_HOSPITAL,
            ResponseActionType.RETURN_TO_BASE,
            ResponseActionType.REROUTE,
            ResponseActionType.ALERT,
            ResponseActionType.UPDATE_STATUS,
            ResponseActionType.REQUEST_BACKUP,
            ResponseActionType.COMMUNICATE
        ]

    def dispatch(
        self,
        patient_id: str,
        patient_location: ResourceLocation,
        hospital_id: str,
        hospital_location: ResourceLocation,
        route: Optional[TransportRoute] = None,
        alternate_route: Optional[TransportRoute] = None
    ) -> bool:
        """
        Dispatch this ambulance to a patient.

        Args:
            patient_id: ID of the patient
            patient_location: Patient's location
            hospital_id: Target hospital ID
            hospital_location: Hospital's location
            route: Primary transport route
            alternate_route: Alternate route if primary blocked

        Returns:
            True if dispatch successful
        """
        if self.current_state != "available":
            logger.warning(f"Ambulance {self.agent_id} not available for dispatch")
            return False

        self.current_patient_id = patient_id
        self.current_hospital_id = hospital_id
        self.destination_location = patient_location
        self.current_route = route
        self.alternate_route = alternate_route

        # Transition to dispatched
        self.set_state("dispatched", ResponseActionType.DISPATCH)

        # Log dispatch
        self.log_action(
            ResponseActionType.DISPATCH,
            {
                "patient_id": patient_id,
                "hospital_id": hospital_id,
                "destination": patient_location.address
            },
            outcome="dispatched"
        )

        logger.info(f"Ambulance {self.name} dispatched to patient {patient_id}")
        return True

    def can_handle_emergency(self, emergency_type: str) -> bool:
        """Check if ambulance can handle the emergency type."""
        capability_map = {
            "fetal_distress": ["neonatal_resuscitation", "emergency_delivery"],
            "maternal_hemorrhage": ["advanced_life_support"],
            "eclampsia": ["advanced_life_support"],
            "cord_prolapse": ["emergency_delivery"],
        }
        required = capability_map.get(emergency_type, ["emergency_delivery"])
        return all(cap in self.equipped_capabilities for cap in required)

    def step(self, simulation_time: float) -> List[ActionMessage]:
        """
        Execute one simulation step.

        This is the main behavior loop that drives ambulance actions.
        """
        messages = []

        # Process incoming messages first
        self._process_inbox()

        # State-based behavior
        if self.current_state == "dispatched":
            messages.extend(self._handle_dispatched(simulation_time))
        elif self.current_state == "en_route_patient":
            messages.extend(self._handle_en_route_patient(simulation_time))
        elif self.current_state == "at_patient":
            messages.extend(self._handle_at_patient(simulation_time))
        elif self.current_state == "stabilizing":
            messages.extend(self._handle_stabilizing(simulation_time))
        elif self.current_state == "en_route_hospital":
            messages.extend(self._handle_en_route_hospital(simulation_time))
        elif self.current_state == "at_hospital":
            messages.extend(self._handle_at_hospital(simulation_time))
        elif self.current_state == "returning":
            messages.extend(self._handle_returning(simulation_time))

        return messages

    def _process_inbox(self) -> None:
        """Process messages in inbox."""
        for message in self._inbox:
            if message.action_type == ResponseActionType.REROUTE:
                self._handle_reroute_message(message)
            elif message.action_type == ResponseActionType.REQUEST_BACKUP:
                self._handle_backup_request(message)

        self.clear_inbox()

    def _handle_reroute_message(self, message: ActionMessage) -> None:
        """Handle a reroute command."""
        new_route_id = message.content.get("route_id")
        reason = message.content.get("reason", "Route blocked")

        if new_route_id and self.current_route and self.current_route.alternate_route_id:
            if new_route_id == self.current_route.alternate_route_id:
                # Swap to alternate
                temp = self.current_route
                self.current_route = self.alternate_route
                self.alternate_route = temp

                self.route_progress = 0.0
                self.reroute_count += 1
                self.blocked_routes.append(self.current_route.route_id)

                self.log_action(
                    ResponseActionType.REROUTE,
                    {
                        "new_route": new_route_id,
                        "reason": reason,
                        "reroute_count": self.reroute_count
                    },
                    outcome="rerouted"
                )

                logger.info(f"Ambulance {self.name} rerouted to {new_route_id}")

    def _handle_backup_request(self, message: ActionMessage) -> None:
        """Handle a backup request from another ambulance."""
        # This ambulance is being asked to backup another
        backup_request = message.content
        logger.info(
            f"Ambulance {self.name} received backup request: {backup_request}"
        )

    def _handle_dispatched(self, sim_time: float) -> List[ActionMessage]:
        """Handle dispatched state - begin journey to patient."""
        messages = []

        # Depart after DEPART_TIME
        if self.dispatch_time is None:
            self.dispatch_time = sim_time

        elapsed = sim_time - self.dispatch_time
        if elapsed >= self.DEPART_TIME:
            self.set_state("en_route_patient", ResponseActionType.DEPART)

            # Calculate ETA
            eta = self._calculate_eta_to_destination()
            if eta:
                self.arrive_patient_time = sim_time + eta

            # Notify dispatch
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.UPDATE_STATUS,
                content={
                    "status": "en_route",
                    "destination": self.destination_location.address if self.destination_location else None,
                    "eta_minutes": eta,
                    "current_location": self.current_location.to_dict() if self.current_location else None
                }
            ))

        return messages

    def _handle_en_route_patient(self, sim_time: float) -> List[ActionMessage]:
        """Handle traveling to patient."""
        messages = []

        # Update location based on progress
        self._update_location_along_route()

        # Check if arrived
        if self.destination_location and self._is_at_destination():
            self.set_state("at_patient", ResponseActionType.ARRIVE_PATIENT)
            self.arrive_patient_time = sim_time

            # Notify dispatch and hospital
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.ARRIVE_PATIENT,
                content={
                    "patient_id": self.current_patient_id,
                    "arrival_time": sim_time,
                    "patient_status": "stable"  # Would be updated by actual assessment
                }
            ))

            # Alert hospital we're coming with patient
            if self.current_hospital_id:
                eta_to_hospital = self._calculate_eta_to_hospital()
                messages.append(self.send_message(
                    to_agent=self.current_hospital_id,
                    action_type=ResponseActionType.RECEIVE_ALERT,
                    content={
                        "type": "patient_incoming",
                        "patient_id": self.current_patient_id,
                        "eta_minutes": eta_to_hospital,
                        "ambulance_id": self.agent_id,
                        "patient_status": "stable"
                    }
                ))

        # Check for route blockages
        if self.current_route and self.current_route.is_blocked:
            if self.reroute_count < self.max_reroutes and self.alternate_route:
                # Trigger reroute
                messages.extend(self._trigger_reroute("Route blocked"))

        return messages

    def _handle_at_patient(self, sim_time: float) -> List[ActionMessage]:
        """Handle being at patient - decide whether to stabilize or depart immediately."""
        messages = []

        # For critical emergencies, go immediately to hospital
        # For non-critical, stabilize first
        # This is a simplified decision - could be enhanced with actual triage

        # For now, go to stabilizing state for all cases
        # In a real system, this would be based on patient assessment
        self.set_state("stabilizing", ResponseActionType.STABILIZE)

        return messages

    def _handle_stabilizing(self, sim_time: float) -> List[ActionMessage]:
        """Handle patient stabilization."""
        messages = []

        # Update destination to hospital
        self.destination_location = None  # Will be set to hospital location

        # After stabilization time, prepare to depart
        elapsed = sim_time - (self.arrive_patient_time or sim_time)
        if elapsed >= self.STABILIZE_TIME:
            self.set_state("en_route_hospital", ResponseActionType.DEPART_HOSPITAL)
            self.depart_hospital_time = sim_time

            # Get hospital location for navigation
            # This would typically come from the registry or a message
            if self.current_hospital_id:
                messages.append(self.send_message(
                    to_agent=self.current_hospital_id,
                    action_type=ResponseActionType.UPDATE_STATUS,
                    content={
                        "status": "departing_with_patient",
                        "patient_id": self.current_patient_id,
                        "eta_minutes": self._calculate_eta_to_hospital()
                    }
                ))

        return messages

    def _handle_en_route_hospital(self, sim_time: float) -> List[ActionMessage]:
        """Handle traveling to hospital with patient."""
        messages = []

        # Update location
        self._update_location_along_route()

        # Check for route blocks
        if self.current_route and self.current_route.is_blocked:
            if self.reroute_count < self.max_reroutes and self.alternate_route:
                messages.extend(self._trigger_reroute("Route blocked"))

        # Check if arrived at hospital
        if self.destination_location and self._is_at_destination():
            self.set_state("at_hospital", ResponseActionType.ARRIVE_HOSPITAL)
            self.arrive_hospital_time = sim_time

            # Hand over patient
            messages.append(self.send_message(
                to_agent=self.current_hospital_id,
                action_type=ResponseActionType.HANDS_OVER,
                content={
                    "patient_id": self.current_patient_id,
                    "arrival_time": sim_time,
                    "handover_notes": "Patient stabilized, monitor vitals"
                }
            ))

            # Notify dispatch
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.ARRIVE_HOSPITAL,
                content={
                    "patient_id": self.current_patient_id,
                    "hospital_id": self.current_hospital_id,
                    "arrival_time": sim_time
                }
            ))

        return messages

    def _handle_at_hospital(self, sim_time: float) -> List[ActionMessage]:
        """Handle at hospital - begin return journey."""
        messages = []

        # After handover, begin return to base
        self.set_state("returning", ResponseActionType.RETURN_TO_BASE)

        # Update location to hospital
        if self.destination_location:
            self.current_location = self.destination_location

        # Return to base
        if self.ambulance.base_location:
            self.destination_location = self.ambulance.base_location

        return messages

    def _handle_returning(self, sim_time: float) -> List[ActionMessage]:
        """Handle returning to base."""
        messages = []

        # Update location
        self._update_location_along_route()

        # Check if at base
        if self.ambulance.base_location and self._is_at_location(self.ambulance.base_location):
            self.set_state("available", ResponseActionType.RETURN_TO_BASE)

            # Reset mission state
            self.current_patient_id = None
            self.current_hospital_id = None
            self.current_route = None
            self.alternate_route = None
            self.route_progress = 0.0
            self.reroute_count = 0
            self.blocked_routes.clear()

            # Notify dispatch
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.UPDATE_STATUS,
                content={
                    "status": "available",
                    "location": self.ambulance.base_location.address if self.ambulance.base_location else None
                }
            ))

        return messages

    def _trigger_reroute(self, reason: str) -> List[ActionMessage]:
        """Trigger reroute to alternate route."""
        messages = []

        if not self.alternate_route or self.reroute_count >= self.max_reroutes:
            # Can't reroute, emit failure
            self.log_action(
                ResponseActionType.ROUTE_BLOCKED,
                {
                    "route": self.current_route.route_id if self.current_route else None,
                    "reason": reason,
                    "cannot_reroute": True
                },
                outcome="failure",
                duration_seconds=0
            )

            # Request backup
            messages.append(self.send_message(
                to_agent="ems_dispatch",
                action_type=ResponseActionType.REQUEST_BACKUP,
                content={
                    "reason": "route_blocked",
                    "current_location": self.current_location.to_dict() if self.current_location else None,
                    "patient_id": self.current_patient_id
                },
                broadcast=True
            ))
            return messages

        # Swap to alternate route
        temp = self.current_route
        self.current_route = self.alternate_route
        self.alternate_route = temp

        self.route_progress = 0.0
        self.reroute_count += 1
        if self.current_route:
            self.blocked_routes.append(self.current_route.route_id)

        self.log_action(
            ResponseActionType.REROUTE,
            {
                "new_route": self.current_route.route_id if self.current_route else None,
                "reason": reason,
                "reroute_count": self.reroute_count
            },
            outcome="rerouted"
        )

        # Notify dispatch
        messages.append(self.send_message(
            to_agent="ems_dispatch",
            action_type=ResponseActionType.REROUTE,
            content={
                "ambulance_id": self.agent_id,
                "new_route": self.current_route.route_id if self.current_route else None,
                "eta_increase_minutes": 5,  # Approximate delay
                "reason": reason
            }
        ))

        # Notify hospital of delay
        if self.current_hospital_id:
            messages.append(self.send_message(
                to_agent=self.current_hospital_id,
                action_type=ResponseActionType.UPDATE_STATUS,
                content={
                    "ambulance_id": self.agent_id,
                    "eta_update": "delayed",
                    "new_eta_minutes": self._calculate_eta_to_hospital(),
                    "reason": reason
                }
            ))

        return messages

    def _update_location_along_route(self) -> None:
        """Update current location along the route based on progress."""
        if not self.current_route or not self.current_location:
            return

        # Extract locations from route segments
        if not self.current_route.segments:
            return

        first_seg = self.current_route.segments[0]
        last_seg = self.current_route.segments[-1]
        from_loc = ResourceLocation(lat=first_seg.from_lat, lng=first_seg.from_lng)
        to_loc = ResourceLocation(lat=last_seg.to_lat, lng=last_seg.to_lng)

        # Calculate progress
        progress = min(self.route_progress, 1.0)

        new_lat = from_loc.lat + (to_loc.lat - from_loc.lat) * progress
        new_lng = from_loc.lng + (to_loc.lng - from_loc.lng) * progress

        self.current_location = ResourceLocation(lat=new_lat, lng=new_lng)

        # Increment progress (speed based on route conditions)
        # Check if any segment is blocked
        has_blocked = any(s.condition.value == "blocked" for s in self.current_route.segments)
        has_congested = any(s.condition.value in ["moderate", "heavy"] for s in self.current_route.segments)

        if has_blocked:
            speed = 0  # Can't move if blocked
        elif has_congested:
            speed = 0.02 / self.simulation_speed  # Slower
        else:
            speed = 0.05 / self.simulation_speed  # Normal

        self.route_progress += speed

    def _calculate_eta_to_destination(self) -> Optional[float]:
        """Calculate ETA to current destination."""
        if not self.destination_location or not self.current_location:
            return None

        distance = self.current_location.distance_to(self.destination_location)
        eta_hours = distance / self.SPEED_KMH
        return eta_hours * 60

    def _calculate_eta_to_hospital(self) -> Optional[float]:
        """Calculate ETA to hospital."""
        if not self.current_hospital_id:
            return None

        # Use route duration if available
        if self.current_route:
            # Handle both Route (property) and TransportRoute (method) interfaces
            if hasattr(self.current_route, 'effective_duration_minutes'):
                return self.current_route.effective_duration_minutes * (1 - self.route_progress)
            elif hasattr(self.current_route, 'get_effective_duration'):
                return self.current_route.get_effective_duration() * (1 - self.route_progress)

        return self._calculate_eta_to_destination()

    def _is_at_destination(self) -> bool:
        """Check if at current destination."""
        return self.destination_location and self._is_at_location(self.destination_location)

    def _is_at_location(self, location: ResourceLocation) -> bool:
        """Check if at a specific location."""
        if not self.current_location:
            return False
        distance = self.current_location.distance_to(location)
        return distance < self.ARRIVAL_THRESHOLD_KM

    def get_eta_report(self) -> Dict[str, Any]:
        """Get ETA report for current mission."""
        return {
            "ambulance_id": self.agent_id,
            "ambulance_name": self.name,
            "current_state": self.current_state,
            "patient_id": self.current_patient_id,
            "hospital_id": self.current_hospital_id,
            "current_location": self.current_location.to_dict() if self.current_location else None,
            "eta_to_patient": self._calculate_eta_to_destination() if self.current_state == "en_route_patient" else None,
            "eta_to_hospital": self._calculate_eta_to_hospital() if self.current_state == "en_route_hospital" else None,
            "route_status": self.current_route.worst_condition.value if self.current_route else None,
            "reroute_count": self.reroute_count,
            "has_paramedic": self.has_paramedic
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export ambulance agent state."""
        base = super().to_dict()
        base.update({
            "ambulance_id": self.ambulance.ambulance_id,
            "current_patient_id": self.current_patient_id,
            "current_hospital_id": self.current_hospital_id,
            "current_route": self.current_route.route_id if self.current_route else None,
            "route_progress": self.route_progress,
            "eta_report": self.get_eta_report()
        })
        return base
