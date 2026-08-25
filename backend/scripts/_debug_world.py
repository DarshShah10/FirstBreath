"""Quick world-level debug (no LangGraph) — is physics terminating?"""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "../../.env"))

from app.world.engine import WorldEngine
from app.world.actions import DispatchAmbulance

eng = WorldEngine('dbg', distress_signals=[{
    'case_id': 'c1', 'severity': 'critical', 'emergency_type': 'fetal_distress',
    'location': {'lat': 28.61, 'lng': 77.2},
    'patient': {'gestational_age_weeks': 36, 'blood_type': 'O_negative'},
    'time_window_minutes': 20}], seed='s', horizon_minutes=5.0)
eng.start()
r = eng.apply('d', DispatchAmbulance(case_id='c1', ambulance_id='amb_001',
                                     hospital_id='hospital_central'))
print('dispatch:', r.ok, r.detail)
for i in range(40):
    evs = eng.step(0.5)
    a = eng.state.ambulances['amb_001']
    interesting = [e['event_type'] for e in evs if e['event_type'] != 'tick']
    if interesting or i < 8:
        print(f"T+{eng.state.sim_time:5.1f} amb={a['status']:<17} seg={a['seg_idx']} "
              f"prog={a['seg_progress']:.2f} route={str(a['route_id'])[:28]:<28} {interesting}")
    if eng.state.is_terminal():
        print('TERMINAL at T+', eng.state.sim_time)
        break
else:
    print('NOT TERMINAL after loop; sim_time=', eng.state.sim_time)
