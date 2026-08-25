"""Determinism contract: same seed + same actions => identical world."""

from app.world.engine import WorldEngine
from tests.conftest import SIGNAL, REGISTRY


def _scripted_run(seed):
    eng = WorldEngine("run_x", registry=REGISTRY, distress_signals=[dict(SIGNAL)], seed=seed)
    events = []
    events += eng.start()
    from app.world.actions import DispatchAmbulance
    # deterministic scripted decisions
    r = eng.apply("dispatcher", DispatchAmbulance(
        case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    assert r.ok, r.detail
    while not eng.is_terminal():
        events += eng.step(dt=0.5)
        if not any(a["status"] != "available" for a in eng.state.ambulances.values()) \
           and eng.state.cases["case_test"]["status"] == "queued":
            eng.apply("dispatcher", DispatchAmbulance(
                case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    return eng.state.timeline_hash(), [e["event_type"] for e in events]


def test_same_seed_same_timeline():
    h1, e1 = _scripted_run("seed-42")
    h2, e2 = _scripted_run("seed-42")
    assert h1 == h2
    assert e1 == e2


def test_world_runs_are_isolated():
    """Two engines in one process must never share state (legacy singleton bug)."""
    a = WorldEngine("run_a", registry=REGISTRY, distress_signals=[dict(SIGNAL)], seed="s1")
    b = WorldEngine("run_b", registry=REGISTRY, distress_signals=[dict(SIGNAL)], seed="s1")
    from app.world.actions import DispatchAmbulance
    ra = a.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    rb = b.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    assert ra.ok and rb.ok  # same ambulance usable in both worlds
    a.step()
    assert b.state.ambulances["amb_1"]["status"] != a.state.ambulances["amb_1"]


def test_no_wall_clock_in_state():
    import datetime
    WorldEngine("run_c", registry=REGISTRY, distress_signals=[dict(SIGNAL)], seed="s")
    blob = repr(WorldEngine("run_d", registry=REGISTRY, distress_signals=[dict(SIGNAL)], seed="s").state.to_dict())
    assert str(datetime.date.today()) not in blob
