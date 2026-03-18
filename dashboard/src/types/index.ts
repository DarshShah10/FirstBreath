// Emergency Response Simulation Types

export interface Location {
  lat: number;
  lng: number;
  address: string;
  district?: string;
}

export interface Patient {
  gestational_age_weeks: number;
  blood_type: string;
  complications: string[];
  previous_cesarean: boolean;
  multiple_gestation: boolean;
  maternal_age?: number;
  maternal_conditions?: string[];
}

export interface DistressSignal {
  case_id: string;
  severity: 'critical' | 'severe' | 'moderate' | 'low';
  emergency_type: string;
  location: Location;
  patient: Patient;
  time_window_minutes: number;
  preferred_hospital_id?: string;
  transport_mode: string;
  caller_info?: string;
  notes?: string;
  source: string;
  created_at: string;
}

export interface Hospital {
  hospital_id: string;
  name: string;
  level: string;
  location: Location;
  obgyn_beds: number;
  nicu_beds: number;
  ot_count: number;
  on_call_obgyn: number;
  on_call_anesthesiologist: number;
  transfer_time_minutes: number;
  blood_bank_status: string;
  status: string;
  capabilities: string[];
}

export interface Ambulance {
  ambulance_id: string;
  name: string;
  base_location: Location;
  status: string;
  equipped_for: string[];
  crew_count: number;
  has_paramedic: boolean;
  response_time_to_location?: number;
}

export interface TransportRoute {
  route_id: string;
  from_location: Location;
  to_location: Location;
  distance_km: number;
  typical_duration_minutes: number;
  traffic_multiplier: number;
  current_status: string;
}

export interface Simulation {
  id: string;
  status: 'created' | 'running' | 'paused' | 'completed' | 'stopped';
  created_at: string;
  config: {
    simulation_speed: number;
    mode: string;
    max_concurrent_cases: number;
  };
}

export interface SimulationState {
  simulation_id: string;
  sim_time: number;
  running: boolean;
  paused: boolean;
  agents: {
    total_agents: number;
    by_type: Record<string, number>;
    by_state: Record<string, number>;
  };
  case_queue: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
  };
  ambulances: Record<string, string>;
  hospitals: Record<string, string>;
}

export interface SimulationResults {
  simulation_id: string;
  duration_simulated: number;
  duration_real_seconds: number;
  metrics: {
    total_agents: number;
    messages_processed: number;
    cases_completed: number;
    cases_failed: number;
    throughput_per_minute: number;
  };
  case_queue: {
    queued: number;
    processing: number;
    completed: number;
    failed: number;
  };
  agent_pool: {
    total_agents: number;
    by_type: Record<string, number>;
    by_state: Record<string, number>;
  };
  completed_cases: any[];
  actionable_analyses?: Record<string, ActionableAnalysis>;
  top_interventions?: Record<string, Intervention[]>;
}

export interface ActionableAnalysis {
  case_id: string;
  is_feasible: boolean;
  success_probability: number;
  time_remaining_minutes: number;
  recommendations: Intervention[];
  bottlenecks: Bottleneck[];
  response_chain_status: ResponseChainStatus;
  alternative_scenarios: AlternativeScenario[];
  outcome_projection: OutcomeProjection;
}

export interface Intervention {
  id: string;
  title: string;
  description: string;
  priority: 'critical' | 'high' | 'medium' | 'low';
  action_steps: ActionStep[];
  contacts: ContactInfo[];
  estimated_time_saved_minutes: number;
  success_probability: number;
  confidence_score: number;
  risks: string[];
  alternatives: string[];
}

export interface ActionStep {
  id: string;
  who: string;
  how: string;
  when_minutes: number;
  priority: string;
  status: string;
}

export interface ContactInfo {
  name: string;
  role: string;
  phone?: string;
  hospital?: string;
}

export interface Bottleneck {
  id: string;
  type: string;
  severity: 'critical' | 'high' | 'medium' | 'low';
  location: string;
  description: string;
  estimated_delay_minutes: number;
  mitigation: string;
}

export interface ResponseChainStatus {
  dispatch: 'optimal' | 'delayed' | 'failed';
  ambulance_response: 'optimal' | 'delayed' | 'failed';
  hospital_preparation: 'optimal' | 'delayed' | 'failed';
  transport: 'optimal' | 'delayed' | 'failed';
  overall_score: number;
}

export interface AlternativeScenario {
  id: string;
  name: string;
  description: string;
  estimated_time_minutes: number;
  success_probability: number;
}

export interface OutcomeProjection {
  best_case_minutes: number;
  worst_case_minutes: number;
  expected_outcome: string;
  survival_probability: number;
}

export interface ResourceData {
  hospitals: Hospital[];
  ambulances: Ambulance[];
  routes: TransportRoute[];
}
