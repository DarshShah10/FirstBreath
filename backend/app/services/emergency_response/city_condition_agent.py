"""
City Condition Agent for Emergency Response Simulation.

Models external factors affecting emergency response:
- Traffic conditions
- Road blockages
- Events/incidents
- Weather conditions
"""

from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
import random

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage
)
from ...models.response_resource import TransportRoute, ResourceLocation
from .base_agent import BaseAgent, AgentEventBus, AgentEvent, AgentEventType
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.city')


class CityConditionAgent(BaseAgent):
    """
    City conditions agent monitoring external factors.

    Monitors:
    - Traffic congestion levels
    - Road blockages (construction, events, accidents)
    - Weather conditions
    - Special events

    Emits alerts when conditions change that affect emergency response.
    """

    # Traffic multipliers by condition
    TRAFFIC_MULTIPLIERS = {
        "clear": 1.0,
        "light": 1.2,
        "moderate": 1.5,
        "heavy": 2.0,
        "blocked": 999
    }

    # Weather impact multipliers
    WEATHER_IMPACT = {
        "clear": 1.0,
        "light_rain": 1.1,
        "heavy_rain": 1.5,
        "fog": 1.3,
        "snow": 2.0
    }

    def __init__(
        self,
        simulation_speed: float = 1.0,
        random_seed: Optional[int] = None
    ):
        super().__init__(
            agent_id="city_conditions",
            agent_type=AgentType.CITY_CONDITIONS,
            name="City Conditions Monitor",
            location=None
        )

        self.simulation_speed = simulation_speed
        self._event_bus = AgentEventBus()

        # Route conditions
        self._route_conditions: Dict[str, Dict] = {}

        # Active events/incidents
        self._active_events: List[Dict] = []

        # Weather
        self._current_weather: str = "clear"

        # Callbacks for condition changes
        self._condition_callbacks: List[Callable] = []

        # Set initial state
        self._current_state = "monitoring"
        logger.info("CityConditionAgent initialized")

    def get_valid_states(self) -> List[str]:
        """Valid states."""
        return ["monitoring", "alerting", "clearing"]

    def get_state_transitions(self) -> Dict[str, List[str]]:
        """Valid transitions."""
        return {
            "monitoring": ["alerting", "clearing"],
            "alerting": ["monitoring", "clearing"],
            "clearing": ["monitoring"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        """Available actions."""
        return [
            ResponseActionType.UPDATE_STATUS,
            ResponseActionType.ALERT,
            ResponseActionType.ROUTE_BLOCKED,
            ResponseActionType.TRAFFIC_DELAY
        ]

    def step(self, simulation_time: float) -> List[ActionMessage]:
        """Execute one simulation step."""
        messages = []

        # Check for random events (for simulation)
        # In real system, this would come from external data sources

        return messages

    def set_route_condition(
        self,
        route_id: str,
        condition: str,
        reason: Optional[str] = None,
        duration_minutes: Optional[float] = None
    ) -> List[ActionMessage]:
        """
        Set a route's condition.

        Args:
            route_id: Route to update
            condition: "clear", "congested", "blocked", "event_affected"
            reason: Reason for condition (e.g., "festival", "construction")
            duration_minutes: Expected duration

        Returns:
            Messages to broadcast about the change
        """
        messages = []

        old_condition = self._route_conditions.get(route_id, {}).get("condition", "clear")
        self._route_conditions[route_id] = {
            "condition": condition,
            "reason": reason,
            "since": datetime.now().isoformat(),
            "duration_minutes": duration_minutes
        }

        # Emit event
        self._emit_condition_change(route_id, old_condition, condition, reason)

        # If blocked, notify dispatch
        if condition == "blocked":
            messages.append(ActionMessage(
                message_id="",
                action_type=ResponseActionType.ROUTE_BLOCKED,
                from_agent=self.agent_id,
                to_agent="ems_dispatch",
                content={
                    "route_id": route_id,
                    "condition": condition,
                    "reason": reason,
                    "duration_minutes": duration_minutes,
                    "alternate_available": True  # Would check route config
                }
            ))

            self.log_action(
                ResponseActionType.ROUTE_BLOCKED,
                {
                    "route_id": route_id,
                    "reason": reason,
                    "duration_minutes": duration_minutes
                },
                outcome="route_blocked"
            )

        elif old_condition != "clear" and condition == "clear":
            # Route cleared
            messages.append(ActionMessage(
                message_id="",
                action_type=ResponseActionType.UPDATE_STATUS,
                from_agent=self.agent_id,
                to_agent="ems_dispatch",
                content={
                    "route_id": route_id,
                    "condition": "clear",
                    "message": "Route now clear"
                }
            ))

            self.log_action(
                ResponseActionType.UPDATE_STATUS,
                {"route_id": route_id, "condition": "clear"},
                outcome="route_cleared"
            )

        logger.info(
            f"Route {route_id} condition changed: {old_condition} -> {condition}"
            f" ({reason or ''})"
        )

        return messages

    def get_route_condition(self, route_id: str) -> Dict[str, Any]:
        """Get current condition of a route."""
        return self._route_conditions.get(route_id, {
            "condition": "clear",
            "reason": None
        })

    def get_effective_duration(
        self,
        route: TransportRoute,
        include_weather: bool = True
    ) -> float:
        """
        Calculate effective duration considering conditions.

        Args:
            route: The route to calculate for
            include_weather: Whether to factor in weather

        Returns:
            Effective duration in minutes
        """
        base_duration = route.typical_duration_minutes

        # Get route condition
        condition = self._route_conditions.get(route.route_id, {}).get("condition", "clear")

        # Apply condition multiplier
        if condition == "blocked":
            return 999  # Effectively unreachable

        condition_mult = self.TRAFFIC_MULTIPLIERS.get(condition, 1.0)

        # Apply weather impact
        weather_mult = 1.0
        if include_weather:
            weather_mult = self.WEATHER_IMPACT.get(self._current_weather, 1.0)

        # Combine
        return base_duration * condition_mult * weather_mult * route.traffic_multiplier

    def set_weather(self, weather: str) -> None:
        """Set current weather conditions."""
        if weather in self.WEATHER_IMPACT:
            old_weather = self._current_weather
            self._current_weather = weather

            self.log_action(
                ResponseActionType.UPDATE_STATUS,
                {"weather": weather, "previous": old_weather},
                outcome="weather_changed"
            )

            logger.info(f"Weather changed: {old_weather} -> {weather}")

    def add_event(
        self,
        event_type: str,
        affected_routes: List[str],
        duration_minutes: Optional[float] = None
    ) -> str:
        """
        Add a special event (festival, construction, etc.).

        Args:
            event_type: Type of event
            affected_routes: Routes affected
            duration_minutes: Expected duration

        Returns:
            Event ID
        """
        event_id = f"event_{len(self._active_events) + 1}"

        event = {
            "event_id": event_id,
            "type": event_type,
            "affected_routes": affected_routes,
            "duration_minutes": duration_minutes,
            "started_at": datetime.now().isoformat()
        }

        self._active_events.append(event)

        # Update affected routes
        for route_id in affected_routes:
            self.set_route_condition(
                route_id,
                "event_affected",
                reason=event_type,
                duration_minutes=duration_minutes
            )

        logger.info(f"Event added: {event_type}, affects {len(affected_routes)} routes")

        return event_id

    def clear_event(self, event_id: str) -> List[ActionMessage]:
        """Clear a special event."""
        messages = []

        event = next((e for e in self._active_events if e["event_id"] == event_id), None)
        if not event:
            return messages

        # Clear affected routes
        for route_id in event["affected_routes"]:
            # Only clear if no other events affecting this route
            other_events = [e for e in self._active_events if e["event_id"] != event_id]
            still_affected = any(route_id in e["affected_routes"] for e in other_events)

            if not still_affected:
                messages.extend(self.set_route_condition(route_id, "clear"))

        # Remove event
        self._active_events = [e for e in self._active_events if e["event_id"] != event_id]

        logger.info(f"Event cleared: {event_id}")

        return messages

    def simulate_traffic_pattern(
        self,
        route_id: str,
        peak_hour: bool = False,
        random_events: bool = False,
        event_probability: float = 0.1
    ) -> None:
        """
        Simulate realistic traffic patterns.

        Args:
            route_id: Route to simulate
            peak_hour: Whether it's peak traffic hours
            random_events: Whether to randomly generate events
            event_probability: Probability of random event
        """
        if peak_hour:
            self.set_route_condition(
                route_id,
                "congested",
                reason="peak_hour_traffic"
            )
        else:
            self.set_route_condition(route_id, "clear")

        if random_events and random.random() < event_probability:
            # Random road incident
            incidents = [
                ("construction", "Road construction"),
                ("accident", "Traffic accident"),
                ("blocked", "Road blockage")
            ]
            incident_type, reason = random.choice(incidents)

            self.set_route_condition(
                route_id,
                incident_type,
                reason=reason,
                duration_minutes=random.randint(15, 60)
            )

    def on_condition_change(self, callback: Callable) -> None:
        """Register callback for condition changes."""
        self._condition_callbacks.append(callback)

    def _emit_condition_change(
        self,
        route_id: str,
        old_condition: str,
        new_condition: str,
        reason: Optional[str]
    ) -> None:
        """Emit condition change event."""
        event = AgentEvent(
            event_id="",
            event_type=AgentEventType.ALERT_EMITTED,
            agent_id=self.agent_id,
            data={
                "route_id": route_id,
                "old_condition": old_condition,
                "new_condition": new_condition,
                "reason": reason
            }
        )

        self._event_bus.publish(event)

        # Call registered callbacks
        for callback in self._condition_callbacks:
            try:
                callback(route_id, old_condition, new_condition, reason)
            except Exception as e:
                logger.error(f"Condition callback error: {e}")

    def get_traffic_report(self) -> Dict[str, Any]:
        """Get current traffic conditions report."""
        return {
            "weather": self._current_weather,
            "active_events": len(self._active_events),
            "event_details": [
                {
                    "event_id": e["event_id"],
                    "type": e["type"],
                    "affected_routes": e["affected_routes"]
                }
                for e in self._active_events
            ],
            "route_conditions": {
                route_id: cond["condition"]
                for route_id, cond in self._route_conditions.items()
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        """Export city condition state."""
        base = super().to_dict()
        base.update({
            "weather": self._current_weather,
            "active_events": len(self._active_events),
            "route_conditions": self._route_conditions,
            "traffic_report": self.get_traffic_report()
        })
        return base
