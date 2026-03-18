"""
Response Action Enums.

Defines all actions that can occur during emergency response simulation.
These are adapted from social media actions to medical emergency context.
"""

from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime


class ResponseActionType(Enum):
    """
    All possible actions in the emergency response simulation.

    Adapted from social media simulation:
    - CREATE_POST, REPOST, LIKE → DISPATCH, ALERT, COORDINATE
    - FOLLOW → TRANSFER
    - QUOTE_TWEET → ESCALATE
    """
    # === Ambulance Actions ===
    DISPATCH = "dispatch"                    # EMS dispatches ambulance
    DEPART = "depart"                      # Ambulance departs station
    ARRIVE_PATIENT = "arrive_patient"       # Ambulance arrives at patient location
    STABILIZE = "stabilize"                # Initial patient stabilization
    DEPART_HOSPITAL = "depart_hospital"   # Depart with patient
    ARRIVE_HOSPITAL = "arrive_hospital"   # Arrive at receiving hospital
    RETURN_TO_BASE = "return_to_base"      # Return to station

    # === Hospital Actions ===
    RECEIVE_ALERT = "receive_alert"         # Hospital receives emergency alert
    ALERT_STAFF = "alert_staff"            # Page on-call staff
    STAFF_CONFIRM = "staff_confirm"         # Staff confirms availability
    PREPARE_OT = "prepare_ot"              # Prepare operating room
    PREPARE_BLOOD = "prepare_blood"         # Prepare blood products
    OT_READY = "ot_ready"                  # OT ready for patient
    RECEIVE_PATIENT = "receive_patient"    # Hospital receives patient

    # === Coordination Actions ===
    COORDINATE = "coordinate"              # Coordinate between entities
    REQUEST_BACKUP = "request_backup"       # Request additional resources
    ESCALATE = "escalate"                  # Escalate to higher authority
    HANDS_OVER = "hands_over"              # Patient handover
    REROUTE = "reroute"                   # Change transport route
    TRANSFER = "transfer"                  # Transfer to another hospital
    REQUEST_BLOOD = "request_blood"       # Request blood from bank

    # === Communication Actions ===
    UPDATE_STATUS = "update_status"         # Update status to dispatch
    COMMUNICATE = "communicate"            # Direct communication
    BROADCAST = "broadcast"                # Broadcast to multiple entities

    # === Failure/Issue Actions ===
    STAFF_UNAVAILABLE = "staff_unavailable"
    OT_OCCUPIED = "ot_occupied"
    ROUTE_BLOCKED = "route_blocked"
    BLOOD_UNAVAILABLE = "blood_unavailable"
    TRAFFIC_DELAY = "traffic_delay"
    AMBULANCE_UNAVAILABLE = "ambulance_unavailable"

    # === Outcome Actions ===
    SUCCESS = "success"                    # Successful outcome
    FAILURE = "failure"                    # Failed outcome
    PARTIAL_SUCCESS = "partial_success"    # Partial success


class AgentType(Enum):
    """Types of agents in the emergency response simulation."""
    PATIENT = "patient"
    EMS_DISPATCH = "ems_dispatch"
    AMBULANCE = "ambulance"
    HOSPITAL = "hospital"
    STAFF = "staff"
    BLOOD_BANK = "blood_bank"
    CITY_CONDITIONS = "city_conditions"
    ROAD_NETWORK = "road_network"


@dataclass
class ActionMessage:
    """
    Message passed between agents during simulation.

    Adapted from social media message passing:
    - @mentions → ALERT (direct message to specific agent)
    - Retweets → REQUEST_BACKUP (broadcast to all)
    - DMs → COMMUNICATE (direct coordination)
    """
    message_id: str
    action_type: ResponseActionType
    from_agent: str
    to_agent: str
    content: Dict
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    requires_ack: bool = True
    acknowledged: bool = False
    broadcast: bool = False

    def to_dict(self) -> Dict:
        return {
            "message_id": self.message_id,
            "action_type": self.action_type.value,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "content": self.content,
            "timestamp": self.timestamp,
            "requires_ack": self.requires_ack,
            "acknowledged": self.acknowledged,
            "broadcast": self.broadcast
        }

    @classmethod
    def create_alert(
        cls,
        from_agent: str,
        to_agent: str,
        content: Dict,
        message_id: str = ""
    ) -> 'ActionMessage':
        """Create an ALERT message (like @mentioning a hospital)."""
        import uuid
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            action_type=ResponseActionType.RECEIVE_ALERT,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            requires_ack=True,
            broadcast=False
        )

    @classmethod
    def create_dispatch(
        cls,
        from_agent: str,
        to_agent: str,
        content: Dict,
        message_id: str = ""
    ) -> 'ActionMessage':
        """Create a DISPATCH message."""
        import uuid
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            action_type=ResponseActionType.DISPATCH,
            from_agent=from_agent,
            to_agent=to_agent,
            content=content,
            requires_ack=True,
            broadcast=False
        )

    @classmethod
    def create_backup_request(
        cls,
        from_agent: str,
        content: Dict,
        message_id: str = ""
    ) -> 'ActionMessage':
        """Create a backup request (like requesting retweets)."""
        import uuid
        return cls(
            message_id=message_id or str(uuid.uuid4()),
            action_type=ResponseActionType.REQUEST_BACKUP,
            from_agent=from_agent,
            to_agent="all",
            content=content,
            requires_ack=True,
            broadcast=True
        )


@dataclass
class AgentState:
    """Current state of an agent in the simulation."""
    agent_id: str
    agent_type: AgentType
    state: str
    location: Optional[Dict] = None
    status: str = "active"
    current_task_id: Optional[str] = None
    eta_minutes: Optional[float] = None
    resources_allocated: List[str] = field(default_factory=list)
    last_update: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "state": self.state,
            "location": self.location,
            "status": self.status,
            "current_task_id": self.current_task_id,
            "eta_minutes": self.eta_minutes,
            "resources_allocated": self.resources_allocated,
            "last_update": self.last_update
        }


@dataclass
class ActionLog:
    """Log entry for an action that occurred in the simulation."""
    action_id: str
    action_type: ResponseActionType
    agent_id: str
    timestamp: str
    details: Dict
    outcome: Optional[str] = None
    duration_seconds: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type.value,
            "agent_id": self.agent_id,
            "timestamp": self.timestamp,
            "details": self.details,
            "outcome": self.outcome,
            "duration_seconds": self.duration_seconds
        }


class AgentStates:
    """Common state constants for different agent types."""

    AMBULANCE_STATES = {
        "available": "Available at station",
        "dispatched": "Dispatched by EMS",
        "en_route_patient": "En route to patient",
        "at_patient": "At patient location",
        "stabilizing": "Stabilizing patient",
        "en_route_hospital": "En route to hospital",
        "at_hospital": "At hospital",
        "returning": "Returning to base"
    }

    HOSPITAL_STATES = {
        "ready": "Ready to receive",
        "alerted": "Received alert",
        "preparing": "Preparing resources",
        "ot_preparing": "Preparing OT",
        "ot_ready": "OT ready",
        "receiving": "Receiving patient",
        "at_capacity": "At capacity"
    }

    STAFF_STATES = {
        "off_duty": "Off duty",
        "on_call": "On call",
        "notified": "Notified of emergency",
        "confirming": "Confirming availability",
        "available": "Available",
        "en_route": "En route to hospital",
        "at_hospital": "At hospital"
    }

    DISPATCH_STATES = {
        "monitoring": "Monitoring",
        "coordinating": "Coordinating response",
        "escalated": "Escalated"
    }
