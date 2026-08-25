"""Physics correctness — the things the legacy engine got backwards."""

from app.world.engine import WorldEngine
from app.world.actions import DispatchAmbulance, UpdateTraffic, PageStaff
from tests.conftest import SIGNAL, REGISTRY
import copy


def _reg():
    return copy.deepcopy(REGISTRY)


def _run_until(eng, pred, max_min=60):
    while not pred() and eng.state.sim_time < max_min:
        eng.step(dt=0.5)
    assert pred(), f"condition never met by T+{eng.state.sim_time}"


def test_distance_and_traffic_affect_travel_time():
    """1.5km clear vs blocked route: blocked must be slower (legacy: identical)."""
    slow = WorldEngine("r1", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    fast = WorldEngine("r2", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")

    for eng in (slow, fast):
        eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
        for _ in range(4):  # depart
            eng.step(0.5)

    slow.apply("city", UpdateTraffic(route_id="r_main", condition="heavy",
                                     reason="procession", duration_min=30))
    t_slow_start = slow.state.sim_time
    _run_until(slow, lambda: slow.state.ambulances["amb_1"]["status"] == "at_patient", 40)
    t_slow = slow.state.sim_time - t_slow_start

    t_fast_start = fast.state.sim_time
    _run_until(fast, lambda: fast.state.ambulances["amb_1"]["status"] == "at_patient", 40)
    t_fast = fast.state.sim_time - t_fast_start

    assert t_slow > t_fast * 1.3, f"blocked travel {t_slow} not slower than clear {t_fast}"


def test_case_completes_within_window():
    """The flagship regression: cases MUST complete (legacy hung forever)."""
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="win")
    eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    _run_until(eng, lambda: eng.state.cases["case_test"]["status"] == "completed", 45)
    case = eng.state.cases["case_test"]
    assert case["outcome"] in ("success", "late_success")
    assert case["completed_at"] is not None


def test_full_lifecycle_events_emitted():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="ev")
    events = []
    events += eng.apply("d", DispatchAmbulance(case_id="case_test",
                                               ambulance_id="amb_1", hospital_id="h1")).events
    while eng.state.cases["case_test"]["status"] != "completed":
        events += eng.step(0.5)
        if eng.state.cases["case_test"]["status"] == "queued":
            break
    kinds = {e["event_type"] for e in events}
    for expected in ("dispatch", "amb_departed", "arrived_patient",
                     "transport_started", "arrived_hospital", "case_completed"):
        assert expected in kinds, f"missing {expected}; got {kinds}"


def test_unassigned_case_fails_at_deadline():
    sig = dict(SIGNAL)
    sig["time_window_minutes"] = 5
    eng = WorldEngine("r", registry=_reg(), distress_signals=[sig], seed="fail")
    while eng.state.cases["case_test"]["status"] == "queued" and eng.state.sim_time < 10:
        eng.step(0.5)
    assert eng.state.cases["case_test"]["status"] == "failed"
    assert eng.state.cases["case_test"]["outcome"] == "failed_unassigned"


def test_ot_prep_timer():
    from app.world.state import OT_PREP_TIME
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="ot")
    hosp = eng.state.hospitals["h1"]
    hosp["ot_prep_started"] = eng.state.sim_time + 1.0  # will start at T+1
    t0 = eng.state.sim_time
    while hosp["ot_ready_at"] is None and eng.state.sim_time < OT_PREP_TIME + 5:
        eng.step(0.5)
    elapsed = eng.state.sim_time - t0
    assert hosp["ot_ready_at"] is not None
    assert abs(elapsed - (OT_PREP_TIME + 1.0)) < 1.0


def test_staff_arrive_after_paging():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="staff")
    r = eng.apply("hosp", PageStaff(hospital_id="h1", specialization="obstetrician",
                                    case_id="case_test"))
    assert r.ok
    sid = r.events[0]["payload"]["staff_ids"][0]
    _run_until(eng, lambda: eng.state.staff[sid]["status"] == "arrived", 20)
