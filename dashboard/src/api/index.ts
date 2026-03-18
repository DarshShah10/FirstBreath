import axios from 'axios';
import type {
  DistressSignal,
  Simulation,
  SimulationState,
  SimulationResults,
  ActionableAnalysis,
  ResourceData
} from '../types';

const API_BASE = '/api/v1';

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
  config?: { duration_minutes?: number; max_steps?: number }
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

export default api;
