/**
 * Mock replay engine — the canonical archived run (festival conflict, Noida).
 * Drives the Home scroll narrative and serves as the offline fallback for
 * Live Simulation when the backend is cold/unreachable.
 */

import type { TranscriptEvent, WorldSnapshot } from "./api";

export const REPLAY_DURATION_MIN = 30;

export const REPLAY_EVENTS: Array<Omit<TranscriptEvent, "run_id">> = [
  { id: 1, event_type: "case_queued", sim_time: 0.0, agent_id: null, agent_type: "system", payload: { description: "case_fetal: fetal_distress / severity critical — window 20 min", case_id: "case_fetal" } },
  { id: 2, event_type: "traffic_changed", sim_time: 0.0, agent_id: "scenario", agent_type: "world", payload: { description: "Main arterial → HEAVY — Ganesh procession blocking Sector 12 route", route_id: "route_patient_central_main", condition: "heavy" } },
  { id: 3, event_type: "agent_decision", sim_time: 0.5, agent_id: "dispatcher", agent_type: "dispatcher", payload: { description: "Two competing scenes. Ward-3 CTG is severity 9 with a 20-minute window — it outranks the hemorrhage call by four minutes of margin. Committing both units.", brain: "llm" } },
  { id: 4, event_type: "dispatch", sim_time: 0.5, agent_id: "dispatcher", agent_type: "dispatcher", payload: { description: "Unit 001 dispatched to case_fetal → Central Maternity Hospital", ambulance_id: "amb_001" } },
  { id: 5, event_type: "dispatch", sim_time: 0.5, agent_id: "dispatcher", agent_type: "dispatcher", payload: { description: "Mobile ICU dispatched to case_hemorrhage → Central Maternity Hospital", ambulance_id: "amb_004" } },
  { id: 6, event_type: "radio", sim_time: 0.6, agent_id: "amb_001", agent_type: "ambulance", payload: { description: "Control, Unit 001 rolling. Procession visible on the main — requesting alternate if it holds." } },
  { id: 7, event_type: "pre_alert", sim_time: 0.8, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "Central Maternity pre-alerted for both inbound cases" } },
  { id: 8, event_type: "agent_decision", sim_time: 1.2, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "Two obstetric inbounds inside ten minutes of each other. Paging both OBs now — anesthesia can wait for triage.", brain: "llm" } },
  { id: 9, event_type: "staff_paged", sim_time: 1.4, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "Dr. Priya Sharma (OB) + Dr. Rajesh Kumar (anesthesia) paged" } },
  { id: 10, event_type: "ot_reserved", sim_time: 2.0, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "OT-2 reserved and prepping for case_fetal — ready ~T+12" } },
  { id: 11, event_type: "radio", sim_time: 6.0, agent_id: "amb_004", agent_type: "ambulance", payload: { description: "Mobile ICU: hemorrhage patient loaded concerns — B-positive, two units standing by on board." } },
  { id: 12, event_type: "request_blood", sim_time: 6.2, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "4u B-positive cross-matched against District stock as buffer" } },
  { id: 13, event_type: "blood_ready", sim_time: 11.5, agent_id: "blood_bank_central", agent_type: "world", payload: { description: "Blood cross-matched & ready for case_hemorrhage (4u)" } },
  { id: 14, event_type: "arrived_patient", sim_time: 11.5, agent_id: "amb_001", agent_type: "ambulance", payload: { description: "Unit 001 on scene — Ward 3 Bed 4. Decels persisting." } },
  { id: 15, event_type: "arrived_patient", sim_time: 11.8, agent_id: "amb_004", agent_type: "ambulance", payload: { description: "Mobile ICU on scene at FC Road." } },
  { id: 16, event_type: "stabilized", sim_time: 16.8, agent_id: "amb_001", agent_type: "ambulance", payload: { description: "Unit 001 stabilized; transporting to Central Maternity" } },
  { id: 17, event_type: "transport_started", sim_time: 17.0, agent_id: "amb_001", agent_type: "ambulance", payload: { description: "amb_001 transporting — ETA hospital 9 min via procession traffic", eta_hospital_min: 9 } },
  { id: 18, event_type: "traffic_changed", sim_time: 18.5, agent_id: "city_conditions", agent_type: "world", payload: { description: "Main arterial easing to MODERATE as procession clears", condition: "moderate" } },
  { id: 19, event_type: "radio", sim_time: 19.0, agent_id: "hospital_central", agent_type: "hospital", payload: { description: "Central to all units: OT hot at T+23, blood on shelf. Bring them straight in." } },
  { id: 20, event_type: "ot_ready", sim_time: 23.0, agent_id: "hospital_central", agent_type: "world", payload: { description: "Central Maternity OT ready" } },
  { id: 21, event_type: "arrived_hospital", sim_time: 26.5, agent_id: "amb_001", agent_type: "ambulance", payload: { description: "Unit 001 at Central Maternity — handover to OB team" } },
  { id: 22, event_type: "arrived_hospital", sim_time: 27.0, agent_id: "amb_004", agent_type: "ambulance", payload: { description: "Mobile ICU at Central Maternity" } },
  { id: 23, event_type: "case_completed", sim_time: 28.5, agent_id: null, agent_type: "world", payload: { description: "case_hemorrhage SUCCESS — window held with 3 minutes spare", outcome: "success" } },
  { id: 24, event_type: "case_completed", sim_time: 28.5, agent_id: null, agent_type: "world", payload: { description: "case_fetal LATE — delivered 8.5 min past window; OT was ready, traffic was not", outcome: "late_success" } },
  { id: 25, event_type: "run_completed", sim_time: 28.5, agent_id: null, agent_type: "system", payload: { description: "Run complete — 2/2 delivered, 1 inside the window", outcomes: { case_fetal: "late_success", case_hemorrhage: "success" } } },
];

/* ── snapshot synthesis ────────────────────────────────────────────────
   Piecewise waypoints per ambulance; everything else keyed off time.   */

const HOSPITALS: WorldSnapshot["hospitals"] = [
  {
    id: "hospital_central", name: "Central Maternity Hospital", level: "tertiary",
    location: { lat: 28.6139, lng: 77.209 },
    ot_total: 4, ot_available: 3, ot_reserved: 1, ot_ready: false, nicu_beds: 20,
    staff: [
      { id: "staff_obgyn_001", name: "Dr. Priya Sharma", specialization: "obstetrician", status: "on_call" },
      { id: "staff_anesth_001", name: "Dr. Rajesh Kumar", specialization: "anesthesiologist", status: "on_call" },
    ],
    contact_phone: "+91-120-222-3333",
  },
  {
    id: "hospital_district", name: "District General Hospital", level: "secondary",
    location: { lat: 28.6239, lng: 77.219 },
    ot_total: 2, ot_available: 2, ot_reserved: 0, ot_ready: false, nicu_beds: 8,
    staff: [],
    contact_phone: "+91-120-222-4444",
  },
];

const PATIENT_FETAL = { lat: 28.61, lng: 77.2 };
const PATIENT_HEM = { lat: 28.612, lng: 77.202 };
const CENTRAL = { lat: 28.6139, lng: 77.209 };

function lerp(a: number, b: number, t: number) { return a + (b - a) * Math.min(1, Math.max(0, t)); }

function posAlong(from: { lat: number; lng: number }, to: { lat: number; lng: number }, t: number) {
  return { lat: lerp(from.lat, to.lat, t), lng: lerp(from.lng, to.lng, t) };
}

function ambFetalPos(t: number) {
  if (t < 1.5) return { lat: 28.6089, lng: 77.204 };
  if (t < 11.5) return posAlong({ lat: 28.6089, lng: 77.204 }, PATIENT_FETAL, (t - 1.5) / 10);
  if (t < 17) return PATIENT_FETAL;
  if (t < 26.5) return posAlong(PATIENT_FETAL, CENTRAL, (t - 17) / 9.5);
  return CENTRAL;
}
function ambHemPos(t: number) {
  const base = { lat: 28.6139, lng: 77.209 };
  if (t < 1.5) return base;
  if (t < 11.8) return posAlong(base, PATIENT_HEM, (t - 1.5) / 10.3);
  if (t < 17.2) return PATIENT_HEM;
  if (t < 27) return posAlong(PATIENT_HEM, CENTRAL, (t - 17.2) / 9.8);
  return CENTRAL;
}

export function replaySnapshot(simTime: number): WorldSnapshot {
  const t = simTime;
  const fetalStatus = t < 1.5 ? "queued" : t < 11.5 ? "en_route_patient" : t < 17 ? "on_scene" : t < 26.5 ? "transporting" : "completed";
  const hemStatus = t < 1.5 ? "queued" : t < 11.8 ? "en_route_patient" : t < 17.2 ? "on_scene" : t < 27 ? "transporting" : "completed";

  return {
    simulation_id: "replay_festival",
    sim_time: t,
    running: t < REPLAY_DURATION_MIN,
    runtime_status: t >= REPLAY_DURATION_MIN ? "completed" : "running",
    ambulances: [
      { id: "amb_001", name: "Ambulance Unit 001", status: t < 1.5 ? "available" : t < 11.5 ? "en_route_patient" : t < 17 ? "at_patient" : t < 26.5 ? "en_route_hospital" : t < 29 ? "at_hospital" : "returning", location: ambFetalPos(t), case_id: t >= 1.5 && t < 29 ? "case_fetal" : null, hospital_id: t >= 17 ? "hospital_central" : null, eta_min: t >= 17 && t < 26.5 ? Math.round((26.5 - t) * 10) / 10 : null, reroute_count: 0 },
      { id: "amb_004", name: "Mobile ICU Unit", status: t < 1.5 ? "available" : t < 11.8 ? "en_route_patient" : t < 17.2 ? "at_patient" : t < 27 ? "en_route_hospital" : t < 29.5 ? "at_hospital" : "returning", location: ambHemPos(t), case_id: t >= 1.5 && t < 29.5 ? "case_hemorrhage" : null, hospital_id: t >= 17.2 ? "hospital_central" : null, eta_min: t >= 17.2 && t < 27 ? Math.round((27 - t) * 10) / 10 : null, reroute_count: 0 },
      { id: "amb_002", name: "Ambulance Unit 002", status: "available", location: { lat: 28.6189, lng: 77.214 }, case_id: null, hospital_id: null, eta_min: null, reroute_count: 0 },
      { id: "amb_003", name: "Ambulance Unit 003", status: "available", location: { lat: 28.6289, lng: 77.224 }, case_id: null, hospital_id: null, eta_min: null, reroute_count: 0 },
    ],
    hospitals: HOSPITALS.map((h) => {
      if (h.id !== "hospital_central") return h;
      const reserved = t >= 2;
      const ready = t >= 23;
      const staffStatus = (id: string) => (t >= 6 ? (t >= 12 ? "arrived" : "paged") : "on_call");
      return {
        ...h,
        ot_reserved: reserved ? 1 : 0,
        ot_available: reserved ? 3 : 4,
        ot_ready: ready,
        staff: h.staff.map((s) => ({ ...s, status: staffStatus(s.id) })),
      };
    }),
    cases: [
      {
        id: "case_fetal", status: fetalStatus,
        outcome: t >= 28.5 ? "late_success" : null,
        emergency_type: "fetal_distress", severity: "critical",
        location: { ...PATIENT_FETAL, address: "Ward 3 Bed 4, Sector 12" },
        patient: { gestational_age_weeks: 36, blood_type: "O_negative" },
        ambulance_id: t >= 0.5 ? "amb_001" : null,
        hospital_id: t >= 0.5 ? "hospital_central" : null,
        deadline: 20,
        minutes_left: Math.max(0, 20 - t),
        timeline: [],
      },
      {
        id: "case_hemorrhage", status: hemStatus,
        outcome: t >= 28.5 ? "success" : null,
        emergency_type: "maternal_hemorrhage", severity: "severe",
        location: { ...PATIENT_HEM, address: "FC Road, Sector 13" },
        patient: { gestational_age_weeks: 38, blood_type: "B_positive" },
        ambulance_id: t >= 0.5 ? "amb_004" : null,
        hospital_id: t >= 0.5 ? "hospital_central" : null,
        deadline: 30,
        minutes_left: Math.max(0, 30 - t),
        timeline: [],
      },
    ],
    routes: [
      { id: "route_patient_central_main", name: "Sector 12 Arterial", worst_condition: t < 18.5 ? "heavy" : t < 21 ? "moderate" : "light", from: { lat: 28.61, lng: 77.2 }, to: { lat: 28.6139, lng: 77.209 }, alternate_route_id: "route_patient_central_alt" },
      { id: "route_patient_central_alt", name: "Ring Bypass", worst_condition: "clear", from: { lat: 28.61, lng: 77.2 }, to: { lat: 28.6139, lng: 77.209 }, alternate_route_id: null },
      { id: "route_patient_district", name: "District Road", worst_condition: "clear", from: { lat: 28.61, lng: 77.2 }, to: { lat: 28.6239, lng: 77.219 }, alternate_route_id: null },
    ],
  };
}

/** Events visible up to `simTime`, exactly-once. */
export function replayEventsUpTo(simTime: number): TranscriptEvent[] {
  return REPLAY_EVENTS.filter((e) => e.sim_time <= simTime);
}
