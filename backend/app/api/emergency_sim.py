"""
Emergency Simulation API - V1 REST + WebSocket.

Complete simulation management endpoints:
- Simulation lifecycle (create, run, pause, stop)
- Case management
- Real-time streaming via WebSocket
- Intervention analysis
"""

import uuid
import json
import threading
from datetime import datetime
from typing import Dict, Any, Optional, List
from flask import Blueprint, request, jsonify, Response
from flask_socketio import SocketIO, emit, join_room, leave_room

from ..config import Config
from ..utils.logger import get_logger
from ..services.emergency_response import (
    ResourceRegistryService,
    DistressSignalProcessor,
    ParallelSimulationEngine,
    SimulationMode
)
from ..services.emergency_response.actionable_intervention_recommender import (
    ActionableInterventionRecommender,
    ReportFormat,
    generate_actionable_report
)
from ..models.emergency_case import (
    DistressSignal, Location, PatientInfo,
    EmergencySeverity, EmergencyType
)
from ..models.response_resource import ResourceLocation
from ..db import db as database

logger = get_logger('mirofish.api.v1')

# Create blueprint
emergency_sim_bp = Blueprint('emergency_sim', __name__, url_prefix='/api/v1')

# Global simulation manager (singleton per process)
_simulation_manager: Optional['SimulationManager'] = None
_socketio: Optional[SocketIO] = None


def get_simulation_manager() -> 'SimulationManager':
    """Get or create the global simulation manager."""
    global _simulation_manager
    if _simulation_manager is None:
        _simulation_manager = SimulationManager()
    return _simulation_manager


def get_socketio() -> Optional[SocketIO]:
    """Get the SocketIO instance."""
    return _socketio


def init_socketio(app) -> SocketIO:
    """Initialize SocketIO with the Flask app."""
    global _socketio
    if _socketio is None:
        _socketio = SocketIO(
            app,
            cors_allowed_origins="*",
            async_mode='threading',
            logger=False,
            engineio_logger=False
        )
        _setup_socketio_handlers(_socketio)
    return _socketio


def _setup_socketio_handlers(socketio: SocketIO) -> None:
    """Setup WebSocket event handlers."""

    @socketio.on('connect')
    def handle_connect():
        logger.info(f"Client connected: {request.sid}")
        emit('connected', {'sid': request.sid, 'timestamp': datetime.now().isoformat()})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info(f"Client disconnected: {request.sid}")
        manager = get_simulation_manager()
        manager.remove_client(request.sid)

    @socketio.on('subscribe')
    def handle_subscribe(data):
        """Subscribe to simulation events."""
        simulation_id = data.get('simulation_id')
        if simulation_id:
            room = f"simulation_{simulation_id}"
            join_room(room)
            logger.info(f"Client {request.sid} subscribed to {room}")
            emit('subscribed', {'room': room, 'simulation_id': simulation_id})

    @socketio.on('unsubscribe')
    def handle_unsubscribe(data):
        """Unsubscribe from simulation events."""
        simulation_id = data.get('simulation_id')
        if simulation_id:
            room = f"simulation_{simulation_id}"
            leave_room(room)
            logger.info(f"Client {request.sid} unsubscribed from {room}")

    @socketio.on('ping')
    def handle_ping():
        emit('pong', {'timestamp': datetime.now().isoformat()})


class SimulationManager:
    """
    Manages simulation lifecycle and provides WebSocket notifications.
    Thread-safe singleton manager.
    """

    def __init__(self):
        self._simulations: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._clients: Dict[str, str] = {}  # sid -> simulation_id
        self._resource_service = ResourceRegistryService()
        self._processor = DistressSignalProcessor()

    def create_simulation(
        self,
        simulation_id: Optional[str] = None,
        simulation_speed: float = 1.0,
        mode: str = "sequential",
        max_concurrent_cases: int = 100
    ) -> Dict[str, Any]:
        """Create a new simulation instance."""
        with self._lock:
            sim_id = simulation_id or f"sim_{uuid.uuid4().hex[:12]}"

            # Determine mode
            mode_enum = SimulationMode.SEQUENTIAL
            if mode == "parallel":
                mode_enum = SimulationMode.PARALLEL
            elif mode == "async":
                mode_enum = SimulationMode.ASYNC

            # Create engine
            engine = ParallelSimulationEngine(
                resource_registry=self._resource_service.get_registry(),
                simulation_speed=simulation_speed,
                mode=mode_enum,
                max_concurrent_cases=max_concurrent_cases
            )

            # Initialize with resources
            engine.initialize()

            # Store
            self._simulations[sim_id] = {
                "id": sim_id,
                "engine": engine,
                "status": "created",
                "created_at": datetime.now().isoformat(),
                "config": {
                    "simulation_speed": simulation_speed,
                    "mode": mode,
                    "max_concurrent_cases": max_concurrent_cases
                },
                "results": None
            }

            logger.info(f"Simulation created: {sim_id}")

            # Persist to Supabase (no-op when not configured)
            try:
                database.create_simulation(
                    meta=self._simulations[sim_id]["config"],
                    simulation_id=sim_id,
                )
            except Exception as e:
                logger.warning(f"Simulation persistence failed: {e}")

            return {"simulation_id": sim_id, "status": "created"}

    def get_simulation(self, simulation_id: str) -> Optional[Dict[str, Any]]:
        """Get simulation by ID."""
        with self._lock:
            return self._simulations.get(simulation_id)

    def run_simulation(
        self,
        simulation_id: str,
        duration_minutes: float = 60,
        max_steps: Optional[int] = None,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """Run a simulation."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

            if sim["status"] == "running":
                return {"error": "Simulation is already running"}

            sim["status"] = "running"

        # Start a persisted run record
        run_id = None
        try:
            run_id = database.start_run(simulation_id)
            with self._lock:
                sim["run_id"] = run_id
        except Exception as e:
            logger.warning(f"Run persistence failed: {e}")

        engine = sim["engine"]

        # Set up step callback for WebSocket updates
        def step_callback(sim_time: float, state: Dict):
            if callback:
                callback(simulation_id, sim_time, state)

        engine.on_step(step_callback)

        # Run simulation
        try:
            results = engine.run(duration_minutes=duration_minutes, max_steps=max_steps)
        except Exception as e:
            if run_id:
                database.finish_run(run_id, "failed", results={"error": str(e)})
            raise

        with self._lock:
            sim["status"] = "completed"
            sim["results"] = results

        # Persist final results
        if run_id:
            try:
                database.finish_run(
                    run_id,
                    "completed",
                    results={"summary": results.get("metrics"), "cases": {
                        c.get("case_id"): {k: v for k, v in c.items() if k != "actionable_analysis"}
                        for c in results.get("completed_cases", [])
                    }},
                    metrics=results.get("metrics"),
                )
                for cid, analysis in (results.get("actionable_analyses") or {}).items():
                    database.update_case(cid, status="completed", outcome={
                        "bottlenecks": len(analysis.get("bottlenecks", [])),
                        "recommendations": len(analysis.get("recommendations", [])),
                    })
            except Exception as e:
                logger.warning(f"Results persistence failed: {e}")

        logger.info(f"Simulation {simulation_id} completed")
        return results

    def pause_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Pause a running simulation."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

            engine = sim["engine"]
            engine.pause()
            sim["status"] = "paused"

        return {"status": "paused", "simulation_id": simulation_id}

    def resume_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Resume a paused simulation."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

            engine = sim["engine"]
            engine.resume()
            sim["status"] = "running"

        return {"status": "running", "simulation_id": simulation_id}

    def stop_simulation(self, simulation_id: str) -> Dict[str, Any]:
        """Stop a simulation."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

            engine = sim["engine"]
            engine.stop()
            sim["status"] = "stopped"

        # Persist stopped run
        run_id = sim.get("run_id")
        if run_id:
            try:
                database.finish_run(run_id, "stopped")
            except Exception as e:
                logger.warning(f"Stop persistence failed: {e}")

        return {"status": "stopped", "simulation_id": simulation_id}

    def add_case(
        self,
        simulation_id: str,
        signal_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Add a case to simulation."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

        # Process signal
        result = self._processor.process_signal(signal_data)
        if not result["success"]:
            return {"error": "Invalid signal", "details": result.get("errors")}

        # Create DistressSignal
        signal = DistressSignal.from_dict(result["signal"])

        # Add to engine
        engine = sim["engine"]
        case_id = engine.add_case(signal)

        # Persist the case
        try:
            database.upsert_case(simulation_id, case_id, result["signal"])
            database.update_simulation(simulation_id)
        except Exception as e:
            logger.warning(f"Case persistence failed: {e}")

        return {"case_id": case_id, "status": "queued"}

    def get_state(self, simulation_id: str) -> Dict[str, Any]:
        """Get simulation state."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

        engine = sim["engine"]
        return engine.get_state_snapshot()

    def get_results(self, simulation_id: str) -> Dict[str, Any]:
        """Get simulation results."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return {"error": f"Simulation {simulation_id} not found"}

        engine = sim["engine"]
        results = engine.update_results_with_actionable_interventions()
        return results

    def get_intervention_report(
        self,
        simulation_id: str,
        case_id: str,
        format: str = "detailed"
    ) -> Optional[str]:
        """Get actionable intervention report for a case."""
        with self._lock:
            sim = self._simulations.get(simulation_id)
            if not sim:
                return None

        engine = sim["engine"]
        return engine.get_actionable_report(case_id, format)

    def add_client(self, sid: str, simulation_id: Optional[str] = None):
        """Track a connected client."""
        with self._lock:
            self._clients[sid] = simulation_id

    def remove_client(self, sid: str):
        """Remove a disconnected client."""
        with self._lock:
            self._clients.pop(sid, None)

    def list_simulations(self) -> List[Dict[str, Any]]:
        """List all simulations."""
        with self._lock:
            return [
                {
                    "id": s["id"],
                    "status": s["status"],
                    "created_at": s["created_at"],
                    "config": s["config"]
                }
                for s in self._simulations.values()
            ]


# =============================================================================
# REST API Endpoints
# =============================================================================

@emergency_sim_bp.route('/simulations', methods=['POST'])
def create_simulation():
    """
    Create a new simulation.

    Request Body:
    {
        "simulation_id": "optional_id",  // Optional, auto-generated if not provided
        "simulation_speed": 1.0,          // Default: 1.0
        "mode": "sequential",             // sequential, parallel, async
        "max_concurrent_cases": 100       // Default: 100
    }

    Response:
    {
        "success": true,
        "simulation_id": "sim_abc123",
        "status": "created"
    }
    """
    try:
        data = request.get_json() or {}
        manager = get_simulation_manager()

        result = manager.create_simulation(
            simulation_id=data.get('simulation_id'),
            simulation_speed=data.get('simulation_speed', 1.0),
            mode=data.get('mode', 'sequential'),
            max_concurrent_cases=data.get('max_concurrent_cases', 100)
        )

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, **result}), 201

    except Exception as e:
        logger.error(f"Error creating simulation: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations', methods=['GET'])
def list_simulations():
    """List all simulations."""
    try:
        manager = get_simulation_manager()
        simulations = manager.list_simulations()
        return jsonify({"success": True, "simulations": simulations}), 200

    except Exception as e:
        logger.error(f"Error listing simulations: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>', methods=['GET'])
def get_simulation(simulation_id: str):
    """
    Get simulation status.

    Response:
    {
        "success": true,
        "simulation": {
            "id": "sim_abc123",
            "status": "running",
            "state": {...}
        }
    }
    """
    try:
        manager = get_simulation_manager()
        sim = manager.get_simulation(simulation_id)

        if not sim:
            return jsonify({"success": False, "error": "Simulation not found"}), 404

        state = manager.get_state(simulation_id)

        return jsonify({
            "success": True,
            "simulation": {
                "id": sim["id"],
                "status": sim["status"],
                "created_at": sim["created_at"],
                "config": sim["config"],
                "state": state
            }
        }), 200

    except Exception as e:
        logger.error(f"Error getting simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/run', methods=['POST'])
def run_simulation(simulation_id: str):
    """
    Run a simulation.

    Request Body:
    {
        "duration_minutes": 60,  // Optional, default 60
        "max_steps": null       // Optional
    }

    Response: Simulation results (see /results endpoint)
    """
    try:
        data = request.get_json() or {}
        manager = get_simulation_manager()

        # Run in background thread
        def run_async():
            manager.run_simulation(
                simulation_id,
                duration_minutes=data.get('duration_minutes', 60),
                max_steps=data.get('max_steps')
            )

        thread = threading.Thread(target=run_async)
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "simulation_id": simulation_id,
            "status": "running"
        }), 202

    except Exception as e:
        logger.error(f"Error running simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/pause', methods=['POST'])
def pause_simulation(simulation_id: str):
    """Pause a running simulation."""
    try:
        manager = get_simulation_manager()
        result = manager.pause_simulation(simulation_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, **result}), 200

    except Exception as e:
        logger.error(f"Error pausing simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/resume', methods=['POST'])
def resume_simulation(simulation_id: str):
    """Resume a paused simulation."""
    try:
        manager = get_simulation_manager()
        result = manager.resume_simulation(simulation_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, **result}), 200

    except Exception as e:
        logger.error(f"Error resuming simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/stop', methods=['POST'])
def stop_simulation(simulation_id: str):
    """Stop a simulation."""
    try:
        manager = get_simulation_manager()
        result = manager.stop_simulation(simulation_id)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, **result}), 200

    except Exception as e:
        logger.error(f"Error stopping simulation: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/results', methods=['GET'])
def get_simulation_results(simulation_id: str):
    """Get simulation results."""
    try:
        manager = get_simulation_manager()
        results = manager.get_results(simulation_id)

        if "error" in results:
            return jsonify({"success": False, "error": results["error"]}), 404

        return jsonify({"success": True, "results": results}), 200

    except Exception as e:
        logger.error(f"Error getting results: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Case Management Endpoints
# =============================================================================

@emergency_sim_bp.route('/simulations/<simulation_id>/cases', methods=['POST'])
def add_case(simulation_id: str):
    """
    Add a case to simulation.

    Request Body:
    {
        "case_id": "optional_case_id",  // Optional
        "severity": "critical",
        "emergency_type": "fetal_distress",
        "location": {"lat": 28.61, "lng": 77.21, "address": "..."},
        "patient": {...},
        "time_window_minutes": 30
    }

    Response:
    {
        "success": true,
        "case_id": "case_xyz",
        "status": "queued"
    }
    """
    try:
        data = request.get_json()
        if not data:
            return jsonify({"success": False, "error": "No data provided"}), 400

        manager = get_simulation_manager()
        result = manager.add_case(simulation_id, data)

        if "error" in result:
            return jsonify({"success": False, "error": result["error"]}), 400

        return jsonify({"success": True, **result}), 201

    except Exception as e:
        logger.error(f"Error adding case: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/cases', methods=['GET'])
def list_cases(simulation_id: str):
    """List all cases in a simulation."""
    try:
        manager = get_simulation_manager()
        sim = manager.get_simulation(simulation_id)

        if not sim:
            return jsonify({"success": False, "error": "Simulation not found"}), 404

        engine = sim["engine"]
        queue_metrics = engine.case_queue.get_metrics()

        return jsonify({
            "success": True,
            "cases": {
                "queued": queue_metrics.get("queued", 0),
                "processing": queue_metrics.get("processing", 0),
                "completed": queue_metrics.get("completed", 0),
                "failed": queue_metrics.get("failed", 0)
            }
        }), 200

    except Exception as e:
        logger.error(f"Error listing cases: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Intervention Analysis Endpoints
# =============================================================================

@emergency_sim_bp.route('/simulations/<simulation_id>/interventions/<case_id>', methods=['GET'])
def get_intervention_analysis(simulation_id: str, case_id: str):
    """
    Get actionable intervention analysis for a case.

    Query params:
    - format: detailed, brief, markdown, json

    Response:
    {
        "success": true,
        "analysis": {...},
        "report": "Mission briefing style text report..."
    }
    """
    try:
        format_type = request.args.get('format', 'detailed')
        manager = get_simulation_manager()

        # Get raw analysis
        sim = manager.get_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "Simulation not found"}), 404

        engine = sim["engine"]
        analysis = engine.get_actionable_analysis(case_id)

        if not analysis:
            return jsonify({"success": False, "error": "Case not found or no analysis available"}), 404

        # Get formatted report
        report = engine.get_actionable_report(case_id, format_type)

        return jsonify({
            "success": True,
            "analysis": analysis.to_dict(),
            "report": report
        }), 200

    except Exception as e:
        logger.error(f"Error getting intervention analysis: {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/simulations/<simulation_id>/interventions/<case_id>/critical', methods=['GET'])
def get_critical_interventions(simulation_id: str, case_id: str):
    """
    Get top critical interventions for a case.

    Query params:
    - count: number of interventions (default: 3)

    Response:
    {
        "success": true,
        "case_id": "...",
        "interventions": [...]
    }
    """
    try:
        count = request.args.get('count', 3, type=int)
        manager = get_simulation_manager()

        sim = manager.get_simulation(simulation_id)
        if not sim:
            return jsonify({"success": False, "error": "Simulation not found"}), 404

        engine = sim["engine"]
        interventions = engine.get_top_interventions(case_id, count)

        return jsonify({
            "success": True,
            "case_id": case_id,
            "interventions": interventions
        }), 200

    except Exception as e:
        logger.error(f"Error getting critical interventions: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Real-time Streaming Endpoints
# =============================================================================

@emergency_sim_bp.route('/simulations/<simulation_id>/stream', methods=['GET'])
def get_stream_info(simulation_id: str):
    """
    Get WebSocket stream information.

    Response:
    {
        "success": true,
        "stream_url": "/ws/simulations/{simulation_id}/events",
        "events": ["step", "case_update", "agent_state", "alert"]
    }
    """
    return jsonify({
        "success": True,
        "stream_url": f"/socket.io/?simulation_id={simulation_id}",
        "events": ["step", "case_update", "agent_state", "alert"],
        "socketio_version": "4.x"
    }), 200


# =============================================================================
# Resources Endpoints
# =============================================================================

@emergency_sim_bp.route('/resources', methods=['GET'])
def get_resources():
    """Get all resources (hospitals, ambulances, etc.)."""
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
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/resources/nearest', methods=['GET'])
def get_nearest_resources():
    """
    Find nearest resources to a location.

    Query params:
    - lat: latitude (required)
    - lng: longitude (required)
    - type: hospital, ambulance, all (default: all)
    """
    try:
        lat = request.args.get('lat', type=float)
        lng = request.args.get('lng', type=float)
        resource_type = request.args.get('type', 'all')

        if lat is None or lng is None:
            return jsonify({
                "success": False,
                "error": "lat and lng are required"
            }), 400

        resource_service = ResourceRegistryService()
        result = {"success": True}

        if resource_type in ('hospital', 'all'):
            hospital = resource_service.find_nearest_hospital(lat, lng)
            result["nearest_hospital"] = hospital.to_dict() if hospital else None

        if resource_type in ('ambulance', 'all'):
            ambulance = resource_service.find_nearest_ambulance(lat, lng)
            result["nearest_ambulance"] = ambulance.to_dict() if ambulance else None

        return jsonify(result), 200

    except Exception as e:
        logger.error(f"Error finding nearest resources: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# Health & Status Endpoints
# =============================================================================

@emergency_sim_bp.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "service": "Emergency Simulation API V1",
        "timestamp": datetime.now().isoformat()
    }), 200


@emergency_sim_bp.route('/status', methods=['GET'])
def get_status():
    """Get overall system status."""
    try:
        manager = get_simulation_manager()
        simulations = manager.list_simulations()

        running = sum(1 for s in simulations if s["status"] == "running")
        completed = sum(1 for s in simulations if s["status"] == "completed")

        return jsonify({
            "status": "ok",
            "simulations": {
                "total": len(simulations),
                "running": running,
                "completed": completed
            },
            "timestamp": datetime.now().isoformat()
        }), 200

    except Exception as e:
        logger.error(f"Error getting status: {str(e)}")
        return jsonify({"status": "error", "error": str(e)}), 500


# =============================================================================
# Event Log & History Endpoints
# =============================================================================

@emergency_sim_bp.route('/simulations/<simulation_id>/events', methods=['GET'])
def get_simulation_events(simulation_id: str):
    """
    Get the event log for a simulation's latest (or specified) run.

    Query params:
    - run_id: specific run (default: latest run for this simulation)
    - after_id: return only events with id > this (incremental polling)
    - limit: max events returned (default 1000)
    """
    try:
        run_id = request.args.get('run_id')
        if not run_id:
            sim = get_simulation_manager().get_simulation(simulation_id)
            run_id = sim.get("run_id") if sim else None
        if not run_id:
            return jsonify({"success": True, "run_id": None, "events": []}), 200

        after_id = request.args.get('after_id', 0, type=int)
        limit = min(request.args.get('limit', 1000, type=int), 5000)
        events = database.get_events(run_id, limit=limit, after_id=after_id)

        return jsonify({
            "success": True,
            "run_id": run_id,
            "count": len(events),
            "events": events,
        }), 200

    except Exception as e:
        logger.error(f"Error getting events: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/history', methods=['GET'])
def get_history():
    """List past simulations and their runs from the database."""
    try:
        sims = database.list_simulations(limit=50)
        return jsonify({"success": True, "simulations": sims}), 200
    except Exception as e:
        logger.error(f"Error getting history: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@emergency_sim_bp.route('/runs/<run_id>', methods=['GET'])
def get_run_detail(run_id: str):
    """Get a persisted run record by ID."""
    try:
        run = database.get_run(run_id)
        if not run:
            return jsonify({"success": False, "error": "Run not found"}), 404
        return jsonify({"success": True, "run": run}), 200
    except Exception as e:
        logger.error(f"Error getting run: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500
