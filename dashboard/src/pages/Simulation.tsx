import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  ArrowLeft,
  Building2,
  Car,
  CheckCircle,
  Clock,
  Pause,
  Play,
  Square,
  Users,
  Zap
} from 'lucide-react';
import {
  getSimulation,
  runSimulation,
  pauseSimulation,
  resumeSimulation,
  stopSimulation,
  getSimulationResults,
  getInterventionAnalysis,
  addCase
} from '../api';
import type { Simulation, SimulationState, SimulationResults, ActionableAnalysis } from '../types';
import './Simulation.css';

export default function Simulation() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [simulation, setSimulation] = useState<Simulation | null>(null);
  const [state, setState] = useState<SimulationState | null>(null);
  const [results, setResults] = useState<SimulationResults | null>(null);
  const [analysis, setAnalysis] = useState<ActionableAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [activeTab, setActiveTab] = useState<'overview' | 'interventions' | 'timeline'>('overview');

  // New case form
  const [showAddCase, setShowAddCase] = useState(false);
  const [newCase, setNewCase] = useState({
    severity: 'critical',
    emergency_type: 'fetal_distress',
    location: { lat: 28.61, lng: 77.21, address: 'Sector 12, Noida, UP' },
    patient: {
      gestational_age_weeks: 38,
      blood_type: 'O_positive',
      complications: [] as string[],
      previous_cesarean: false,
      multiple_gestation: false
    },
    time_window_minutes: 30
  });

  const loadSimulation = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getSimulation(id);
      setSimulation(data.simulation);
      setState(data.simulation_state);
    } catch (error) {
      console.error('Failed to load simulation:', error);
    }
  }, [id]);

  const loadResults = useCallback(async () => {
    if (!id) return;
    try {
      const data = await getSimulationResults(id);
      setResults(data);
    } catch (error) {
      console.error('Failed to load results:', error);
    }
  }, [id]);

  const loadAnalysis = useCallback(async () => {
    if (!id || !results?.completed_cases?.[0]?.case_id) return;
    try {
      const caseId = results.completed_cases[0].case_id;
      const data = await getInterventionAnalysis(id, caseId, 'brief');
      setAnalysis(data.analysis);
    } catch (error) {
      console.error('Failed to load analysis:', error);
    }
  }, [id, results]);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await loadSimulation();
      setLoading(false);
    };
    init();
  }, [loadSimulation]);

  useEffect(() => {
    if (simulation?.status === 'running') {
      const interval = setInterval(async () => {
        await loadSimulation();
        if (simulation.status !== 'running') {
          clearInterval(interval);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [simulation?.status, loadSimulation]);

  useEffect(() => {
    if (results) {
      loadAnalysis();
    }
  }, [results, loadAnalysis]);

  const handleRun = async () => {
    if (!id) return;
    setRunning(true);
    try {
      await runSimulation(id, { duration_minutes: 60, max_steps: 1000 });
      await loadSimulation();
      setTimeout(loadResults, 3000);
    } catch (error) {
      console.error('Failed to run simulation:', error);
    } finally {
      setRunning(false);
    }
  };

  const handlePause = async () => {
    if (!id) return;
    try {
      await pauseSimulation(id);
      await loadSimulation();
    } catch (error) {
      console.error('Failed to pause:', error);
    }
  };

  const handleResume = async () => {
    if (!id) return;
    try {
      await resumeSimulation(id);
      await loadSimulation();
    } catch (error) {
      console.error('Failed to resume:', error);
    }
  };

  const handleStop = async () => {
    if (!id) return;
    try {
      await stopSimulation(id);
      await loadSimulation();
      await loadResults();
    } catch (error) {
      console.error('Failed to stop:', error);
    }
  };

  const handleAddCase = async () => {
    if (!id) return;
    try {
      await addCase(id, {
        severity: newCase.severity as any,
        emergency_type: newCase.emergency_type,
        location: newCase.location,
        patient: newCase.patient,
        time_window_minutes: newCase.time_window_minutes
      });
      setShowAddCase(false);
      await loadSimulation();
    } catch (error) {
      console.error('Failed to add case:', error);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'var(--green-500)';
      case 'paused': return 'var(--orange-500)';
      case 'completed': return 'var(--blue-500)';
      case 'stopped': return 'var(--gray-500)';
      default: return 'var(--gray-400)';
    }
  };

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case 'critical': return 'var(--red-500)';
      case 'high': return 'var(--orange-500)';
      case 'medium': return 'var(--blue-500)';
      default: return 'var(--gray-500)';
    }
  };

  if (loading) {
    return (
      <div className="simulation-page loading">
        <div className="spinner-large"></div>
        <span>Loading simulation...</span>
      </div>
    );
  }

  return (
    <div className="simulation-page">
      {/* Header */}
      <header className="sim-header">
        <div className="header-left">
          <button className="btn-back" onClick={() => navigate('/')}>
            <ArrowLeft />
          </button>
          <div className="sim-info">
            <span className="sim-id font-mono">{id}</span>
            <span
              className="sim-status"
              style={{ color: getStatusColor(simulation?.status || '') }}
            >
              {simulation?.status?.toUpperCase()}
            </span>
          </div>
        </div>
        <div className="header-center">
          <div className="time-display">
            <Clock size={18} />
            <span className="time-value font-mono">
              {state?.sim_time?.toFixed(1) || '0.0'} min
            </span>
          </div>
        </div>
        <div className="header-right">
          <button
            className="btn-control"
            onClick={handleRun}
            disabled={running || simulation?.status === 'running'}
            title="Run Simulation"
          >
            <Play />
          </button>
          {simulation?.status === 'running' ? (
            <button className="btn-control" onClick={handlePause} title="Pause">
              <Pause />
            </button>
          ) : simulation?.status === 'paused' ? (
            <button className="btn-control" onClick={handleResume} title="Resume">
              <Play />
            </button>
          ) : null}
          <button
            className="btn-control stop"
            onClick={handleStop}
            disabled={!['running', 'paused'].includes(simulation?.status || '')}
            title="Stop"
          >
            <Square />
          </button>
          <button
            className="btn-control"
            onClick={() => setShowAddCase(true)}
            title="Add Case"
          >
            <Zap />
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="sim-main">
        {/* Metrics Bar */}
        <div className="metrics-bar">
          <div className="metric">
            <Activity size={16} />
            <span className="metric-label">Agents</span>
            <span className="metric-value">{state?.agents?.total_agents || 0}</span>
          </div>
          <div className="metric">
            <Clock size={16} />
            <span className="metric-label">Simulation Time</span>
            <span className="metric-value">{state?.sim_time?.toFixed(1) || 0} min</span>
          </div>
          <div className="metric">
            <Users size={16} />
            <span className="metric-label">Cases</span>
            <span className="metric-value">
              {state?.case_queue?.completed || 0} / {state?.case_queue?.processing || 0}
            </span>
          </div>
          <div className="metric">
            <Car size={16} />
            <span className="metric-label">Messages</span>
            <span className="metric-value">{results?.metrics?.messages_processed || 0}</span>
          </div>
        </div>

        {/* Tabs */}
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'overview' ? 'active' : ''}`}
            onClick={() => setActiveTab('overview')}
          >
            Overview
          </button>
          <button
            className={`tab ${activeTab === 'interventions' ? 'active' : ''}`}
            onClick={() => setActiveTab('interventions')}
          >
            Interventions
          </button>
          <button
            className={`tab ${activeTab === 'timeline' ? 'active' : ''}`}
            onClick={() => setActiveTab('timeline')}
          >
            Timeline
          </button>
        </div>

        {/* Tab Content */}
        <div className="tab-content">
          {activeTab === 'overview' && (
            <div className="overview-grid">
              {/* Agent Status */}
              <div className="card agent-status">
                <h3><Users size={18} /> Agent Status</h3>
                <div className="agent-list">
                  {state?.agents?.by_type && Object.entries(state.agents.by_type).map(([type, count]) => (
                    <div key={type} className="agent-item">
                      <span className="agent-type">{type.replace('_', ' ')}</span>
                      <span className="agent-count">{count}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Ambulance Status */}
              <div className="card ambulance-status">
                <h3><Car size={18} /> Ambulances</h3>
                <div className="unit-list">
                  {state?.ambulances && Object.entries(state.ambulances).map(([ambId, status]) => (
                    <div key={ambId} className="unit-item">
                      <span className="unit-id">{ambId}</span>
                      <span
                        className="unit-status"
                        style={{ color: status === 'available' ? 'var(--green-500)' : 'var(--gray-500)' }}
                      >
                        {status}
                      </span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Hospital Status */}
              <div className="card hospital-status">
                <h3><Building2 size={18} /> Hospitals</h3>
                <div className="unit-list">
                  {state?.hospitals && Object.entries(state.hospitals).map(([hospId, status]) => (
                    <div key={hospId} className="unit-item">
                      <span className="unit-id">{hospId}</span>
                      <span className="unit-status">{status}</span>
                    </div>
                  ))}
                </div>
              </div>

              {/* Results Summary */}
              <div className="card results-summary">
                <h3><CheckCircle size={18} /> Results Summary</h3>
                <div className="results-grid">
                  <div className="result-item">
                    <span className="result-value">{results?.metrics?.cases_completed || 0}</span>
                    <span className="result-label">Completed</span>
                  </div>
                  <div className="result-item">
                    <span className="result-value">{results?.metrics?.cases_failed || 0}</span>
                    <span className="result-label">Failed</span>
                  </div>
                  <div className="result-item">
                    <span className="result-value">{results?.duration_simulated?.toFixed(1) || 0}</span>
                    <span className="result-label">Sim Minutes</span>
                  </div>
                  <div className="result-item">
                    <span className="result-value">{((results?.metrics?.throughput_per_minute || 0)).toFixed(2)}</span>
                    <span className="result-label">Throughput</span>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'interventions' && (
            <div className="interventions-panel">
              {analysis ? (
                <div className="intervention-content">
                  {/* Feasibility Banner */}
                  <div
                    className="feasibility-banner"
                    style={{
                      background: analysis.is_feasible ? 'var(--green-100)' : 'var(--red-100)',
                      borderColor: analysis.is_feasible ? 'var(--green-500)' : 'var(--red-500)'
                    }}
                  >
                    <span className="feasibility-icon">
                      {analysis.is_feasible ? <CheckCircle /> : <AlertTriangle />}
                    </span>
                    <div className="feasibility-text">
                      <strong>{analysis.is_feasible ? 'FEASIBLE' : 'NOT FEASIBLE'}</strong>
                      <span>
                        Success Probability: {(analysis.success_probability * 100).toFixed(0)}%
                        | Time Remaining: {analysis.time_remaining_minutes.toFixed(1)} min
                      </span>
                    </div>
                  </div>

                  {/* Recommendations */}
                  <div className="recommendations">
                    <h3>Recommended Actions</h3>
                    {analysis.recommendations?.slice(0, 5).map((rec, idx) => (
                      <div key={idx} className="recommendation-card">
                        <div className="rec-header">
                          <span
                            className="rec-priority"
                            style={{ background: getPriorityColor(rec.priority) }}
                          >
                            {rec.priority?.toUpperCase()}
                          </span>
                          <span className="rec-title">{rec.title}</span>
                        </div>
                        <p className="rec-description">{rec.description}</p>
                        <div className="rec-steps">
                          {rec.action_steps?.slice(0, 3).map((step, sIdx) => (
                            <div key={sIdx} className="step-item">
                              <span className="step-who">{step.who}</span>
                              <span className="step-action">{step.how}</span>
                            </div>
                          ))}
                        </div>
                        {rec.contacts && rec.contacts.length > 0 && (
                          <div className="rec-contacts">
                            <strong>Contacts:</strong>
                            {rec.contacts.map((c, cIdx) => (
                              <span key={cIdx} className="contact-item">
                                {c.name} ({c.role})
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              ) : (
                <div className="empty-interventions">
                  <Zap size={48} strokeWidth={1.5} />
                  <h3>No Intervention Analysis Available</h3>
                  <p>Run a simulation with completed cases to see intervention recommendations.</p>
                </div>
              )}
            </div>
          )}

          {activeTab === 'timeline' && (
            <div className="timeline-panel">
              <div className="timeline">
                <div className="timeline-item current">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <span className="timeline-time font-mono">0:00</span>
                    <span className="timeline-event">Simulation Initialized</span>
                  </div>
                </div>
                <div className="timeline-item">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <span className="timeline-time font-mono">0:02</span>
                    <span className="timeline-event">Ambulance Dispatched</span>
                  </div>
                </div>
                <div className="timeline-item">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <span className="timeline-time font-mono">5:00</span>
                    <span className="timeline-event">Hospital Alerted</span>
                  </div>
                </div>
                <div className="timeline-item">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <span className="timeline-time font-mono">15:00</span>
                    <span className="timeline-event">OT Ready</span>
                  </div>
                </div>
                <div className="timeline-item pending">
                  <div className="timeline-dot"></div>
                  <div className="timeline-content">
                    <span className="timeline-time font-mono">25:00</span>
                    <span className="timeline-event">Patient Arrival</span>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Add Case Modal */}
      {showAddCase && (
        <div className="modal-overlay" onClick={() => setShowAddCase(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Add Emergency Case</h2>
              <button className="btn-icon" onClick={() => setShowAddCase(false)}>&times;</button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Severity</label>
                <select value={newCase.severity} onChange={(e) => setNewCase({ ...newCase, severity: e.target.value })}>
                  <option value="critical">Critical</option>
                  <option value="severe">Severe</option>
                  <option value="moderate">Moderate</option>
                  <option value="low">Low</option>
                </select>
              </div>
              <div className="form-group">
                <label>Emergency Type</label>
                <select value={newCase.emergency_type} onChange={(e) => setNewCase({ ...newCase, emergency_type: e.target.value })}>
                  <option value="fetal_distress">Fetal Distress</option>
                  <option value="maternal_hemorrhage">Maternal Hemorrhage</option>
                  <option value="eclampsia">Eclampsia</option>
                  <option value="other">Other</option>
                </select>
              </div>
              <div className="form-group">
                <label>Location</label>
                <input type="text" value={newCase.location.address} onChange={(e) => setNewCase({ ...newCase, location: { ...newCase.location, address: e.target.value } })} />
              </div>
              <div className="form-row">
                <div className="form-group">
                  <label>Gestational Age (weeks)</label>
                  <input type="number" value={newCase.patient.gestational_age_weeks} onChange={(e) => setNewCase({ ...newCase, patient: { ...newCase.patient, gestational_age_weeks: parseInt(e.target.value) } })} />
                </div>
                <div className="form-group">
                  <label>Blood Type</label>
                  <select value={newCase.patient.blood_type} onChange={(e) => setNewCase({ ...newCase, patient: { ...newCase.patient, blood_type: e.target.value } })}>
                    <option value="O_positive">O+</option>
                    <option value="O_negative">O-</option>
                    <option value="A_positive">A+</option>
                    <option value="B_positive">B+</option>
                    <option value="AB_positive">AB+</option>
                  </select>
                </div>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowAddCase(false)}>Cancel</button>
              <button className="btn-primary" onClick={handleAddCase}><Zap /> Add Case</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
