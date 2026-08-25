"""
Festival conflict demo â€” the canonical FirstBreath scenario.

Two simultaneous emergencies during Ganesh Chaturthi:
  1. fetal distress (critical, 20-min window)
  2. maternal hemorrhage (severe, 30-min window, +2 min later)
Main route degraded by festival procession.

Usage:
  uv run python scripts/run_agentic_demo.py --mode stub
  uv run python scripts/run_agentic_demo.py --mode llm --seed festival-7
"""

import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from app.agents.graph import build_run_graph  # noqa: E402
from app.world.events import events_to_text  # noqa: E402


FESTIVAL_SIGNALS = [
    {
        "case_id": "case_fetal",
        "severity": "critical",
        "emergency_type": "fetal_distress",
        "location": {"lat": 28.6100, "lng": 77.2000,
                     "address": "Ward 3 Bed 4, Sector 12"},
        "patient": {"gestational_age_weeks": 36, "blood_type": "O_negative",
                    "complications": ["late_decelerations"],
                    "previous_cesarean": False},
        "time_window_minutes": 20,
        "source": "firstbreath",
        "notes": "FirstBreath CTG alert",
    },
    {
        "case_id": "case_hemorrhage",
        "severity": "severe",
        "emergency_type": "maternal_hemorrhage",
        "location": {"lat": 28.6120, "lng": 77.2020,
                     "address": "FC Road, Sector 13"},
        "patient": {"gestational_age_weeks": 38, "blood_type": "B_positive",
                    "complications": ["postpartum_hemorrhage_risk"],
                    "previous_cesarean": True},
        "time_window_minutes": 30,
        "t_offset_min": 2.0,
        "source": "emergency_call",
        "notes": "108 call",
    },
]

FESTIVAL_CONDITIONS = {
    "random_incidents": False,
    "preset_disruptions": [
        {"route_id": "route_patient_central_main", "condition": "heavy",
         "reason": "Ganesh procession blocking main road", "duration_min": 45},
    ],
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["stub", "llm"], default="stub")
    ap.add_argument("--seed", default="festival-42")
    args = ap.parse_args()

    graph = build_run_graph()
    config = {
        "configurable": {"thread_id": f"demo-{args.seed}"},
        "recursion_limit": 5000,
    }
    inputs = {
        "run_id": f"demo_{args.mode}_{int(time.time())}",
        "mode": args.mode,
        "seed": args.seed,
        "signals": FESTIVAL_SIGNALS,
        "city_conditions": FESTIVAL_CONDITIONS,
        "horizon_minutes": 60.0,
    }

    print("=" * 70)
    print(f" FIRSTBREATH AGENTIC RUN â€” mode={args.mode} seed={args.seed}")
    print("=" * 70)

    t0 = time.time()
    final_state = None
    llm_calls = 0

    for chunk in graph.stream(inputs, config, stream_mode="updates"):
        for node, update in chunk.items():
            if not isinstance(update, dict):
                continue
            llm_calls += update.get("llm_calls", 0) or 0
            for ev in update.get("fresh_events") or []:
                et = ev.get("event_type")
                if et in ("tick",):
                    continue
                t = ev.get("sim_time", 0)
                who = (ev.get("agent_id") or ev.get("agent_type") or "?")
                desc = (ev.get("payload") or {}).get("description", "")
                marker = {
                    "radio": "\033[36mRADIO \033[0m",
                    "agent_decision": "\033[35mBRAIN \033[0m",
                    "dispatch": "\033[33mACT  \033[0m",
                    "case_completed": "\033[32mDONE \033[0m",
                    "case_failed": "\033[31mFAIL \033[0m",
                    "action_rejected": "\033[31mREJ  \033[0m",
                }.get(et, "EVT  ")
                print(f"T+{t:6.1f} {marker} {who:<22.22} {desc[:100]}")

            if "world" in update and node == "world_tick":
                final_state = update["world"]

    elapsed = time.time() - t0
    ws = final_state or {}
    print("=" * 70)
    print(f" RUN COMPLETE in {elapsed:.1f}s real time | sim T+{ws.get('sim_time', 0):.1f}m "
          f"| LLM calls: {llm_calls}")
    print("-" * 70)
    for cid, c in (ws.get("cases") or {}).items():
        outcome = c.get("outcome") or c.get("status")
        mark = "OK " if outcome and "success" in str(outcome) else "!! "
        print(f"  {mark}{cid:<18} status={c.get('status'):<12} outcome={outcome}")
    print("=" * 70)


if __name__ == "__main__":
    main()

