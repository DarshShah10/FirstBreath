"""Action validation matrix — rejections must be explicit and safe."""

import pytest
from app.world.engine import WorldEngine
from app.world.actions import (
    DispatchAmbulance, PreAlertHospital, RerouteAmbulance,
    RequestBlood, PageStaff, UpdateTraffic, NoOp, DecisionList,
)
from tests.conftest import SIGNAL


def test_double_dispatch_rejected():
    eng = WorldEngine("r", registry=None, distress_signals=[dict(SIGNAL)], seed="s") \
        if False else WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    a1 = eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    assert a1.ok
    a2 = eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_2", hospital_id="h1"))
    assert not a2.ok  # case already dispatched
    assert any(e["event_type"] == "action_rejected" for e in a2.events)


def test_unknown_unit_rejected():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    r = eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_99", hospital_id="h1"))
    assert not r.ok


def test_reroute_requires_en_route():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    r = eng.apply("d", RerouteAmbulance(ambulance_id="amb_1", route_id="r_alt"))
    assert not r.ok  # ambulance is available, not en route


def test_reroute_preserves_progress():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    eng.apply("d", DispatchAmbulance(case_id="case_test", ambulance_id="amb_1", hospital_id="h1"))
    # depart + travel a bit
    for _ in range(4):
        eng.step(dt=0.5)
    amb = eng.state.ambulances["amb_1"]
    assert amb["status"] == "en_route_patient"
    before_eta = _eta(eng)
    res = eng.apply("radio", RerouteAmbulance(ambulance_id="amb_1", route_id="r_alt",
                                              rationale="main blocked"))
    assert res.ok
    after_eta = _eta(eng)
    # longer route => remaining ETA should grow but stay finite (< legacy 999 nonsense)
    assert 0 < after_eta < 30
    assert amb["reroute_count"] == 1


def test_blood_request_normalizes_type():
    eng = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    r = eng.apply("hosp", RequestBlood(case_id="case_test", hospital_id="h1",
                                       blood_type="O-negative", units=2))
    assert r.ok
    bank = eng.state.blood_banks["bb_1"]
    assert any(k.startswith("o_negative") for k in bank["reservations"]["case_test"])


def test_page_staff_with_jitter_is_deterministic():
    e1 = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    e2 = WorldEngine("r", registry=_reg(), distress_signals=[dict(SIGNAL)], seed="s")
    r1 = e1.apply("hosp", PageStaff(hospital_id="h1", specialization="obstetrician", case_id="case_test"))
    r2 = e2.apply("hosp", PageStaff(hospital_id="h1", specialization="obstetrician", case_id="case_test"))
    s1 = e1.state.staff["s_ob_1"]
    s2 = e2.state.staff["s_ob_1"]
    assert r1.ok == r2.ok
    assert s1["arrives_at"] == s2["arrives_at"]


def test_decision_list_accepts_plain_dicts():
    dl = DecisionList(**{
        "decisions": [
            {"kind": "dispatch_ambulance", "case_id": "c", "ambulance_id": "a", "hospital_id": "h"},
            {"kind": "noop", "rationale": "waiting"},
        ],
        "radio_messages": ["Control, unit one rolling."],
        "reasoning_summary": "test",
    })
    assert dl.decisions[0].case_id == "c"


def _reg():
    from tests.conftest import REGISTRY
    import copy
    return copy.deepcopy(REGISTRY)


def _eta(eng):
    from app.world.physics import _remaining_min
    return _remaining_min(eng.state, eng.state.ambulances["amb_1"])
