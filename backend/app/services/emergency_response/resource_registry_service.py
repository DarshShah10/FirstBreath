"""
Resource Registry Service.

Loads and manages pre-configured healthcare resources for emergency simulation.
"""

import os
import yaml
from typing import Dict, List, Optional, Any
from dataclasses import asdict

from ...models.response_resource import (
    ResourceRegistry,
    Hospital,
    Ambulance,
    MedicalStaff,
    BloodBank,
    TransportRoute,
    ResourceLocation,
    HospitalLevel,
    StaffSpecialization,
    ResourceStatus
)
from ...utils.logger import get_logger

logger = get_logger('mirofish.resource_registry')


class ResourceRegistryService:
    """
    Service for loading and managing healthcare resources.

    Loads pre-configured resources from emergency_resources.yaml
    and provides methods to query and update resource states.
    """

    _instance: Optional['ResourceRegistryService'] = None
    _registry: Optional[ResourceRegistry] = None

    def __new__(cls):
        """Singleton pattern for resource registry."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the resource registry service."""
        if self._registry is None:
            self._registry = self._load_resources()

    def _load_resources(self) -> ResourceRegistry:
        """Load resources from YAML configuration."""
        config_path = os.path.join(
            os.path.dirname(__file__),
            '../../../config/emergency_resources.yaml'
        )
        config_path = os.path.normpath(config_path)

        logger.info(f"Loading emergency resources from: {config_path}")

        if not os.path.exists(config_path):
            logger.warning(f"Config file not found: {config_path}, using empty registry")
            return ResourceRegistry()

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        registry = ResourceRegistry()

        # Load hospitals
        for hosp_data in config.get('hospitals', []):
            hospital = self._parse_hospital(hosp_data)
            registry.hospitals[hospital.hospital_id] = hospital

        # Load ambulances
        for amb_data in config.get('ambulances', []):
            ambulance = self._parse_ambulance(amb_data)
            registry.ambulances[ambulance.ambulance_id] = ambulance

        # Load staff
        for staff_data in config.get('staff', []):
            staff = self._parse_staff(staff_data)
            registry.staff[staff.staff_id] = staff

        # Load blood banks
        for blood_data in config.get('blood_banks', []):
            blood_bank = self._parse_blood_bank(blood_data)
            registry.blood_banks[blood_bank.blood_bank_id] = blood_bank

        # Load routes
        for route_data in config.get('routes', []):
            route = self._parse_route(route_data)
            registry.routes[route.route_id] = route

        logger.info(
            f"Loaded {len(registry.hospitals)} hospitals, "
            f"{len(registry.ambulances)} ambulances, "
            f"{len(registry.staff)} staff, "
            f"{len(registry.blood_banks)} blood banks, "
            f"{len(registry.routes)} routes"
        )

        return registry

    def _parse_hospital(self, data: Dict) -> Hospital:
        """Parse hospital data."""
        loc_data = data.get('location', {})
        location = ResourceLocation(
            lat=loc_data.get('lat', 0),
            lng=loc_data.get('lng', 0),
            address=loc_data.get('address', '')
        )

        return Hospital(
            hospital_id=data.get('hospital_id', ''),
            name=data.get('name', ''),
            level=HospitalLevel(data.get('level', 'secondary')),
            location=location,
            obgyn_beds=data.get('obgyn_beds', 0),
            nicu_beds=data.get('nicu_beds', 0),
            ot_count=data.get('ot_count', 0),
            on_call_obgyn=data.get('on_call_obgyn', 0),
            on_call_anesthesiologist=data.get('on_call_anesthesiologist', 0),
            transfer_time_minutes=data.get('transfer_time_minutes', 15),
            blood_bank_status=data.get('blood_bank_status', 'adequate'),
            status=ResourceStatus(data.get('status', 'available')),
            contact_phone=data.get('contact_phone', ''),
            capabilities=data.get('capabilities', [])
        )

    def _parse_ambulance(self, data: Dict) -> Ambulance:
        """Parse ambulance data."""
        loc_data = data.get('base_location', {})
        base_location = ResourceLocation(
            lat=loc_data.get('lat', 0),
            lng=loc_data.get('lng', 0),
            address=loc_data.get('address', '')
        )

        return Ambulance(
            ambulance_id=data.get('ambulance_id', ''),
            name=data.get('name', ''),
            location=base_location,
            status=ResourceStatus(data.get('status', 'available')),
            equipped_for=data.get('equipped_for', []),
            base_location=base_location,
            crew_count=data.get('crew_count', 2),
            has_paramedic=data.get('has_paramedic', False)
        )

    def _parse_staff(self, data: Dict) -> MedicalStaff:
        """Parse staff data."""
        return MedicalStaff(
            staff_id=data.get('staff_id', ''),
            name=data.get('name', ''),
            specialization=StaffSpecialization(data.get('specialization', 'obstetrician')),
            hospital_id=data.get('hospital_id'),
            status=ResourceStatus(data.get('status', 'off_duty')),
            on_call=data.get('on_call', False),
            response_time_minutes=data.get('response_time_minutes', 15),
            contact_phone=data.get('contact_phone', '')
        )

    def _parse_blood_bank(self, data: Dict) -> BloodBank:
        """Parse blood bank data."""
        loc_data = data.get('location', {})
        location = ResourceLocation(
            lat=loc_data.get('lat', 0),
            lng=loc_data.get('lng', 0),
            address=loc_data.get('address', '')
        )

        return BloodBank(
            blood_bank_id=data.get('blood_bank_id', ''),
            name=data.get('name', ''),
            location=location,
            hospital_id=data.get('hospital_id'),
            inventory=data.get('inventory', {}),
            status=ResourceStatus(data.get('status', 'available'))
        )

    def _parse_route(self, data: Dict) -> TransportRoute:
        """Parse route data."""
        from_loc = data.get('from_location', {})
        to_loc = data.get('to_location', {})

        return TransportRoute(
            route_id=data.get('route_id', ''),
            from_location=ResourceLocation(
                lat=from_loc.get('lat', 0),
                lng=from_loc.get('lng', 0),
                address=from_loc.get('address', '')
            ),
            to_location=ResourceLocation(
                lat=to_loc.get('lat', 0),
                lng=to_loc.get('lng', 0),
                address=to_loc.get('address', '')
            ),
            distance_km=data.get('distance_km', 0),
            typical_duration_minutes=data.get('typical_duration_minutes', 20),
            traffic_multiplier=data.get('traffic_multiplier', 1.0),
            alternate_route_available=data.get('alternate_route_available', False),
            alternate_route_id=data.get('alternate_route_id'),
            current_status=data.get('current_status', 'clear')
        )

    def get_registry(self) -> ResourceRegistry:
        """Get the resource registry."""
        return self._registry

    def get_hospital(self, hospital_id: str) -> Optional[Hospital]:
        """Get hospital by ID."""
        return self._registry.get_hospital_by_id(hospital_id)

    def get_all_hospitals(self) -> List[Hospital]:
        """Get all hospitals."""
        return list(self._registry.hospitals.values())

    def get_available_hospitals(self) -> List[Hospital]:
        """Get available hospitals."""
        return self._registry.get_available_hospitals()

    def get_ambulance(self, ambulance_id: str) -> Optional[Ambulance]:
        """Get ambulance by ID."""
        return self._registry.get_ambulance_by_id(ambulance_id)

    def get_all_ambulances(self) -> List[Ambulance]:
        """Get all ambulances."""
        return list(self._registry.ambulances.values())

    def get_available_ambulances(self) -> List[Ambulance]:
        """Get available ambulances."""
        return self._registry.get_available_ambulances()

    def find_nearest_hospital(self, lat: float, lng: float) -> Optional[Hospital]:
        """Find nearest hospital to coordinates."""
        location = ResourceLocation(lat=lat, lng=lng)
        return self._registry.find_nearest_hospital(location)

    def find_nearest_ambulance(self, lat: float, lng: float) -> Optional[Ambulance]:
        """Find nearest ambulance to coordinates."""
        location = ResourceLocation(lat=lat, lng=lng)
        return self._registry.find_nearest_ambulance(location)

    def find_route(self, from_lat: float, from_lng: float,
                   to_lat: float, to_lng: float) -> Optional[TransportRoute]:
        """Find route between two coordinates."""
        from_loc = ResourceLocation(lat=from_lat, lng=from_lng)
        to_loc = ResourceLocation(lat=to_lat, lng=to_lng)
        return self._registry.find_route(from_loc, to_loc)

    def update_route_status(self, route_id: str, status: str,
                           block_reason: Optional[str] = None) -> bool:
        """Update route status (e.g., for traffic/road block)."""
        route = self._registry.routes.get(route_id)
        if route:
            route.current_status = status
            route.block_reason = block_reason
            logger.info(f"Route {route_id} status updated to: {status}")
            return True
        return False

    def update_ambulance_status(self, ambulance_id: str, status: ResourceStatus) -> bool:
        """Update ambulance status."""
        ambulance = self._registry.ambulances.get(ambulance_id)
        if ambulance:
            ambulance.status = status
            logger.info(f"Ambulance {ambulance_id} status updated to: {status.value}")
            return True
        return False

    def update_hospital_status(self, hospital_id: str, status: ResourceStatus) -> bool:
        """Update hospital status."""
        hospital = self._registry.hospitals.get(hospital_id)
        if hospital:
            hospital.status = status
            logger.info(f"Hospital {hospital_id} status updated to: {status.value}")
            return True
        return False

    def get_staff_for_hospital(self, hospital_id: str) -> List[MedicalStaff]:
        """Get all staff assigned to a hospital."""
        return [
            s for s in self._registry.staff.values()
            if s.hospital_id == hospital_id
        ]

    def get_on_call_staff(self, specialization: Optional[StaffSpecialization] = None) -> List[MedicalStaff]:
        """Get on-call staff, optionally filtered by specialization."""
        on_call = [s for s in self._registry.staff.values() if s.on_call]
        if specialization:
            on_call = [s for s in on_call if s.specialization == specialization]
        return on_call

    def to_dict(self) -> Dict[str, Any]:
        """Export registry as dictionary."""
        return self._registry.to_dict()

    def reload(self) -> None:
        """Reload resources from config file."""
        logger.info("Reloading emergency resources...")
        self._registry = self._load_resources()
