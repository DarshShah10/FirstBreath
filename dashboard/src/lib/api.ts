/**
 * Typed FirstBreath API client.
 * Every call is honest: it resolves with backend data or throws ApiError —
 * callers decide whether to degrade to the mock replay (lib/mock.ts).
 */

export const API_BASE: string =
  import.meta.env.VITE_API_URL || "/api/v1";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new ApiError(res.status, body?.error || res.statusText);
  return body as T;
}

/* ── domain types (mirrors backend app/world snapshot shapes) ──────── */

export interface AmbulanceState {
  id: string; name: string; status: string;
  location: { lat: number; lng: number };
  case_id: string | null; hospital_id: string | null;
  eta_min: number | null; reroute_count: number;
}
export interface StaffState {
  id: string; name: string; specialization: string; status: string;
}
export interface HospitalState {
  id: string; name: string; level: string;
  location: { lat: number; lng: number };
  ot_total: number; ot_available: number; ot_reserved: number;
  ot_ready: boolean; nicu_beds: number;
  staff: StaffState[];
  contact_phone: string;
}
export interface CaseState {
  id: string; status: string; outcome: string | null;
  emergency_type: string; severity: string;
  location: { lat: number; lng: number; address?: string };
  patient: Record<string, unknown>;
  ambulance_id: string | null; hospital_id: string | null;
  deadline: number; minutes_left: number;
  timeline: Array<{ sim_time: number; note: string }>;
}
export interface RouteState {
  id: string; name: string; worst_condition: string;
  from: { lat: number; lng: number }; to: { lat: number; lng: number };
  alternate_route_id: string | null;
}
export interface WorldSnapshot {
  simulation_id: string;
  sim_time: number;
  running: boolean;
  runtime_status?: string;
  ambulances: AmbulanceState[];
  hospitals: HospitalState[];
  cases: CaseState[];
  routes: RouteState[];
}

export interface TranscriptEvent {
  id?: number;
  run_id?: string;
  event_type: string;
  sim_time: number;
  agent_id: string | null;
  agent_type: string;
  payload: Record<string, any>;
}

export interface RuntimeStatus {
  simulation_id: string; status: string; mode: string;
  sim_time: number; event_count: number; error?: string | null;
}

/* ── lifecycle ──────────────────────────────────────────────────────── */

export function createSimulation(config?: Record<string, unknown>) {
  return req<{ simulation_id: string; status: string }>("/simulations", {
    method: "POST",
    body: JSON.stringify(config ?? {}),
  });
}

export function addCase(simulationId: string, signal: Record<string, unknown>) {
  return req<{ case_id: string; status: string }>(
    `/simulations/${simulationId}/cases`,
    { method: "POST", body: JSON.stringify(signal) }
  );
}

export function runSimulation(
  simulationId: string,
  config: { duration_minutes?: number; engine?: "agentic" | "deterministic"; seed?: string; mode?: string } = {}
) {
  return req<{ status: string; error?: string }>(
    `/simulations/${simulationId}/run`,
    { method: "POST", body: JSON.stringify(config) }
  );
}

export const pauseSimulation = (id: string) =>
  req<{ status: string }>(`/simulations/${id}/pause`, { method: "POST" });
export const resumeSimulation = (id: string) =>
  req<{ status: string }>(`/simulations/${id}/resume`, { method: "POST" });
export const stopSimulation = (id: string) =>
  req<{ status: string }>(`/simulations/${id}/stop`, { method: "POST" });

/* ── telemetry ──────────────────────────────────────────────────────── */

export async function getSnapshot(id: string): Promise<WorldSnapshot> {
  const data = await req<{ success: boolean; snapshot?: WorldSnapshot; error?: string }>(
    `/simulations/${id}/snapshot`
  );
  if (!data.snapshot) throw new ApiError(404, data.error || "no run");
  return data.snapshot;
}

export async function getEvents(id: string, afterId = 0): Promise<TranscriptEvent[]> {
  const data = await req<{ events: TranscriptEvent[] }>(
    `/simulations/${id}/events?after_id=${afterId}`
  );
  return data.events ?? [];
}

export function getRuntime(id: string): Promise<RuntimeStatus> {
  return req<RuntimeStatus>(`/simulations/${id}/runtime`);
}

export function getResults(id: string): Promise<Record<string, any>> {
  return req<{ results: Record<string, any> }>(`/simulations/${id}/results`).then((d) => d.results);
}

export function getHistory(): Promise<Array<Record<string, any>>> {
  return req<{ simulations: Array<Record<string, any>> }>("/history").then(
    (d) => d.simulations ?? []
  );
}
