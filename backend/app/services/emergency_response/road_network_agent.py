"""
Road Network Agent for Emergency Response Simulation.

Models road network with dynamic routing:
- Multiple route options between locations
- Traffic congestion simulation
- Road closure/blockage handling
- Dynamic route recalculation
- Travel time estimation with real-time conditions
"""

from typing import Dict, List, Optional, Any, Tuple, Set
from datetime import datetime, timedelta
from enum import Enum
import math
import random

from ...models.response_action import (
    ResponseActionType, AgentType, ActionMessage
)
from ...models.response_resource import TransportRoute, ResourceLocation
from .base_agent import BaseAgent, AgentEvent, AgentEventType
from ...utils.logger import get_logger

logger = get_logger('mirofish.agents.road_network')


class RoadCondition(Enum):
    """Road condition states."""
    CLEAR = "clear"
    LIGHT_TRAFFIC = "light_traffic"
    MODERATE_TRAFFIC = "moderate_traffic"
    HEAVY_TRAFFIC = "heavy_traffic"
    CONGESTED = "congested"
    BLOCKED = "blocked"
    CLOSED = "closed"


class RouteSegment:
    """A segment of a route (intersection to intersection)."""
    def __init__(
        self,
        segment_id: str,
        from_lat: float,
        from_lng: float,
        to_lat: float,
        to_lng: float,
        distance_km: float,
        typical_duration_minutes: float
    ):
        self.segment_id = segment_id
        self.from_lat = from_lat
        self.from_lng = from_lng
        self.to_lat = to_lat
        self.to_lng = to_lng
        self.distance_km = distance_km
        self.typical_duration_minutes = typical_duration_minutes
        self.condition = RoadCondition.CLEAR
        self.condition_reason: Optional[str] = None
        self.condition_until: Optional[float] = None

    @property
    def condition_multiplier(self) -> float:
        multipliers = {
            RoadCondition.CLEAR: 1.0,
            RoadCondition.LIGHT_TRAFFIC: 1.2,
            RoadCondition.MODERATE_TRAFFIC: 1.5,
            RoadCondition.HEAVY_TRAFFIC: 2.0,
            RoadCondition.CONGESTED: 3.0,
            RoadCondition.BLOCKED: 999,
            RoadCondition.CLOSED: 999
        }
        return multipliers.get(self.condition, 1.0)

    def get_effective_duration(self) -> float:
        return self.typical_duration_minutes * self.condition_multiplier

    def to_dict(self) -> Dict[str, Any]:
        return {
            "segment_id": self.segment_id,
            "from": {"lat": self.from_lat, "lng": self.from_lng},
            "to": {"lat": self.to_lat, "lng": self.to_lng},
            "distance_km": self.distance_km,
            "typical_duration": self.typical_duration_minutes,
            "condition": self.condition.value,
            "effective_duration": self.get_effective_duration()
        }


class Route:
    """A complete route with multiple segments."""
    def __init__(
        self,
        route_id: str,
        name: str,
        segments: List[RouteSegment],
        alternate_route_ids: List[str] = None
    ):
        self.route_id = route_id
        self.name = name
        self.segments = segments
        self.alternate_route_ids = alternate_route_ids or []

    @property
    def distance_km(self) -> float:
        return sum(s.distance_km for s in self.segments)

    @property
    def typical_duration_minutes(self) -> float:
        return sum(s.typical_duration_minutes for s in self.segments)

    @property
    def effective_duration_minutes(self) -> float:
        return sum(s.get_effective_duration() for s in self.segments)

    @property
    def is_blocked(self) -> bool:
        return any(s.condition in [RoadCondition.BLOCKED, RoadCondition.CLOSED]
                   for s in self.segments)

    @property
    def worst_condition(self) -> RoadCondition:
        conditions = [s.condition for s in self.segments]
        if RoadCondition.CLOSED in conditions:
            return RoadCondition.CLOSED
        if RoadCondition.BLOCKED in conditions:
            return RoadCondition.BLOCKED
        if RoadCondition.CONGESTED in conditions:
            return RoadCondition.CONGESTED
        if RoadCondition.HEAVY_TRAFFIC in conditions:
            return RoadCondition.HEAVY_TRAFFIC
        if RoadCondition.MODERATE_TRAFFIC in conditions:
            return RoadCondition.MODERATE_TRAFFIC
        if RoadCondition.LIGHT_TRAFFIC in conditions:
            return RoadCondition.LIGHT_TRAFFIC
        return RoadCondition.CLEAR

    def get_condition_report(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "name": self.name,
            "is_blocked": self.is_blocked,
            "worst_condition": self.worst_condition.value,
            "distance_km": self.distance_km,
            "typical_duration": self.typical_duration_minutes,
            "effective_duration": self.effective_duration_minutes,
            "segments": [s.to_dict() for s in self.segments],
            "alternates": self.alternate_route_ids
        }


class RoadNetworkAgent(BaseAgent):
    """
    Road network agent for dynamic routing.

    Features:
    - Multiple routes between locations
    - Real-time traffic simulation
    - Dynamic condition updates
    - Route alternatives
    - Travel time optimization
    """

    TRAFFIC_PATTERNS = {
        "morning_peak": {"start": 7, "end": 9, "multiplier": 2.0},
        "evening_peak": {"start": 17, "end": 19, "multiplier": 2.0},
        "midday": {"start": 12, "end": 14, "multiplier": 1.3},
        "night": {"start": 22, "end": 5, "multiplier": 0.8}
    }

    WEATHER_IMPACT = {
        "clear": 1.0,
        "light_rain": 1.1,
        "heavy_rain": 1.5,
        "fog": 1.3,
        "snow": 2.0
    }

    def __init__(self, simulation_speed: float = 1.0):
        super().__init__(
            agent_id="road_network",
            agent_type=AgentType.ROAD_NETWORK,
            name="Road Network",
            location=None
        )

        self.simulation_speed = simulation_speed
        self._routes: Dict[str, Route] = {}
        self._location_routes: Dict[str, List[str]] = {}
        self._active_events: List[Dict] = []
        self._current_weather = "clear"
        self._total_route_calculations = 0
        self._alternate_routes_used = 0

        logger.info("RoadNetworkAgent initialized")

    @property
    def current_state(self) -> str:
        return "monitoring"

    def get_valid_states(self) -> List[str]:
        return ["monitoring", "updating", "alerting"]

    def get_state_transitions(self) -> Dict[str, List[str]]:
        return {
            "monitoring": ["updating", "alerting"],
            "updating": ["monitoring"],
            "alerting": ["monitoring"]
        }

    def get_available_actions(self) -> List[ResponseActionType]:
        return [ResponseActionType.UPDATE_STATUS, ResponseActionType.REROUTE]

    def step(self, simulation_time: float) -> List[ActionMessage]:
        messages = []
        self._process_inbox()
        self._simulate_traffic_patterns(simulation_time)
        self._check_event_expiration(simulation_time)
        return messages

    def _process_inbox(self) -> None:
        for message in self._inbox:
            if message.action_type == ResponseActionType.UPDATE_STATUS:
                self._handle_status_update(message)
            elif message.action_type == ResponseActionType.REROUTE:
                self._handle_reroute_request(message)
        self.clear_inbox()

    def _handle_status_update(self, message: ActionMessage) -> None:
        content = message.content
        if "route_id" in content:
            self.update_segment_condition(
                content["route_id"],
                content.get("condition", "clear"),
                content.get("reason"),
                content.get("duration_minutes")
            )

    def _handle_reroute_request(self, message: ActionMessage) -> None:
        content = message.content
        from_loc = content.get("from_location")
        to_loc = content.get("to_location")
        if from_loc and to_loc:
            route = self.find_best_route(
                ResourceLocation(**from_loc) if isinstance(from_loc, dict) else from_loc,
                ResourceLocation(**to_loc) if isinstance(to_loc, dict) else to_loc
            )
            if route and route.alternate_route_ids:
                self._alternate_routes_used += 1

    def add_route(
        self,
        route_id: str,
        name: str,
        segments: List[RouteSegment],
        alternate_route_ids: List[str] = None
    ) -> None:
        route = Route(route_id, name, segments, alternate_route_ids)
        self._routes[route_id] = route

        if segments:
            first = segments[0]
            last = segments[-1]
            key = self._location_key(
                first.from_lat, first.from_lng,
                last.to_lat, last.to_lng
            )
            if key not in self._location_routes:
                self._location_routes[key] = []
            self._location_routes[key].append(route_id)

        logger.debug(f"Added route {route_id}: {name}")

    def add_route_from_locations(
        self,
        route_id: str,
        name: str,
        from_lat: float,
        from_lng: float,
        to_lat: float,
        to_lng: float,
        distance_km: float,
        duration_minutes: float,
        alternate_route_ids: List[str] = None
    ) -> None:
        segment = RouteSegment(
            segment_id=f"{route_id}_seg1",
            from_lat=from_lat,
            from_lng=from_lng,
            to_lat=to_lat,
            to_lng=to_lng,
            distance_km=distance_km,
            typical_duration_minutes=duration_minutes
        )
        self.add_route(route_id, name, [segment], alternate_route_ids)

    def update_segment_condition(
        self,
        route_id: str,
        condition: str,
        reason: Optional[str] = None,
        duration_minutes: Optional[float] = None,
        simulation_time: Optional[float] = None
    ) -> List[ActionMessage]:
        messages = []
        route = self._routes.get(route_id)
        if not route:
            return messages

        condition_enum = self._parse_condition(condition)

        for segment in route.segments:
            old_condition = segment.condition
            segment.condition = condition_enum
            segment.condition_reason = reason

            if duration_minutes and simulation_time:
                segment.condition_until = simulation_time + duration_minutes

            if old_condition != condition_enum:
                logger.info(
                    f"Route {route_id}: {old_condition.value} -> {condition_enum.value}"
                )
                self._emit_condition_change(route_id, old_condition.value, condition_enum.value, reason)

                if condition_enum in [RoadCondition.BLOCKED, RoadCondition.CLOSED]:
                    messages.extend(self._create_blockage_alert(route, reason))
                    self.set_state("alerting", ResponseActionType.UPDATE_STATUS)

        return messages

    def _parse_condition(self, condition: str) -> RoadCondition:
        mapping = {
            "clear": RoadCondition.CLEAR,
            "light_traffic": RoadCondition.LIGHT_TRAFFIC,
            "light": RoadCondition.LIGHT_TRAFFIC,
            "moderate": RoadCondition.MODERATE_TRAFFIC,
            "moderate_traffic": RoadCondition.MODERATE_TRAFFIC,
            "heavy": RoadCondition.HEAVY_TRAFFIC,
            "heavy_traffic": RoadCondition.HEAVY_TRAFFIC,
            "congested": RoadCondition.CONGESTED,
            "blocked": RoadCondition.BLOCKED,
            "closed": RoadCondition.CLOSED
        }
        return mapping.get(condition.lower(), RoadCondition.CLEAR)

    def _emit_condition_change(
        self,
        route_id: str,
        old_condition: str,
        new_condition: str,
        reason: Optional[str]
    ) -> None:
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

    def _create_blockage_alert(
        self,
        route: Route,
        reason: Optional[str]
    ) -> List[ActionMessage]:
        messages = []
        messages.append(ActionMessage(
            message_id="",
            action_type=ResponseActionType.ROUTE_BLOCKED,
            from_agent=self.agent_id,
            to_agent="ems_dispatch",
            content={
                "route_id": route.route_id,
                "route_name": route.name,
                "condition": "blocked",
                "reason": reason,
                "distance_km": route.distance_km,
                "alternatives": [
                    {"route_id": alt_id, "effective_duration": self._routes.get(alt_id, Route("", "", [])).effective_duration_minutes}
                    for alt_id in route.alternate_route_ids
                    if alt_id in self._routes
                ]
            }
        ))
        return messages

    def find_best_route(
        self,
        from_location: ResourceLocation,
        to_location: ResourceLocation,
        avoid_conditions: Set[RoadCondition] = None,
        max_duration_minutes: Optional[float] = None
    ) -> Optional[Route]:
        self._total_route_calculations += 1
        avoid_conditions = avoid_conditions or set()

        key = self._location_key(
            from_location.lat, from_location.lng,
            to_location.lat, to_location.lng
        )

        candidate_routes = []
        route_ids = self._location_routes.get(key, [])

        for route_id in route_ids:
            route = self._routes.get(route_id)
            if not route:
                continue
            if any(s.condition in avoid_conditions for s in route.segments):
                continue
            if max_duration_minutes and route.effective_duration_minutes > max_duration_minutes:
                continue
            candidate_routes.append(route)

        if not candidate_routes:
            for route in self._routes.values():
                if route.route_id in route_ids:
                    continue
                if any(s.condition in avoid_conditions for s in route.segments):
                    continue
                if max_duration_minutes and route.effective_duration_minutes > max_duration_minutes:
                    continue
                candidate_routes.append(route)

        if not candidate_routes:
            return None

        candidate_routes.sort(key=lambda r: r.effective_duration_minutes)
        return candidate_routes[0]

    def find_alternate_route(
        self,
        blocked_route_id: str,
        from_location: ResourceLocation,
        to_location: ResourceLocation
    ) -> Optional[Route]:
        blocked_route = self._routes.get(blocked_route_id)

        if blocked_route:
            for alt_id in blocked_route.alternate_route_ids:
                alt = self._routes.get(alt_id)
                if alt and not alt.is_blocked:
                    return alt

        return self.find_best_route(
            from_location,
            to_location,
            avoid_conditions={RoadCondition.BLOCKED, RoadCondition.CLOSED}
        )

    def add_event(
        self,
        event_type: str,
        affected_routes: List[str],
        duration_minutes: Optional[float] = None,
        reason: Optional[str] = None
    ) -> str:
        event_id = f"event_{len(self._active_events) + 1}"
        event = {
            "event_id": event_id,
            "type": event_type,
            "affected_routes": affected_routes,
            "duration_minutes": duration_minutes,
            "reason": reason,
            "started_at": datetime.now().isoformat()
        }
        self._active_events.append(event)

        condition = "congested" if event_type == "construction" else "blocked"
        for route_id in affected_routes:
            self.update_segment_condition(route_id, condition, reason, duration_minutes)

        logger.info(f"Traffic event: {event_type} affects {len(affected_routes)} routes")
        return event_id

    def clear_event(self, event_id: str) -> None:
        event = next((e for e in self._active_events if e["event_id"] == event_id), None)
        if not event:
            return

        for route_id in event["affected_routes"]:
            route = self._routes.get(route_id)
            if route:
                other_events = [e for e in self._active_events
                               if e["event_id"] != event_id
                               and route_id in e["affected_routes"]]
                if not other_events:
                    self.update_segment_condition(route_id, "clear")

        self._active_events = [e for e in self._active_events if e["event_id"] != event_id]
        logger.info(f"Cleared traffic event: {event_id}")

    def _simulate_traffic_patterns(self, sim_time: float) -> None:
        hour = (sim_time / 60) % 24

        pattern_mult = 1.0
        for pattern_name, pattern in self.TRAFFIC_PATTERNS.items():
            if pattern["start"] <= hour < pattern["end"]:
                pattern_mult = pattern["multiplier"]
                break

        for route in self._routes.values():
            for segment in route.segments:
                if segment.condition == RoadCondition.CLEAR:
                    natural_mult = pattern_mult * random.uniform(0.9, 1.1)
                    if natural_mult > 1.5:
                        segment.condition = RoadCondition.MODERATE_TRAFFIC
                    elif natural_mult > 1.2:
                        segment.condition = RoadCondition.LIGHT_TRAFFIC

    def _check_event_expiration(self, sim_time: float) -> None:
        expired = []
        for event in self._active_events:
            if event.get("duration_minutes"):
                elapsed = sim_time
                if elapsed >= event["duration_minutes"]:
                    expired.append(event["event_id"])

        for event_id in expired:
            self.clear_event(event_id)

    def set_weather(self, weather: str) -> None:
        self._current_weather = weather

    def get_route(self, route_id: str) -> Optional[Route]:
        return self._routes.get(route_id)

    def get_all_routes(self) -> List[Route]:
        return list(self._routes.values())

    def _location_key(self, lat1: float, lng1: float, lat2: float, lng2: float) -> str:
        return f"{lat1:.4f},{lng1:.4f}->{lat2:.4f},{lng2:.4f}"

    def get_network_status(self) -> Dict[str, Any]:
        total_routes = len(self._routes)
        blocked = sum(1 for r in self._routes.values() if r.is_blocked)
        avg_duration = sum(r.effective_duration_minutes for r in self._routes.values()) / total_routes if total_routes else 0

        return {
            "agent_id": self.agent_id,
            "total_routes": total_routes,
            "blocked_routes": blocked,
            "active_events": len(self._active_events),
            "weather": self._current_weather,
            "avg_duration_minutes": avg_duration,
            "total_route_calculations": self._total_route_calculations,
            "alternate_routes_used": self._alternate_routes_used,
            "routes": {
                route_id: route.get_condition_report()
                for route_id, route in self._routes.items()
            }
        }

    def to_dict(self) -> Dict[str, Any]:
        base = super().to_dict()
        base.update(self.get_network_status())
        return base


class RoadNetworkPool:
    """Pool of road network agents for managing multiple network segments."""
    def __init__(self):
        self._networks: Dict[str, RoadNetworkAgent] = {}

    def add(self, network: RoadNetworkAgent) -> None:
        self._networks[network.agent_id] = network

    def get(self, network_id: str) -> Optional[RoadNetworkAgent]:
        return self._networks.get(network_id)

    def get_all_networks(self) -> List[RoadNetworkAgent]:
        return list(self._networks.values())

    def find_best_route_global(
        self,
        from_location: ResourceLocation,
        to_location: ResourceLocation,
        avoid_conditions: Set[RoadCondition] = None
    ) -> Optional[Route]:
        best_route = None
        best_duration = float('inf')

        for network in self._networks.values():
            route = network.find_best_route(from_location, to_location, avoid_conditions)
            if route and route.effective_duration_minutes < best_duration:
                best_duration = route.effective_duration_minutes
                best_route = route

        return best_route

    def get_pool_status(self) -> Dict[str, Any]:
        return {
            "total_networks": len(self._networks),
            "networks": {
                net_id: net.get_network_status()
                for net_id, net in self._networks.items()
            }
        }
