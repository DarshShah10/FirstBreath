"""
Event helpers — every observable thing that happens in the world becomes
one structured dict. These are the rows that land in the Supabase `events`
table and the raw material for reports.
"""

from typing import Any, Dict, List, Optional

# Event types
RUN_STARTED = "run_started"
CASE_QUEUED_EV = "case_queued"
DISPATCH = "dispatch"                       # ambulance assigned to case
PRE_ALERT = "pre_alert"
AMB_DEPARTED = "amb_departed"
ARRIVED_PATIENT = "arrived_patient"
STABILIZED = "stabilized"
TRANSPORT_STARTED = "transport_started"
ARRIVED_HOSPITAL = "arrived_hospital"
CASE_COMPLETED_EV = "case_completed"
OT_RESERVED = "ot_reserved"
OT_READY = "ot_ready"
STAFF_PAGED_EV = "staff_paged"
STAFF_ARRIVED_EV = "staff_arrived"
BLOOD_REQUESTED = "blood_requested"
BLOOD_READY = "blood_ready"
REROUTE = "reroute"
TRAFFIC_CHANGED = "traffic_changed"
ACTION_REJECTED = "action_rejected"
RADIO = "radio"
AGENT_DECISION = "agent_decision"
TICK = "tick"
RUN_COMPLETED_EV = "run_completed"

AGENT_TYPES = {
    "dispatcher": "dispatcher",
    "hospital": "hospital",
    "ambulance": "ambulance",
    "world": "world",
    "system": "system",
}


def make_event(
    run_id: str,
    event_type: str,
    sim_time: float,
    agent_id: Optional[str] = None,
    agent_type: str = "world",
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "run_id": run_id,
        "event_type": event_type,
        "sim_time": round(float(sim_time), 3),
        "agent_id": agent_id,
        "agent_type": agent_type,
        "payload": payload or {},
    }


def events_to_text(events: List[Dict[str, Any]]) -> str:
    """Human-readable rendering for logs / demo output."""
    lines = []
    for e in events:
        t = e.get("sim_time", 0)
        who = e.get("agent_id") or e.get("agent_type") or "world"
        p = e.get("payload", {})
        desc = p.get("description") or p.get("reason") or ""
        lines.append(f"T+{t:6.1f}  [{e.get('event_type','?'):<18}] {who}: {desc}")
    return "\n".join(lines)
