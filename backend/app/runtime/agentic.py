"""
AgenticRuntime â€” hosts LangGraph agentic runs for the API layer.

One record per simulation_id. The graph owns the world; this service
mirrors it, streams events over Socket.IO, buffers them for the
transcript API, and persists to Supabase in batches.

Pause = stop pulling from graph.stream (we control the iterator).
Stop  = abandon iteration and finalize.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger('firstbreath.runtime')

DT = 0.5


class AgenticRuntime:
    _runs: Dict[str, Dict[str, Any]] = {}
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------

    @classmethod
    def start(
        cls,
        simulation_id: str,
        signals: List[Dict[str, Any]],
        seed: str = "golden-hour",
        horizon_minutes: float = 90.0,
        city_conditions: Optional[Dict[str, Any]] = None,
        mode: str = "llm",
        dt: float = DT,
        speed: float = 60.0,          # sim-min per real-second pacing hint
    ) -> bool:
        with cls._lock:
            existing = cls._runs.get(simulation_id)
            if existing and existing["status"] in ("running", "paused"):
                return False

            rec: Dict[str, Any] = {
                "simulation_id": simulation_id,
                "status": "starting",
                "mode": mode,
                "events": [],             # transcript buffer (with seq ids)
                "seq": 0,
                "mirror_world": None,
                "error": None,
                "started_at": time.time(),
                "finished_at": None,
                "outcomes": None,
                "pause_flag": False,
                "stop_flag": False,
                "_cond": threading.Condition(),
            }
            cls._runs[simulation_id] = rec

        t = threading.Thread(
            target=cls._run_worker,
            args=(rec, signals, seed, horizon_minutes, city_conditions, mode, dt),
            daemon=True,
        )
        t.start()
        return True

    # ------------------------------------------------------------------

    @classmethod
    def _emit(cls, rec: Dict[str, Any], events: List[Dict[str, Any]]):
        """Buffer new events, assign seq ids, push over Socket.IO."""
        from ..api.emergency_sim import get_socketio
        from ..db import db as database

        sio = get_socketio()
        room = f"simulation_{rec['simulation_id']}"
        fresh = []
        for ev in events:
            rec["seq"] += 1
            ev = {**ev, "id": rec["seq"]}
            rec["events"].append(ev)
            fresh.append(ev)

        if sio and fresh:
            try:
                for ev in fresh[-24:]:
                    sio.emit("agentic_event", ev, room=room)
            except Exception as e:
                logger.debug(f"socket emit failed: {e}")

        # persist (batched, best-effort) â€” skip noisy ticks
        if fresh and database.enabled:
            try:
                run_id = database.get_run(rec["simulation_id"])  # may be None
            except Exception:
                run_id = None
            rid = run_id["id"] if run_id else rec["simulation_id"]
            try:
                for ev in fresh:
                    if ev.get("event_type") == "tick":
                        continue
                    database.append_event(
                        rid, ev.get("event_type"), sim_time=ev.get("sim_time"),
                        agent_id=ev.get("agent_id"), agent_type=ev.get("agent_type"),
                        payload=ev.get("payload"),
                    )
            except Exception as e:
                logger.warning(f"event persistence failed: {e}")

    @classmethod
    def _run_worker(
        cls,
        rec: Dict[str, Any],
        signals: List[Dict[str, Any]],
        seed: str,
        horizon_minutes: float,
        city_conditions: Optional[Dict[str, Any]],
        mode: str,
        dt: float,
    ):
        from ..agents.graph import build_run_graph

        sim_id = rec["simulation_id"]
        llm_calls = 0
        try:
            graph = build_run_graph()
            cfg = {
                "configurable": {"thread_id": sim_id},
                "recursion_limit": 20000,
            }
            inputs = {
                "run_id": sim_id,
                "mode": mode,
                "seed": seed,
                "signals": signals,
                "city_conditions": city_conditions or {},
                "horizon_minutes": horizon_minutes,
                "dt": dt,
            }

            rec["status"] = "running"
            last_snap_push = 0.0

            for chunk in graph.stream(inputs, cfg, stream_mode="updates"):
                # pause / stop gates between super-steps
                with rec["_cond"]:
                    while rec["pause_flag"] and not rec["stop_flag"]:
                        rec["status"] = "paused"
                        rec["_cond"].wait(0.2)
                if rec["stop_flag"]:
                    rec["status"] = "stopped"
                    break
                if rec["status"] == "paused":
                    rec["status"] = "running"

                if not isinstance(chunk, dict):
                    continue
                for node, update in chunk.items():
                    if not isinstance(update, dict):
                        continue
                    llm_calls += update.get("llm_calls", 0) or 0
                    tev = update.get("fresh_events") or []
                    if tev:
                        cls._emit(rec, tev)
                    if "world" in update:
                        rec["mirror_world"] = update["world"]

                # throttled full-snapshot broadcast (~2 Hz of wall clock)
                now = time.time()
                if rec["mirror_world"] and now - last_snap_push > 2.0:
                    last_snap_push = now
                    sio = get_socketio_safe()
                    if sio:
                        try:
                            snap = cls.snapshot(sim_id)
                            if snap:
                                sio.emit("world_snapshot", snap, room=f"simulation_{sim_id}")
                        except Exception:
                            pass

            if rec["status"] != "stopped":
                rec["status"] = "completed"

            # finalize outcomes
            mirror = rec.get("mirror_world") or {}
            cases = mirror.get("cases") or {}
            rec["outcomes"] = {
                cid: {
                    "status": c.get("status"),
                    "outcome": c.get("outcome"),
                    "completed_at": c.get("completed_at"),
                    "timeline": c.get("timeline"),
                } for cid, c in cases.items()
            }
            rec["finished_at"] = time.time()

            cls._emit(rec, [{
                "run_id": sim_id, "event_type": "run_finished",
                "sim_time": mirror.get("sim_time", 0),
                "agent_type": "system",
                "payload": {"description": "Agentic run finalized",
                            "outcomes": {k: v.get("outcome") for k, v in rec["outcomes"].items()}},
            }])

            # persist run completion
            try:
                from ..db import db as database
                if database.enabled:
                    database.finish_run(
                        sim_id, rec["status"],
                        results={"outcomes": rec["outcomes"], "engine": "agentic"},
                        metrics={"llm_calls": llm_calls,
                                 "wall_seconds": round(time.time() - rec["started_at"], 1)},
                    )
            except Exception as e:
                logger.warning(f"finish_run persistence failed: {e}")

        except Exception as e:
            import traceback
            logger.error(f"agentic run crashed: {traceback.format_exc()}")
            rec["status"] = "failed"
            rec["error"] = str(e)
            rec["finished_at"] = time.time()

    # ------------------------------------------------------------------
    # controls
    # ------------------------------------------------------------------

    @classmethod
    def pause(cls, simulation_id: str) -> bool:
        rec = cls._runs.get(simulation_id)
        if not rec or rec["status"] != "running":
            return False
        rec["pause_flag"] = True
        return True

    @classmethod
    def resume(cls, simulation_id: str) -> bool:
        rec = cls._runs.get(simulation_id)
        if not rec or rec["status"] != "paused":
            return False
        with rec["_cond"]:
            rec["pause_flag"] = False
            rec["_cond"].notify_all()
        return True

    @classmethod
    def stop(cls, simulation_id: str) -> bool:
        rec = cls._runs.get(simulation_id)
        if not rec or rec["status"] not in ("running", "paused", "starting"):
            return False
        with rec["_cond"]:
            rec["stop_flag"] = True
            rec["pause_flag"] = False
            rec["_cond"].notify_all()
        return True

    # ------------------------------------------------------------------
    # queries
    # ------------------------------------------------------------------

    @classmethod
    def status(cls, simulation_id: str) -> Optional[Dict[str, Any]]:
        rec = cls._runs.get(simulation_id)
        if not rec:
            return None
        return {
            "simulation_id": simulation_id,
            "status": rec["status"],
            "mode": rec["mode"],
            "sim_time": (rec.get("mirror_world") or {}).get("sim_time", 0),
            "event_count": rec["seq"],
            "llm_note": "brains engaged" if rec["mode"] == "llm" else "rule brains",
            "error": rec.get("error"),
        }

    @classmethod
    def snapshot(cls, simulation_id: str) -> Optional[Dict[str, Any]]:
        rec = cls._runs.get(simulation_id)
        if not rec or not rec.get("mirror_world"):
            return None
        ws = WorldState.from_dict(rec["mirror_world"])
        eng = _shim_engine(ws, simulation_id)
        snap = eng.snapshot_for_client()
        snap["runtime_status"] = rec["status"]
        return snap

    @classmethod
    def d3(cls, simulation_id: str) -> Optional[Dict[str, Any]]:
        rec = cls._runs.get(simulation_id)
        if not rec or not rec.get("mirror_world"):
            return None
        ws = WorldState.from_dict(rec["mirror_world"])
        eng = _shim_engine(ws, simulation_id)
        return eng.d3_graph()

    @classmethod
    def events_since(cls, simulation_id: str, after_seq: int = 0,
                     limit: int = 500) -> List[Dict[str, Any]]:
        rec = cls._runs.get(simulation_id)
        if not rec:
            return []
        return [e for e in rec["events"] if (e.get("id") or 0) > after_seq][:limit]


def _shim_engine(ws: WorldState, sim_id: str):
    """Wrap a bare WorldState with WorldEngine's presentation helpers."""
    eng = object.__new__(WorldEngine)
    eng.state = ws
    eng.run_id = sim_id
    return eng


def get_socketio_safe():
    try:
        from ..api.emergency_sim import get_socketio
        return get_socketio()
    except Exception:
        return None


from ..world.state import WorldState  # noqa: E402  (bottom import avoids cycle)
from ..world.engine import WorldEngine  # noqa: E402

