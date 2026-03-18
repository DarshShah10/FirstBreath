"""
Emergency Response Simulation Engine.

Coordinates all agents and runs the emergency response simulation:
- Initializes agents
- Runs simulation loop
- Manages parallel tracks
- Handles agent communication
- Generates intervention recommendations
"""

from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ...models.emergency_case import (
    DistressSignal, EmergencyCase, EmergencySeverity,
    Intervention, InterventionAction
)
from ...models.response_action import ActionMessage, ResponseActionType
from ...models.response_resource import (
    ResourceRegistry, Hospital, Ambulance, MedicalStaff,
    BloodBank, TransportRoute, ResourceLocation
)
from .base_agent import BaseAgent, AgentEventBus
from .ambulance_agent import AmbulanceAgent
from .hospital_agent import HospitalAgent
from .dispatch_agent import DispatchAgent
from .city_condition_agent import CityConditionAgent
from ...utils.logger import get_logger

logger = get_logger('mirofish.simulation')


@dataclass
class SimulationTrack:
    """A parallel simulation track."""
    track_id: str
    name: str
    agents: Dict[str, BaseAgent]
    status: str = "pending"  # pending, running, completed, failed
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    result: Optional[Dict] = None


@dataclass
class SimulationState:
    """Current state of the simulation."""
    simulation_id: str
    status: str  # initializing, running, paused, completed, failed
    current_time: float = 0.0
    speed: float = 1.0  # Simulation speed multiplier
    tracks: Dict[str, SimulationTrack] = field(default_factory=dict)
    message_log: List[Dict] = field(default_factory=list)
    action_log: List[Dict] = field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "status": self.status,
            "current_time": self.current_time,
            "speed": self.speed,
            "tracks": {
                k: {"name": v.name, "status": v.status}
                for k, v in self.tracks.items()
            },
            "message_count": len(self.message_log),
            "action_count": len(self.action_log)
        }


class EmergencySimulationEngine:
    """
    Main simulation engine for emergency response.

    Coordinates:
    - DispatchAgent (central coordinator)
    - AmbulanceAgents (transport)
    - HospitalAgents (receiving facilities)
    - CityConditionAgent (external factors)

    Runs parallel tracks for different scenarios.
    """

    # Simulation time step (in minutes)
    TIME_STEP = 0.5

    def __init__(
        self,
        resource_registry: ResourceRegistry,
        simulation_speed: float = 1.0
    ):
        self.resource_registry = resource_registry
        self.simulation_speed = simulation_speed

        # Agents
        self.dispatch: Optional[DispatchAgent] = None
        self.ambulances: Dict[str, AmbulanceAgent] = {}
        self.hospitals: Dict[str, HospitalAgent] = {}
        self.city_conditions: Optional[CityConditionAgent] = None

        # Simulation state
        self.state: Optional[SimulationState] = None
        self._running = False
        self._paused = False

        # Callbacks
        self._step_callbacks: List[Callable] = []
        self._event_bus = AgentEventBus()

        logger.info("EmergencySimulationEngine initialized")

    def initialize(
        self,
        simulation_id: Optional[str] = None,
        ambulance_ids: Optional[List[str]] = None,
        hospital_ids: Optional[List[str]] = None
    ) -> str:
        """
        Initialize the simulation with specified resources.

        Args:
            simulation_id: Optional ID, auto-generated if not provided
            ambulance_ids: Specific ambulances to include
            hospital_ids: Specific hospitals to include

        Returns:
            Simulation ID
        """
        sim_id = simulation_id or f"sim_{uuid.uuid4().hex[:12]}"

        # Create simulation state
        self.state = SimulationState(
            simulation_id=sim_id,
            status="initializing",
            started_at=datetime.now().isoformat()
        )

        # Initialize agents
        self._initialize_agents(ambulance_ids, hospital_ids)

        # Create simulation tracks
        self._create_tracks()

        self.state.status = "ready"
        logger.info(f"Simulation {sim_id} initialized")

        return sim_id

    def _initialize_agents(
        self,
        ambulance_ids: Optional[List[str]] = None,
        hospital_ids: Optional[List[str]] = None
    ) -> None:
        """Initialize all agents."""
        # Dispatch
        self.dispatch = DispatchAgent()

        # City conditions
        self.city_conditions = CityConditionAgent()

        # Set up route conditions from config
        for route in self.resource_registry.routes.values():
            if route.current_status != "clear":
                self.city_conditions.set_route_condition(
                    route.route_id,
                    route.current_status,
                    reason=route.block_reason
                )

        # Ambulances
        amb_list = ambulance_ids if ambulance_ids else list(self.resource_registry.ambulances.keys())
        for amb_id in amb_list:
            ambulance = self.resource_registry.ambulances.get(amb_id)
            if ambulance:
                self.ambulances[amb_id] = AmbulanceAgent(ambulance, self.simulation_speed)

        # Hospitals
        hosp_list = hospital_ids if hospital_ids else list(self.resource_registry.hospitals.keys())
        for hosp_id in hosp_list:
            hospital = self.resource_registry.hospitals.get(hosp_id)
            if hospital:
                staff = self.resource_registry.get_staff_for_hospital(hosp_id)
                blood_bank = self._get_blood_bank_for_hospital(hosp_id)
                self.hospitals[hosp_id] = HospitalAgent(hospital, staff, blood_bank)

        # Subscribe to events
        self._setup_event_subscriptions()

        logger.info(
            f"Agents initialized: {len(self.ambulances)} ambulances, "
            f"{len(self.hospitals)} hospitals"
        )

    def _get_blood_bank_for_hospital(self, hospital_id: str) -> Optional[BloodBank]:
        """Get blood bank associated with hospital."""
        for bb in self.resource_registry.blood_banks.values():
            if bb.hospital_id == hospital_id:
                return bb
        return None

    def _create_tracks(self) -> None:
        """Create simulation tracks."""
        # Primary response track
        self.state.tracks["primary"] = SimulationTrack(
            track_id="primary",
            name="Primary Response",
            agents={
                "dispatch": self.dispatch,
                "city": self.city_conditions
            }
        )

        # Ambulance track
        for amb_id, amb in self.ambulances.items():
            self.state.tracks["primary"].agents[amb_id] = amb

        # Hospital track
        for hosp_id, hosp in self.hospitals.items():
            self.state.tracks["primary"].agents[hosp_id] = hosp

    def _setup_event_subscriptions(self) -> None:
        """Set up event subscriptions between agents."""
        # All ambulances subscribe to dispatch
        if self.dispatch:
            for amb in self.ambulances.values():
                self.dispatch.subscribe_to_agent(amb.agent_id)

        # Hospitals subscribe to ambulances
        for hosp in self.hospitals.values():
            for amb in self.ambulances.values():
                amb.subscribe_to_agent(hosp.agent_id)

        # City conditions emits events that ambulances listen to
        if self.city_conditions:
            self.city_conditions.on_condition_change(self._on_route_condition_change)

    def _on_route_condition_change(
        self,
        route_id: str,
        old_condition: str,
        new_condition: str,
        reason: Optional[str]
    ) -> None:
        """Handle route condition changes."""
        logger.info(
            f"Route {route_id} changed: {old_condition} -> {new_condition} ({reason})"
        )

        # Update route in registry
        route = self.resource_registry.routes.get(route_id)
        if route:
            route.current_status = new_condition
            route.block_reason = reason

        # Notify ambulances on affected routes
        for amb in self.ambulances.values():
            if amb.current_route and amb.current_route.route_id == route_id:
                if new_condition == "blocked":
                    # Ambulance needs to reroute
                    logger.info(f"Ambulance {amb.agent_id} on blocked route {route_id}")

    def run_emergency_case(
        self,
        signal: DistressSignal
    ) -> Tuple[EmergencyCase, List[ActionMessage]]:
        """
        Run an emergency case through the simulation.

        Args:
            signal: The distress signal

        Returns:
            Tuple of (EmergencyCase with results, messages sent)
        """
        if not self.state or self.state.status not in ("ready", "completed"):
            raise RuntimeError("Simulation not initialized")

        # Initialize if needed
        if self.state.status == "completed":
            self.initialize(self.state.simulation_id)

        self.state.status = "running"

        # Dispatch
        available_amb = {
            amb_id: amb.ambulance.to_dict()
            for amb_id, amb in self.ambulances.items()
            if amb.current_state == "available"
        }
        available_hosps = [
            hosp_id for hosp_id, hosp in self.hospitals.items()
            if hosp.current_state in ("ready", "alerted")
        ]

        case_id, dispatch_messages = self.dispatch.receive_emergency(
            signal=signal,
            available_ambulances=available_amb,
            available_hospitals=available_hosps,
            routes=self.resource_registry.routes
        )

        if not case_id:
            logger.error(f"Failed to dispatch case {signal.case_id}")
            return EmergencyCase(
                distress_signal=signal,
                status="failed",
                bottlenecks=["dispatch_failed"]
            ), []

        # Create emergency case
        case = EmergencyCase(
            distress_signal=signal,
            status="simulating",
            simulation_id=self.state.simulation_id
        )

        # Process dispatch messages
        for msg in dispatch_messages:
            self._deliver_message(msg)

        # Run simulation steps
        max_steps = 500  # Prevent infinite loops
        case_completed = False

        for step in range(max_steps):
            # Run one simulation step
            messages = self._simulation_step()

            # Check if case completed
            case_result = self._check_case_completion(case_id)
            if case_result:
                case_completed = True
                case = case_result
                break

            # Fire step callbacks
            for callback in self._step_callbacks:
                try:
                    callback(self.state.current_time, messages)
                except Exception as e:
                    logger.error(f"Step callback error: {e}")

        if not case_completed:
            case.status = "timeout"
            case.bottlenecks.append("simulation_timeout")

        self.state.status = "completed"
        self.state.completed_at = datetime.now().isoformat()

        # Generate interventions if failed
        if case.status in ("failed", "timeout"):
            case.interventions = self._generate_interventions(case)

        return case, self.state.message_log

    def _simulation_step(self) -> List[ActionMessage]:
        """Run one simulation step. Returns messages generated."""
        messages = []

        # Increment time
        self.state.current_time += self.TIME_STEP * self.simulation_speed

        # Step each agent
        for track in self.state.tracks.values():
            if track.status == "running":
                for agent in list(track.agents.values()):
                    try:
                        agent_messages = agent.step(self.state.current_time)
                        messages.extend(agent_messages)

                        # Deliver messages
                        for msg in agent_messages:
                            self._deliver_message(msg)
                            self.state.message_log.append(msg.to_dict())

                    except Exception as e:
                        logger.error(f"Agent {agent.agent_id} step error: {e}")

        return messages

    def _deliver_message(self, message: ActionMessage) -> None:
        """Deliver a message to the target agent."""
        target_id = message.to_agent

        # Deliver to dispatch
        if target_id == "ems_dispatch" and self.dispatch:
            self.dispatch.receive_message(message)

        # Deliver to ambulance
        elif target_id in self.ambulances:
            self.ambulances[target_id].receive_message(message)

        # Deliver to hospital
        elif target_id in self.hospitals:
            self.hospitals[target_id].receive_message(message)

        # Broadcast to all
        elif target_id == "all":
            for agent in list(self.ambulances.values()) + list(self.hospitals.values()):
                agent.receive_message(message)

    def _check_case_completion(self, case_id: str) -> Optional[EmergencyCase]:
        """Check if a case has completed."""
        # Check dispatch case status
        cases = self.dispatch.get_active_cases()
        active_case = next((c for c in cases if case_id in str(c.get("case_id", ""))), None)

        if not active_case:
            # Case no longer active - check if completed
            dispatched = self.dispatch._dispatched_ambulances
            available = self.dispatch._available_ambulances

            # Find the ambulance from this case
            case_ambulance = None
            for amb_id, amb in self.ambulances.items():
                if amb.current_patient_id and case_id in str(amb.current_patient_id):
                    case_ambulance = amb
                    break

            if case_ambulance:
                if case_ambulance.current_state == "at_hospital":
                    # Success!
                    return EmergencyCase(
                        distress_signal=self.dispatch._active_cases.get(case_id, {}).get("signal"),
                        status="success",
                        simulation_id=self.state.simulation_id,
                        primary_ambulance_id=case_ambulance.agent_id,
                        estimated_response_time_minutes=self.state.current_time,
                        completed_at=datetime.now().isoformat()
                    )
                elif case_ambulance.current_state == "available":
                    # Returned to base - completed
                    return EmergencyCase(
                        distress_signal=self.dispatch._active_cases.get(case_id, {}).get("signal"),
                        status="completed",
                        simulation_id=self.state.simulation_id,
                        primary_ambulance_id=case_ambulance.agent_id,
                        completed_at=datetime.now().isoformat()
                    )

        return None

    def _generate_interventions(self, failed_case: EmergencyCase) -> List[Intervention]:
        """Generate intervention recommendations for a failed case."""
        interventions = []

        # Analyze bottlenecks
        bottlenecks = failed_case.bottlenecks or []

        # Intervention 1: Reroute
        if "route_blocked" in bottlenecks or any("route" in b for b in bottlenecks):
            interventions.append(Intervention(
                intervention_id="intervention_1",
                name="Reroute via Alternate Path",
                description="Use alternate route to avoid blocked road",
                success_probability=0.85,
                estimated_time_minutes=15,
                actions=[
                    InterventionAction(
                        action_id="action_1_1",
                        priority="immediate",
                        responsible="EMS Dispatch",
                        description="Confirm alternate route is clear",
                        time_limit_minutes=1
                    ),
                    InterventionAction(
                        action_id="action_1_2",
                        priority="immediate",
                        responsible="Ambulance",
                        description="Switch to alternate route",
                        time_limit_minutes=1
                    )
                ],
                is_recommended=True,
                risk_level="moderate"
            ))

        # Intervention 2: Backup Ambulance
        interventions.append(Intervention(
            intervention_id="intervention_2",
            name="Dispatch Backup Ambulance",
            description="Send second ambulance as backup",
            success_probability=0.78,
            estimated_time_minutes=20,
            actions=[
                InterventionAction(
                    action_id="action_2_1",
                    priority="immediate",
                    responsible="EMS Dispatch",
                    description="Dispatch nearest backup ambulance",
                    time_limit_minutes=2
                )
            ],
            is_recommended=False,
            risk_level="low"
        ))

        # Intervention 3: Alert Hospital Early
        interventions.append(Intervention(
            intervention_id="intervention_3",
            name="Early Hospital Alert",
            description="Alert hospital immediately for parallel preparation",
            success_probability=0.92,
            estimated_time_minutes=5,
            actions=[
                InterventionAction(
                    action_id="action_3_1",
                    priority="immediate",
                    responsible="EMS Dispatch",
                    description="Alert hospital with ETA",
                    time_limit_minutes=1
                ),
                InterventionAction(
                    action_id="action_3_2",
                    priority="immediate",
                    responsible="Hospital",
                    description="Begin OT preparation immediately",
                    time_limit_minutes=1
                )
            ],
            is_recommended=False,
            risk_level="low"
        ))

        return interventions

    def on_step(self, callback: Callable) -> None:
        """Register callback for simulation steps."""
        self._step_callbacks.append(callback)

    def get_state(self) -> SimulationState:
        """Get current simulation state."""
        return self.state

    def get_agent_states(self) -> Dict[str, Dict]:
        """Get state of all agents."""
        states = {}

        if self.dispatch:
            states["dispatch"] = self.dispatch.get_state().to_dict()

        for amb_id, amb in self.ambulances.items():
            states[amb_id] = amb.to_dict()

        for hosp_id, hosp in self.hospitals.items():
            states[hosp_id] = hosp.to_dict()

        if self.city_conditions:
            states["city"] = self.city_conditions.to_dict()

        return states

    def get_message_log(self) -> List[Dict]:
        """Get all messages sent during simulation."""
        return self.state.message_log if self.state else []

    def pause(self) -> None:
        """Pause the simulation."""
        self._paused = True
        if self.state:
            self.state.status = "paused"

    def resume(self) -> None:
        """Resume the simulation."""
        self._paused = False
        if self.state:
            self.state.status = "running"

    def stop(self) -> None:
        """Stop the simulation."""
        self._running = False
        self._paused = False
        if self.state:
            self.state.status = "stopped"
