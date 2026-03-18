"""
Response Chain Graph.

Builds a connected graph of the emergency response chain showing:
- Patient
- EMS Dispatch
- Ambulances
- Routes
- Hospitals
- Staff
- Blood Banks

All entities are connected through communication/coordination relationships.
"""

from enum import Enum
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime
import uuid

from ...models.emergency_case import DistressSignal
from ...models.response_resource import (
    Hospital, Ambulance, MedicalStaff, BloodBank, TransportRoute,
    ResourceRegistry, ResourceLocation
)
from ...models.response_action import AgentType
from ...utils.logger import get_logger

logger = get_logger('mirofish.response_chain_graph')


class NodeType(Enum):
    """Types of nodes in the response chain graph."""
    PATIENT = "patient"
    EMS_DISPATCH = "ems_dispatch"
    AMBULANCE = "ambulance"
    ROUTE = "route"
    HOSPITAL = "hospital"
    STAFF = "staff"
    OT = "operating_theater"
    NICU = "nicu"
    BLOOD_BANK = "blood_bank"
    TRAFFIC = "traffic"


class EdgeType(Enum):
    """Types of edges (relationships) between nodes."""
    CALLS_FOR = "calls_for"
    DISPATCHES = "dispatches"
    TRANSPORTS = "transports"
    ALERTS = "alerts"
    TRANSFERS = "transfers"
    COORDINATES = "coordinates"
    PREPARES = "prepares"
    REQUIRES = "requires"
    BLOCKED_BY = "blocked_by"
    FEEDS_INTO = "feeds_into"
    COMMUNICATES = "communicates"
    STANDBY_FOR = "standby_for"


class NodeStatus(Enum):
    """Status indicators for nodes."""
    CLEAR = "clear"
    DELAYED = "delayed"
    CRITICAL = "critical"
    BLOCKED = "blocked"
    READY = "ready"
    PREPARING = "preparing"
    OCCUPIED = "occupied"


@dataclass
class ResponseChainNode:
    """
    A node in the response chain graph.

    Represents an entity in the emergency response system.
    """
    node_id: str
    node_type: NodeType
    name: str
    status: NodeStatus = NodeStatus.CLEAR
    lat: Optional[float] = None
    lng: Optional[float] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    connected_to: List[str] = field(default_factory=list)  # Node IDs
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.node_id,
            "type": self.node_type.value,
            "name": self.name,
            "status": self.status.value,
            "lat": self.lat,
            "lng": self.lng,
            "attributes": self.attributes,
            "connected_to": self.connected_to,
            "last_update": self.last_update
        }


@dataclass
class ResponseChainEdge:
    """
    An edge in the response chain graph.

    Represents a relationship or action between two entities.
    """
    edge_id: str
    source_id: str
    target_id: str
    edge_type: EdgeType
    duration_minutes: Optional[float] = None
    status: str = "active"
    action: Optional[str] = None  # e.g., "PREP_OT", "DISPATCH"
    blocked: bool = False
    block_reason: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.edge_id,
            "source": self.source_id,
            "target": self.target_id,
            "type": self.edge_type.value,
            "duration_minutes": self.duration_minutes,
            "status": self.status,
            "action": self.action,
            "blocked": self.blocked,
            "block_reason": self.block_reason,
            "metadata": self.metadata
        }


@dataclass
class ResponseChainGraph:
    """
    The complete response chain graph.

    Contains all nodes and edges representing the emergency response network.
    Every entity is connected through communication/coordination relationships.
    """

    def __init__(self):
        """Initialize empty graph."""
        self.nodes: Dict[str, ResponseChainNode] = {}
        self.edges: Dict[str, ResponseChainEdge] = {}
        self.created_at: str = datetime.now().isoformat()
        self.graph_id: str = f"rcg_{uuid.uuid4().hex[:12]}"

    def add_node(self, node: ResponseChainNode) -> None:
        """Add a node to the graph."""
        self.nodes[node.node_id] = node

    def add_edge(self, edge: ResponseChainEdge) -> None:
        """Add an edge to the graph."""
        self.edges[edge.edge_id] = edge
        # Update connected nodes
        if edge.source_id in self.nodes:
            if edge.target_id not in self.nodes[edge.source_id].connected_to:
                self.nodes[edge.source_id].connected_to.append(edge.target_id)
        if edge.target_id in self.nodes:
            if edge.source_id not in self.nodes[edge.target_id].connected_to:
                self.nodes[edge.target_id].connected_to.append(edge.source_id)

    def get_node(self, node_id: str) -> Optional[ResponseChainNode]:
        """Get a node by ID."""
        return self.nodes.get(node_id)

    def get_edge(self, edge_id: str) -> Optional[ResponseChainEdge]:
        """Get an edge by ID."""
        return self.edges.get(edge_id)

    def get_nodes_by_type(self, node_type: NodeType) -> List[ResponseChainNode]:
        """Get all nodes of a specific type."""
        return [n for n in self.nodes.values() if n.node_type == node_type]

    def get_edges_by_type(self, edge_type: EdgeType) -> List[ResponseChainEdge]:
        """Get all edges of a specific type."""
        return [e for e in self.edges.values() if e.edge_type == edge_type]

    def update_node_status(self, node_id: str, status: NodeStatus,
                          attributes: Optional[Dict[str, Any]] = None) -> bool:
        """Update a node's status."""
        node = self.nodes.get(node_id)
        if node:
            node.status = status
            node.last_update = datetime.now().isoformat()
            if attributes:
                node.attributes.update(attributes)
            return True
        return False

    def update_edge_status(self, edge_id: str, status: str,
                          blocked: bool = False, block_reason: Optional[str] = None) -> bool:
        """Update an edge's status."""
        edge = self.edges.get(edge_id)
        if edge:
            edge.status = status
            edge.blocked = blocked
            edge.block_reason = block_reason
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        """Export graph as dictionary."""
        return {
            "graph_id": self.graph_id,
            "created_at": self.created_at,
            "nodes": {k: v.to_dict() for k, v in self.nodes.items()},
            "edges": {k: v.to_dict() for k, v in self.edges.items()},
            "node_count": len(self.nodes),
            "edge_count": len(self.edges)
        }

    def to_d3_format(self) -> Dict[str, Any]:
        """Export graph in D3.js force-directed graph format."""
        nodes = []
        for node in self.nodes.values():
            nodes.append({
                "id": node.node_id,
                "name": node.name,
                "group": node.node_type.value,
                "status": node.status.value,
                "lat": node.lat,
                "lng": node.lng,
                **node.attributes
            })

        links = []
        for edge in self.edges.values():
            links.append({
                "id": edge.edge_id,
                "source": edge.source_id,
                "target": edge.target_id,
                "type": edge.edge_type.value,
                "duration": edge.duration_minutes,
                "status": edge.status,
                "action": edge.action,
                "blocked": edge.blocked
            })

        return {
            "nodes": nodes,
            "links": links
        }


class ResponseChainBuilder:
    """
    Builder for creating response chain graphs.

    Takes a distress signal and resources, builds a connected graph.
    """

    def __init__(self, resource_registry: ResourceRegistry):
        """Initialize with resource registry."""
        self.registry = resource_registry
        self._edge_counter = 0

    def _next_edge_id(self) -> str:
        """Generate unique edge ID."""
        self._edge_counter += 1
        return f"edge_{self._edge_counter:04d}"

    def build_graph(self, signal: DistressSignal,
                    ambulance: Optional[Ambulance],
                    hospital: Optional[Hospital],
                    route: Optional[TransportRoute]) -> ResponseChainGraph:
        """
        Build a response chain graph from a distress signal and resources.

        Every entity is connected through communication/coordination relationships.
        """
        graph = ResponseChainGraph()

        # 1. Add Patient node
        patient_node = ResponseChainNode(
            node_id=f"patient_{signal.case_id}",
            node_type=NodeType.PATIENT,
            name=f"Patient ({signal.emergency_type.value})",
            status=NodeStatus.CRITICAL if signal.severity.value == "critical" else NodeStatus.DELAYED,
            lat=signal.location.lat,
            lng=signal.location.lng,
            attributes={
                "severity": signal.severity.value,
                "emergency_type": signal.emergency_type.value,
                "gestational_age": signal.patient.gestational_age_weeks,
                "blood_type": signal.patient.blood_type,
                "complications": signal.patient.complications,
                "time_window_minutes": signal.time_window_minutes
            }
        )
        graph.add_node(patient_node)

        # 2. Add EMS Dispatch node
        dispatch_node = ResponseChainNode(
            node_id="ems_dispatch",
            node_type=NodeType.EMS_DISPATCH,
            name="EMS Dispatch Center",
            status=NodeStatus.READY,
            attributes={"manages": ["ambulances", "hospital_alerts"]}
        )
        graph.add_node(dispatch_node)

        # 3. Connect Patient to Dispatch (CALLS_FOR)
        graph.add_edge(ResponseChainEdge(
            edge_id=self._next_edge_id(),
            source_id=patient_node.node_id,
            target_id=dispatch_node.node_id,
            edge_type=EdgeType.CALLS_FOR,
            action="EMERGENCY_CALL",
            duration_minutes=2
        ))

        # 4. Add Ambulance node if available
        ambulance_node = None
        if ambulance:
            ambulance_node = ResponseChainNode(
                node_id=ambulance.ambulance_id,
                node_type=NodeType.AMBULANCE,
                name=ambulance.name,
                status=NodeStatus.READY,
                lat=ambulance.location.lat,
                lng=ambulance.location.lng,
                attributes={
                    "status": ambulance.status.value,
                    "equipped_for": ambulance.equipped_for,
                    "has_paramedic": ambulance.has_paramedic
                }
            )
            graph.add_node(ambulance_node)

            # Connect Dispatch to Ambulance (DISPATCHES)
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id=dispatch_node.node_id,
                target_id=ambulance_node.node_id,
                edge_type=EdgeType.DISPATCHES,
                action="DISPATCH_AMBULANCE",
                duration_minutes=2
            ))

            # Connect Ambulance to Patient (TRANSPORTS)
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id=ambulance_node.node_id,
                target_id=patient_node.node_id,
                edge_type=EdgeType.TRANSPORTS,
                action="EN_ROUTE_TO_PATIENT",
                duration_minutes=ambulance.response_time_to_location or 10
            ))

        # 5. Add Route node if available
        route_node = None
        if route:
            route_node = ResponseChainNode(
                node_id=route.route_id,
                node_type=NodeType.ROUTE,
                name=f"Route to Hospital",
                status=NodeStatus.CLEAR if route.current_status == "clear" else NodeStatus.BLOCKED,
                lat=(route.from_location.lat + route.to_location.lat) / 2,
                lng=(route.from_location.lng + route.to_location.lng) / 2,
                attributes={
                    "distance_km": route.distance_km,
                    "typical_duration": route.typical_duration_minutes,
                    "traffic_multiplier": route.traffic_multiplier,
                    "alternate_available": route.alternate_route_available,
                    "current_status": route.current_status,
                    "block_reason": route.block_reason
                }
            )
            graph.add_node(route_node)

            if ambulance_node:
                # Connect Ambulance to Route
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=ambulance_node.node_id,
                    target_id=route_node.node_id,
                    edge_type=EdgeType.FEEDS_INTO,
                    action="TRANSPORT_VIA",
                    duration_minutes=route.typical_duration_minutes
                ))

        # 6. Add Hospital node if available
        hospital_node = None
        if hospital:
            hospital_level = hospital.level.value if hasattr(hospital.level, 'value') else hospital.level
            hospital_node = ResponseChainNode(
                node_id=hospital.hospital_id,
                node_type=NodeType.HOSPITAL,
                name=hospital.name,
                status=NodeStatus.READY,
                lat=hospital.location.lat,
                lng=hospital.location.lng,
                attributes={
                    "level": hospital_level,
                    "ot_count": hospital.ot_count,
                    "ot_available": hospital.get_ot_availability(),
                    "on_call_obgyn": hospital.on_call_obgyn,
                    "on_call_anesthesiologist": hospital.on_call_anesthesiologist,
                    "blood_bank_status": hospital.blood_bank_status,
                    "capabilities": hospital.capabilities
                }
            )
            graph.add_node(hospital_node)

            # Add OT sub-node
            ot_node = ResponseChainNode(
                node_id=f"{hospital.hospital_id}_ot",
                node_type=NodeType.OT,
                name=f"{hospital.name} - Operating Theater",
                status=NodeStatus.READY,
                attributes={"ot_count": hospital.ot_count}
            )
            graph.add_node(ot_node)

            # Connect Hospital to OT (PREPARES)
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id=hospital_node.node_id,
                target_id=ot_node.node_id,
                edge_type=EdgeType.PREPARES,
                action="PREPARE_OT"
            ))

            # Add NICU sub-node if hospital has NICU
            if hospital.nicu_beds > 0:
                nicu_node = ResponseChainNode(
                    node_id=f"{hospital.hospital_id}_nicu",
                    node_type=NodeType.NICU,
                    name=f"{hospital.name} - NICU",
                    status=NodeStatus.READY,
                    attributes={"nicu_beds": hospital.nicu_beds}
                )
                graph.add_node(nicu_node)

                # Connect Hospital to NICU
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=hospital_node.node_id,
                    target_id=nicu_node.node_id,
                    edge_type=EdgeType.PREPARES,
                    action="PREPARE_NICU"
                ))

            # Connect Route to Hospital (TRANSFERS)
            if route_node:
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=route_node.node_id,
                    target_id=hospital_node.node_id,
                    edge_type=EdgeType.TRANSFERS,
                    action="ARRIVE_HOSPITAL",
                    duration_minutes=route.get_effective_duration()
                ))

            # Connect Ambulance to Hospital (ALERTS) - Hospital gets alert while ambulance is en route
            if ambulance_node:
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=ambulance_node.node_id,
                    target_id=hospital_node.node_id,
                    edge_type=EdgeType.ALERTS,
                    action="ALERT_HOSPITAL",
                    duration_minutes=2
                ))

            # Connect Dispatch to Hospital (COORDINATES)
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id=dispatch_node.node_id,
                target_id=hospital_node.node_id,
                edge_type=EdgeType.COORDINATES,
                action="COORDINATE_RESPONSE"
            ))

            # Connect Patient to Hospital (REQUIRES)
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id=patient_node.node_id,
                target_id=hospital_node.node_id,
                edge_type=EdgeType.REQUIRES,
                action="REQUIRES_ADMISSION"
            ))

            # Add Staff nodes for hospital
            for staff in self.registry.get_staff_for_hospital(hospital.hospital_id):
                if staff.on_call:
                    staff_node = ResponseChainNode(
                        node_id=staff.staff_id,
                        node_type=NodeType.STAFF,
                        name=staff.name,
                        status=NodeStatus.READY if staff.status.value == "off_duty" else NodeStatus.DELAYED,
                        attributes={
                            "specialization": staff.specialization.value if hasattr(staff.specialization, 'value') else staff.specialization,
                            "response_time_minutes": staff.response_time_minutes
                        }
                    )
                    graph.add_node(staff_node)

                    # Connect Hospital to Staff (COORDINATES)
                    graph.add_edge(ResponseChainEdge(
                        edge_id=self._next_edge_id(),
                        source_id=hospital_node.node_id,
                        target_id=staff_node.node_id,
                        edge_type=EdgeType.COORDINATES,
                        action="ALERT_STAFF",
                        duration_minutes=2
                    ))

                    # Connect Staff to OT
                    graph.add_edge(ResponseChainEdge(
                        edge_id=self._next_edge_id(),
                        source_id=staff_node.node_id,
                        target_id=ot_node.node_id,
                        edge_type=EdgeType.FEEDS_INTO,
                        action="PERFORM_SURGERY"
                    ))

        # 7. Add Traffic/Road Condition node if route exists
        if route and route.current_status != "clear":
            traffic_node = ResponseChainNode(
                node_id=f"traffic_{route.route_id}",
                node_type=NodeType.TRAFFIC,
                name=f"Traffic: {route.current_status}",
                status=NodeStatus.BLOCKED if route.current_status == "blocked" else NodeStatus.DELAYED,
                attributes={
                    "condition": route.current_status,
                    "block_reason": route.block_reason,
                    "impact_minutes": route.block_duration_minutes
                }
            )
            graph.add_node(traffic_node)

            # Connect Traffic to Route (BLOCKED_BY)
            if route_node:
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=route_node.node_id,
                    target_id=traffic_node.node_id,
                    edge_type=EdgeType.BLOCKED_BY,
                    blocked=True,
                    block_reason=route.block_reason
                ))

        # 8. Add communication lines between all key entities
        # This ensures everything is connected and communicating
        connected_nodes = [
            n for n in [patient_node, ambulance_node, hospital_node]
            if n is not None
        ]

        for i, node_a in enumerate(connected_nodes):
            for node_b in connected_nodes[i+1:]:
                # Add bidirectional communication
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=node_a.node_id,
                    target_id=node_b.node_id,
                    edge_type=EdgeType.COMMUNICATES,
                    action="STATUS_UPDATE"
                ))

        logger.info(
            f"Built response chain graph: {len(graph.nodes)} nodes, {len(graph.edges)} edges"
        )
        return graph

    def build_with_alternates(self, signal: DistressSignal,
                              primary_ambulance: Optional[Ambulance],
                              primary_hospital: Optional[Hospital],
                              primary_route: Optional[TransportRoute],
                              backup_ambulance: Optional[Ambulance],
                              backup_route: Optional[TransportRoute]) -> ResponseChainGraph:
        """
        Build a graph with alternate resources for redundancy.

        Shows both primary and backup paths for rerouting scenarios.
        """
        # Build primary graph
        graph = self.build_graph(signal, primary_ambulance, primary_hospital, primary_route)

        # Add backup ambulance if different from primary
        if backup_ambulance and backup_ambulance != primary_ambulance:
            backup_amb_node = ResponseChainNode(
                node_id=backup_ambulance.ambulance_id,
                node_type=NodeType.AMBULANCE,
                name=f"{backup_ambulance.name} (Backup)",
                status=NodeStatus.READY,
                lat=backup_ambulance.location.lat,
                lng=backup_ambulance.location.lng,
                attributes={
                    "role": "backup",
                    "equipped_for": backup_ambulance.equipped_for
                }
            )
            graph.add_node(backup_amb_node)

            # Connect backup to dispatch
            graph.add_edge(ResponseChainEdge(
                edge_id=self._next_edge_id(),
                source_id="ems_dispatch",
                target_id=backup_amb_node.node_id,
                edge_type=EdgeType.DISPATCHES,
                action="STANDBY"
            ))

            # Connect backup to patient (STANDBY_FOR)
            patient_node = graph.get_node(f"patient_{signal.case_id}")
            if patient_node:
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=backup_amb_node.node_id,
                    target_id=patient_node.node_id,
                    edge_type=EdgeType.STANDBY_FOR,
                    action="READY_TO_INTERCEPT"
                ))

        # Add backup route if provided
        if backup_route:
            backup_route_node = ResponseChainNode(
                node_id=backup_route.route_id,
                node_type=NodeType.ROUTE,
                name="Alternate Route",
                status=NodeStatus.READY,
                attributes={
                    "role": "alternate",
                    "distance_km": backup_route.distance_km,
                    "typical_duration": backup_route.typical_duration_minutes
                }
            )
            graph.add_node(backup_route_node)

            # Connect to backup ambulance if exists
            if backup_ambulance:
                backup_amb_node = graph.get_node(backup_ambulance.ambulance_id)
                if backup_amb_node:
                    graph.add_edge(ResponseChainEdge(
                        edge_id=self._next_edge_id(),
                        source_id=backup_amb_node.node_id,
                        target_id=backup_route_node.node_id,
                        edge_type=EdgeType.TRANSPORTS,
                        action="ALTERNATE_TRANSPORT"
                    ))

            # Connect to hospital
            if primary_hospital:
                graph.add_edge(ResponseChainEdge(
                    edge_id=self._next_edge_id(),
                    source_id=backup_route_node.node_id,
                    target_id=primary_hospital.hospital_id,
                    edge_type=EdgeType.TRANSFERS,
                    action="ALTERNATE_ARRIVAL"
                ))

        return graph
