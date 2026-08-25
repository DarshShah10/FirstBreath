import axios from 'axios';
import type {
  DistressSignal,
  Simulation,
  SimulationState,
  SimulationResults,
  ActionableAnalysis,
  ResourceData
} from '../types';

const API_BASE = import.meta.env.VITE_API_URL || '/api/v1';

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Simulation APIs
export const createSimulation = async (config?: {
  simulation_speed?: number;
  mode?: string;
  max_concurrent_cases?: number;
}): Promise<{ simulation_id: string; status: string }> => {
  const response = await api.post('/simulations', config || {});
  return response.data;
};

export const listSimulations = async (): Promise<Simulation[]> => {
  const response = await api.get('/simulations');
  return response.data.simulations || [];
};

export const getSimulation = async (simulationId: string): Promise<{
  simulation: Simulation;
  simulation_state: SimulationState;
}> => {
  const response = await api.get(`/simulations/${simulationId}`);
  return response.data;
};

export const runSimulation = async (
  simulationId: string,
  config?: {
    duration_minutes?: number;
    max_steps?: number;
    engine?: 'agentic' | 'deterministic';
    seed?: string;
  }
): Promise<{ simulation_id: string; status: string }> => {
  const response = await api.post(`/simulations/${simulationId}/run`, config || {});
  return response.data;
};

export const pauseSimulation = async (simulationId: string) => {
  const response = await api.post(`/simulations/${simulationId}/pause`);
  return response.data;
};

export const resumeSimulation = async (simulationId: string) => {
  const response = await api.post(`/simulations/${simulationId}/resume`);
  return response.data;
};

export const stopSimulation = async (simulationId: string) => {
  const response = await api.post(`/simulations/${simulationId}/stop`);
  return response.data;
};

export const getSimulationResults = async (simulationId: string): Promise<SimulationResults> => {
  const response = await api.get(`/simulations/${simulationId}/results`);
  return response.data.results || response.data;
};

// Case APIs
export const addCase = async (
  simulationId: string,
  caseData: Partial<DistressSignal>
): Promise<{ case_id: string; status: string }> => {
  const response = await api.post(`/simulations/${simulationId}/cases`, caseData);
  return response.data;
};

export const listCases = async (simulationId: string) => {
  const response = await api.get(`/simulations/${simulationId}/cases`);
  return response.data;
};

// Intervention APIs
export const getInterventionAnalysis = async (
  simulationId: string,
  caseId: string,
  format: 'detailed' | 'brief' | 'markdown' | 'json' = 'detailed'
): Promise<{ analysis: ActionableAnalysis; report: string }> => {
  const response = await api.get(
    `/simulations/${simulationId}/interventions/${caseId}`,
    { params: { format } }
  );
  return response.data;
};

export const getCriticalInterventions = async (
  simulationId: string,
  caseId: string,
  count: number = 3
) => {
  const response = await api.get(
    `/simulations/${simulationId}/interventions/${caseId}/critical`,
    { params: { count } }
  );
  return response.data;
};

// Resource APIs
export const getResources = async (): Promise<ResourceData> => {
  const response = await api.get('/resources');
  return response.data;
};

export const getNearestResources = async (
  lat: number,
  lng: number,
  type: 'hospital' | 'ambulance' | 'all' = 'all'
) => {
  const response = await api.get('/resources/nearest', {
    params: { lat, lng, type },
  });
  return response.data;
};

// Health APIs
export const healthCheck = async () => {
  const response = await api.get('/health');
  return response.data;
};

export const getStatus = async () => {
  const response = await api.get('/status');
  return response.data;
};

// ── Agentic runtime APIs ────────────────────────────────────────────

export interface WorldSnapshot {
  simulation_id: string;
  sim_time: number;
  running: boolean;
  ambulances: Array<{
    id: string; name: string; status: string;
    location: { lat: number; lng: number };
    case_id: string | null; hospital_id: string | null;
    eta_min: number | null; reroute_count: number;
  }>;
  hospitals: Array<{
    id: string; name: string; level: string;
    location: { lat: number; lng: number };
    ot_total: number; ot_available: number; ot_reserved: number;
    ot_ready: boolean; nicu_beds: number;
    staff: Array<{ id: string; name: string; specialization: string; status: string }>;
    contact_phone: string;
  }>;
  cases: Array<{
    id: string; status: string; outcome: string | null;
    emergency_type: string; severity: string;
    location: { lat: number; lng: number; address?: string };
    patient: Record<string, unknown>;
    ambulance_id: string | null; hospital_id: string | null;
    deadline: number; minutes_left: number;
    timeline: Array<{ sim_time: number; note: string }>;
  }>;
  routes: Array<{
    id: string; name: string; worst_condition: string;
    from: { lat: number; lng: number }; to: { lat: number; lng: number };
    alternate_route_id: string | null;
  }>;
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

/** Live world snapshot for the Mission Control console. */
export const getWorldSnapshot = async (simulationId: string): Promise<WorldSnapshot> => {
  const response = await api.get(`/simulations/${simulationId}/snapshot`);
  return response.data.snapshot || response.data;
};

/** Incremental transcript fetch (events after a given id). */
export const getEvents = async (
  simulationId: string,
  afterId = 0,
  runId?: string
): Promise<{ run_id: string | null; events: TranscriptEvent[] }> => {
  const response = await api.get(`/simulations/${simulationId}/events`, {
    params: { after_id: afterId, ...(runId ? { run_id: runId } : {}) },
  });
  return response.data;
};

/** Run history from Supabase. */
export const getHistory = async (): Promise<Record<string, any>[]> => {
  const response = await api.get('/history');
  return response.data.simulations || [];
};

export default api;
