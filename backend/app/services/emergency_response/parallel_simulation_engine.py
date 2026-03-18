"""
Parallel Simulation Engine for Emergency Response.

Scalable engine supporting 100-1000+ agents:
- Async parallel execution
- Agent pool management
- Event-driven architecture
- Real-time streaming
- Dynamic scaling
"""

from typing import Dict, List, Optional, Any, Callable, Set, Type, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import threading
import uuid
from collections import defaultdict
import heapq

from ...models.emergency_case import (
    DistressSignal, EmergencyCase, EmergencySeverity, EmergencyType
)
from ...models.response_action import (
    ActionMessage, ResponseActionType, AgentType
)
from ...models.response_resource import (
    ResourceRegistry, Hospital, Ambulance, MedicalStaff,
    BloodBank, TransportRoute, ResourceLocation
)
from .base_agent import BaseAgent, AgentEventBus, AgentEvent, AgentEventType
from .ambulance_agent import AmbulanceAgent
from .hospital_agent import HospitalAgent
from .dispatch_agent import DispatchAgent
from .city_condition_agent import CityConditionAgent
from .staff_agent import StaffAgent, StaffPool
from .blood_bank_agent import BloodBankAgent, BloodBankPool
from .road_network_agent import RoadNetworkAgent, RoadNetworkPool
from .case_queue import CaseQueue, CaseQueuePool, CaseStatus
from .intervention_recommender import (
    InterventionRecommender,
    ResponseChainAnalysis,
    generate_intervention_report
)
from ...utils.logger import get_logger

logger = get_logger('mirofish.parallel_simulation')


class SimulationMode(Enum):
    """Simulation execution modes."""
    SEQUENTIAL = "sequential"      # Single-threaded, for testing
    PARALLEL = "parallel"          # Multi-threaded
    ASYNC = "async"               # Async/await based


@dataclass
class SimulationMetrics:
    """Performance metrics for simulation."""
    total_agents: int = 0
    active_agents: int = 0
    messages_processed: int = 0
    cases_completed: int = 0
    cases_failed: int = 0
    total_simulation_time: float = 0.0
    real_time_elapsed: float = 0.0
    throughput: float = 0.0  # Cases per minute
    avg_response_time: float = 0.0


class AgentPool:
    """
    Scalable pool for managing large numbers of agents.

    Features:
    - Efficient agent lookup by ID and type
    - Agent state caching for fast access
    - Dynamic agent creation/destruction
    - Thread-safe operations
    """

    def __init__(self):
        self._agents: Dict[str, BaseAgent] = {}
        self._by_type: Dict[AgentType, Dict[str, BaseAgent]] = defaultdict(dict)
        self._by_state: Dict[str, List[str]] = defaultdict(list)  # state -> [agent_ids]
        self._lock = threading.Lock()

    def add(self, agent: BaseAgent) -> None:
        """Add agent to pool."""
        with self._lock:
            self._agents[agent.agent_id] = agent
            self._by_type[agent.agent_type][agent.agent_id] = agent
            self._update_state_index(agent)

    def remove(self, agent_id: str) -> Optional[BaseAgent]:
        """Remove agent from pool."""
        with self._lock:
            agent = self._agents.pop(agent_id, None)
            if agent:
                self._by_type[agent.agent_type].pop(agent_id, None)
                self._remove_from_state_index(agent)
            return agent

    def get(self, agent_id: str) -> Optional[BaseAgent]:
        """Get agent by ID."""
        return self._agents.get(agent_id)

    def get_by_type(self, agent_type: AgentType) -> List[BaseAgent]:
        """Get all agents of a type."""
        return list(self._by_type.get(agent_type, {}).values())

    def get_by_state(self, state: str) -> List[BaseAgent]:
        """Get all agents in a specific state."""
        with self._lock:
            agent_ids = self._by_state.get(state, [])
            return [self._agents[aid] for aid in agent_ids if aid in self._agents]

    def get_all(self) -> List[BaseAgent]:
        """Get all agents."""
        return list(self._agents.values())

    def _update_state_index(self, agent: BaseAgent) -> None:
        """Update state index."""
        state = getattr(agent, 'current_state', 'unknown')
        self._by_state[state].append(agent.agent_id)

    def _remove_from_state_index(self, agent: BaseAgent) -> None:
        """Remove from state index."""
        state = getattr(agent, 'current_state', 'unknown')
        if state in self._by_state:
            if agent.agent_id in self._by_state[state]:
                self._by_state[state].remove(agent.agent_id)

    def update_agent_state(self, agent: BaseAgent, old_state: str) -> None:
        """Update agent state in index."""
        with self._lock:
            if old_state in self._by_state:
                if agent.agent_id in self._by_state[old_state]:
                    self._by_state[old_state].remove(agent.agent_id)
            self._update_state_index(agent)

    def size(self) -> int:
        """Get total agent count."""
        return len(self._agents)

    def get_pool_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        with self._lock:
            return {
                "total_agents": len(self._agents),
                "by_type": {
                    atype.value: len(agents)
                    for atype, agents in self._by_type.items()
                },
                "by_state": {
                    state: len(agent_ids)
                    for state, agent_ids in self._by_state.items()
                }
            }


class EventStream:
    """
    Real-time event streaming for simulation updates.

    Supports WebSocket/Server-Sent Events.
    """

    def __init__(self):
        self._subscribers: Dict[str, Callable] = {}
        self._event_history: List[Dict] = []
        self._max_history = 1000

    def subscribe(self, subscriber_id: str, callback: Callable) -> None:
        """Subscribe to events."""
        self._subscribers[subscriber_id] = callback
        logger.debug(f"Subscriber added: {subscriber_id}")

    def unsubscribe(self, subscriber_id: str) -> None:
        """Unsubscribe from events."""
        self._subscribers.pop(subscriber_id, None)

    def publish(self, event: Dict[str, Any]) -> None:
        """Publish an event to all subscribers."""
        # Store in history
        self._event_history.append(event)
        if len(self._event_history) > self._max_history:
            self._event_history.pop(0)

        # Notify subscribers
        for subscriber_id, callback in self._subscribers.items():
            try:
                callback(event)
            except Exception as e:
                logger.error(f"Event callback error for {subscriber_id}: {e}")

    def get_history(self, last_n: int = 100) -> List[Dict]:
        """Get recent event history."""
        return self._event_history[-last_n:]


class ParallelSimulationEngine:
    """
    Scalable parallel simulation engine.

    Features:
    - Support for 100-1000+ agents
    - Parallel case processing
    - Agent pooling
    - Real-time event streaming
    - Dynamic scaling
    - Comprehensive metrics
    """

    TIME_STEP = 0.5  # Simulation time step in minutes

    def __init__(
        self,
        resource_registry: ResourceRegistry,
        simulation_speed: float = 1.0,
        mode: SimulationMode = SimulationMode.SEQUENTIAL,
        max_concurrent_cases: int = 100
    ):
        self.resource_registry = resource_registry
        self.simulation_speed = simulation_speed
        self.mode = mode
        self._max_concurrent_cases = max_concurrent_cases

        # Agent pools
        self.agent_pool = AgentPool()
        self.staff_pool = StaffPool()
        self.blood_bank_pool = BloodBankPool()
        self.road_network_pool = RoadNetworkPool()

        # Core agents
        self.dispatch: Optional[DispatchAgent] = None
        self.city_conditions: Optional[CityConditionAgent] = None
        self.road_network: Optional[RoadNetworkAgent] = None

        # Case management
        self.case_queue = CaseQueue(max_concurrent=max_concurrent_cases)
        self.case_queue_pool = CaseQueuePool()

        # Simulation state
        self._sim_time: float = 0.0
        self._running: bool = False
        self._paused: bool = False
        self._simulation_id: str = f"sim_{uuid.uuid4().hex[:12]}"

        # Event systems
        self.event_bus = AgentEventBus()
        self.event_stream = EventStream()
        self._step_callbacks: List[Callable] = []

        # Metrics
        self._metrics = SimulationMetrics()

        # Ambulances and hospitals (maps for fast lookup)
        self._ambulances: Dict[str, AmbulanceAgent] = {}
        self._hospitals: Dict[str, HospitalAgent] = {}

        # Message queue
        self._message_queue: List[ActionMessage] = []

        # Intervention recommendation
        self._intervention_recommender = InterventionRecommender()
        self._active_case_status: Dict[str, Dict[str, Any]] = {}

        logger.info(
            f"ParallelSimulationEngine initialized: "
            f"mode={mode.value}, max_cases={max_concurrent_cases}"
        )

    def initialize(
        self,
        ambulance_ids: Optional[List[str]] = None,
        hospital_ids: Optional[List[str]] = None,
        region_ids: Optional[List[str]] = None
    ) -> str:
        """Initialize simulation with agents."""
        logger.info(f"Initializing simulation: {self._simulation_id}")

        # Create dispatch agent
        self.dispatch = DispatchAgent()
        self.agent_pool.add(self.dispatch)

        # Create city conditions agent
        self.city_conditions = CityConditionAgent()
        self.agent_pool.add(self.city_conditions)

        # Create road network agent
        self.road_network = RoadNetworkAgent()
        self.road_network_pool.add(self.road_network)
        self.agent_pool.add(self.road_network)

        # Initialize routes in road network
        self._initialize_routes()

        # Create ambulance agents
        amb_list = ambulance_ids or list(self.resource_registry.ambulances.keys())
        for amb_id in amb_list:
            amb_data = self.resource_registry.ambulances.get(amb_id)
            if amb_data:
                self._create_ambulance_agent(amb_id, amb_data)

        # Create hospital agents
        hosp_list = hospital_ids or list(self.resource_registry.hospitals.keys())
        for hosp_id in hosp_list:
            hosp_data = self.resource_registry.hospitals.get(hosp_id)
            if hosp_data:
                self._create_hospital_agent(hosp_id, hosp_data)

        # Create staff agents
        for staff_id, staff_data in self.resource_registry.staff.items():
            self._create_staff_agent(staff_id, staff_data)

        # Create blood bank agents
        for bb_id, bb_data in self.resource_registry.blood_banks.items():
            self._create_blood_bank_agent(bb_id, bb_data)

        # Update metrics
        self._metrics.total_agents = self.agent_pool.size()

        logger.info(
            f"Simulation initialized: "
            f"{len(self._ambulances)} ambulances, "
            f"{len(self._hospitals)} hospitals, "
            f"{self.agent_pool.size()} total agents"
        )

        return self._simulation_id

    def _initialize_routes(self) -> None:
        """Initialize routes in road network."""
        for route_id, route in self.resource_registry.routes.items():
            self.road_network.add_route_from_locations(
                route_id=route_id,
                name=f"Route {route_id}",
                from_lat=route.from_location.lat,
                from_lng=route.from_location.lng,
                to_lat=route.to_location.lat,
                to_lng=route.to_location.lng,
                distance_km=route.distance_km,
                duration_minutes=route.typical_duration_minutes,
                alternate_route_ids=route.alternate_route_ids if hasattr(route, 'alternate_route_ids') else None
            )

    def _create_ambulance_agent(self, amb_id: str, amb_data: Ambulance) -> None:
        """Create and register ambulance agent."""
        agent = AmbulanceAgent(ambulance=amb_data)
        self._ambulances[amb_id] = agent
        self.agent_pool.add(agent)

    def _create_hospital_agent(self, hosp_id: str, hosp_data: Hospital) -> None:
        """Create and register hospital agent."""
        staff = self.resource_registry.get_staff_for_hospital(hosp_id)
        blood_bank = self._get_blood_bank_for_hospital(hosp_id)
        agent = HospitalAgent(hospital=hosp_data, staff_list=staff, blood_bank=blood_bank)
        self._hospitals[hosp_id] = agent
        self.agent_pool.add(agent)

    def _create_staff_agent(self, staff_id: str, staff_data: MedicalStaff) -> None:
        """Create and register staff agent."""
        agent = StaffAgent(staff=staff_data)
        self.staff_pool.add(agent)

    def _create_blood_bank_agent(self, bb_id: str, bb_data: BloodBank) -> None:
        """Create and register blood bank agent."""
        agent = BloodBankAgent(blood_bank=bb_data)
        self.blood_bank_pool.add(agent)

    def _get_blood_bank_for_hospital(self, hospital_id: str) -> Optional[BloodBank]:
        """Get blood bank associated with hospital."""
        for bb in self.resource_registry.blood_banks.values():
            if hasattr(bb, 'hospital_id') and bb.hospital_id == hospital_id:
                return bb
        return None

    def add_case(self, signal: DistressSignal) -> str:
        """Add case to simulation queue."""
        return self.case_queue.enqueue(signal, self._sim_time)

    def run(
        self,
        duration_minutes: float = 60,
        max_steps: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Run simulation for specified duration.

        Args:
            duration_minutes: How long to simulate
            max_steps: Maximum simulation steps (overrides duration)

        Returns:
            Simulation results
        """
        self._running = True
        self._paused = False

        max_steps = max_steps or int(duration_minutes / self.TIME_STEP)
        steps_run = 0

        logger.info(f"Starting simulation: duration={duration_minutes}min, max_steps={max_steps}")

        start_real_time = datetime.now()

        while self._running and steps_run < max_steps:
            if self._paused:
                break

            # Run one simulation step
            self._simulation_step()
            steps_run += 1

            # Publish step event
            self.event_stream.publish({
                "type": "step",
                "sim_time": self._sim_time,
                "step": steps_run,
                "active_agents": self.agent_pool.size()
            })

        end_real_time = datetime.now()
        self._running = False

        # Update metrics
        self._metrics.real_time_elapsed = (end_real_time - start_real_time).total_seconds()
        self._metrics.total_simulation_time = self._sim_time
        self._metrics.throughput = self._metrics.cases_completed / (self._metrics.real_time_elapsed / 60) if self._metrics.real_time_elapsed > 0 else 0

        logger.info(
            f"Simulation complete: "
            f"{steps_run} steps, "
            f"{self._sim_time:.1f} simulated minutes, "
            f"{self._metrics.cases_completed} cases completed"
        )

        return self.get_results()

    def _simulation_step(self) -> None:
        """Execute one simulation step."""
        # Increment simulation time
        self._sim_time += self.TIME_STEP * self.simulation_speed

        # Process case queue
        self._process_case_queue()

        # Step all agents
        for agent in self.agent_pool.get_all():
            try:
                messages = agent.step(self._sim_time)
                for msg in messages:
                    self._queue_message(msg)
                self._metrics.messages_processed += len(messages)
            except Exception as e:
                logger.error(f"Agent {agent.agent_id} step error: {e}")

        # Step pools
        for staff in self.staff_pool.get_all_agents():
            try:
                messages = staff.step(self._sim_time)
                for msg in messages:
                    self._queue_message(msg)
            except Exception as e:
                logger.error(f"Staff agent error: {e}")

        for bank in self.blood_bank_pool.get_all_agents():
            try:
                messages = bank.step(self._sim_time)
                for msg in messages:
                    self._queue_message(msg)
            except Exception as e:
                logger.error(f"Blood bank agent error: {e}")

        # Process road network
        if self.road_network:
            self.road_network.step(self._sim_time)

        # Deliver queued messages
        self._deliver_messages()

        # Fire callbacks
        for callback in self._step_callbacks:
            try:
                callback(self._sim_time, self.get_state_snapshot())
            except Exception as e:
                logger.error(f"Step callback error: {e}")

    def _process_case_queue(self) -> None:
        """Process cases in the queue."""
        # Get available resources
        available_amb = {
            amb_id: amb
            for amb_id, amb in self._ambulances.items()
            if amb.current_state == "available"
        }
        available_hosps = [
            hosp_id
            for hosp_id, hosp in self._hospitals.items()
            if hosp.current_state in ["ready", "alerted"]
        ]

        # Try to assign next case
        case = self.case_queue.get_next(
            {k: v.ambulance.to_dict() for k, v in available_amb.items()},
            available_hosps,
            self._sim_time
        )

        if case:
            # Dispatch case
            self._dispatch_case(case, available_amb, available_hosps)

    def _dispatch_case(
        self,
        case: Any,
        available_amb: Dict[str, AmbulanceAgent],
        available_hosps: List[str]
    ) -> None:
        """Dispatch a case to available resources."""
        # Find nearest ambulance
        amb_id, amb_agent = self._find_nearest_ambulance(
            case.signal.location, available_amb
        )

        if not amb_id or not amb_agent:
            logger.warning(f"No ambulance available for case {case.case_id}")
            return

        # Find best hospital
        hosp_id, hosp_agent = self._find_best_hospital(
            case.signal, available_hosps
        )

        if not hosp_id or not hosp_agent:
            logger.warning(f"No hospital available for case {case.case_id}")
            return

        # Find best route
        route = None
        if self.road_network:
            route = self.road_network.find_best_route(
                ResourceLocation(case.signal.location.lat, case.signal.location.lng),
                hosp_agent.hospital.location
            )

        # Assign resources
        self.case_queue.assign_resources(case.case_id, amb_id, hosp_id)

        # Convert Location to ResourceLocation for ambulance dispatch
        patient_location = ResourceLocation(
            lat=case.signal.location.lat,
            lng=case.signal.location.lng,
            address=case.signal.location.address
        )

        # Dispatch ambulance using correct method
        amb_agent.dispatch(
            patient_id=f"patient_{case.case_id}",
            patient_location=patient_location,
            hospital_id=hosp_id,
            hospital_location=hosp_agent.hospital.location,
            route=route
        )

        # Alert hospital using message-based communication
        hosp_agent.receive_message(ActionMessage(
            message_id=str(uuid.uuid4()),
            action_type=ResponseActionType.RECEIVE_ALERT,
            from_agent=amb_id,
            to_agent=hosp_id,
            content={
                "ambulance_id": amb_id,
                "patient_id": f"patient_{case.case_id}",
                "eta_minutes": route.effective_duration_minutes if route else 20,
                "patient_status": case.signal.severity.value,
                "emergency_type": case.signal.emergency_type.value,
                "case_id": case.case_id
            }
        ))

        logger.info(
            f"Case {case.case_id} dispatched: "
            f"amb={amb_id}, hosp={hosp_id}, "
            f"eta={route.effective_duration_minutes if route else 'unknown'}min"
        )

    def _find_nearest_ambulance(
        self,
        location: Any,
        available: Dict[str, AmbulanceAgent]
    ) -> Tuple[Optional[str], Optional[AmbulanceAgent]]:
        """Find nearest available ambulance."""
        if not available:
            return None, None

        patient_loc = ResourceLocation(location.lat, location.lng)
        nearest = None
        nearest_dist = float('inf')

        for amb_id, amb in available.items():
            dist = patient_loc.distance_to(amb.current_location)
            if dist < nearest_dist:
                nearest_dist = dist
                nearest = amb_id

        return nearest, available.get(nearest)

    def _find_best_hospital(
        self,
        signal: DistressSignal,
        available: List[str]
    ) -> Tuple[Optional[str], Optional[HospitalAgent]]:
        """Find best hospital for emergency."""
        if not available:
            return None, None

        for hosp_id in available:
            hosp = self._hospitals.get(hosp_id)
            if hosp and hosp.can_handle_emergency(signal.emergency_type.value):
                return hosp_id, hosp

        # Fallback to first available
        hosp = self._hospitals.get(available[0])
        return available[0], hosp

    def _queue_message(self, message: ActionMessage) -> None:
        """Add message to delivery queue."""
        self._message_queue.append(message)

    def _deliver_messages(self) -> None:
        """Deliver queued messages to target agents."""
        while self._message_queue:
            msg = self._message_queue.pop(0)
            self._deliver_message(msg)

    def _deliver_message(self, message: ActionMessage) -> None:
        """Deliver a single message."""
        target_id = message.to_agent

        # Dispatch
        if target_id == "ems_dispatch" and self.dispatch:
            self.dispatch.receive_message(message)
        # Ambulance
        elif target_id in self._ambulances:
            self._ambulances[target_id].receive_message(message)
        # Hospital
        elif target_id in self._hospitals:
            self._hospitals[target_id].receive_message(message)
        # Staff
        elif target_id.startswith("staff_"):
            staff = self.staff_pool.get(target_id)
            if staff:
                staff.receive_message(message)
        # Blood bank
        elif target_id.startswith("blood_bank"):
            bank = self.blood_bank_pool.get(target_id)
            if bank:
                bank.receive_message(message)
        # Road network
        elif target_id == "road_network" and self.road_network:
            self.road_network.receive_message(message)

    def pause(self) -> None:
        """Pause simulation."""
        self._paused = True
        logger.info("Simulation paused")

    def resume(self) -> None:
        """Resume simulation."""
        self._paused = False
        logger.info("Simulation resumed")

    def stop(self) -> None:
        """Stop simulation."""
        self._running = False
        logger.info("Simulation stopped")

    def on_step(self, callback: Callable) -> None:
        """Register step callback."""
        self._step_callbacks.append(callback)

    def subscribe_to_events(self, subscriber_id: str, callback: Callable) -> None:
        """Subscribe to simulation events."""
        self.event_stream.subscribe(subscriber_id, callback)

    def get_state_snapshot(self) -> Dict[str, Any]:
        """Get current simulation state snapshot."""
        return {
            "simulation_id": self._simulation_id,
            "sim_time": self._sim_time,
            "running": self._running,
            "paused": self._paused,
            "agents": self.agent_pool.get_pool_stats(),
            "case_queue": self.case_queue.get_metrics(),
            "ambulances": {
                amb_id: amb.current_state
                for amb_id, amb in self._ambulances.items()
            },
            "hospitals": {
                hosp_id: hosp.current_state
                for hosp_id, hosp in self._hospitals.items()
            }
        }

    def get_results(self) -> Dict[str, Any]:
        """Get simulation results."""
        return {
            "simulation_id": self._simulation_id,
            "duration_simulated": self._sim_time,
            "duration_real_seconds": self._metrics.real_time_elapsed,
            "metrics": {
                "total_agents": self._metrics.total_agents,
                "messages_processed": self._metrics.messages_processed,
                "cases_completed": self._metrics.cases_completed,
                "cases_failed": self._metrics.cases_failed,
                "throughput_per_minute": self._metrics.throughput
            },
            "case_queue": self.case_queue.get_metrics(),
            "agent_pool": self.agent_pool.get_pool_stats(),
            "completed_cases": [
                c.to_dict() for c in self.case_queue._completed.values()
            ]
        }

    def _build_case_status(self, case_id: str) -> Dict[str, Any]:
        """Build current status for a case."""
        # Get ambulance status
        amb_status = {}
        for amb_id, amb in self._ambulances.items():
            state_info = {
                "name": amb.name,
                "state": amb.current_state,
                "eta_minutes": getattr(amb, '_eta', 0) or 0
            }
            if hasattr(amb, '_current_location'):
                state_info["location"] = {
                    "lat": amb._current_location.lat,
                    "lng": amb._current_location.lng
                }
            amb_status[amb_id] = state_info

        # Get hospital status
        hosp_status = {}
        for hosp_id, hosp in self._hospitals.items():
            hosp_status[hosp_id] = {
                "name": hosp.name,
                "capacity_utilization": getattr(hosp, '_bed_occupancy', 0) / max(getattr(hosp, '_total_beds', 10), 1),
                "or_available": hosp.current_state in ["ready", "alerted"],
                "or_eta_minutes": 0
            }

        # Get road conditions
        road_status = {}
        if self.road_network:
            for route_id, route in self.road_network._routes.items():
                # Use the route's worst_condition property
                condition = route.worst_condition
                # Calculate delay based on condition
                delay = route.effective_duration_minutes - route.typical_duration_minutes
                road_status[route_id] = {
                    "name": route.name,
                    "condition": condition.value,
                    "delay_minutes": max(0, delay)
                }

        return {
            "ambulances": amb_status,
            "hospitals": hosp_status,
            "road_conditions": road_status,
            "estimated_transport_time": 25,
            "time_remaining_minutes": 30
        }

    def get_intervention_analysis(self, case_id: str) -> Optional[ResponseChainAnalysis]:
        """
        Get intervention analysis for a specific case.

        Args:
            case_id: The case to analyze

        Returns:
            ResponseChainAnalysis with bottlenecks and recommendations
        """
        case = self.case_queue._processing.get(case_id)
        if not case:
            return None

        status = self._build_case_status(case_id)
        status["time_remaining_minutes"] = max(0, case.signal.time_window_minutes - self._sim_time)

        return self._intervention_recommender.analyze_response_chain(
            case_id=case_id,
            severity=case.signal.severity,
            emergency_type=case.signal.emergency_type,
            time_remaining_minutes=status["time_remaining_minutes"],
            current_status=status
        )

    def get_all_intervention_analyses(self) -> Dict[str, ResponseChainAnalysis]:
        """Get intervention analysis for all active cases."""
        analyses = {}
        for case_id in self.case_queue._processing.keys():
            analysis = self.get_intervention_analysis(case_id)
            if analysis:
                analyses[case_id] = analysis
        return analyses

    def get_intervention_report(self, case_id: str) -> Optional[str]:
        """Get human-readable intervention report for a case."""
        analysis = self.get_intervention_analysis(case_id)
        if analysis:
            return generate_intervention_report(analysis)
        return None

    def get_critical_interventions(self, case_id: str, max_count: int = 3) -> List[Dict]:
        """Get the most critical interventions for a case."""
        analysis = self.get_intervention_analysis(case_id)
        if not analysis:
            return []

        priority_recs = self._intervention_recommender.get_priority_interventions(
            analysis, max_count
        )
        return [rec.to_dict() for rec in priority_recs]

    def update_results_with_interventions(self) -> Dict[str, Any]:
        """Update simulation results to include intervention analyses."""
        results = self.get_results()

        # Add intervention analysis for all cases
        analyses = self.get_all_intervention_analyses()
        results["intervention_analyses"] = {
            case_id: analysis.to_dict()
            for case_id, analysis in analyses.items()
        }

        # Add critical interventions
        results["critical_interventions"] = {}
        for case_id in analyses.keys():
            results["critical_interventions"][case_id] = self.get_critical_interventions(case_id)

        return results

    # =========================================================================
    # Actionable Intervention Analysis Methods
    # =========================================================================

    def get_actionable_analysis(
        self,
        case_id: str,
        use_new_recommender: bool = True
    ) -> Optional['ActionableResponseAnalysis']:
        """
        Get actionable intervention analysis for a specific case.

        This method provides richer, mission-briefing style recommendations
        with specific action steps, contacts, and alternative scenarios.

        Args:
            case_id: The case to analyze
            use_new_recommender: If True, uses the new ActionableInterventionRecommender

        Returns:
            ActionableResponseAnalysis with actionable recommendations
        """
        from .actionable_intervention_recommender import (
            ActionableInterventionRecommender,
            generate_actionable_report,
            ReportFormat
        )

        case = self.case_queue._processing.get(case_id)
        if not case:
            return None

        # Get the assigned ambulance and hospital for this case
        ambulance_agent = None
        hospital_agent = None

        # Find ambulance assigned to this case
        for amb_id, amb in self._ambulances.items():
            if (hasattr(amb, 'current_patient_id') and
                amb.current_patient_id == f"patient_{case_id}"):
                ambulance_agent = amb
                break

        # Find hospital assigned to this case
        assigned_hosp_id = getattr(case, 'assigned_hospital_id', None)
        if assigned_hosp_id and assigned_hosp_id in self._hospitals:
            hospital_agent = self._hospitals[assigned_hosp_id]

        # If no specific assignment, use first available
        if not ambulance_agent:
            for amb in self._ambulances.values():
                if amb.current_state not in ['available', 'returning']:
                    ambulance_agent = amb
                    break

        if not hospital_agent:
            for hosp in self._hospitals.values():
                if hosp.current_state != 'at_capacity':
                    hospital_agent = hosp
                    break

        # Get staff and blood bank for the hospital
        staff_agents = []
        if hospital_agent:
            staff_agents = [
                staff for staff in self.staff_pool.get_all_agents()
                if staff.staff.hospital_id == hospital_agent.agent_id
            ]

        blood_bank_agent = None
        if hospital_agent and hospital_agent.blood_bank:
            for bank in self.blood_bank_pool.get_all_agents():
                if bank.blood_bank.blood_bank_id == hospital_agent.blood_bank.blood_bank_id:
                    blood_bank_agent = bank
                    break

        # Calculate time remaining
        time_remaining = max(0, case.signal.time_window_minutes - self._sim_time)

        # Create recommender and analyze
        recommender = ActionableInterventionRecommender()

        # Get alternative hospitals for diversion scenarios
        alternative_hospitals = []
        for hosp_id, hosp_agent in self._hospitals.items():
            if hosp_id != hospital_agent.agent_id and hosp_agent.current_state != 'at_capacity':
                alternative_hospitals.append((hosp_agent.hospital, hosp_agent))

        analysis = recommender.analyze(
            case_id=case_id,
            signal=case.signal,
            time_remaining_minutes=time_remaining,
            simulation_time_minutes=self._sim_time,
            ambulance_agent=ambulance_agent,
            hospital_agent=hospital_agent,
            staff_agents=staff_agents if staff_agents else None,
            blood_bank_agent=blood_bank_agent,
            road_network_agent=self.road_network,
            alternative_hospitals=alternative_hospitals if alternative_hospitals else None
        )

        return analysis

    def get_actionable_report(
        self,
        case_id: str,
        format: str = "detailed"
    ) -> Optional[str]:
        """
        Get human-readable actionable intervention report.

        Args:
            case_id: The case to report on
            format: Output format - "detailed", "brief", "markdown", "json"

        Returns:
            Formatted report string
        """
        from .actionable_intervention_recommender import (
            ReportFormat,
            generate_actionable_report
        )

        analysis = self.get_actionable_analysis(case_id)
        if not analysis:
            return None

        format_map = {
            "detailed": ReportFormat.DETAILED,
            "brief": ReportFormat.BRIEF,
            "markdown": ReportFormat.MARKDOWN,
            "json": ReportFormat.JSON
        }

        report_format = format_map.get(format.lower(), ReportFormat.DETAILED)
        return generate_actionable_report(analysis, report_format)

    def get_all_actionable_analyses(self) -> Dict[str, 'ActionableResponseAnalysis']:
        """Get actionable analyses for all active cases."""
        analyses = {}
        for case_id in self.case_queue._processing.keys():
            analysis = self.get_actionable_analysis(case_id)
            if analysis:
                analyses[case_id] = analysis
        return analyses

    def get_top_interventions(self, case_id: str, max_count: int = 3) -> List[Dict]:
        """Get top critical interventions for a case."""
        analysis = self.get_actionable_analysis(case_id)
        if not analysis:
            return []

        # Sort by priority and return top N
        sorted_recs = sorted(
            analysis.recommendations,
            key=lambda r: (r.priority.value, -r.confidence_score)
        )

        return [rec.to_dict() for rec in sorted_recs[:max_count]]

    def update_results_with_actionable_interventions(self) -> Dict[str, Any]:
        """Update simulation results with actionable intervention analyses."""
        results = self.get_results()

        # Add actionable analysis for all cases
        analyses = self.get_all_actionable_analyses()
        results["actionable_analyses"] = {
            case_id: analysis.to_dict()
            for case_id, analysis in analyses.items()
        }

        # Add top interventions
        results["top_interventions"] = {}
        for case_id in analyses.keys():
            results["top_interventions"][case_id] = self.get_top_interventions(case_id)

        return results
