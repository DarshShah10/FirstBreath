"""Trace graph super-steps to find the non-progressing loop."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from app.agents.graph import build_run_graph

g = build_run_graph()
cfg = {'configurable': {'thread_id': 'dbg'}, 'recursion_limit': 60}
inputs = {'run_id': 'dbg1', 'mode': 'stub', 'seed': 's', 'horizon_minutes': 5.0,
          'signals': [{'case_id': 'c1', 'severity': 'critical',
                       'emergency_type': 'fetal_distress',
                       'location': {'lat': 28.61, 'lng': 77.2},
                       'patient': {'gestational_age_weeks': 36, 'blood_type': 'O_negative'},
                       'time_window_minutes': 20}]}
n = 0
try:
    for chunk in g.stream(inputs, cfg, stream_mode='updates'):
        n += 1
        for node, upd in chunk.items():
            if isinstance(upd, dict):
                w = upd.get('world') or {}
                te = len(upd.get('tick_events') or [])
                print(f"{n:3d} {node:<14} sim={w.get('sim_time','-'):>5} "
                      f"tick_events={te} keys={sorted(k for k in upd if k != 'world')}")
            else:
                print(f"{n:3d} {node} -> {type(upd).__name__}")
except Exception as e:
    print('STOPPED:', type(e).__name__, str(e)[:100])
