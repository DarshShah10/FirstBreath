"""
Response Resource Models.

Models for healthcare resources: hospitals, ambulances, staff, blood banks.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any
from datetime import datetime


class ResourceStatus(Enum):
    """Resource availability status."""
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    UNAVAILABLE = "unavailable"
    EN_ROUTE = "en_route"
    PREPARING = "preparing"
    OFF_DUTY = "off_duty"


class HospitalLevel(Enum):
    """Hospital capability levels."""
    TERTIARY = "tertiary"      # Level III NICU, full OB capability
    SECONDARY = "secondary"    # Basic OB, limited NICU
    PRIMARY = "primary"        # Limited OB services


class StaffSpecialization(Enum):
    """Medical staff specializations."""
    OBSTETRICIAN = "obstetrician"
    ANESTHESIOLOGIST = "anesthesiologist"
    NEONATOLOGIST = "neonatologist"
    MIDWIFE = "midwife"
    NURSE = "nurse"
    EMERGENCY_MEDIC = "emergency_medic"


@dataclass
class ResourceLocation:
    """Geographic location for resources."""
    lat: float
    lng: float
    address: str = ""

    def distance_to(self, other: 'ResourceLocation') -> float:
        """Calculate distance in km."""
        import math
        R = 6371
        lat1, lon1 = math.radians(self.lat), math.radians(self.lng)
        lat2, lon2 = math.radians(other.lat), math.radians(other.lng)
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        return R * 2 * math.asin(math.sqrt(a))

    def to_dict(self) -> Dict[str, Any]:
        return {"lat": self.lat, "lng": self.lng, "address": self.address}


@dataclass
class Hospital:
    """
    Hospital resource model.
    """
    hospital_id: str
    name: str
    level: HospitalLevel
    location: ResourceLocation
    obgyn_beds: int = 0
    nicu_beds: int = 0
    ot_count: int = 0
    on_call_obgyn: int = 0
    on_call_anesthesiologist: int = 0
    transfer_time_minutes: int = 15
    blood_bank_status: str = "adequate"
    status: ResourceStatus = ResourceStatus.AVAILABLE
    contact_phone: str = ""
    capabilities: List[str] = field(default_factory=list)

    def get_ot_availability(self) -> int:
        """Get available OT count."""
        if self.status in (ResourceStatus.UNAVAILABLE, ResourceStatus.OCCUPIED):
            return 0
        return self.ot_count

    def can_handle_emergency(self, emergency_type: str) -> bool:
        """Check if hospital can handle specific emergency type."""
        capability_map = {
            "fetal_distress": ["obgyn", "nicu", "ot"],
            "maternal_hemorrhage": ["obgyn", "blood_bank", "ot"],
            "eclampsia": ["obgyn", "nicu", "icu"],
            "cord_prolapse": ["obgyn", "ot", "nicu"],
        }
        required = capability_map.get(emergency_type, ["obgyn", "ot"])
        return all(cap in self.capabilities for cap in required)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hospital_id": self.hospital_id,
            "name": self.name,
            "level": self.level.value,
            "location": self.location.to_dict(),
            "obgyn_beds": self.obgyn_beds,
            "nicu_beds": self.nicu_beds,
            "ot_count": self.ot_count,
            "on_call_obgyn": self.on_call_obgyn,
            "on_call_anesthesiologist": self.on_call_anesthesiologist,
            "transfer_time_minutes": self.transfer_time_minutes,
            "blood_bank_status": self.blood_bank_status,
            "status": self.status.value,
            "contact_phone": self.contact_phone,
            "capabilities": self.capabilities,
            "ot_availability": self.get_ot_availability()
        }


@dataclass
class Ambulance:
    """
    Ambulance resource model.
    """
    ambulance_id: str
    name: str
    location: ResourceLocation
    status: ResourceStatus = ResourceStatus.AVAILABLE
    current_task_id: Optional[str] = None
    equipped_for: List[str] = field(default_factory=list)
    base_location: Optional[ResourceLocation] = None
    response_time_to_location: Optional[float] = None
    crew_count: int = 2
    has_paramedic: bool = False

    def can_handle_emergency(self, emergency_type: str) -> bool:
        """Check if ambulance can handle specific emergency."""
        capability_map = {
            "fetal_distress": ["neonatal_resuscitation", "emergency_delivery"],
            "maternal_hemorrhage": ["advanced_life_support"],
            "eclampsia": ["advanced_life_support"],
        }
        required = capability_map.get(emergency_type, ["emergency_delivery"])
        return all(cap in self.equipped_for for cap in required)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ambulance_id": self.ambulance_id,
            "name": self.name,
            "location": self.location.to_dict(),
            "status": self.status.value,
            "current_task_id": self.current_task_id,
            "equipped_for": self.equipped_for,
            "base_location": self.base_location.to_dict() if self.base_location else None,
            "response_time_to_location": self.response_time_to_location,
            "crew_count": self.crew_count,
            "has_paramedic": self.has_paramedic
        }


@dataclass
class MedicalStaff:
    """
    Medical staff resource model.
    """
    staff_id: str
    name: str
    specialization: StaffSpecialization
    hospital_id: Optional[str] = None
    status: ResourceStatus = ResourceStatus.OFF_DUTY
    on_call: bool = False
    response_time_minutes: float = 15.0
    contact_phone: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "staff_id": self.staff_id,
            "name": self.name,
            "specialization": self.specialization.value,
            "hospital_id": self.hospital_id,
            "status": self.status.value,
            "on_call": self.on_call,
            "response_time_minutes": self.response_time_minutes,
            "contact_phone": self.contact_phone
        }


@dataclass
class BloodBank:
    """
    Blood bank resource model.
    """
    blood_bank_id: str
    name: str
    location: ResourceLocation
    hospital_id: Optional[str] = None
    inventory: Dict[str, int] = field(default_factory=lambda: {
        "a_positive": 10, "a_negative": 5,
        "b_positive": 8, "b_negative": 4,
        "ab_positive": 4, "ab_negative": 2,
        "o_positive": 15, "o_negative": 8
    })
    status: ResourceStatus = ResourceStatus.AVAILABLE

    def has_blood_type(self, blood_type: str, units_needed: int = 2) -> bool:
        """Check if blood type is available."""
        return self.inventory.get(blood_type, 0) >= units_needed

    def get_units(self, blood_type: str) -> int:
        """Get available units of blood type."""
        return self.inventory.get(blood_type, 0)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "blood_bank_id": self.blood_bank_id,
            "name": self.name,
            "location": self.location.to_dict(),
            "hospital_id": self.hospital_id,
            "inventory": self.inventory,
            "status": self.status.value
        }


@dataclass
class TransportRoute:
    """
    Transport route between locations.
    """
    route_id: str
    from_location: ResourceLocation
    to_location: ResourceLocation
    distance_km: float
    typical_duration_minutes: float
    traffic_multiplier: float = 1.0
    alternate_route_available: bool = False
    alternate_route_id: Optional[str] = None
    current_status: str = "clear"
    block_reason: Optional[str] = None
    block_duration_minutes: Optional[float] = None

    def get_effective_duration(self) -> float:
        """Get actual duration considering current conditions."""
        if self.current_status == "blocked":
            if self.alternate_route_available and self.alternate_route_id:
                return self.typical_duration_minutes * 1.3
            return 999

        if self.current_status == "congested":
            return self.typical_duration_minutes * 1.5
        if self.current_status == "event_affected":
            return self.typical_duration_minutes * self.traffic_multiplier

        return self.typical_duration_minutes

    def to_dict(self) -> Dict[str, Any]:
        return {
            "route_id": self.route_id,
            "from_location": self.from_location.to_dict(),
            "to_location": self.to_location.to_dict(),
            "distance_km": self.distance_km,
            "typical_duration_minutes": self.typical_duration_minutes,
            "traffic_multiplier": self.traffic_multiplier,
            "alternate_route_available": self.alternate_route_available,
            "alternate_route_id": self.alternate_route_id,
            "current_status": self.current_status,
            "block_reason": self.block_reason,
            "block_duration_minutes": self.block_duration_minutes,
            "effective_duration_minutes": self.get_effective_duration()
        }


@dataclass
class ResourceRegistry:
    """
    Central registry for all healthcare resources.
    """
    hospitals: Dict[str, Hospital] = field(default_factory=dict)
    ambulances: Dict[str, Ambulance] = field(default_factory=dict)
    staff: Dict[str, MedicalStaff] = field(default_factory=dict)
    blood_banks: Dict[str, BloodBank] = field(default_factory=dict)
    routes: Dict[str, TransportRoute] = field(default_factory=dict)

    def get_available_hospitals(self) -> List[Hospital]:
        """Get all available hospitals."""
        return [h for h in self.hospitals.values() if h.status == ResourceStatus.AVAILABLE]

    def get_available_ambulances(self) -> List[Ambulance]:
        """Get all available ambulances."""
        return [a for a in self.ambulances.values() if a.status == ResourceStatus.AVAILABLE]

    def get_hospital_by_id(self, hospital_id: str) -> Optional[Hospital]:
        """Get hospital by ID."""
        return self.hospitals.get(hospital_id)

    def get_ambulance_by_id(self, ambulance_id: str) -> Optional[Ambulance]:
        """Get ambulance by ID."""
        return self.ambulances.get(ambulance_id)

    def find_nearest_ambulance(self, location: ResourceLocation) -> Optional[Ambulance]:
        """Find nearest available ambulance to a location."""
        available = self.get_available_ambulances()
        if not available:
            return None
        return min(available, key=lambda a: a.location.distance_to(location))

    def find_nearest_hospital(self, location: ResourceLocation) -> Optional[Hospital]:
        """Find nearest available hospital to a location."""
        available = self.get_available_hospitals()
        if not available:
            return None
        return min(available, key=lambda h: h.location.distance_to(location))

    def find_route(self, from_loc: ResourceLocation, to_loc: ResourceLocation) -> Optional[TransportRoute]:
        """Find a route between two locations by matching coordinates."""
        for route in self.routes.values():
            if (abs(route.from_location.lat - from_loc.lat) < 0.001 and
                abs(route.from_location.lng - from_loc.lng) < 0.001 and
                abs(route.to_location.lat - to_loc.lat) < 0.001 and
                abs(route.to_location.lng - to_loc.lng) < 0.001):
                return route
        return None

    def get_staff_for_hospital(self, hospital_id: str) -> List['MedicalStaff']:
        """Get all staff assigned to a hospital."""
        return [s for s in self.staff.values() if s.hospital_id == hospital_id]

    def get_on_call_staff(self, specialization: Optional['StaffSpecialization'] = None) -> List['MedicalStaff']:
        """Get on-call staff, optionally filtered by specialization."""
        on_call = [s for s in self.staff.values() if s.on_call]
        if specialization:
            on_call = [s for s in on_call if s.specialization == specialization]
        return on_call

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hospitals": {k: v.to_dict() for k, v in self.hospitals.items()},
            "ambulances": {k: v.to_dict() for k, v in self.ambulances.items()},
            "staff": {k: v.to_dict() for k, v in self.staff.items()},
            "blood_banks": {k: v.to_dict() for k, v in self.blood_banks.items()},
            "routes": {k: v.to_dict() for k, v in self.routes.items()}
        }
