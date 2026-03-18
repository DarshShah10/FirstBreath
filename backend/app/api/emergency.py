"""
Emergency Simulation API Routes.

Fast distress signal input and response chain simulation endpoints.
"""

import uuid
from flask import Blueprint, request, jsonify
from datetime import datetime

from . import simulation_bp
from ..config import Config
from ..utils.logger import get_logger
from ..services.emergency_response import (
    ResourceRegistryService,
    DistressSignalProcessor,
    ResponseChainGraph,
    ResponseChainNode,
    ResponseChainEdge,
    ResponseChainBuilder
)
from ..models.response_resource import ResourceStatus
from ..models.emergency_case import EmergencyCase, EmergencySeverity

logger = get_logger('mirofish.api.emergency')

# Create emergency API blueprint
emergency_bp = Blueprint('emergency', __name__, url_prefix='/api/emergency')


@emergency_bp.route('/signal', methods=['POST'])
def create_emergency_signal():
    """
    Process a distress signal from FirstBreath or manual input.

    Fast input endpoint - replaces slow document upload/ontology parsing.

    Request Body:
    {
        "case_id": "case_abc123",  // Optional, auto-generated if not provided
        "severity": "critical",     // critical, severe, moderate, low
        "emergency_type": "fetal_distress",  // fetal_distress, maternal_hemorrhage, etc.
        "location": {
            "lat": 39.9042,
            "lng": 116.4074,
            "address": "Beijing Chaoyang District"
        },
        "patient": {
            "gestational_age_weeks": 38,
            "blood_type": "O_positive",
            "complications": ["late_decelerations"],
            "previous_cesarean": false,
            "multiple_gestation": false
        },
        "time_window_minutes": 30,
        "preferred_hospital_id": "hospital_001",  // Optional
        "transport_mode": "ambulance",  // ambulance, helicopter, private_vehicle
        "source": "firstbreath"  // firstbreath, manual, emergency_call
    }

    Response:
    {
        "success": true,
        "signal": {...},
        "nearest_hospital": {...},
        "nearest_ambulance": {...},
        "recommended_route": {...},
        "estimated_times": {...}
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        processor = DistressSignalProcessor()
        result = processor.process_signal(data)

        if not result["success"]:
            return jsonify({
                "success": False,
                "errors": result["errors"]
            }), 400

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error processing distress signal: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@emergency_bp.route('/resources', methods=['GET'])
def get_resources():
    """
    Get all available healthcare resources.

    Response:
    {
        "success": true,
        "hospitals": [...],
        "ambulances": [...],
        "routes": [...]
    }
    """
    try:
        resource_service = ResourceRegistryService()
        registry = resource_service.get_registry()

        return jsonify({
            "success": True,
            "hospitals": [h.to_dict() for h in registry.hospitals.values()],
            "ambulances": [a.to_dict() for a in registry.ambulances.values()],
            "routes": [r.to_dict() for r in registry.routes.values()],
            "staff": [s.to_dict() for s in registry.staff.values()],
            "blood_banks": [b.to_dict() for b in registry.blood_banks.values()]
        }), 200

    except Exception as e:
        logger.error(f"Error getting resources: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@emergency_bp.route('/resources/hospitals', methods=['GET'])
def get_hospitals():
    """Get all hospitals."""
    try:
        resource_service = ResourceRegistryService()
        hospitals = resource_service.get_all_hospitals()

        return jsonify({
            "success": True,
            "hospitals": [h.to_dict() for h in hospitals]
        }), 200

    except Exception as e:
        logger.error(f"Error getting hospitals: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_bp.route('/resources/ambulances', methods=['GET'])
def get_ambulances():
    """Get all ambulances."""
    try:
        resource_service = ResourceRegistryService()
        ambulances = resource_service.get_all_ambulances()

        return jsonify({
            "success": True,
            "ambulances": [a.to_dict() for a in ambulances]
        }), 200

    except Exception as e:
        logger.error(f"Error getting ambulances: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_bp.route('/resources/nearest', methods=['GET'])
def get_nearest_resources():
    """
    Get nearest resources to a location.

    Query params:
    - lat: latitude
    - lng: longitude
    - type: hospital, ambulance, or both (default: both)
    """
    try:
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        resource_type = request.args.get('type', 'both')

        if lat is None or lng is None:
            return jsonify({
                "success": False,
                "error": "lat and lng query parameters are required"
            }), 400

        resource_service = ResourceRegistryService()

        result = {"success": True}

        if resource_type in ('hospital', 'both'):
            hospital = resource_service.find_nearest_hospital(lat, lng)
            result["nearest_hospital"] = hospital.to_dict() if hospital else None

        if resource_type in ('ambulance', 'both'):
            ambulance = resource_service.find_nearest_ambulance(lat, lng)
            result["nearest_ambulance"] = ambulance.to_dict() if ambulance else None

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error finding nearest resources: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_bp.route('/case', methods=['POST'])
def create_case():
    """
    Create a complete emergency case for simulation.

    This is the main entry point for creating a case ready for simulation.
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        processor = DistressSignalProcessor()
        case = processor.create_emergency_case(data)

        return jsonify({
            "success": True,
            "case": case.to_dict()
        }), 200

    except ValueError as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 400

    except Exception as e:
        logger.error(f"Error creating case: {str(e)}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@emergency_bp.route('/case/<case_id>/graph', methods=['POST'])
def build_response_graph(case_id: str):
    """
    Build a response chain graph for an emergency case.

    Request Body:
    {
        "severity": "critical",
        "emergency_type": "fetal_distress",
        "location": {"lat": 39.9042, "lng": 116.4074, "address": "..."},
        "patient": {...},
        "include_alternates": true  // Include backup resources
    }

    Response:
    {
        "success": true,
        "graph_id": "rcg_xxx",
        "nodes": [...],
        "edges": [...],
        "d3_format": {...}  // Ready for D3.js visualization
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        # Process signal
        processor = DistressSignalProcessor()
        signal_result = processor.process_signal(data)

        if not signal_result["success"]:
            return jsonify({
                "success": False,
                "errors": signal_result["errors"]
            }), 400

        # Get resources
        resource_service = ResourceRegistryService()
        registry = resource_service.get_registry()

        # Parse signal for graph building
        from ..models.emergency_case import DistressSignal, Location, PatientInfo, EmergencySeverity, EmergencyType

        location_data = data.get('location', {})
        patient_data = data.get('patient', {})

        signal = DistressSignal(
            case_id=case_id,
            severity=EmergencySeverity(data.get('severity', 'moderate')),
            emergency_type=EmergencyType(data.get('emergency_type', 'other')),
            location=Location(
                lat=location_data.get('lat', 0),
                lng=location_data.get('lng', 0),
                address=location_data.get('address', '')
            ),
            patient=PatientInfo(
                gestational_age_weeks=patient_data.get('gestational_age_weeks', 38),
                blood_type=patient_data.get('blood_type', 'O_positive'),
                complications=patient_data.get('complications', [])
            ),
            source='api'
        )

        # Build graph
        builder = ResponseChainBuilder(registry)

        # Convert dict results back to proper objects
        from ..models.response_resource import (
            Hospital, Ambulance, TransportRoute, ResourceLocation, HospitalLevel
        )

        ambulance_obj = None
        hospital_obj = None
        route_obj = None

        if signal_result.get('nearest_ambulance'):
            amb_data = signal_result['nearest_ambulance']
            ambulance_obj = Ambulance(
                ambulance_id=amb_data['ambulance_id'],
                name=amb_data['name'],
                location=ResourceLocation(
                    lat=amb_data['location']['lat'],
                    lng=amb_data['location']['lng']
                ),
                equipped_for=amb_data.get('equipped_for', []),
                response_time_to_location=amb_data.get('response_time_to_location', 10.0)
            )

        if signal_result.get('nearest_hospital'):
            hosp_data = signal_result['nearest_hospital']
            hospital_obj = Hospital(
                hospital_id=hosp_data['hospital_id'],
                name=hosp_data['name'],
                level=hosp_data.get('level', 'secondary'),
                location=ResourceLocation(
                    lat=hosp_data['location']['lat'],
                    lng=hosp_data['location']['lng']
                ),
                ot_count=hosp_data.get('ot_count', 0)
            )

        if signal_result.get('recommended_route'):
            route_data = signal_result['recommended_route']
            route_obj = TransportRoute(
                route_id=route_data['route_id'],
                from_location=ResourceLocation(
                    lat=route_data['from_location']['lat'],
                    lng=route_data['from_location']['lng']
                ),
                to_location=ResourceLocation(
                    lat=route_data['to_location']['lat'],
                    lng=route_data['to_location']['lng']
                ),
                distance_km=route_data.get('distance_km', 0),
                typical_duration_minutes=route_data.get('typical_duration_minutes', 20),
                current_status=route_data.get('current_status', 'clear')
            )

        if data.get('include_alternates', False):
            # Find backup resources
            backup_ambulance = None
            backup_route = None

            available_ambulances = registry.get_available_ambulances()
            if len(available_ambulances) > 1:
                backup_ambulance = available_ambulances[1]

            graph = builder.build_with_alternates(
                signal=signal,
                primary_ambulance=ambulance_obj,
                primary_hospital=hospital_obj,
                primary_route=route_obj,
                backup_ambulance=backup_ambulance,
                backup_route=backup_route
            )
        else:
            graph = builder.build_graph(
                signal=signal,
                ambulance=ambulance_obj,
                hospital=hospital_obj,
                route=route_obj
            )

        return jsonify({
            "success": True,
            "graph": graph.to_dict(),
            "d3_format": graph.to_d3_format(),
            "signal_result": signal_result
        }), 200

    except Exception as e:
        logger.error(f"Error building response graph: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@emergency_bp.route('/route/status', methods=['PUT'])
def update_route_status():
    """
    Update a route's status (e.g., for traffic/road block).

    Request Body:
    {
        "route_id": "route_patient_central_main",
        "status": "blocked",  // clear, congested, blocked, event_affected
        "block_reason": "Festival parade"  // Required if status is blocked
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        route_id = data.get('route_id')
        status = data.get('status', 'clear')
        block_reason = data.get('block_reason')

        if not route_id:
            return jsonify({
                "success": False,
                "error": "route_id is required"
            }), 400

        resource_service = ResourceRegistryService()
        success = resource_service.update_route_status(route_id, status, block_reason)

        return jsonify({
            "success": success,
            "message": f"Route {route_id} status updated to {status}" if success else "Route not found"
        }), 200 if success else 404

    except Exception as e:
        logger.error(f"Error updating route status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_bp.route('/ambulance/status', methods=['PUT'])
def update_ambulance_status():
    """
    Update an ambulance's status.

    Request Body:
    {
        "ambulance_id": "amb_001",
        "status": "en_route"  // available, en_route, occupied
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        ambulance_id = data.get('ambulance_id')
        status_str = data.get('status', 'available')

        if not ambulance_id:
            return jsonify({
                "success": False,
                "error": "ambulance_id is required"
            }), 400

        try:
            status = ResourceStatus(status_str)
        except ValueError:
            return jsonify({
                "success": False,
                "error": f"Invalid status: {status_str}"
            }), 400

        resource_service = ResourceRegistryService()
        success = resource_service.update_ambulance_status(ambulance_id, status)

        return jsonify({
            "success": success,
            "message": f"Ambulance {ambulance_id} status updated" if success else "Ambulance not found"
        }), 200 if success else 404

    except Exception as e:
        logger.error(f"Error updating ambulance status: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_bp.route('/validate', methods=['POST'])
def validate_signal():
    """
    Validate a distress signal without processing.

    Request Body: Same as /signal endpoint

    Response:
    {
        "valid": true/false,
        "errors": ["error message"]  // If not valid
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "valid": False,
                "errors": ["No JSON data provided"]
            }), 400

        processor = DistressSignalProcessor()
        result = processor.validate_signal(data)

        return jsonify(result), 200 if result["valid"] else 400

    except Exception as e:
        logger.error(f"Error validating signal: {str(e)}")
        return jsonify({
            "valid": False,
            "errors": [str(e)]
        }), 500


@emergency_bp.route('/quick-signal', methods=['POST'])
def quick_signal():
    """
    Quick distress signal from emergency call.

    Simplified format for rapid input.

    Request Body:
    {
        "case_id": "case_xxx",  // Optional
        "emergency_type": "fetal_distress",
        "location": {"lat": 39.9042, "lng": 116.4074},
        "gestational_age_weeks": 38,
        "critical_indicators": true,  // If critical
        "notes": "Late decelerations detected"
    }
    """
    try:
        data = request.get_json()

        if not data:
            return jsonify({
                "success": False,
                "error": "No JSON data provided"
            }), 400

        processor = DistressSignalProcessor()
        signal = processor.quick_signal_from_emergency_call(data)

        # Process the quick signal
        signal_data = {
            "case_id": signal.case_id,
            "severity": signal.severity.value,
            "emergency_type": signal.emergency_type.value,
            "location": {
                "lat": signal.location.lat,
                "lng": signal.location.lng
            },
            "patient": {
                "gestational_age_weeks": signal.patient.gestational_age_weeks,
                "blood_type": signal.patient.blood_type,
                "complications": signal.patient.complications
            },
            "notes": signal.notes,
            "source": "emergency_call"
        }

        result = processor.process_signal(signal_data)

        return jsonify({
            "success": result["success"],
            "signal": signal.to_dict(),
            **result
        }), 200 if result["success"] else 400

    except Exception as e:
        logger.error(f"Error processing quick signal: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
