"""
LangGraph agentic runtime.

One compiled graph execution = one simulation run.
Loop: init -> world_tick -> route_attention -(Send fan-out)-> thinker*
      -> apply_actions -> flush_radio -> world_tick -> ...

Agents PROPOSE decisions; `apply_actions` applies them through the world's
validated action schema. LLM brains degrade to deterministic rule-brains on
any failure â€” a run never stalls because an API died.
"""

from __future__ import annotations

import json
import logging
from typing import Annotated, Any, Dict, List, Literal, Optional

from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, Send
from typing_extensions import TypedDict

from ..world.state import WorldState
from ..world.physics import tick
from ..world.actions import apply_action
from ..world.events import make_event, RADIO, RUN_COMPLETED_EV
from ..world.engine import WorldEngine
from ..world.actions import DecisionList
from ..world.observation import (
    dispatcher_observation, hospital_observation, ambulance_observation,
)
from .llm import BrainRouter
from .skills import DISPATCHER_SKILL, HOSPITAL_SKILL, AMBULANCE_SKILL

logger = logging.getLogger('firstbreath.graph')

DT = 0.5  # sim-minutes per tick


# ---------------------------------------------------------------------------
# State schema (TypedDict so reducers are honored)
# ---------------------------------------------------------------------------

def _append(left, right):
    return (left or []) + (right or [])


def _sum(left, right):
    return (left or 0) + (right or 0)


def _radio_window(left, right):
    return ((left or []) + (right or []))[-60:]


class GraphState(TypedDict, total=False):
    # config / identity
    run_id: str
    mode: Literal["llm", "stub"]
    seed: str
    horizon_minutes: float
    registry: Optional[Dict[str, Any]]
    signals: List[Dict[str, Any]]
    city_conditions: Dict[str, Any]

    # authoritative simulation state (serialized WorldState)
    world: Dict[str, Any]

    # accumulators
    event_log: Annotated[List[Dict[str, Any]], _append]
    tick_events: List[Dict[str, Any]]
    radio: Annotated[List[str], _radio_window]
    proposals: Annotated[List[Dict[str, Any]], _append]
    decision_log: Annotated[List[Dict[str, Any]], _append]
    radio_flushed_count: int
    llm_calls: Annotated[int, _sum]


# ---------------------------------------------------------------------------
# Rule-based fallback brains (always available)
# ---------------------------------------------------------------------------

def _capable(amb: Dict, emergency_type: Optional[str]) -> bool:
    need = {
        "fetal_distress": ["neonatal_resuscitation", "emergency_delivery"],
        "maternal_hemorrhage": ["advanced_life_support"],
        "eclampsia": ["advanced_life_support"],
        "cord_prolapse": ["emergency_delivery"],
    }.get(emergency_type or "", ["emergency_delivery"])
    have = set(amb.get("equipped_for", []))
    if not need:
        return True
    return any(n in have for n in need)


def _dist(a: Dict, b: Dict) -> float:
    try:
        return abs(a.get("lat", 0) - b.get("lat", 0)) + abs(a.get("lng", 0) - b.get("lng", 0))
    except Exception:
        return 999.0


def stub_dispatcher_brain(obs: Dict[str, Any]) -> DecisionList:
    decisions, radios = [], []
    available = [a for a in obs["ambulances"] if a["status"] == "available"]
    open_cases = sorted(obs["open_cases"], key=lambda c: c["minutes_left_in_window"])
    for case in open_cases:
        if case["status"] != "queued":
            continue
        capable = [a for a in available if _capable(a, case.get("emergency_type"))]
        pool = capable or available
        if not pool:
            continue
        amb = min(pool, key=lambda a: _dist(a["location"], case["location"] or {}))
        hosp = max(obs["hospitals"],
                   key=lambda h: h["ot_available"] * 10 + h["nicu_beds"])
        decisions.append({
            "kind": "dispatch_ambulance",
            "case_id": case["case_id"], "ambulance_id": amb["id"],
            "hospital_id": hosp["id"],
            "rationale": f"nearest {'capable ' if capable else ''}unit; "
                         f"{case['minutes_left_in_window']}m left in window",
        })
        decisions.append({
            "kind": "pre_alert_hospital",
            "case_id": case["case_id"], "hospital_id": hosp["id"],
            "rationale": "early prep per golden hour doctrine",
        })
        available = [a for a in available if a["id"] != amb["id"]]
        radios.append(f"{case['case_id']}: {amb['name']} dispatched, "
                      f"{hosp['name']} pre-alerted.")
    return DecisionList(decisions=decisions, radio_messages=radios,
                        reasoning_summary="rule brain: nearest-capable dispatch")


def stub_hospital_brain(obs: Dict[str, Any]) -> DecisionList:
    decisions, radios = [], []
    cap = obs["capacity"]
    paged_specs = {s["specialization"] for s in obs["staff"]
                   if s["status"] in ("paged", "arrived")}
    for case in obs["incoming_cases"]:
        if not cap["ot_preparing"] and cap["ot_available"] > 0 \
                and case["status"] in ("transporting", "en_route_patient"):
            decisions.append({
                "kind": "prepare_ot", "hospital_id": obs["hospital_id"],
                "case_id": case["case_id"],
                "rationale": f"inbound ETA {case.get('eta_hospital_min', '?')}m",
            })
            radios.append(f"{obs['hospital_name']}: OT prepping for {case['case_id']}.")
        for spec in ("obstetrician", "anesthesiologist"):
            if spec not in paged_specs:
                decisions.append({
                    "kind": "page_staff", "hospital_id": obs["hospital_id"],
                    "specialization": spec, "case_id": case["case_id"],
                    "rationale": "standing order on inbound",
                })
        complications = (case.get("patient") or {}).get("complications") or []
        if any("hemorrhage" in str(c).lower() for c in complications):
            decisions.append({
                "kind": "request_blood", "hospital_id": obs["hospital_id"],
                "case_id": case["case_id"],
                "blood_type": (case.get("patient") or {}).get("blood_type", "O_positive"),
                "units": 2, "rationale": "hemorrhage protocol",
            })
    return DecisionList(decisions=decisions, radio_messages=radios,
                        reasoning_summary="rule brain: standing orders")


def stub_ambulance_brain(obs: Dict[str, Any]) -> DecisionList:
    route = obs.get("route")
    if not route:
        return DecisionList(reasoning_summary="no active leg")
    ahead = route.get("segments_ahead", [])
    if any(s["condition"] == "blocked" for s in ahead):
        alts = route.get("alternate_route_ids", [])
        if alts:
            current = set(route.get("current_route_id", ""))
            alt = next((x for x in alts if x not in current), alts[0])
            return DecisionList(
                decisions=[{"kind": "reroute_ambulance",
                            "ambulance_id": obs["ambulance_id"],
                            "route_id": alt,
                            "rationale": "blocked segment ahead"}],
                radio_messages=["Route blocked â€” diverting to alternate."],
                reasoning_summary="blocked segment â†’ reroute")
    if any(s["condition"] == "heavy" for s in ahead):
        return DecisionList(
            decisions=[],
            radio_messages=["Heavy traffic ahead, expect delay."],
            reasoning_summary="reported delay")
    return DecisionList(reasoning_summary="clear ahead")


# ---------------------------------------------------------------------------
# LLM brains
# ---------------------------------------------------------------------------

_router_cache: Dict[str, BrainRouter] = {}


def _router() -> BrainRouter:
    key = "t0.55"
    if key not in _router_cache:
        _router_cache[key] = BrainRouter(temperature=0.55)
    return _router_cache[key]


ROLE_META = {
    "dispatcher": ("EMS dispatch coordinator", DISPATCHER_SKILL),
    "hospital": ("receiving hospital coordinator", HOSPITAL_SKILL),
    "ambulance": ("ambulance unit commander", AMBULANCE_SKILL),
}


def llm_brain(role: str, agent_id: str, obs: Dict[str, Any]) -> Optional[DecisionList]:
    from langchain_core.messages import SystemMessage, HumanMessage
    title, skill = ROLE_META[role]
    router = _router()
    system = (
        f"You are the {title} inside FirstBreath, a live emergency-response simulation "
        f"(obstetric golden hour). You perceive structured JSON and propose concrete "
        f"actions through the decision schema. Be decisive, terse, operational.\n\n{skill}"
    )
    human = (
        f"CURRENT SITUATION at T+{obs.get('sim_time_min', 0)} minutes:\n"
        f"{json.dumps(obs, default=str, ensure_ascii=False)}\n\n"
        f"Propose your next actions. If nothing needs doing right now, emit one noop."
    )
    result, model_used = router.invoke_structured(
        DecisionList, [SystemMessage(content=system), HumanMessage(content=human)])
    if result is None:
        return None
    logger.info(f"brain[{role}/{agent_id}] via {model_used}")
    return result


def get_brain_decision(mode: str, role: str, agent_id: Optional[str],
                       world_dict: Dict, radio: List[str]):
    """Returns (DecisionList, brain_name). Never raises."""
    ws = WorldState.from_dict(world_dict)

    if role == "dispatcher":
        obs = dispatcher_observation(ws, radio)
        stub = stub_dispatcher_brain
    elif role == "hospital":
        obs = hospital_observation(ws, agent_id, radio)
        stub = lambda o: (stub_hospital_brain(o) if o else DecisionList())
    else:
        obs = ambulance_observation(ws, agent_id, radio)
        stub = lambda o: (stub_ambulance_brain(o) if o else DecisionList())

    if obs is None:
        return DecisionList(), "none"

    if mode == "llm":
        try:
            result = llm_brain(role, agent_id or role, obs)
            if result is not None:
                return result, "llm"
        except Exception as e:
            logger.warning(f"LLM brain failure ({role}/{agent_id}): {e}")
    return stub(obs), "stub"


# ---------------------------------------------------------------------------
# Graph nodes
# ---------------------------------------------------------------------------

def init_node(state: GraphState) -> GraphState:
    eng = WorldEngine(
        simulation_id=state["run_id"],
        registry=state.get("registry"),
        distress_signals=state.get("signals") or [],
        seed=state.get("seed", "golden-hour"),
        horizon_minutes=state.get("horizon_minutes", 90.0),
        city_conditions=state.get("city_conditions") or {},
    )
    events = eng.start()
    for d in (state.get("city_conditions") or {}).get("preset_disruptions", []):
        r = eng.apply("scenario", {"kind": "update_traffic", **d})
        events += r.events
    return {
        "world": eng.state.to_dict(),
        "event_log": events,
        "tick_events": events,
        "radio_flushed_count": 0,
        "llm_calls": 0,
    }


def world_tick(state: GraphState) -> GraphState:
    ws = WorldState.from_dict(state["world"])
    events = tick(ws, state["run_id"], dt=state.get("dt", DT))
    out: GraphState = {"world": ws.to_dict(),
                       "tick_events": events}
    if ws.is_terminal():
        outcomes = {cid: c["outcome"] for cid, c in ws.cases.items()}
        wins = sum(1 for o in outcomes.values() if o and "success" in str(o))
        out["tick_events"].append(make_event(
            state["run_id"], RUN_COMPLETED_EV, ws.sim_time, agent_type="system",
            payload={"description": f"Run complete at T+{ws.sim_time:.0f}m â€” "
                                    f"{wins}/{len(outcomes)} delivered within care",
                     "outcomes": outcomes},
        ))
    return out


def check_terminal(state: GraphState) -> Literal["route_attention", "__end__"]:
    ws = WorldState.from_dict(state["world"])
    return "__end__" if ws.is_terminal() else "route_attention"


def route_attention(state: GraphState):
    """
    Conditional edge from world_tick: terminal check + event-triggered
    wake-up. Only thinkers whose situation changed get invoked.
    Returns Send fan-out, 'world_tick' to continue, or END.
    """
    ws = WorldState.from_dict(state["world"])
    if ws.is_terminal():
        return "__end__"
    events = state.get("tick_events") or []

    wakes: Dict[tuple, List[str]] = {}

    def wake(role, agent_id=None, why=""):
        wakes.setdefault((role, agent_id), []).append(why)

    etypes = {e["event_type"] for e in events}
    unassigned = any(c["status"] == "queued" for c in ws.cases.values())

    if unassigned or "case_queued" in etypes or "amb_available" in etypes:
        wake("dispatcher", None, "triage")

    if "traffic_changed" in etypes:
        affected = {e["payload"].get("route_id") for e in events
                    if e["event_type"] == "traffic_changed"}
        for aid, a in ws.ambulances.items():
            if a["status"] == "en_route_patient" and a.get("route_id") in affected:
                wake("ambulance", aid, "route conditions changed")

    for e in events:
        if e["event_type"] == "transport_started":
            cid = e["payload"].get("case_id")
            c = ws.cases.get(cid or "")
            if c and c.get("hospital_id"):
                wake("hospital", c["hospital_id"], "inbound transport")

    if not wakes:
        return "world_tick"

    return [
        Send("thinker", {
            "role": role,
            "agent_id": agent_id,
            "wake_reasons": sorted(set(reasons)),
            "mode": state.get("mode", "stub"),
            "world": state["world"],
            "radio_snapshot": list(state.get("radio", []))[-12:],
        })
        for (role, agent_id), reasons in wakes.items()
    ]


def thinker(payload: Dict[str, Any]) -> GraphState:
    """One agent-brain invocation (parallel across the Send fan-out)."""
    role, agent_id = payload["role"], payload.get("agent_id")
    decision, brain_used = get_brain_decision(
        payload.get("mode", "stub"), role, agent_id,
        payload["world"], payload.get("radio_snapshot", []))

    speaker = agent_id or role
    record = {
        "speaker": speaker,
        "role": role,
        "agent_id": agent_id,
        "brain": brain_used,
        "wake_reasons": payload.get("wake_reasons", []),
        "reasoning": decision.reasoning_summary,
        "decisions": [d.model_dump() if hasattr(d, "model_dump") else d
                      for d in decision.decisions],
    }
    radio_out = [f"{speaker}: {m}" for m in decision.radio_messages]
    return {
        "proposals": [record],
        "decision_log": [record],
        "radio": radio_out,
        "llm_calls": 1 if brain_used == "llm" else 0,
    }


def apply_actions_node(state: GraphState) -> GraphState:
    """The world disposes: validate + apply every proposal sequentially."""
    ws = WorldState.from_dict(state["world"])
    new_events: List[Dict[str, Any]] = []

    for prop in state.get("proposals", []):
        speaker = prop.get("speaker", prop.get("role", "agent"))
        for dec in prop.get("decisions", []):
            result = apply_action(ws, state["run_id"], speaker, dec)
            new_events += result.events
        # persist agent reasoning + decisions as transcript events
        new_events.append(make_event(
            state["run_id"], "agent_decision", ws.sim_time,
            agent_id=speaker, agent_type=prop.get("role", "system"),
            payload={
                "description": prop.get("reasoning") or "",
                "brain": prop.get("brain"),
                "wake_reasons": prop.get("wake_reasons", []),
                "proposed": prop.get("decisions", []),
            },
        ))
    # radio lines become transcript events too
    radio = state.get("radio", [])
    flushed = state.get("radio_flushed_count", 0)
    fresh = radio[flushed:]
    for line in fresh:
        new_events.append(make_event(
            state["run_id"], RADIO, ws.sim_time,
            agent_id=line.split(":", 1)[0] if ":" in line else "unknown",
            agent_type="system", payload={"description": line},
        ))

    return {
        "world": ws.to_dict(),
        "event_log": new_events,
        "tick_events": [],
        "proposals": [],
        "radio_flushed_count": len(radio),
    }


# ---------------------------------------------------------------------------
# Assembly
# ---------------------------------------------------------------------------

def build_run_graph(checkpointer=None):
    builder = StateGraph(GraphState)

    builder.add_node("init", init_node)
    builder.add_node("world_tick", world_tick)
    builder.add_node("thinker", thinker)
    builder.add_node("apply_actions", apply_actions_node)

    builder.add_edge(START, "init")
    builder.add_edge("init", "world_tick")
    # single conditional router: END | continue ticking | Send(thinker) fan-out
    builder.add_conditional_edges(
        "world_tick", route_attention,
        {"world_tick": "world_tick", "__end__": END, "thinker": "thinker"})
    builder.add_edge("thinker", "apply_actions")
    builder.add_edge("apply_actions", "world_tick")

    return builder.compile(checkpointer=checkpointer)


