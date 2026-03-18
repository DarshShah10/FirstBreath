"""
Emergency Response Simulation Services.

Services for the MiroFish medical emergency response simulation engine.
"""

from .resource_registry_service import ResourceRegistryService
from .distress_signal_processor import DistressSignalProcessor
from .response_chain_graph import (
    ResponseChainGraph,
    ResponseChainNode,
    ResponseChainEdge,
    ResponseChainBuilder,
    NodeType,
    EdgeType,
    NodeStatus
)
from .base_agent import BaseAgent, AgentEventBus, AgentEvent, AgentEventType
from .ambulance_agent import AmbulanceAgent
from .hospital_agent import HospitalAgent
from .dispatch_agent import DispatchAgent
from .city_condition_agent import CityConditionAgent
from .staff_agent import StaffAgent, StaffPool
from .blood_bank_agent import BloodBankAgent, BloodBankPool
from .road_network_agent import RoadNetworkAgent, RoadNetworkPool, RoadCondition, Route, RouteSegment
from .case_queue import CaseQueue, CaseQueuePool, CasePriority, CaseStatus
from .simulation_engine import EmergencySimulationEngine, SimulationState
from .parallel_simulation_engine import (
    ParallelSimulationEngine,
    SimulationMode,
    SimulationMetrics,
    AgentPool
)
from .intervention_recommender import (
    InterventionRecommender,
    InterventionRecommendation,
    InterventionType,
    InterventionPriority,
    ResponseChainAnalysis,
    BottleneckAnalysis,
    generate_intervention_report
)
from .actionable_intervention_recommender import (
    ActionableInterventionRecommender,
    ActionableResponseAnalysis,
    ActionableRecommendation,
    ActionStep,
    ContactInfo,
    ResourceStatus,
    ResponseChainStatus,
    InterventionScenario,
    OutcomeProjection,
    BottleneckSeverity,
    ReportFormat,
    generate_actionable_report
)

__all__ = [
    # Core services
    'ResourceRegistryService',
    'DistressSignalProcessor',
    # Graph
    'ResponseChainGraph',
    'ResponseChainNode',
    'ResponseChainEdge',
    'ResponseChainBuilder',
    'NodeType',
    'EdgeType',
    'NodeStatus',
    # Agents
    'BaseAgent',
    'AgentEventBus',
    'AgentEvent',
    'AgentEventType',
    'AmbulanceAgent',
    'HospitalAgent',
    'DispatchAgent',
    'CityConditionAgent',
    'StaffAgent',
    'StaffPool',
    'BloodBankAgent',
    'BloodBankPool',
    'RoadNetworkAgent',
    'RoadNetworkPool',
    'RoadCondition',
    'Route',
    'RouteSegment',
    # Case Management
    'CaseQueue',
    'CaseQueuePool',
    'CasePriority',
    'CaseStatus',
    # Engines
    'EmergencySimulationEngine',
    'SimulationState',
    'ParallelSimulationEngine',
    'SimulationMode',
    'SimulationMetrics',
    'AgentPool',
    # Legacy Intervention Recommender
    'InterventionRecommender',
    'InterventionRecommendation',
    'InterventionType',
    'InterventionPriority',
    'ResponseChainAnalysis',
    'BottleneckAnalysis',
    'generate_intervention_report',
    # Actionable Intervention Recommender (NEW)
    'ActionableInterventionRecommender',
    'ActionableResponseAnalysis',
    'ActionableRecommendation',
    'ActionStep',
    'ContactInfo',
    'ResourceStatus',
    'ResponseChainStatus',
    'InterventionScenario',
    'OutcomeProjection',
    'BottleneckSeverity',
    'ReportFormat',
    'generate_actionable_report'
]
