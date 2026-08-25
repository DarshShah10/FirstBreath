"""
Observation packets — filtered, role-appropriate views of the world.

Each LLM agent sees only what its real-world counterpart would know,
keeping prompts small and decisions grounded.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .state import WorldState
from .physics import _remaining_min


def _case_view(state: WorldState, cid: str) -> Dict[str, Any]:
    c = state.cases[cid]
    sig = c["signal"]
    return {
        "case_id": cid,
        "emergency_type": sig.get("emergency_type"),
        "severity": sig.get("severity"),
        "location": sig.get("location", {}).get("address")
                    or sig.get("location"),
        "patient": sig.get("patient"),
        "status": c["status"],
        "ambulance_id": c["ambulance_id"],
        "hospital_id": c["hospital_id"],
        "minutes_left_in_window": round(max(0.0, c["deadline"] - state.sim_time), 1),
        "window_total_min": sig.get("time_window_minutes", 30),
    }


def dispatcher_observation(state: WorldState, recent_radio: List[str]) -> Dict[str, Any]:
    return {
        "role": "dispatcher",
        "sim_time_min": round(state.sim_time, 1),
        "open_cases": [_case_view(state, cid) for cid in state.cases
                       if state.cases[cid]["status"] not in ("completed", "failed")],
        "ambulances": [
            {
                "id": a["id"], "name": a["name"], "type": a["type"],
                "status": a["status"],
                "location": a["location"],
                "equipped_for": a["equipped_for"],
                "case_id": a["case_id"],
                "eta_min": (round(_remaining_min(state, a), 1)
                            if a["status"] in ("en_route_patient", "en_route_hospital") else None),
            }
            for a in state.ambulances.values()
        ],
        "hospitals": [
            {
                "id": h["id"], "name": h["name"], "level": h["level"],
                "ot_available": h["ot_available"], "ot_total": h["ot_total"],
                "ot_preparing": h["ot_prep_started"] is not None and h["ot_ready_at"] is None,
                "nicu_beds": h["nicu_beds"],
                "on_call_staff": sum(
                    1 for s in state.staff.values()
                    if s["hospital_id"] == h["id"] and s["status"] == "on_call"),
                "pre_alerted_cases": len(h["incoming_alerts"]),
            }
            for h in state.hospitals.values()
        ],
        "routes_status": [
            {"route_id": rid, "worst_condition": max(
                (seg["condition"] for seg in r["segments"]),
                key=lambda c: ["clear", "light", "moderate", "heavy", "blocked"].index(c))}
            for rid, r in state.routes.items()
        ],
        "recent_radio": recent_radio[-12:],
    }


def hospital_observation(state: WorldState, hospital_id: str,
                         recent_radio: List[str]) -> Optional[Dict[str, Any]]:
    h = state.hospitals.get(hospital_id)
    if h is None:
        return None
    inbound = []
    for cid, c in state.cases.items():
        if c.get("hospital_id") == hospital_id and c["status"] not in ("completed", "failed"):
            amb = state.ambulances.get(c.get("ambulance_id") or "")
            inbound.append({
                **_case_view(state, cid),
                "ambulance_status": amb["status"] if amb else None,
                "eta_hospital_min": (round(_remaining_min(state, amb), 1)
                                     if amb and amb["status"] == "en_route_hospital" else None),
            })
    staff = [
        {"id": s["id"], "name": s["name"], "specialization": s["specialization"],
         "status": s["status"]}
        for s in state.staff.values() if s["hospital_id"] == hospital_id
    ]
    bank = next((b for b in state.blood_banks.values() if b.get("hospital_id") == hospital_id), None)
    return {
        "role": "hospital",
        "hospital_id": hospital_id,
        "hospital_name": h["name"],
        "sim_time_min": round(state.sim_time, 1),
        "capacity": {
            "ot_available": h["ot_available"], "ot_total": h["ot_total"],
            "ot_preparing": h["ot_prep_started"] is not None and h["ot_ready_at"] is None,
            "nicu_beds": h["nicu_beds"],
            "receiving_case": h["receiving_case"],
        },
        "staff": staff,
        "blood_inventory": bank["inventory"] if bank else {},
        "incoming_cases": inbound,
        "recent_radio": recent_radio[-10:],
    }


def ambulance_observation(state: WorldState, ambulance_id: str,
                          recent_radio: List[str]) -> Optional[Dict[str, Any]]:
    a = state.ambulances.get(ambulance_id)
    if a is None:
        return None
    route_info = None
    if a["route_id"]:
        r = state.routes[a["route_id"]]
        segs = []
        for i, seg in enumerate(r["segments"]):
            segs.append({
                "segment_index": i + 1,
                "distance_km": seg["distance_km"],
                "condition": seg["condition"],
                "reason": seg.get("condition_reason", ""),
                "eta_this_segment_min": round(seg["duration_min"] * {
                    "clear": 1.0, "light": 1.2, "moderate": 1.5,
                    "heavy": 2.0, "blocked": 999}.get(seg["condition"], 1.0), 1),
            })
        alternates = [rid for rid, rr in state.routes.items()
                      if rid != a["route_id"]]
        route_info = {
            "current_route_id": a["route_id"],
            "segments_ahead": segs[min(a["seg_idx"], len(segs)):],
            "total_eta_min": round(_remaining_min(state, a), 1),
            "alternate_route_ids": alternates,
        }
    case_view = None
    if a["case_id"] and a["case_id"] in state.cases:
        cv = _case_view(state, a["case_id"])
        hosp = state.hospitals.get(a["hospital_id"] or "", {})
        cv["destination_hospital"] = {"id": a["hospital_id"], "name": hosp.get("name")}
        case_view = cv
    return {
        "role": "ambulance",
        "ambulance_id": ambulance_id,
        "unit_name": a["name"],
        "sim_time_min": round(state.sim_time, 1),
        "mission_status": a["status"],
        "assigned_case": case_view,
        "route": route_info,
        "recent_radio": recent_radio[-8:],
    }
