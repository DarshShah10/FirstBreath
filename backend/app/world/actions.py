"""
Agent action schema and application.

Agents PROPOSE; the world DISPOSES. Every action is validated against the
current WorldState; rejections are returned (and logged as events), never
silently dropped â€” failed decisions are report material.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Union

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .state import (
    AMB_AT_HOSPITAL, AMB_AVAILABLE, AMB_DISPATCHED, AMB_RETURNING,
    AMB_STABILIZING, AMB_TO_HOSPITAL, AMB_TO_PATIENT,
    CASE_QUEUED, CASE_DISPATCHED, CASE_TRANSPORTING,
    CONDITION_MULTIPLIERS, ROUTE_BLOCKED, STAFF_PAGED, WorldState,
    DEPART_TIME, PAGE_RESPONSE_BASE, draw_float,
)
from .events import make_event, ACTION_REJECTED, DISPATCH, PRE_ALERT, REROUTE, OT_RESERVED as OT_RESERVED_EV


# ---------------------------------------------------------------------------
# Pydantic contracts â€” what LLM agents must emit
# ---------------------------------------------------------------------------

class _Action(BaseModel):
    model_config = ConfigDict(extra='ignore')


class DispatchAmbulance(_Action):
    """Send an ambulance to a case's patient location, bound to a hospital."""
    kind: Literal["dispatch_ambulance"] = "dispatch_ambulance"
    case_id: str
    ambulance_id: str
    hospital_id: str
    rationale: str = ""


class PreAlertHospital(_Action):
    """Warn a hospital that a case is inbound so it can prep OT/staff."""
    kind: Literal["pre_alert_hospital"] = "pre_alert_hospital"
    case_id: str
    hospital_id: str
    rationale: str = ""


class PrepareOt(_Action):
    """Reserve + start preparing an operating theater (~10 min prep)."""
    kind: Literal["prepare_ot"] = "prepare_ot"
    hospital_id: str
    case_id: str
    rationale: str = ""


class RerouteAmbulance(_Action):
    """Switch an en-route ambulance onto a specific alternate route."""
    kind: Literal["reroute_ambulance"] = "reroute_ambulance"
    ambulance_id: str
    route_id: str
    rationale: str = ""


class RequestBlood(_Action):
    kind: Literal["request_blood"] = "request_blood"
    case_id: str
    hospital_id: str
    blood_type: str
    units: int = 2
    rationale: str = ""


class PageStaff(_Action):
    kind: Literal["page_staff"] = "page_staff"
    hospital_id: str
    specialization: str
    case_id: str
    rationale: str = ""


class UpdateTraffic(_Action):
    """Rule-based actor / scenario input: change a route segment's condition."""
    kind: Literal["update_traffic"] = "update_traffic"
    route_id: str
    condition: str
    reason: str = ""
    duration_min: float = 30.0
    rationale: str = ""


class Escalate(_Action):
    """Declare on-record that a case cannot meet its window as things stand."""
    kind: Literal["escalate"] = "escalate"
    case_id: str
    reason: str
    rationale: str = ""


class NoOp(_Action):
    kind: Literal["noop"] = "noop"
    rationale: str = ""


Action = Union[
    DispatchAmbulance, PreAlertHospital, PrepareOt, RerouteAmbulance, RequestBlood,
    PageStaff, UpdateTraffic, Escalate, NoOp,
]


class DecisionList(BaseModel):
    model_config = ConfigDict(extra='ignore')
    """The structured output every LLM agent returns each invocation."""
    decisions: List[Action] = Field(default_factory=list)
    radio_messages: List[str] = Field(default_factory=list)
    reasoning_summary: str = ""


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

class ActionResult:
    def __init__(self, ok: bool, detail: str, events: Optional[List[Dict]] = None):
        self.ok = ok
        self.detail = detail
        self.events = events or []

    def __repr__(self):
        return f"ActionResult(ok={self.ok}, detail={self.detail!r})"


def _reject(state: WorldState, run_id: str, agent_id: str, why: str) -> ActionResult:
    return ActionResult(False, why, [make_event(
        run_id, ACTION_REJECTED, state.sim_time, agent_id=agent_id,
        agent_type="system", payload={"reason": why},
    )])


def _find_route(state: WorldState, from_loc: Dict, to_loc: Dict) -> Optional[str]:
    """Nearest route by endpoint distance (haversine-ish)."""
    def d(a, b):
        from math import radians, sin, cos, asin, sqrt
        la1, lo1, la2, lo2 = map(radians, [a["lat"], a["lng"], b["lat"], b["lng"]])
        h = sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2
        return 6371 * 2 * asin(sqrt(h))
    best, best_d = None, 1e9
    for rid, r in state.routes.items():
        dist = d(from_loc, r["from"]) + d(to_loc, r["to"])
        if dist < best_d:
            best, best_d = rid, dist
    return best if best_d < 15.0 else None   # tolerance km


def apply_action(state: WorldState, run_id: str, agent_id: str, action: Any) -> ActionResult:
    """Validate + apply one action against current world state."""

    if isinstance(action, dict):
        # tolerate plain dicts from JSON
        kind = action.get("kind")
        cls = {x.model_fields['kind'].default: x for x in (
            DispatchAmbulance, PreAlertHospital, PrepareOt, RerouteAmbulance, RequestBlood,
            PageStaff, UpdateTraffic, Escalate, NoOp,
        )}.get(kind)
        if cls is None:
            return _reject(state, run_id, agent_id, f"unknown action kind: {kind!r}")
        try:
            action = cls(**{k: v for k, v in action.items() if k != "kind"})
        except Exception as e:
            return _reject(state, run_id, agent_id, f"malformed {kind}: {e}")

    if isinstance(action, NoOp):
        return ActionResult(True, "noop")

    if isinstance(action, DispatchAmbulance):
        case = state.cases.get(action.case_id)
        amb = state.ambulances.get(action.ambulance_id)
        hosp = state.hospitals.get(action.hospital_id)
        if case is None:
            return _reject(state, run_id, agent_id, f"unknown case {action.case_id}")
        if amb is None:
            return _reject(state, run_id, agent_id, f"unknown ambulance {action.ambulance_id}")
        if hosp is None:
            return _reject(state, run_id, agent_id, f"unknown hospital {action.hospital_id}")
        if amb["status"] != AMB_AVAILABLE:
            return _reject(state, run_id, agent_id,
                           f"ambulance {amb['id']} not available (status={amb['status']})")
        if case["status"] != CASE_QUEUED:
            return _reject(state, run_id, agent_id,
                           f"case {case['case_id']} not dispatchable (status={case['status']})")

        patient_loc = {
            "lat": case["signal"]["location"]["lat"],
            "lng": case["signal"]["location"]["lng"],
        }
        route_id = _find_route(state, amb["location"], patient_loc)

        amb.update({
            "status": AMB_DISPATCHED,
            "case_id": case["case_id"],
            "patient_id": f"patient_{case['case_id']}",
            "hospital_id": action.hospital_id,
            "route_id": route_id,
            "leg": "to_patient",
            "seg_idx": 0,
            "seg_progress": 0.0,
            "depart_at": state.sim_time + DEPART_TIME,
        })
        case["status"] = CASE_DISPATCHED
        case["ambulance_id"] = amb["id"]
        case["hospital_id"] = action.hospital_id
        case["timeline"].append({"sim_time": round(state.sim_time, 2),
                                 "note": f"dispatched {amb['id']} via {route_id}"})

        ev = [make_event(
            run_id, DISPATCH, state.sim_time, agent_id=agent_id, agent_type="dispatcher",
            payload={
                "description": f"{amb['name']} dispatched to {case['case_id']} â†’ {hosp['name']}",
                "case_id": case["case_id"], "ambulance_id": amb["id"],
                "hospital_id": action.hospital_id, "route_id": route_id,
                "rationale": action.rationale,
                "eta_to_patient_min": round(state.route_duration(route_id), 1) if route_id else None,
            },
        )]
        return ActionResult(True, "dispatched", ev)

    if isinstance(action, PreAlertHospital):
        case = state.cases.get(action.case_id)
        hosp = state.hospitals.get(action.hospital_id)
        if case is None or hosp is None:
            return _reject(state, run_id, agent_id, "pre_alert: unknown case/hospital")
        if action.hospital_id not in hosp["incoming_alerts"]:
            hosp["incoming_alerts"].append(action.hospital_id)
        ev = [make_event(
            run_id, PRE_ALERT, state.sim_time, agent_id=agent_id, agent_type="hospital",
            payload={
                "description": f"{hosp['name']} pre-alerted for {case['case_id']}",
                "case_id": case["case_id"], "hospital_id": hosp["id"],
                "rationale": action.rationale,
            },
        )]
        return ActionResult(True, "pre-alerted", ev)

    if isinstance(action, PrepareOt):
        hosp = state.hospitals.get(action.hospital_id)
        if hosp is None:
            return _reject(state, run_id, agent_id, f"unknown hospital {action.hospital_id}")
        if hosp["ot_prep_started"] is not None and hosp["ot_ready_at"] is None:
            return _reject(state, run_id, agent_id,
                           f"{hosp['name']} OT already preparing")
        if hosp["ot_available"] <= 0:
            ev = [make_event(
                run_id, "action_rejected", state.sim_time, agent_id=agent_id,
                agent_type="hospital",
                payload={"reason": f"{hosp['name']} has NO free OT — diversion recommended",
                         "hospital_id": hosp["id"], "case_id": action.case_id},
            )]
            return ActionResult(False, "no OT available", ev)
        hosp["ot_prep_started"] = state.sim_time
        hosp["ot_ready_at"] = None
        hosp["ot_available"] -= 1
        hosp["ot_reserved"] += 1
        hosp["receiving_case"] = action.case_id
        ev = [make_event(
            run_id, OT_RESERVED_EV, state.sim_time, agent_id=agent_id, agent_type="hospital",
            payload={
                "description": f"{hosp['name']} reserving + prepping OT for {action.case_id} "
                               f"(ready ~T+{state.sim_time + 10:.0f})",
                "hospital_id": hosp["id"], "case_id": action.case_id,
                "rationale": action.rationale,
            },
        )]
        return ActionResult(True, "ot prep started", ev)

    if isinstance(action, RerouteAmbulance):
        amb = state.ambulances.get(action.ambulance_id)
        if amb is None:
            return _reject(state, run_id, agent_id, f"unknown ambulance {action.ambulance_id}")
        if amb["status"] not in (AMB_DISPATCHED, AMB_TO_PATIENT, AMB_TO_HOSPITAL):
            return _reject(state, run_id, agent_id,
                           f"cannot reroute {amb['id']} in status {amb['status']}")
        if action.route_id not in state.routes:
            return _reject(state, run_id, agent_id, f"unknown route {action.route_id}")
        new_route = state.routes[action.route_id]
        old_route_id = amb["route_id"]

        # Preserve physical progress proportionally across the swap.
        old_remaining = _remaining_duration(state, amb)
        new_total = state.route_duration(action.route_id)
        consumed_frac = 0.0
        if old_route_id:
            total_old = sum(
                s["duration_min"] * CONDITION_MULTIPLIERS.get(s["condition"], 1.0)
                for s in state.routes[old_route_id]["segments"]
            )
            consumed_frac = max(0.0, min(0.95, 1 - old_remaining / max(total_old, 0.01)))
        target = min(new_total * consumed_frac, max(new_total - 0.1, 0))

        amb["route_id"] = action.route_id
        amb["reroute_count"] += 1
        _seek_position_on_new_route(state, amb, target)

        ev = [make_event(
            run_id, REROUTE, state.sim_time, agent_id=agent_id, agent_type="ambulance",
            payload={
                "description": f"{amb['name']} rerouted onto {new_route['name']} ({action.rationale})",
                "ambulance_id": amb["id"], "from_route": old_route_id,
                "to_route": action.route_id, "rationale": action.rationale,
                "new_eta_min": round(_remaining_duration(state, amb), 1),
            },
        )]
        return ActionResult(True, "rerouted", ev)

    if isinstance(action, RequestBlood):
        case = state.cases.get(action.case_id)
        hosp = state.hospitals.get(action.hospital_id)
        if case is None or hosp is None:
            return _reject(state, run_id, agent_id, "blood request: unknown case/hospital")
        bank = next((b for b in state.blood_banks.values()
                     if b.get("hospital_id") == action.hospital_id), None) \
            or next(iter(state.blood_banks.values()), None)
        if bank is None:
            return _reject(state, run_id, agent_id, "no blood bank in registry")
        bt = action.blood_type.lower().replace(" ", "_").replace("-", "_negative").replace("+", "_positive")
        units = int(max(1, min(10, action.units)))
        bank.setdefault("reservations", {})[case["case_id"]] = {bt: units}
        bank["fulfilling_until"][case["case_id"]] = state.sim_time + 5.0  # BLOOD_PREP_TIME
        ev = [make_event(
            run_id, "blood_requested", state.sim_time, agent_id=agent_id, agent_type="hospital",
            payload={
                "description": f"{units}u {bt} requested from {bank['name']} for {case['case_id']}",
                "case_id": case["case_id"], "blood_bank_id": bank["id"],
                "blood_type": bt, "units": units, "rationale": action.rationale,
            },
        )]
        return ActionResult(True, "requested", ev)

    if isinstance(action, PageStaff):
        hosp = state.hospitals.get(action.hospital_id)
        if hosp is None:
            return _reject(state, run_id, agent_id, f"unknown hospital {action.hospital_id}")
        candidates = [s for s in state.staff.values()
                      if s["hospital_id"] == action.hospital_id
                      and s["specialization"] == action.specialization
                      and s["status"] == "on_call"]
        if not candidates:
            return _reject(state, run_id, agent_id,
                           f"no {action.specialization} on call at {hosp['id']}")
        paged = []
        for s in candidates:
            jitter = draw_float(state.seed, state.tick_count, f"page:{s['id']}", 0.8, 1.3)
            eta = s["response_eta_min"] * jitter
            s["status"] = STAFF_PAGED
            s["paged_at"] = state.sim_time
            s["arrives_at"] = state.sim_time + max(1.0, PAGE_RESPONSE_BASE * s["response_eta_min"] / 5.0 * jitter)
            paged.append(s["id"])
        ev = [make_event(
            run_id, "staff_paged", state.sim_time, agent_id=agent_id, agent_type="hospital",
            payload={
                "description": f"Paged {len(paged)} {action.specialization}(s) at {hosp['name']}",
                "hospital_id": hosp["id"], "staff_ids": paged,
                "specialization": action.specialization, "case_id": action.case_id,
                "rationale": action.rationale,
            },
        )]
        return ActionResult(True, "paged", ev)

    if isinstance(action, UpdateTraffic):
        route = state.routes.get(action.route_id)
        if route is None:
            return _reject(state, run_id, agent_id, f"unknown route {action.route_id}")
        cond = action.condition.lower()
        if cond not in CONDITION_MULTIPLIERS:
            return _reject(state, run_id, agent_id, f"bad condition {cond!r}")
        until = None if cond == "clear" else state.sim_time + float(action.duration_min)
        for seg in route["segments"]:
            seg["condition"] = cond
            seg["condition_reason"] = action.reason
            seg["condition_until"] = until
        ev = [make_event(
            run_id, "traffic_changed", state.sim_time, agent_id=agent_id, agent_type="world",
            payload={
                "description": f"{route['name']} â†’ {cond.upper()} ({action.reason})",
                "route_id": route["id"], "condition": cond,
                "reason": action.reason, "duration_min": action.duration_min,
                "blocked": cond == ROUTE_BLOCKED,
            },
        )]
        return ActionResult(True, "updated", ev)

    if isinstance(action, Escalate):
        case = state.cases.get(action.case_id)
        if case is None:
            return _reject(state, run_id, agent_id, f"unknown case {action.case_id}")
        case["timeline"].append({"sim_time": round(state.sim_time, 2),
                                 "note": f"ESCALATED: {action.reason}"})
        ev = [make_event(
            run_id, "escalated", state.sim_time, agent_id=agent_id, agent_type="dispatcher",
            payload={"description": f"{case['case_id']} escalated: {action.reason}",
                     "case_id": case["case_id"], "reason": action.reason},
        )]
        return ActionResult(True, "escalated", ev)

    return _reject(state, run_id, agent_id, f"unhandled action type {type(action).__name__}")


# ---------------------------------------------------------------------------
# Movement helpers (shared by actions + physics)
# ---------------------------------------------------------------------------

def _remaining_duration(state: WorldState, amb: Dict[str, Any]) -> float:
    """Minutes left on the ambulance's current leg."""
    rid = amb.get("route_id")
    if not rid or rid not in state.routes:
        return 0.0
    segs = state.routes[rid]["segments"]
    remaining = 0.0
    for i, seg in enumerate(segs):
        mult = CONDITION_MULTIPLIERS.get(seg["condition"], 1.0)
        dur = seg["duration_min"] * mult
        if i < amb["seg_idx"]:
            continue
        if i == amb["seg_idx"]:
            remaining += dur * (1.0 - amb["seg_progress"])
        else:
            remaining += dur
    return remaining


def _seek_position_on_new_route(state: WorldState, amb: Dict[str, Any], target_minutes: float):
    """Place seg_idx/seg_progress such that ~target_minutes remain on the leg."""
    segs = state.routes[amb["route_id"]]["segments"]
    acc = 0.0
    for i, seg in enumerate(segs):
        dur = seg["duration_min"] * CONDITION_MULTIPLIERS.get(seg["condition"], 1.0)
        if acc + dur >= target_minutes or i == len(segs) - 1:
            frac = 0.0 if dur <= 0 else min((target_minutes - acc) / dur, 0.999)
            amb["seg_idx"] = i
            amb["seg_progress"] = max(0.0, frac)
            return
        acc += dur




