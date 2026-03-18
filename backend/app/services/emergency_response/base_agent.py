"""
Base Agent for Emergency Response Simulation.

Provides the foundation for all response agents with:
- State machine for agent lifecycle
- Message passing system
- Event handling
- Observable state changes
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable, Set
from enum import Enum
from datetime import datetime
import uuid

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage, AgentState, ActionLog
)
from ...models.response_resource import ResourceLocation
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents')


class AgentEventType(Enum):
    """Events that agents can emit."""
    STATE_CHANGED = "state_changed"
    MESSAGE_SENT = "message_sent"
    MESSAGE_RECEIVED = "message_received"
    ACTION_EXECUTED = "action_executed"
    ALERT_EMITTED = "alert_emitted"
    COORDINATION_REQUESTED = "coordination_requested"
    FAILURE_DETECTED = "failure_detected"
    SUCCESS_ACHIEVED = "success_achieved"


@dataclass
class AgentEvent:
    """Event emitted by an agent."""
    event_id: str
    event_type: AgentEventType
    agent_id: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    data: Dict[str, Any] = field(default_factory=dict)


class AgentEventBus:
    """
    Central event bus for agent communication.

    Allows agents to subscribe to events from other agents.
    This is the "communication backbone" that connects all agents.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers: Dict[str, List[Callable]] = {}
            cls._instance._event_log: List[AgentEvent] = []
        return cls._instance

    def subscribe(self, agent_id: str, callback: Callable[[AgentEvent], None]) -> None:
        """Subscribe an agent to receive events."""
        if agent_id not in self._subscribers:
            self._subscribers[agent_id] = []
        self._subscribers[agent_id].append(callback)

    def unsubscribe(self, agent_id: str, callback: Callable) -> None:
        """Unsubscribe an agent from events."""
        if agent_id in self._subscribers:
            self._subscribers[agent_id] = [
                cb for cb in self._subscribers[agent_id] if cb != callback
            ]

    def publish(self, event: AgentEvent) -> None:
        """Publish an event to all subscribers."""
        self._event_log.append(event)

        # Publish to specific agent if targeted
        if event.data.get('to_agent'):
            target = event.data['to_agent']
            if target in self._subscribers:
                for callback in self._subscribers[target]:
                    try:
                        callback(event)
                    except Exception as e:
                        logger.error(f"Event callback error: {e}")

        # Broadcast to all if marked as broadcast
        if event.data.get('broadcast'):
            for agent_id, callbacks in self._subscribers.items():
                if agent_id != event.agent_id:
                    for callback in callbacks:
                        try:
                            callback(event)
                        except Exception as e:
                            logger.error(f"Broadcast callback error: {e}")

    def get_event_log(self, agent_id: Optional[str] = None) -> List[AgentEvent]:
        """Get event log, optionally filtered by agent."""
        if agent_id:
            return [e for e in self._event_log if e.agent_id == agent_id]
        return self._event_log.copy()

    def clear_log(self) -> None:
        """Clear the event log."""
        self._event_log.clear()


@dataclass
class StateTransition:
    """Represents a state transition."""
    from_state: str
    to_state: str
    action: ResponseActionType
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    success: bool = True


class BaseAgent(ABC):
    """
    Base class for all response agents.

    Provides:
    - Unique agent identification
    - State machine with transitions
    - Message sending/receiving
    - Event emission
    - Action logging
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: AgentType,
        name: str,
        location: Optional[ResourceLocation] = None
    ):
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.name = name
        self.location = location

        # State management
        self._current_state: str = ""
        self._state_history: List[StateTransition] = []

        # Communication
        self._inbox: List[ActionMessage] = []
        self._outbox: List[ActionMessage] = []
        self._event_bus = AgentEventBus()

        # Subscribed to events
        self._subscribed_agents: Set[str] = set()

        # Action log
        self._action_log: List[ActionLog] = []

        # Callbacks
        self._state_change_callbacks: List[Callable] = []

        logger.info(f"Agent created: {self.name} ({self.agent_id})")

    @abstractmethod
    def get_valid_states(self) -> List[str]:
        """Return list of valid states for this agent type."""
        pass

    @abstractmethod
    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Return valid state transitions: {from_state: [to_states]}"""
        pass

    @abstractmethod
    def get_available_actions(self) -> List[ResponseActionType]:
        """Return list of actions this agent can perform."""
        pass

    @property
    def current_state(self) -> str:
        """Get current state."""
        return self._current_state

    def set_state(self, new_state: str, action: Optional[ResponseActionType] = None) -> bool:
        """
        Attempt to transition to a new state.

        Returns True if transition was successful.
        """
        valid_states = self.get_valid_states()
        if new_state not in valid_states:
            logger.warning(
                f"Invalid state '{new_state}' for agent {self.agent_id}. "
                f"Valid states: {valid_states}"
            )
            return False

        transitions = self.get_state_transitions()
        allowed = transitions.get(self._current_state, [])

        if self._current_state and new_state not in allowed:
            logger.warning(
                f"Invalid transition from '{self._current_state}' to '{new_state}' "
                f"for agent {self.agent_id}"
            )
            return False

        old_state = self._current_state
        self._current_state = new_state

        # Log transition
        self._state_history.append(StateTransition(
            from_state=old_state or "initial",
            to_state=new_state,
            action=action or ResponseActionType.COORDINATE
        ))

        # Emit event
        self._emit_event(AgentEventType.STATE_CHANGED, {
            "from_state": old_state,
            "to_state": new_state,
            "action": action.value if action else None
        })

        # Notify callbacks
        for callback in self._state_change_callbacks:
            try:
                callback(self, old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        logger.info(f"Agent {self.agent_id} transitioned: {old_state or 'init'} -> {new_state}")
        return True

    def send_message(
        self,
        to_agent: str,
        action_type: ResponseActionType,
        content: Dict[str, Any],
        broadcast: bool = False,
        requires_ack: bool = True
    ) -> ActionMessage:
        """Send a message to another agent."""
        message = ActionMessage(
            message_id=str(uuid.uuid4()),
            action_type=action_type,
            from_agent=self.agent_id,
            to_agent=to_agent,
            content=content,
            requires_ack=requires_ack,
            broadcast=broadcast
        )

        self._outbox.append(message)
        self._event_bus.publish(AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=AgentEventType.MESSAGE_SENT,
            agent_id=self.agent_id,
            data=message.to_dict()
        ))

        logger.debug(f"Agent {self.agent_id} sent message to {to_agent}: {action_type.value}")
        return message

    def receive_message(self, message: ActionMessage) -> None:
        """Receive a message from another agent."""
        self._inbox.append(message)
        self._event_bus.publish(AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=AgentEventType.MESSAGE_RECEIVED,
            agent_id=self.agent_id,
            data=message.to_dict()
        ))
        logger.debug(f"Agent {self.agent_id} received message from {message.from_agent}")

    def get_messages(self, action_type: Optional[ResponseActionType] = None) -> List[ActionMessage]:
        """Get messages from inbox, optionally filtered by action type."""
        if action_type:
            return [m for m in self._inbox if m.action_type == action_type]
        return self._inbox.copy()

    def clear_inbox(self) -> None:
        """Clear the inbox."""
        self._inbox.clear()

    def log_action(
        self,
        action_type: ResponseActionType,
        details: Dict[str, Any],
        outcome: Optional[str] = None,
        duration_seconds: float = 0.0
    ) -> ActionLog:
        """Log an action that was executed."""
        action_log = ActionLog(
            action_id=str(uuid.uuid4()),
            action_type=action_type,
            agent_id=self.agent_id,
            timestamp=datetime.now().isoformat(),
            details=details,
            outcome=outcome,
            duration_seconds=duration_seconds
        )
        self._action_log.append(action_log)

        self._emit_event(AgentEventType.ACTION_EXECUTED, {
            "action": action_type.value,
            "outcome": outcome,
            "details": details
        })

        return action_log

    def _emit_event(self, event_type: AgentEventType, data: Dict[str, Any]) -> None:
        """Emit an event through the event bus."""
        self._event_bus.publish(AgentEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            agent_id=self.agent_id,
            data=data
        ))

    def subscribe_to_agent(self, agent_id: str) -> None:
        """Subscribe to events from another agent."""
        self._subscribed_agents.add(agent_id)

    def on_state_change(self, callback: Callable) -> None:
        """Register a callback for state changes."""
        self._state_change_callbacks.append(callback)

    def get_state(self) -> AgentState:
        """Get current agent state for external queries."""
        return AgentState(
            agent_id=self.agent_id,
            agent_type=self.agent_type,
            state=self._current_state,
            location=self.location.to_dict() if self.location else None,
            last_update=datetime.now().isoformat()
        )

    def get_state_history(self) -> List[Dict]:
        """Get state transition history."""
        return [
            {
                "from_state": t.from_state,
                "to_state": t.to_state,
                "action": t.action.value,
                "timestamp": t.timestamp
            }
            for t in self._state_history
        ]

    def get_action_log(self) -> List[Dict]:
        """Get action log."""
        return [log.to_dict() for log in self._action_log]

    def to_dict(self) -> Dict[str, Any]:
        """Export agent as dictionary."""
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type.value,
            "name": self.name,
            "current_state": self._current_state,
            "location": self.location.to_dict() if self.location else None,
            "state_history": self.get_state_history(),
            "pending_messages": len(self._inbox),
            "actions_logged": len(self._action_log)
        }

    @abstractmethod
    def step(self, simulation_time: float) -> List[ActionMessage]:
        """
        Execute one simulation step.

        This is the main method that drives agent behavior.
        Each agent type implements its own step logic.

        Args:
            simulation_time: Current simulation time in minutes

        Returns:
            List of messages to be sent to other agents
        """
        pass
