"""
World model state — the single source of truth for a simulation run.

Plain-dict-friendly dataclasses so LangGraph checkpoints serialize natively.
No globals, no singletons, no wall-clock in logic. Determinism via
counter-based seeding (see SeededRandom).
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Statuses / enums (string constants for serialization friendliness)
# ---------------------------------------------------------------------------

AMB_AVAILABLE = "available"
AMB_DISPATCHED = "dispatched"
AMB_TO_PATIENT = "en_route_patient"
AMB_AT_PATIENT = "at_patient"
AMB_STABILIZING = "stabilizing"
AMB_TO_HOSPITAL = "en_route_hospital"
AMB_AT_HOSPITAL = "at_hospital"
AMB_RETURNING = "returning"

CASE_QUEUED = "queued"
CASE_DISPATCHED = "dispatched"          # ambulance en route to patient
CASE_TRANSPORTING = "transporting"      # patient aboard
CASE_COMPLETED = "completed"
CASE_FAILED = "failed"

STAFF_ON_CALL = "on_call"
STAFF_PAGED = "paged"
STAFF_ARRIVED = "arrived"
STAFF_BUSY = "busy"

ROUTE_CLEAR = "clear"
ROUTE_LIGHT = "light"
ROUTE_MODERATE = "moderate"
ROUTE_HEAVY = "heavy"
ROUTE_BLOCKED = "blocked"

CONDITION_MULTIPLIERS = {
    ROUTE_CLEAR: 1.0,
    ROUTE_LIGHT: 1.2,
    ROUTE_MODERATE: 1.5,
    ROUTE_HEAVY: 2.0,
    ROUTE_BLOCKED: 999.0,
}

# Clinical timings (minutes) — extracted from legacy engine, now explicit
DEPART_TIME = 1.0
STABILIZE_TIME = 5.0
HANDOVER_TIME = 2.0
OT_PREP_TIME = 10.0
BLOOD_PREP_TIME = 5.0
PAGE_RESPONSE_BASE = 5.0        # minutes before paged staff arrives
SPEED_KMH = 40.0                # off-route / fallback speed


# ---------------------------------------------------------------------------
# Deterministic randomness — counter-based so checkpoint/resume cannot
# change the stream. draw(seed, tick, purpose) is a pure function.
# ---------------------------------------------------------------------------

def draw_float(seed: str, tick: int, purpose: str, lo: float, hi: float) -> float:
    h = hashlib.sha256(f"{seed}:{tick}:{purpose}".encode()).hexdigest()
    unit = int(h[:12], 16) / float(16 ** 12)
    return lo + unit * (hi - lo)


def draw_choice(seed: str, tick: int, purpose: str, options: List[str]) -> str:
    return options[int(draw_float(seed, tick, purpose, 0, len(options))) % len(options)]


def rng_for(seed: str, tick: int, purpose: str) -> random.Random:
    """Full Random object when many draws are needed at once."""
    return random.Random(int(hashlib.sha256(f"{seed}:{tick}:{purpose}".encode()).hexdigest()[:16], 16))


# ---------------------------------------------------------------------------
# State containers
# ---------------------------------------------------------------------------

@dataclass
class WorldState:
    simulation_id: str
    seed: str
    sim_time: float = 0.0                 # simulated minutes since T0
    horizon_minutes: float = 90.0
    tick_count: int = 0

    ambulances: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    hospitals: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    blood_banks: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    routes: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cases: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    staff: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    # scenario flavor: festival effects, weather etc. applied at init
    city_conditions: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "simulation_id": self.simulation_id,
            "seed": self.seed,
            "sim_time": round(self.sim_time, 3),
            "horizon_minutes": self.horizon_minutes,
            "tick_count": self.tick_count,
            "ambulances": self.ambulances,
            "hospitals": self.hospitals,
            "blood_banks": self.blood_banks,
            "routes": self.routes,
            "cases": self.cases,
            "staff": self.staff,
            "city_conditions": self.city_conditions,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WorldState":
        return cls(
            simulation_id=d["simulation_id"],
            seed=d["seed"],
            sim_time=d.get("sim_time", 0.0),
            horizon_minutes=d.get("horizon_minutes", 90.0),
            tick_count=d.get("tick_count", 0),
            ambulances=d.get("ambulances", {}),
            hospitals=d.get("hospitals", {}),
            blood_banks=d.get("blood_banks", {}),
            routes=d.get("routes", {}),
            cases=d.get("cases", {}),
            staff=d.get("staff", {}),
            city_conditions=d.get("city_conditions", {}),
        )

    # -- convenience accessors ---------------------------------------------

    def route_duration(self, route_id: str, from_segment: int = 0) -> float:
        """Remaining effective duration (min) of a route from a segment index."""
        route = self.routes[route_id]
        total = 0.0
        for seg in route["segments"][from_segment:]:
            mult = CONDITION_MULTIPLIERS.get(seg["condition"], 1.0)
            total += seg["duration_min"] * mult
        return total

    def route_blocked(self, route_id: str) -> bool:
        return any(s["condition"] == ROUTE_BLOCKED for s in self.routes[route_id]["segments"])

    def open_cases(self) -> List[Dict[str, Any]]:
        return [c for c in self.cases.values()
                if c["status"] not in (CASE_COMPLETED, CASE_FAILED)]

    def is_terminal(self) -> bool:
        if self.sim_time >= self.horizon_minutes:
            return True
        return len(self.open_cases()) == 0 and self.tick_count > 0

    def timeline_hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Construction from registry + signals
# ---------------------------------------------------------------------------

def build_world(
    simulation_id: str,
    registry_dict: Dict[str, Any],
    distress_signals: List[Dict[str, Any]],
    seed: str = "golden-hour",
    horizon_minutes: float = 90.0,
    city_conditions: Optional[Dict[str, Any]] = None,
) -> WorldState:
    """
    Build initial world state.

    registry_dict shape mirrors backend/config/emergency_resources.yaml:
      {hospitals: [...], ambulances: [...], staff: [...], blood_banks: [...], routes: [...]}
    distress_signals are plain dicts matching DistressSignal.to_dict().
    """
    st = WorldState(simulation_id=simulation_id, seed=seed, horizon_minutes=horizon_minutes)
    st.city_conditions = dict(city_conditions or {})

    for h in registry_dict.get("hospitals", []):
        hid = h["hospital_id"]
        st.hospitals[hid] = {
            "id": hid,
            "name": h.get("name", hid),
            "level": h.get("level", "secondary"),
            "location": {"lat": h["location"]["lat"], "lng": h["location"]["lng"], "address": h["location"].get("address", "")},
            "ot_total": int(h.get("ot_count", 2)),
            "ot_available": int(h.get("ot_count", 2)),
            "ot_reserved": 0,
            "ot_ready_at": None,
            "ot_prep_started": None,
            "nicu_beds": int(h.get("nicu_beds", 0)),
            "obgyn_beds": int(h.get("obgyn_beds", 4)),
            "capabilities": list(h.get("capabilities", [])),
            "contact_phone": h.get("contact_phone", ""),
            "incoming_alerts": [],       # case_ids pre-alerted
            "receiving_case": None,
        }

    for a in registry_dict.get("ambulances", []):
        aid = a["ambulance_id"]
        loc = {"lat": a["base_location"]["lat"], "lng": a["base_location"]["lng"]}
        st.ambulances[aid] = {
            "id": aid,
            "name": a.get("name", aid),
            "type": a.get("type", "BLS"),
            "location": dict(loc),
            "base_location": dict(loc),
            "equipped_for": list(a.get("equipped_for", [])),
            "has_paramedic": bool(a.get("has_paramedic", False)),
            "status": AMB_AVAILABLE,
            "case_id": None,
            "patient_id": None,
            "hospital_id": None,
            "route_id": None,
            "leg": None,                  # "to_patient" | "to_hospital"
            "seg_idx": 0,
            "seg_progress": 0.0,          # 0..1 within current segment
            "depart_at": None,
            "stabilize_until": None,
            "handover_until": None,
            "reroute_count": 0,
        }

    for s in registry_dict.get("staff", []):
        sid = s["staff_id"]
        st.staff[sid] = {
            "id": sid,
            "name": s.get("name", sid),
            "specialization": s.get("specialization"),
            "hospital_id": s.get("hospital_id"),
            "status": STAFF_ON_CALL if s.get("on_call") else STAFF_BUSY,
            "response_eta_min": float(s.get("response_time_minutes", PAGE_RESPONSE_BASE)),
            "paged_at": None,
            "arrives_at": None,
        }

    for b in registry_dict.get("blood_banks", []):
        bid = b["blood_bank_id"]
        inv = {}
        for k, v in (b.get("inventory") or {}).items():
            inv[k.lower()] = int(v)
        st.blood_banks[bid] = {
            "id": bid,
            "name": b.get("name", bid),
            "hospital_id": b.get("hospital_id"),
            "inventory": inv,
            "reservations": {},           # case_id -> {type: units}
            "fulfilling_until": {},       # case_id -> ready_at
        }

    for r in registry_dict.get("routes", []):
        rid = r["route_id"]
        segs = r.get("segments") or [{
            "distance_km": float(r.get("distance_km", 5.0)),
            "duration_min": float(r.get("typical_duration_minutes", 15.0)),
            "condition": r.get("current_status", ROUTE_CLEAR),
        }]
        st.routes[rid] = {
            "id": rid,
            "name": r.get("name", rid),
            "from": {"lat": r["from_location"]["lat"], "lng": r["from_location"]["lng"]},
            "to": {"lat": r["to_location"]["lat"], "lng": r["to_location"]["lng"]},
            "segments": [
                {
                    "distance_km": float(s["distance_km"]),
                    "duration_min": float(s["duration_min"]),
                    "condition": s.get("condition", ROUTE_CLEAR),
                    "condition_reason": s.get("condition_reason", ""),
                    "condition_until": s.get("condition_until"),  # abs sim-time or None
                }
                for s in segs
            ],
            "alternate_route_id": r.get("alternate_route_id"),
        }

    t0_default = 0.0
    for i, sig in enumerate(distress_signals):
        cid = sig.get("case_id") or f"case_{i+1:02d}"
        st.cases[cid] = {
            "case_id": cid,
            "signal": sig,
            "t0": t0_default + float(sig.get("t_offset_min", 0.0)),
            "status": CASE_QUEUED,
            "ambulance_id": None,
            "hospital_id": None,
            "deadline": t0_default + float(sig.get("time_window_minutes", 30)),
            "completed_at": None,
            "outcome": None,               # success | late_success | failed
            "timeline": [],                # [{sim_time, note}]
        }

    return st
