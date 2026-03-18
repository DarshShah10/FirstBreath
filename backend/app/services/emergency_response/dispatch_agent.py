"""
Dispatch Agent for Emergency Response Simulation.

Central coordination agent that:
- Receives emergency calls
- Dispatches ambulances
- Coordinates between ambulances and hospitals
- Manages backup resources
- Handles escalations
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
import uuid

from ...models.emergency_case import DistressSignal, EmergencySeverity
from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage, AgentStates
)
from ...models.response_resource import (
    ResourceLocation, TransportRoute, ResourceStatus
)
from .base_agent import BaseAgent
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.dispatch')

# Shared constants
AMBULANCE_SPEED_KMH = 40.0  # Average ambulance speed in city


class DispatchAgent(BaseAgent):
    """
    Dispatch center agent coordinating emergency response.

    State Machine:
    - monitoring -> coordinating -> escalating -> coordinating

    Key Behaviors:
    - Receives distress signals
    - Assigns nearest ambulance
    - Coordinates hospital alerts
    - Manages backup resources
    - Handles failures and escalations
    """

    def __init__(
        self,
        name: str = "EMS Dispatch Center",
        simulation_speed: float = 1.0
    ):
        super().__init__(
            agent_id="ems_dispatch",
            agent_type=AgentType.EMS_DISPATCH,
            name=name,
            location=None  # Dispatch center doesn't have physical location
        )

        self.simulation_speed = simulation_speed

        # Resource tracking
        self._available_ambulances: Dict[str, Dict] = {}
        self._dispatched_ambulances: Dict[str, Dict] = {}
        self._available_hospitals: List[str] = []

        # Active cases
        self._active_cases: Dict[str, Dict] = {}

        # Simulation state
        self._simulation_time: float = 0.0

        # Set initial state
        self._current_state = "monitoring"
        logger.info("DispatchAgent initialized")

    def get_valid_states(self) -> List[str]:
        """Valid states for dispatch."""
        return list(AgentStates.DISPATCH_STATES.keys())

    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Valid state transitions."""
        return {
            "monitoring": ["coordinating"],
            "coordinating": ["monitoring", "escalating"],
            "escalating": ["coordinating", "monitoring"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        """Actions this agent can perform."""
        return [
            ResponseActionType.DISPATCH,
            ResponseActionType.ALERT,
            ResponseActionType.COORDINATE,
            ResponseActionType.REQUEST_BACKUP,
            ResponseActionType.ESCALATE,
            ResponseActionType.REROUTE,
            ResponseActionType.UPDATE_STATUS
        ]

    def step(self, simulation_time: float) -> List[ActionMessage]:
        """Execute one simulation step."""
        self._simulation_time = simulation_time
        messages = []

        # Process incoming messages
        self._process_inbox()

        # Monitor active cases
        self._check_case_status()

        return messages

    def _process_inbox(self) -> None:
        """Process incoming messages."""
        for message in self._inbox:
            if message.action_type == ResponseActionType.RECEIVE_ALERT:
                self._handle_emergency_call(message)
            elif message.action_type == ResponseActionType.REQUEST_BACKUP:
                self._handle_backup_request(message)
            elif message.action_type == ResponseActionType.REROUTE:
                self._handle_reroute_request(message)
            elif message.action_type == ResponseActionType.UPDATE_STATUS:
                self._handle_status_update(message)
            elif message.action_type == ResponseActionType.OT_READY:
                self._handle_ot_ready(message)
            elif message.action_type == ResponseActionType.ARRIVE_HOSPITAL:
                self._handle_arrival(message)

        self.clear_inbox()

    def receive_emergency(
        self,
        signal: DistressSignal,
        available_ambulances: Dict[str, Any],
        available_hospitals: List[str],
        routes: Dict[str, TransportRoute]
    ) -> Tuple[Optional[str], List[ActionMessage]]:
        """
        Process an incoming emergency call.

        Args:
            signal: The distress signal
            available_ambulances: Dict of ambulance_id -> ambulance info
            available_hospitals: List of hospital IDs
            routes: Dict of route_id -> route

        Returns:
            Tuple of (case_id, messages to send)
        """
        messages = []
        case_id = signal.case_id

        # Create case
        self._active_cases[case_id] = {
            "signal": signal,
            "status": "dispatching",
            "start_time": self._simulation_time,
            "dispatched_ambulance": None,
            "assigned_hospital": None,
            "eta": None,
            "issues": []
        }

        # Find nearest ambulance
        ambulance_id, ambulance_info = self._find_nearest_ambulance(
            signal.location.lat,
            signal.location.lng,
            available_ambulances
        )

        if not ambulance_id:
            logger.warning(f"No ambulances available for case {case_id}")
            self._active_cases[case_id]["status"] = "failed"
            self._active_cases[case_id]["issues"].append("no_ambulance_available")
            return None, messages

        # Find appropriate hospital
        hospital_id, route = self._find_best_hospital(
            signal,
            ambulance_id,
            available_hospitals,
            routes
        )

        if not hospital_id:
            logger.warning(f"No suitable hospital for case {case_id}")
            self._active_cases[case_id]["status"] = "failed"
            self._active_cases[case_id]["issues"].append("no_hospital_available")
            return None, messages

        # Update case
        self._active_cases[case_id]["dispatched_ambulance"] = ambulance_id
        self._active_cases[case_id]["assigned_hospital"] = hospital_id
        self._active_cases[case_id]["route"] = route

        # Calculate ETA
        eta = self._calculate_eta(ambulance_info, route, signal)
        self._active_cases[case_id]["eta"] = eta

        # Dispatch ambulance
        messages.append(ActionMessage(
            message_id=str(uuid.uuid4()),
            action_type=ResponseActionType.DISPATCH,
            from_agent=self.agent_id,
            to_agent=ambulance_id,
            content={
                "case_id": case_id,
                "patient_id": f"patient_{case_id}",
                "patient_location": {
                    "lat": signal.location.lat,
                    "lng": signal.location.lng,
                    "address": signal.location.address
                },
                "hospital_id": hospital_id,
                "hospital_location": None,  # Would be filled from registry
                "route": route.to_dict() if route else None,
                "emergency_type": signal.emergency_type.value,
                "severity": signal.severity.value,
                "priority": signal.severity.priority_score
            }
        ))

        # Store ambulance as dispatched
        self._dispatched_ambulances[ambulance_id] = {
            "case_id": case_id,
            "status": "dispatched"
        }

        # Remove from available
        if ambulance_id in self._available_ambulances:
            del self._available_ambulances[ambulance_id]

        # Transition to coordinating
        self.set_state("coordinating", ResponseActionType.COORDINATE)

        # Log
        self.log_action(
            ResponseActionType.DISPATCH,
            {
                "case_id": case_id,
                "ambulance_id": ambulance_id,
                "hospital_id": hospital_id,
                "eta": eta
            },
            outcome="dispatched"
        )

        logger.info(
            f"Case {case_id}: Dispatched {ambulance_id} to patient, "
            f"ETA {eta:.1f} min"
        )

        return case_id, messages

    def _find_nearest_ambulance(
        self,
        lat: float,
        lng: float,
        available_ambulances: Dict[str, Any]
    ) -> Tuple[Optional[str], Optional[Dict]]:
        """Find nearest available ambulance."""
        if not available_ambulances:
            return None, None

        import math
        patient_loc = ResourceLocation(lat=lat, lng=lng)

        def distance(amb):
            loc = ResourceLocation(
                lat=amb.get("location", {}).get("lat", 0),
                lng=amb.get("location", {}).get("lng", 0)
            )
            return patient_loc.distance_to(loc)

        # Sort by distance
        sorted_ambulances = sorted(
            available_ambulances.items(),
            key=lambda x: distance(x[1])
        )

        if sorted_ambulances:
            amb_id, amb_info = sorted_ambulances[0]
            # Add response time estimate
            dist = distance(amb_info)
            amb_info["response_time_minutes"] = (dist / AMBULANCE_SPEED_KMH) * 60
            return amb_id, amb_info

        return None, None

    def _find_best_hospital(
        self,
        signal: DistressSignal,
        ambulance_id: str,
        available_hospitals: List[str],
        routes: Dict[str, TransportRoute]
    ) -> Tuple[Optional[str], Optional[TransportRoute]]:
        """Find best hospital and route for the emergency."""
        if not available_hospitals:
            return None, None

        # For now, pick the first available hospital with a route
        # In a real system, this would consider:
        # - Hospital capabilities vs emergency type
        # - Current load
        # - Travel time
        # - Staff availability

        patient_loc = ResourceLocation(
            lat=signal.location.lat,
            lng=signal.location.lng
        )

        for hosp_id in available_hospitals:
            # Find route to this hospital
            for route in routes.values():
                # Match route by destination hospital ID pattern
                if hosp_id in route.to_location.address or hosp_id in str(route.to_location.address):
                    return hosp_id, route

        # Fallback: just return first hospital with no route
        return available_hospitals[0] if available_hospitals else None, None

    def _calculate_eta(
        self,
        ambulance_info: Dict,
        route: Optional[TransportRoute],
        signal: DistressSignal
    ) -> float:
        """Calculate estimated time of arrival."""
        # Response time to patient
        response_time = ambulance_info.get("response_time_minutes", 10)

        # Transport to hospital
        transport_time = route.get_effective_duration() if route else 20

        # Dispatch overhead
        dispatch_time = 2

        return response_time + transport_time + dispatch_time

    def _handle_emergency_call(self, message: ActionMessage) -> None:
        """Handle incoming emergency call."""
        # This would be called when 911/emergency call received
        logger.info(f"Emergency call received: {message.content}")

    def _handle_backup_request(self, message: ActionMessage) -> List[ActionMessage]:
        """Handle backup request from ambulance."""
        messages = []

        from_agent = message.from_agent
        reason = message.content.get("reason", "unknown")

        logger.info(f"Backup requested by {from_agent}: {reason}")

        # Find another ambulance
        if self._available_ambulances:
            backup_id, backup_info = list(self._available_ambulances.items())[0]

            messages.append(ActionMessage(
                message_id=str(uuid.uuid4()),
                action_type=ResponseActionType.DISPATCH,
                from_agent=self.agent_id,
                to_agent=backup_id,
                content={
                    "type": "backup_dispatch",
                    "reason": reason,
                    "primary_ambulance": from_agent,
                    "priority": "high"
                }
            ))

            # Remove from available
            del self._available_ambulances[backup_id]

            self.log_action(
                ResponseActionType.REQUEST_BACKUP,
                {
                    "from_ambulance": from_agent,
                    "backup_ambulance": backup_id,
                    "reason": reason
                },
                outcome="backup_dispatched"
            )

        else:
            # Escalate
            self.set_state("escalating", ResponseActionType.ESCALATE)
            logger.warning(f"No ambulances available for backup - escalating")

        return messages

    def _handle_reroute_request(self, message: ActionMessage) -> List[ActionMessage]:
        """Handle reroute request from ambulance."""
        messages = []

        ambulance_id = message.from_agent
        new_route = message.content.get("new_route")
        reason = message.content.get("reason", "Route blocked")

        logger.info(f"Reroute requested by {ambulance_id}: {reason}")

        # Notify hospital of delay
        case_info = self._dispatched_ambulances.get(ambulance_id, {})
        case_id = case_info.get("case_id")

        if case_id and case_id in self._active_cases:
            hosp_id = self._active_cases[case_id]["assigned_hospital"]
            if hosp_id:
                messages.append(ActionMessage(
                    message_id=str(uuid.uuid4()),
                    action_type=ResponseActionType.UPDATE_STATUS,
                    from_agent=self.agent_id,
                    to_agent=hosp_id,
                    content={
                        "ambulance_id": ambulance_id,
                        "status": "delayed",
                        "new_eta_minutes": message.content.get("eta_increase_minutes", 5),
                        "reason": reason
                    }
                ))

        return messages

    def _handle_status_update(self, message: ActionMessage) -> None:
        """Handle status updates from ambulances/hospitals."""
        content = message.content
        status = content.get("status")

        if status == "en_route":
            logger.debug(
                f"Ambulance {message.from_agent} en route, "
                f"ETA {content.get('eta_minutes')} min"
            )
        elif status == "at_patient":
            logger.info(f"Ambulance {message.from_agent} at patient")
        elif status == "delayed":
            logger.info(
                f"Ambulance {message.from_agent} delayed: "
                f"{content.get('reason', 'unknown')}"
            )

    def _handle_ot_ready(self, message: ActionMessage) -> None:
        """Handle OT ready notification from hospital."""
        content = message.content
        hospital_id = message.from_agent

        logger.info(
            f"Hospital {hospital_id}: OT ready at "
            f"{content.get('ot_ready_at', 'unknown time')}"
        )

    def _handle_arrival(self, message: ActionMessage) -> None:
        """Handle patient arrival at hospital."""
        content = message.content
        case_id = content.get("patient_id")

        logger.info(
            f"Patient {case_id} arrived at hospital "
            f"{content.get('hospital_id')}"
        )

        # Mark case as completed
        if case_id in self._active_cases:
            self._active_cases[case_id]["status"] = "completed"
            self._active_cases[case_id]["completion_time"] = self._simulation_time

            # Release ambulance
            ambulance_id = self._active_cases[case_id]["dispatched_ambulance"]
            if ambulance_id and ambulance_id in self._dispatched_ambulances:
                del self._dispatched_ambulances[ambulance_id]
                self._available_ambulances[ambulance_id] = {"status": "available"}

        # Return to monitoring if no active cases
        if not self._dispatched_ambulances:
            self.set_state("monitoring", ResponseActionType.COORDINATE)

    def _check_case_status(self) -> None:
        """Check status of all active cases."""
        for case_id, case in self._active_cases.items():
            if case["status"] == "dispatching":
                # Check if ambulance was dispatched
                amb_id = case.get("dispatched_ambulance")
                if amb_id and amb_id not in self._dispatched_ambulances:
                    # Ambulance status changed, update case
                    case["status"] = "in_progress"

            # Check for timeouts
            if case["status"] in ("dispatching", "in_progress"):
                elapsed = self._simulation_time - case.get("start_time", self._simulation_time)
                time_window = case["signal"].time_window_minutes if "signal" in case else 30

                if elapsed > time_window:
                    if "timeout" not in case.get("issues", []):
                        case["issues"].append("timeout")
                        logger.warning(
                            f"Case {case_id} exceeding time window: "
                            f"{elapsed:.1f} min > {time_window} min"
                        )

    def update_availability(
        self,
        ambulances: Dict[str, Any],
        hospitals: List[str]
    ) -> None:
        """Update available resources."""
        self._available_ambulances = {
            k: v for k, v in ambulances.items()
            if v.get("status") == "available"
        }
        self._available_hospitals = hospitals

    def get_dashboard_report(self) -> Dict[str, Any]:
        """Get dispatch dashboard report."""
        active_count = sum(
            1 for c in self._active_cases.values()
            if c["status"] in ("dispatching", "in_progress")
        )

        return {
            "dispatch_id": self.agent_id,
            "current_state": self.current_state,
            "available_ambulances": len(self._available_ambulances),
            "dispatched_ambulances": len(self._dispatched_ambulances),
            "available_hospitals": len(self._available_hospitals),
            "active_cases": active_count,
            "active_cases_count": active_count,
            "total_cases": len(self._active_cases),
            "simulation_time": self._simulation_time
        }

    def get_active_cases(self) -> List[Dict[str, Any]]:
        """Get all active cases."""
        return [
            {
                "case_id": case_id,
                "status": case["status"],
                "start_time": case.get("start_time"),
                "eta": case.get("eta"),
                "ambulance_id": case.get("dispatched_ambulance"),
                "hospital_id": case.get("assigned_hospital"),
                "issues": case.get("issues", [])
            }
            for case_id, case in self._active_cases.items()
            if case["status"] in ("dispatching", "in_progress")
        ]

    def to_dict(self) -> Dict[str, Any]:
        """Export dispatch agent state."""
        base = super().to_dict()
        base.update({
            "available_ambulances": list(self._available_ambulances.keys()),
            "dispatched_ambulances": list(self._dispatched_ambulances.keys()),
            "available_hospitals": self._available_hospitals,
            "active_cases_count": len([
                c for c in self._active_cases.values()
                if c["status"] in ("dispatching", "in_progress")
            ]),
            "dashboard_report": self.get_dashboard_report()
        })
        return base
