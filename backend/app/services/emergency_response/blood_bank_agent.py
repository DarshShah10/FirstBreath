"""
Blood Bank Agent for Emergency Response Simulation.

Models blood bank behavior:
- Inventory management
- Blood type availability
- Cross-matching
- Request coordination between hospitals
- Emergency blood ordering
"""

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
from enum import Enum
import random

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage
)
from ...models.response_resource import BloodBank
from .base_agent import BaseAgent, AgentEvent, AgentEventType
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.blood_bank')


class BloodBankState(Enum):
    """Blood bank states."""
    READY = "ready"
    PROCESSING = "processing"
    LOW_STOCK = "low_stock"
    CRITICAL = "critical"
    RESTOCKING = "restocking"


class BloodRequest:
    """Represents a blood request."""
    def __init__(
        self,
        request_id: str,
        blood_type: str,
        units_needed: int,
        urgency: str = "normal",
        requesting_hospital: str = None,
        case_id: str = None
    ):
        self.request_id = request_id
        self.blood_type = blood_type
        self.units_needed = units_needed
        self.urgency = urgency
        self.requesting_hospital = requesting_hospital
        self.case_id = case_id
        self.status = "pending"
        self.requested_at = datetime.now()
        self.fulfilled_at: Optional[datetime] = None
        self.fulfillment_time_minutes: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "blood_type": self.blood_type,
            "units_needed": self.units_needed,
            "urgency": self.urgency,
            "requesting_hospital": self.requesting_hospital,
            "case_id": self.case_id,
            "status": self.status,
            "requested_at": self.requested_at.isoformat(),
            "fulfillment_time_minutes": self.fulfillment_time_minutes
        }


class BloodBankAgent(BaseAgent):
    """
    Blood bank agent for managing blood inventory.

    State Machine:
    - ready -> processing -> ready
              -> low_stock (inventory low)
              -> critical (inventory very low)
              -> restocking (waiting for delivery)

    Key Behaviors:
    - Tracks blood inventory by type
    - Processes blood requests from hospitals
    - Cross-matching for rare blood types
    - Emergency ordering when stock low
    - Coordinates between hospitals for shared resources
    """

    # Blood type compatibility map
    BLOOD_COMPATIBILITY: Dict[str, Set[str]] = {
        "A+": {"A+", "A-", "O+", "O-"},
        "A-": {"A-", "O-"},
        "B+": {"B+", "B-", "O+", "O-"},
        "B-": {"B-", "O-"},
        "AB+": {"A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"},
        "AB-": {"A-", "B-", "AB-", "O-"},
        "O+": {"O+", "O-"},
        "O-": {"O-"},
    }

    # Minimum stock levels
    MIN_STOCK_NORMAL = 10
    MIN_STOCK_CRITICAL = 3

    # Processing time (minutes)
    REQUEST_PROCESSING_TIME = 3.0
    CROSS_MATCH_TIME = 10.0
    EMERGENCY_ORDER_TIME = 30.0

    def __init__(
        self,
        blood_bank: BloodBank,
        simulation_speed: float = 1.0
    ):
        super().__init__(
            agent_id=blood_bank.blood_bank_id,
            agent_type=AgentType.BLOOD_BANK,
            name=blood_bank.name,
            location=blood_bank.location
        )

        self.blood_bank = blood_bank
        self.simulation_speed = simulation_speed

        # Inventory (blood_type -> units available)
        self._inventory: Dict[str, int] = blood_bank.inventory.copy()
        self._reserved: Dict[str, Dict[str, int]] = {}

        # Requests
        self._pending_requests: Dict[str, BloodRequest] = {}
        self._fulfilled_requests: Dict[str, BloodRequest] = {}
        self._request_counter = 0

        # State
        self._bank_state = BloodBankState.READY

        logger.info(f"BloodBankAgent initialized: {self.name}")

    @property
    def current_state(self) -> str:
        return self._bank_state.value

    def get_valid_states(self) -> List[str]:
        return [s.value for s in BloodBankState]

    def get_state_transitions(self) -> Dict[str, List[str]]:
        return {
            "ready": ["processing", "low_stock", "critical", "restocking"],
            "processing": ["ready", "low_stock", "critical"],
            "low_stock": ["ready", "critical", "restocking"],
            "critical": ["low_stock", "restocking"],
            "restocking": ["ready", "low_stock"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        return [
            ResponseActionType.REQUEST_BLOOD,
            ResponseActionType.COORDINATE,
            ResponseActionType.UPDATE_STATUS
        ]

    def step(self, simulation_time: float) -> List[ActionMessage]:
        messages = []
        self._process_inbox()
        messages.extend(self._process_requests(simulation_time))
        self._check_inventory_levels()
        return messages

    def _process_inbox(self) -> None:
        for message in self._inbox:
            if message.action_type == ResponseActionType.REQUEST_BLOOD:
                self._handle_blood_request(message)
            elif message.action_type == ResponseActionType.COORDINATE:
                self._handle_coordinate(message)
        self.clear_inbox()

    def _handle_blood_request(self, message: ActionMessage) -> None:
        content = message.content
        self._request_counter += 1
        request = BloodRequest(
            request_id=f"req_{self._request_counter:06d}",
            blood_type=content.get("blood_type", "O-"),
            units_needed=content.get("units_needed", 2),
            urgency=content.get("urgency", "normal"),
            requesting_hospital=content.get("requesting_hospital"),
            case_id=content.get("case_id")
        )
        self._pending_requests[request.request_id] = request
        logger.info(
            f"Blood request: {request.request_id} - "
            f"{request.units_needed} units {request.blood_type}"
        )

    def _handle_coordinate(self, message: ActionMessage) -> None:
        content = message.content
        if content.get("action") == "check_availability":
            blood_type = content.get("blood_type")
            units = content.get("units_needed", 2)
            available = self._check_availability(blood_type, units)
            logger.debug(f"Availability check: {blood_type} x{units} = {available}")

    def _process_requests(self, sim_time: float) -> List[ActionMessage]:
        messages = []
        sorted_requests = sorted(
            self._pending_requests.values(),
            key=lambda r: (
                0 if r.urgency == "critical" else
                1 if r.urgency == "urgent" else 2,
                r.requested_at
            )
        )
        for request in sorted_requests:
            if self._check_availability(request.blood_type, request.units_needed):
                self._fulfill_request(request, sim_time)
                messages.extend(self._create_fulfillment_messages(request))
            elif request.urgency in ["urgent", "critical"]:
                fulfilled = self._try_compatible_types(request, sim_time, messages)
                if fulfilled:
                    messages.extend(fulfilled)
        return messages

    def _check_availability(self, blood_type: str, units_needed: int) -> bool:
        direct = self._inventory.get(blood_type, 0) >= units_needed
        if direct:
            return True
        reserved = sum(
            self._reserved.get(case_id, {}).get(blood_type, 0)
            for case_id in self._reserved
        )
        return (self._inventory.get(blood_type, 0) - reserved) >= units_needed

    def _try_compatible_types(
        self,
        request: BloodRequest,
        sim_time: float,
        messages: List[ActionMessage]
    ) -> bool:
        compatible = self.BLOOD_COMPATIBILITY.get(request.blood_type, set())
        for compat_type in compatible:
            if compat_type != request.blood_type:
                if self._check_availability(compat_type, request.units_needed):
                    self._inventory[compat_type] -= request.units_needed
                    request.status = "fulfilled"
                    request.fulfillment_time_minutes = (
                        datetime.now() - request.requested_at
                    ).total_seconds() / 60
                    self._fulfilled_requests[request.request_id] = request
                    del self._pending_requests[request.request_id]
                    messages.extend(self._create_fulfillment_messages(request, compat_type))
                    return True
        return False

    def _fulfill_request(self, request: BloodRequest, sim_time: float) -> None:
        self._inventory[request.blood_type] -= request.units_needed
        if request.case_id:
            if request.case_id not in self._reserved:
                self._reserved[request.case_id] = {}
            self._reserved[request.case_id][request.blood_type] = (
                self._reserved[request.case_id].get(request.blood_type, 0) +
                request.units_needed
            )
        request.status = "fulfilled"
        request.fulfillment_time_minutes = (
            datetime.now() - request.requested_at
        ).total_seconds() / 60
        self._fulfilled_requests[request.request_id] = request
        del self._pending_requests[request.request_id]
        logger.info(f"Fulfilled: {request.request_id} - {request.units_needed} units {request.blood_type}")

    def _create_fulfillment_messages(
        self,
        request: BloodRequest,
        actual_type: Optional[str] = None
    ) -> List[ActionMessage]:
        messages = []
        if request.requesting_hospital:
            messages.append(ActionMessage(
                message_id="",
                action_type=ResponseActionType.REQUEST_BLOOD,
                from_agent=self.agent_id,
                to_agent=request.requesting_hospital,
                content={
                    "request_id": request.request_id,
                    "status": "fulfilled",
                    "blood_type": actual_type or request.blood_type,
                    "units_provided": request.units_needed,
                    "fulfillment_time_minutes": request.fulfillment_time_minutes,
                    "case_id": request.case_id
                }
            ))
        return messages

    def _check_inventory_levels(self) -> None:
        total_stock = sum(self._inventory.values())
        avg_stock = total_stock / len(self._inventory) if self._inventory else 0
        if avg_stock < self.MIN_STOCK_CRITICAL:
            self._bank_state = BloodBankState.CRITICAL
        elif avg_stock < self.MIN_STOCK_NORMAL:
            self._bank_state = BloodBankState.LOW_STOCK
        else:
            self._bank_state = BloodBankState.READY

    def request_blood(
        self,
        blood_type: str,
        units_needed: int,
        hospital_id: str,
        case_id: str,
        urgency: str = "normal"
    ) -> str:
        self._request_counter += 1
        request = BloodRequest(
            request_id=f"req_{self._request_counter:06d}",
            blood_type=blood_type,
            units_needed=units_needed,
            urgency=urgency,
            requesting_hospital=hospital_id,
            case_id=case_id
        )
        self._pending_requests[request.request_id] = request
        return request.request_id

    def release_reserved(self, case_id: str) -> Dict[str, int]:
        if case_id in self._reserved:
            released = self._reserved[case_id].copy()
            for blood_type, units in released.items():
                self._inventory[blood_type] = (
                    self._inventory.get(blood_type, 0) + units
                )
            del self._reserved[case_id]
            logger.info(f"Released reserved blood for case {case_id}: {released}")
            return released
        return {}

    def check_compatibility(self, patient_type: str, donor_type: str) -> bool:
        compatible = self.BLOOD_COMPATIBILITY.get(patient_type, set())
        return donor_type in compatible

    def get_inventory_status(self) -> Dict[str, Any]:
        return {
            "bank_id": self.agent_id,
            "bank_name": self.name,
            "state": self._bank_state.value,
            "inventory": self._inventory.copy(),
            "total_units": sum(self._inventory.values()),
            "pending_requests": len(self._pending_requests),
            "fulfilled_today": len(self._fulfilled_requests)
        }

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(self.get_inventory_status())
        return base


class BloodBankPool:
    """Pool of blood bank agents."""
    def __init__(self):
        self._banks: Dict[str, BloodBankAgent] = {}

    def add(self, agent: BloodBankAgent) -> None:
        self._banks[agent.agent_id] = agent

    def get(self, bank_id: str) -> Optional[BloodBankAgent]:
        return self._banks.get(bank_id)

    def get_all_agents(self) -> List[BloodBankAgent]:
        return list(self._banks.values())

    def find_available_blood(
        self,
        blood_type: str,
        units_needed: int
    ) -> Optional[BloodBankAgent]:
        for bank in self._banks.values():
            if bank._check_availability(blood_type, units_needed):
                return bank
        return None

    def get_pool_status(self) -> Dict[str, Any]:
        return {
            "total_banks": len(self._banks),
            "banks": {
                bank_id: bank.get_inventory_status()
                for bank_id, bank in self._banks.items()
            }
        }
