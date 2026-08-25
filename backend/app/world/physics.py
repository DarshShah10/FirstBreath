"""
Deterministic physics tick.

Advances the world by dt minutes: movement along route segments by real
distance/duration math, timers, staff travel, blood fulfillment, traffic
decay and seeded incidents. Emits typed events for everything observable.
"""

from __future__ import annotations

from typing import Any, Dict, List

from .state import (
    AMB_AVAILABLE, AMB_DISPATCHED, AMB_TO_PATIENT, AMB_AT_PATIENT,
    AMB_STABILIZING, AMB_TO_HOSPITAL, AMB_AT_HOSPITAL, AMB_RETURNING,
    CASE_QUEUED, CASE_DISPATCHED, CASE_TRANSPORTING, CASE_COMPLETED, CASE_FAILED,
    CONDITION_MULTIPLIERS, ROUTE_CLEAR, ROUTE_LIGHT, ROUTE_MODERATE,
    ROUTE_HEAVY, STAFF_PAGED, STAFF_ARRIVED,
    DEPART_TIME, STABILIZE_TIME, HANDOVER_TIME, OT_PREP_TIME, BLOOD_PREP_TIME,
    SPEED_KMH, WorldState, draw_float, rng_for,
)
from .events import (
    make_event, AMB_DEPARTED, ARRIVED_PATIENT, STABILIZED, TRANSPORT_STARTED,
    ARRIVED_HOSPITAL, CASE_COMPLETED_EV, OT_RESERVED, OT_READY,
    STAFF_ARRIVED_EV, BLOOD_READY, TRAFFIC_CHANGED, TICK,
)


def _seg_position(state: WorldState, amb: Dict[str, Any]) -> Dict[str, float]:
    """Interpolate lat/lng along the ambulance's current leg."""
    rid = amb.get("route_id")
    if not rid or rid not in state.routes:
        return dict(amb["location"])
    segs = state.routes[rid]["segments"]
    if not segs:
        return dict(amb["location"])
    i = min(amb["seg_idx"], len(segs) - 1)
    seg = segs[i]
    p = amb["seg_progress"]

    # walk segment endpoints from route endpoints (single-segment routes are
    # exact; multi-segment interpolate within current segment bounds)
    lat0 = state.routes[rid]["from"]["lat"] + (state.routes[rid]["to"]["lat"] - state.routes[rid]["from"]["lat"]) * (i / len(segs))
    lng0 = state.routes[rid]["from"]["lng"] + (state.routes[rid]["to"]["lng"] - state.routes[rid]["from"]["lng"]) * (i / len(segs))
    lat1 = state.routes[rid]["from"]["lat"] + (state.routes[rid]["to"]["lat"] - state.routes[rid]["from"]["lat"]) * ((i + 1) / len(segs))
    lng1 = state.routes[rid]["from"]["lng"] + (state.routes[rid]["to"]["lng"] - state.routes[rid]["from"]["lng"]) * ((i + 1) / len(segs))

    return {
        "lat": round(lat0 + (lat1 - lat0) * p, 6),
        "lng": round(lng0 + (lng1 - lng0) * p, 6),
    }


def _advance_leg(state: WorldState, amb: Dict[str, Any], dt: float) -> bool:
    """
    Move one leg forward by dt. Returns True when the leg completed this tick.
    Progress is driven by real per-segment effective durations — distance and
    traffic actually matter (the legacy fixed-fraction bug is dead).
    """
    rid = amb["route_id"]
    if not rid or rid not in state.routes:
        # No mapped route: fall back to straight-line at SPEED_KMH.
        case = state.cases.get(amb["case_id"]) if amb["case_id"] else None
        target = None
        if case is not None:
            target = {"lat": case["signal"]["location"]["lat"],
                      "lng": case["signal"]["location"]["lng"]} \
                if amb["leg"] == "to_patient" else state.hospitals.get(amb["hospital_id"], {}).get("location")
        if target is None:
            return True
        from math import radians, sin, cos, asin, sqrt
        a, b = amb["location"], target
        la1, lo1, la2, lo2 = map(radians, [a["lat"], a["lng"], b["lat"], b["lng"]])
        dist_km = 6371 * 2 * asin(sqrt(sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2))
        eta = dist_km / SPEED_KMH * 60
        frac = min(dt / max(eta, 0.01), 1.0)
        amb["location"] = {
            "lat": round(a["lat"] + (b["lat"]-a["lat"]) * frac, 6),
            "lng": round(a["lng"] + (b["lng"]-a["lng"]) * frac, 6),
        }
        return eta <= dt

    segs = state.routes[rid]["segments"]
    moved = dt
    while moved > 0 and amb["seg_idx"] < len(segs):
        seg = segs[amb["seg_idx"]]
        dur = seg["duration_min"] * CONDITION_MULTIPLIERS.get(seg["condition"], 1.0)
        need = dur * (1.0 - amb["seg_progress"])
        if moved >= need:
            moved -= need
            amb["seg_idx"] += 1
            amb["seg_progress"] = 0.0
        else:
            amb["seg_progress"] += moved / max(dur, 0.01)
            moved = 0.0
        amb["location"] = _seg_position(state, amb)
    return amb["seg_idx"] >= len(segs)


def tick(state: WorldState, run_id: str, dt: float = 0.5) -> List[Dict[str, Any]]:
    """Advance the world one step. Returns the events generated."""
    ev: List[Dict[str, Any]] = []
    state.sim_time += dt
    state.tick_count += 1
    t = state.sim_time

    # ---- traffic lifecycle -------------------------------------------------
    for rid, route in state.routes.items():
        for k, seg in enumerate(route["segments"]):
            if seg["condition_until"] is not None and t >= seg["condition_until"]:
                old = seg["condition"]
                seg["condition"] = ROUTE_CLEAR
                seg["condition_reason"] = ""
                seg["condition_until"] = None
                if old != ROUTE_CLEAR:
                    ev.append(make_event(
                        run_id, TRAFFIC_CHANGED, t, agent_type="world",
                        payload={"description": f"{route['name']} cleared ({old} → clear)",
                                 "route_id": rid, "condition": ROUTE_CLEAR},
                    ))
            elif seg["condition"] in (ROUTE_HEAVY, ROUTE_MODERATE):
                # heavy decays to moderate to light to clear over time
                decay_to = {ROUTE_HEAVY: ROUTE_MODERATE, ROUTE_MODERATE: ROUTE_LIGHT}
                if draw_float(state.seed, state.tick_count, f"decay:{rid}:{k}", 0, 1) < dt / 30.0:
                    seg["condition"] = decay_to[seg["condition"]]
                    seg["condition_until"] = None
                    ev.append(make_event(
                        run_id, TRAFFIC_CHANGED, t, agent_type="world",
                        payload={"description": f"{route['name']} easing to {seg['condition']}",
                                 "route_id": rid, "condition": seg["condition"]},
                    ))

    # Seeded incidental disruptions (~every 25 route-minutes expected)
    if state.city_conditions.get("random_incidents", False) and state.routes:
        import random as _r
        rrng = rng_for(state.seed, state.tick_count, "incidents")
        if rrng.random() < dt / 25.0:
            rid = rrng.choice(list(state.routes.keys()))
            route = state.routes[rid]
            conds = [ROUTE_MODERATE, ROUTE_HEAVY]
            cond = rrng.choice(conds)
            reason = rrng.choice(["minor accident", "construction crew", "vehicle breakdown", "double parking"])
            for seg in route["segments"]:
                if seg["condition"] == ROUTE_CLEAR:
                    seg["condition"] = cond
                    seg["condition_reason"] = reason
                    seg["condition_until"] = t + rrng.uniform(10, 30)
                    break
            ev.append(make_event(
                run_id, TRAFFIC_CHANGED, t, agent_type="world",
                payload={"description": f"{route['name']}: {reason} → {cond}",
                         "route_id": rid, "condition": cond, "reason": reason},
            ))

    # ---- ambulances --------------------------------------------------------
    for aid, amb in list(state.ambulances.items()):
        status = amb["status"]
        case = state.cases.get(amb["case_id"]) if amb["case_id"] else None

        if status == AMB_DISPATCHED and amb["depart_at"] is not None and t >= amb["depart_at"]:
            amb["status"] = AMB_TO_PATIENT
            ev.append(make_event(
                run_id, AMB_DEPARTED, t, agent_id=aid, agent_type="ambulance",
                payload={"description": f"{amb['name']} rolling to patient",
                         "case_id": amb["case_id"], "route_id": amb["route_id"]},
            ))

        elif status == AMB_TO_PATIENT:
            arrived = _advance_leg(state, amb, dt)
            if case is not None and case["status"] == CASE_DISPATCHED:
                case["status"] = "en_route_patient"
            if arrived:
                amb["status"] = AMB_AT_PATIENT
                ev.append(make_event(
                    run_id, ARRIVED_PATIENT, t, agent_id=aid, agent_type="ambulance",
                    payload={"description": f"{amb['name']} on scene",
                             "case_id": amb["case_id"]},
                ))
                if case is not None:
                    case["status"] = "on_scene"
                    case["timeline"].append({"sim_time": round(t, 2), "note": f"arrived on scene ({aid})"})

        elif status == AMB_AT_PATIENT:
            amb["status"] = AMB_STABILIZING
            amb["stabilize_until"] = t + STABILIZE_TIME

        elif status == AMB_STABILIZING:
            if t >= (amb["stabilize_until"] or t):
                amb["status"] = AMB_TO_HOSPITAL
                amb["leg"] = "to_hospital"
                # swap to hospital-bound leg: reuse same route geometry toward hospital
                hosp = state.hospitals.get(amb["hospital_id"], {})
                route = next((r for r in state.routes.values()
                              if abs(r["to"]["lat"] - hosp.get("location", {}).get("lat", 999)) < 0.02
                              and abs(r["to"]["lng"] - hosp.get("location", {}).get("lng", 999)) < 0.02),
                             None)
                if route:
                    amb["route_id"] = route["id"]
                amb["seg_idx"] = 0
                amb["seg_progress"] = 0.0
                ev.append(make_event(
                    run_id, STABILIZED, t, agent_id=aid, agent_type="ambulance",
                    payload={"description": f"{amb['name']} stabilized; transporting to "
                                            f"{hosp.get('name', amb['hospital_id'])}",
                             "case_id": amb["case_id"], "hospital_id": amb["hospital_id"]},
                ))
                if case is not None:
                    case["status"] = CASE_TRANSPORTING
                    case["timeline"].append({"sim_time": round(t, 2), "note": f"transport started ({aid})"})
                    # transport_started event with ETA
                    ev.append(make_event(
                        run_id, TRANSPORT_STARTED, t, agent_id=aid, agent_type="ambulance",
                        payload={"description": f"{aid} transporting", "case_id": case["case_id"],
                                 "eta_hospital_min": round(_remaining_min(state, amb), 1)},
                    ))

        elif status == AMB_TO_HOSPITAL:
            arrived = _advance_leg(state, amb, dt)
            if arrived:
                amb["status"] = AMB_AT_HOSPITAL
                amb["handover_until"] = t + HANDOVER_TIME
                hosp = state.hospitals.get(amb["hospital_id"], {})
                ev.append(make_event(
                    run_id, ARRIVED_HOSPITAL, t, agent_id=aid, agent_type="ambulance",
                    payload={"description": f"{amb['name']} at {hosp.get('name', amb['hospital_id'])}",
                             "case_id": amb["case_id"], "hospital_id": amb["hospital_id"]},
                ))

        elif status == AMB_AT_HOSPITAL:
            if t >= (amb["handover_until"] or t):
                hosp = state.hospitals.get(amb["hospital_id"], {})
                # complete the case
                if case is not None:
                    late = t > case["deadline"]
                    case["status"] = CASE_COMPLETED
                    case["completed_at"] = t
                    case["outcome"] = "late_success" if late else "success"
                    case["timeline"].append({
                        "sim_time": round(t, 2),
                        "note": ("completed AFTER window" if late else "completed within window"),
                    })
                    ev.append(make_event(
                        run_id, CASE_COMPLETED_EV, t, agent_type="world",
                        payload={
                            "description": f"{case['case_id']} {'LATE' if late else 'SUCCESS'} "
                                           f"(window {case['deadline']:.0f}m, finished T+{t:.1f})",
                            "case_id": case["case_id"], "outcome": case["outcome"],
                            "total_minutes": round(t, 1), "within_window": not late,
                            "timeline": case["timeline"],
                        },
                    ))
                # OT release
                if hosp.get("receiving_case") == amb["case_id"]:
                    hosp["receiving_case"] = None
                    if hosp["ot_reserved"] > 0:
                        hosp["ot_reserved"] -= 1
                        hosp["ot_available"] += 1
                # release blood reservation
                for bank in state.blood_banks.values():
                    bank["reservations"].pop(amb["case_id"], None)
                    bank["fulfilling_until"].pop(amb["case_id"], None)

                amb["status"] = AMB_RETURNING

        elif status == AMB_RETURNING:
            base = amb["base_location"]
            from math import radians, sin, cos, asin, sqrt
            a = amb["location"]
            la1, lo1, la2, lo2 = map(radians, [a["lat"], a["lng"], base["lat"], base["lng"]])
            dist_km = 6371 * 2 * asin(sqrt(sin((la2-la1)/2)**2 + cos(la1)*cos(la2)*sin((lo2-lo1)/2)**2))
            eta = dist_km / SPEED_KMH * 60
            if eta <= dt or dist_km < 0.05:
                amb.update({
                    "status": AMB_AVAILABLE, "case_id": None, "patient_id": None,
                    "hospital_id": None, "route_id": None, "leg": None,
                    "seg_idx": 0, "seg_progress": 0.0, "reroute_count": 0,
                    "location": dict(base),
                })
                ev.append(make_event(
                    run_id, "amb_available", t, agent_id=aid, agent_type="ambulance",
                    payload={"description": f"{amb['name']} back in service"},
                ))
            else:
                frac = dt / eta
                amb["location"] = {
                    "lat": round(a["lat"] + (base["lat"]-a["lat"])*frac, 6),
                    "lng": round(a["lng"] + (base["lng"]-a["lng"])*frac, 6),
                }

    # ---- hospitals: OT prep timers -----------------------------------------
    for hid, hosp in state.hospitals.items():
        if hosp["ot_prep_started"] is not None and hosp["ot_ready_at"] is None:
            if t >= hosp["ot_prep_started"] + OT_PREP_TIME:
                hosp["ot_ready_at"] = t
                ev.append(make_event(
                    run_id, OT_READY, t, agent_type="world",
                    payload={"description": f"{hosp['name']} OT ready",
                             "hospital_id": hid},
                ))
        # expire stale incoming alerts once case closes
        hosp["incoming_alerts"] = [
            cid for cid in hosp["incoming_alerts"]
            if cid in state.cases and state.cases[cid]["status"] != CASE_COMPLETED
        ]

    # ---- staff travel -------------------------------------------------------
    for sid, s in state.staff.items():
        if s["status"] == STAFF_PAGED and s["arrives_at"] is not None and t >= s["arrives_at"]:
            s["status"] = STAFF_ARRIVED
            ev.append(make_event(
                run_id, STAFF_ARRIVED_EV, t, agent_id=sid, agent_type="system",
                payload={"description": f"{s['name']} ({s['specialization']}) on site",
                         "hospital_id": s["hospital_id"]},
            ))

    # ---- blood fulfillment ---------------------------------------------------
    for bid, bank in state.blood_banks.items():
        for cid, ready_at in list(bank["fulfilling_until"].items()):
            if t >= ready_at:
                bank["fulfilling_until"].pop(cid, None)
                resv = bank["reservations"].get(cid, {})
                for bt, units in resv.items():
                    have = bank["inventory"].get(bt, 0)
                    used = min(have, units)
                    bank["inventory"][bt] = have - used
                ev.append(make_event(
                    run_id, BLOOD_READY, t, agent_id=bid, agent_type="world",
                    payload={"description": f"Blood cross-matched & ready for {cid} "
                                            f"({sum(resv.values()) if resv else 0}u)",
                             "case_id": cid, "blood_bank_id": bid},
                ))

    # ---- queued cases missing their window -> fail ---------------------------
    for cid, case in state.cases.items():
        if case["status"] == CASE_QUEUED and t > case["deadline"]:
            case["status"] = CASE_FAILED
            case["outcome"] = "failed_unassigned"
            case["completed_at"] = t
            ev.append(make_event(
                run_id, "case_failed", t, agent_type="world",
                payload={"description": f"{cid} window expired while unassigned",
                         "case_id": cid, "outcome": "failed_unassigned"},
            ))

    ev.append(make_event(
        run_id, TICK, t, agent_type="world",
        payload={"open_cases": len(state.open_cases()),
                 "sim_time": round(t, 1)},
    ))
    return ev


def _remaining_min(state: WorldState, amb: Dict[str, Any]) -> float:
    """ETA helper mirroring actions._remaining_duration without circular import."""
    rid = amb.get("route_id")
    if not rid or rid not in state.routes:
        return 0.0
    remaining = 0.0
    for i, seg in enumerate(state.routes[rid]["segments"]):
        mult = CONDITION_MULTIPLIERS.get(seg["condition"], 1.0)
        dur = seg["duration_min"] * mult
        if i < amb["seg_idx"]:
            continue
        remaining += dur * ((1.0 - amb["seg_progress"]) if i == amb["seg_idx"] else 1.0)
    return remaining
