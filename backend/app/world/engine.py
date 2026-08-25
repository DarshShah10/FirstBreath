"""
WorldEngine — thin wrapper binding state + physics + action application.
This is what LangGraph nodes and the API talk to. One instance per run;
no shared global state anywhere.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import yaml

from .actions import ActionResult, apply_action
from .physics import tick
from .state import WorldState, build_world

_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../config"))
DEFAULT_REGISTRY_PATH = os.path.join(_CONFIG_DIR, "emergency_resources.yaml")


def load_registry(path: Optional[str] = None) -> Dict[str, Any]:
    p = path or DEFAULT_REGISTRY_PATH
    with open(p, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class WorldEngine:
    """Owns one WorldState; applies actions and advances time."""

    def __init__(self, simulation_id: str, registry: Optional[Dict[str, Any]] = None,
                 distress_signals: Optional[List[Dict[str, Any]]] = None,
                 seed: str = "golden-hour", horizon_minutes: float = 90.0,
                 city_conditions: Optional[Dict[str, Any]] = None):
        self.run_id = simulation_id
        reg = registry or load_registry()
        # normalize YAML keys to world schema keys
        norm = {
            "hospitals": [
                {**h, "hospital_id": h.get("hospital_id")} for h in reg.get("hospitals", [])
            ],
            "ambulances": reg.get("ambulances", []),
            "staff": reg.get("staff", []),
            "blood_banks": reg.get("blood_banks", []),
            "routes": reg.get("routes", []),
        }
        self.state: WorldState = build_world(
            simulation_id=simulation_id,
            registry_dict=norm,
            distress_signals=distress_signals or [],
            seed=seed,
            horizon_minutes=horizon_minutes,
            city_conditions=city_conditions,
        )

    # -- lifecycle -----------------------------------------------------------

    def start(self) -> List[Dict[str, Any]]:
        from .events import make_event, RUN_STARTED, CASE_QUEUED_EV
        ev = [make_event(
            self.run_id, RUN_STARTED, 0.0, agent_type="system",
            payload={"description": f"Run started (seed={self.state.seed}, "
                                    f"{len(self.state.cases)} case(s))",
                     "seed": self.state.seed},
        )]
        for cid, case in self.state.cases.items():
            sig = case["signal"]
            ev.append(make_event(
                self.run_id, CASE_QUEUED_EV, case["t0"], agent_type="system",
                payload={
                    "description": f"{cid}: {sig.get('emergency_type','other')} / "
                                   f"severity {sig.get('severity','?')} — window "
                                   f"{case['deadline']:.0f} min",
                    "case_id": cid,
                    "emergency_type": sig.get("emergency_type"),
                    "severity": sig.get("severity"),
                    "location": sig.get("location"),
                    "patient": sig.get("patient"),
                    "deadline_min": case["deadline"],
                    "window_min": sig.get("time_window_minutes", 30),
                },
            ))
        return ev

    def step(self, dt: float = 0.5) -> List[Dict[str, Any]]:
        return tick(self.state, self.run_id, dt)

    def apply(self, agent_id: str, action: Any) -> ActionResult:
        return apply_action(self.state, self.run_id, agent_id, action)

    def is_terminal(self) -> bool:
        return self.state.is_terminal()

    def summary(self) -> Dict[str, Any]:
        st = self.state
        return {
            "simulation_id": self.run_id,
            "sim_time": round(st.sim_time, 1),
            "tick_count": st.tick_count,
            "cases": {
                cid: {
                    "status": c["status"], "outcome": c["outcome"],
                    "ambulance_id": c["ambulance_id"], "hospital_id": c["hospital_id"],
                    "deadline": c["deadline"],
                    "minutes_left": round(c["deadline"] - st.sim_time, 1)
                                    if c["status"] not in ("completed", "failed") else 0,
                } for cid, c in st.cases.items()
            },
            "ambulances": {
                aid: {"status": a["status"], "location": a["location"],
                      "case_id": a["case_id"]} for aid, a in st.ambulances.items()
            },
            "hospitals": {
                hid: {"ot_available": h["ot_available"], "ot_reserved": h["ot_reserved"],
                      "incoming_alerts": len(h["incoming_alerts"])}
                for hid, h in st.hospitals.items()
            },
        }

    def snapshot_for_client(self) -> Dict[str, Any]:
        """Rich live snapshot for the dashboard (map/graph/vitals)."""
        st = self.state
        ambulances = []
        for aid, a in st.ambulances.items():
            eta = None
            if a["status"] in ("en_route_patient", "en_route_hospital"):
                from .physics import _remaining_min
                eta = round(_remaining_min(st, a), 1)
            ambulances.append({
                "id": aid, "name": a["name"], "status": a["status"],
                "location": a["location"], "case_id": a["case_id"],
                "hospital_id": a["hospital_id"], "eta_min": eta,
                "reroute_count": a["reroute_count"],
            })
        hospitals = []
        for hid, h in st.hospitals.items():
            staff_here = [s for s in st.staff.values() if s["hospital_id"] == hid]
            hospitals.append({
                "id": hid, "name": h["name"], "level": h["level"],
                "location": h["location"],
                "ot_total": h["ot_total"], "ot_available": h["ot_available"],
                "ot_reserved": h["ot_reserved"], "ot_ready": h["ot_ready_at"] is not None,
                "nicu_beds": h["nicu_beds"],
                "staff": [{"id": s["id"], "name": s["name"],
                           "specialization": s["specialization"], "status": s["status"]}
                          for s in staff_here],
                "contact_phone": h.get("contact_phone", ""),
            })
        cases = []
        for cid, c in st.cases.items():
            cases.append({
                "id": cid,
                "status": c["status"], "outcome": c["outcome"],
                "emergency_type": c["signal"].get("emergency_type"),
                "severity": c["signal"].get("severity"),
                "location": c["signal"].get("location"),
                "patient": c["signal"].get("patient"),
                "ambulance_id": c["ambulance_id"], "hospital_id": c["hospital_id"],
                "deadline": c["deadline"],
                "minutes_left": round(max(0.0, c["deadline"] - st.sim_time), 1),
                "timeline": c["timeline"],
            })
        routes = []
        for rid, r in st.routes.items():
            worst = "clear"
            rank = ["clear", "light", "moderate", "heavy", "blocked"]
            for seg in r["segments"]:
                if rank.index(seg["condition"]) > rank.index(worst):
                    worst = seg["condition"]
            routes.append({"id": rid, "name": r["name"], "worst_condition": worst,
                           "from": r["from"], "to": r["to"],
                           "alternate_route_id": r.get("alternate_route_id")})
        return {
            "simulation_id": self.run_id,
            "sim_time": round(st.sim_time, 1),
            "running": not st.is_terminal(),
            "ambulances": ambulances,
            "hospitals": hospitals,
            "cases": cases,
            "routes": routes,
        }

    def d3_graph(self) -> Dict[str, Any]:
        """Response-chain graph for D3 force layout, built from LIVE state."""
        nodes, links = [], []
        st = self.state

        def add(node_id: str, name: str, group: str, status: str = "", **attrs):
            nodes.append({"id": node_id, "name": name, "group": group,
                          "status": status, **attrs})

        def link(src: str, dst: str, ltype: str, status: str = ""):
            links.append({"source": src, "target": dst, "type": ltype, "status": status})

        add("city", "Golden Hour Net", "system", "active")
        for cid, c in st.cases.items():
            add(cid, cid.replace("case_", "CASE "), "patient", c["status"])
            link("city", cid, "monitors")
            amb = st.ambulances.get(c.get("ambulance_id") or "")
            hosp = st.hospitals.get(c.get("hospital_id") or "")
            if amb:
                if amb["id"] not in [n["id"] for n in nodes]:
                    add(amb["id"], amb["name"], "ambulance", amb["status"],
                        location=amb["location"], eta=self._amb_eta(amb))
                link("ems_dispatch", amb["id"], "dispatches", amb["status"])
                link(amb["id"], cid, "responds", amb["status"])
            if hosp:
                if hosp["id"] not in [n["id"] for n in nodes]:
                    ot_status = "ready" if hosp["ot_ready_at"] else (
                        "preparing" if hosp["ot_prep_started"] else "standby")
                    add(hosp["id"], hosp["name"], "hospital",
                        ot_status, ot=f'{hosp["ot_available"]}/{hosp["ot_total"]}')
                if amb:
                    link(amb["id"], hosp["id"], "transports", c["status"])
                for s in [s for s in st.staff.values() if s["hospital_id"] == hosp["id"]
                          and s["status"] in ("paged", "arrived")]:
                    if s["id"] not in [n["id"] for n in nodes]:
                        add(s["id"], s["name"], "staff", s["status"],
                            specialization=s["specialization"])
                    link(s["id"], hosp["id"], "prepares", s["status"])
        if "ems_dispatch" not in [n["id"] for n in nodes]:
            add("ems_dispatch", "EMS Dispatch", "dispatch", "active")

        # traffic overlay
        for rid, r in st.routes.items():
            blocked = any(seg["condition"] == "blocked" for seg in r["segments"])
            heavy = any(seg["condition"] in ("heavy", "moderate") for seg in r["segments"])
            if blocked or heavy:
                grp = "traffic"
                add(f"traffic_{rid}", r["name"], grp,
                    "blocked" if blocked else "heavy")
                targets = [n for n in nodes if n["group"] in ("ambulance",)]
                for tgt in targets[:2]:
                    link(f"traffic_{rid}", tgt["id"], "blocks", "blocked" if blocked else "slow")

        return {"nodes": nodes, "links": links}

    def _amb_eta(self, amb: Dict[str, Any]) -> Optional[float]:
        if amb["status"] in ("en_route_patient", "en_route_hospital"):
            from .physics import _remaining_min
            return round(_remaining_min(self.state, amb), 1)
        return None
