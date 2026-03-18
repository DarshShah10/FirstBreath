"""
Distress Signal Processor.

Processes incoming distress signals and prepares them for simulation.
This replaces the slow document upload/ontology parsing with fast direct input.
"""

import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...models.emergency_case import (
    DistressSignal,
    EmergencyCase,
    EmergencySeverity,
    EmergencyType,
    Location,
    PatientInfo
)
from ...models.response_resource import ResourceRegistry, ResourceLocation
from ...utils.logger import get_logger
from .resource_registry_service import ResourceRegistryService

logger = get_logger('mirofish.distress_signal_processor')


class DistressSignalProcessor:
    """
    Processes distress signals for emergency simulation.

    This is a fast alternative to document upload/ontology parsing.
    Accepts structured distress signals and prepares them for simulation.
    """

    def __init__(self):
        """Initialize the processor."""
        self.resource_service = ResourceRegistryService()
        self.resource_registry = self.resource_service.get_registry()

    def process_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a distress signal from raw data.

        Args:
            signal_data: Raw signal data (from API request)

        Returns:
            Dict with processed signal and validation results
        """
        logger.info(f"Processing distress signal: {signal_data.get('case_id', 'unknown')}")

        # Parse the signal
        signal = self._parse_signal(signal_data)

        # Validate
        validation_errors = signal.validate()

        if validation_errors:
            logger.warning(f"Signal validation failed: {validation_errors}")
            return {
                "success": False,
                "errors": validation_errors,
                "signal": None
            }

        # Find nearest resources
        nearest_hospital = self.resource_service.find_nearest_hospital(
            signal.location.lat,
            signal.location.lng
        )

        nearest_ambulance = self.resource_service.find_nearest_ambulance(
            signal.location.lat,
            signal.location.lng
        )

        # Find appropriate route
        route = None
        if nearest_hospital:
            route = self.resource_service.find_route(
                signal.location.lat,
                signal.location.lng,
                nearest_hospital.location.lat,
                nearest_hospital.location.lng
            )

        # Build response
        result = {
            "success": True,
            "signal": signal.to_dict(),
            "nearest_hospital": nearest_hospital.to_dict() if nearest_hospital else None,
            "nearest_ambulance": nearest_ambulance.to_dict() if nearest_ambulance else None,
            "recommended_route": route.to_dict() if route else None,
            "estimated_times": self._calculate_estimated_times(signal, nearest_ambulance, nearest_hospital, route)
        }

        logger.info(f"Signal processed successfully for case: {signal.case_id}")
        return result

    def _parse_signal(self, data: Dict[str, Any]) -> DistressSignal:
        """Parse raw data into DistressSignal."""
        location_data = data.get('location', {})
        patient_data = data.get('patient', {})

        location = Location(
            lat=location_data.get('lat', 0.0),
            lng=location_data.get('lng', 0.0),
            address=location_data.get('address', ''),
            district=location_data.get('district', '')
        )

        patient = PatientInfo(
            gestational_age_weeks=patient_data.get('gestational_age_weeks', 38),
            blood_type=patient_data.get('blood_type', 'O_positive'),
            complications=patient_data.get('complications', []),
            previous_cesarean=patient_data.get('previous_cesarean', False),
            multiple_gestation=patient_data.get('multiple_gestation', False),
            maternal_age=patient_data.get('maternal_age', 0),
            maternal_conditions=patient_data.get('maternal_conditions', [])
        )

        # Handle severity
        severity_str = data.get('severity', 'moderate')
        try:
            severity = EmergencySeverity(severity_str)
        except ValueError:
            severity = EmergencySeverity.MODERATE

        # Handle emergency type
        emergency_type_str = data.get('emergency_type', 'other')
        try:
            emergency_type = EmergencyType(emergency_type_str)
        except ValueError:
            emergency_type = EmergencyType.OTHER

        # Generate case ID if not provided
        case_id = data.get('case_id', '')
        if not case_id:
            case_id = f"case_{uuid.uuid4().hex[:12]}"

        return DistressSignal(
            case_id=case_id,
            severity=severity,
            emergency_type=emergency_type,
            location=location,
            patient=patient,
            time_window_minutes=data.get('time_window_minutes', 30),
            preferred_hospital_id=data.get('preferred_hospital_id'),
            transport_mode=data.get('transport_mode', 'ambulance'),
            caller_info=data.get('caller_info', ''),
            notes=data.get('notes', ''),
            source=data.get('source', 'manual'),
            created_at=data.get('created_at', datetime.now().isoformat())
        )

    def _calculate_estimated_times(
        self,
        signal: DistressSignal,
        ambulance: Optional[Any],
        hospital: Optional[Any],
        route: Optional[Any]
    ) -> Dict[str, Any]:
        """Calculate estimated response times."""
        times = {
            "dispatch_time": 2,  # minutes to dispatch
            "ambulance_response": 0,
            "transport_to_hospital": 0,
            "hospital_prep": 0,
            "total_estimated": 0,
            "within_golden_hour": True
        }

        if ambulance and ambulance.response_time_to_location:
            times["ambulance_response"] = ambulance.response_time_to_location
        elif ambulance and ambulance.base_location:
            # Calculate approximate response time based on distance
            dist = ambulance.base_location.distance_to(
                ResourceLocation(signal.location.lat, signal.location.lng)
            )
            times["ambulance_response"] = (dist / 40.0) * 60  # 40 km/h average speed

        if route:
            times["transport_to_hospital"] = route.get_effective_duration()

        if hospital:
            times["hospital_prep"] = hospital.transfer_time_minutes

        times["total_estimated"] = (
            times["dispatch_time"] +
            times["ambulance_response"] +
            times["transport_to_hospital"] +
            times["hospital_prep"]
        )

        times["within_golden_hour"] = (
            times["total_estimated"] <= signal.time_window_minutes
        )

        return times

    def create_emergency_case(self, signal_data: Dict[str, Any]) -> EmergencyCase:
        """
        Create a full EmergencyCase from signal data.

        This is the main entry point for creating a case ready for simulation.
        """
        result = self.process_signal(signal_data)

        if not result["success"]:
            raise ValueError(f"Invalid distress signal: {result['errors']}")

        signal = self._parse_signal(result["signal"])

        return EmergencyCase(
            distress_signal=signal,
            status="pending",
            assigned_hospital_id=(
                result["nearest_hospital"]["hospital_id"]
                if result["nearest_hospital"] else None
            ),
            primary_ambulance_id=(
                result["nearest_ambulance"]["ambulance_id"]
                if result["nearest_ambulance"] else None
            ),
            estimated_response_time_minutes=(
                result["estimated_times"]["total_estimated"]
            )
        )

    def quick_signal_from_emergency_call(self, call_data: Dict[str, Any]) -> DistressSignal:
        """
        Create a distress signal from a simplified emergency call format.

        For rapid input when full details aren't available.
        """
        location_data = call_data.get('location', {})

        # Determine severity from available indicators
        severity = EmergencySeverity.MODERATE
        if call_data.get('critical_indicators'):
            severity = EmergencySeverity.CRITICAL
        elif call_data.get('warning_indicators'):
            severity = EmergencySeverity.SEVERE

        return DistressSignal(
            case_id=call_data.get('case_id', f"case_{uuid.uuid4().hex[:12]}"),
            severity=severity,
            emergency_type=EmergencyType(call_data.get('emergency_type', 'other')),
            location=Location(
                lat=location_data.get('lat', 0.0),
                lng=location_data.get('lng', 0.0),
                address=location_data.get('address', ''),
                district=location_data.get('district', '')
            ),
            patient=PatientInfo(
                gestational_age_weeks=call_data.get('gestational_age_weeks', 38),
                blood_type=call_data.get('blood_type', 'unknown'),
                complications=call_data.get('complications', [])
            ),
            time_window_minutes=call_data.get('time_window_minutes', 30),
            transport_mode=call_data.get('transport_mode', 'ambulance'),
            caller_info=call_data.get('caller_phone', ''),
            notes=call_data.get('notes', ''),
            source='emergency_call'
        )

    def validate_signal(self, signal_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a distress signal without processing.

        Returns validation result with errors (if any).
        """
        try:
            signal = self._parse_signal(signal_data)
            errors = signal.validate()

            return {
                "valid": len(errors) == 0,
                "errors": errors
            }
        except Exception as e:
            return {
                "valid": False,
                "errors": [str(e)]
            }
