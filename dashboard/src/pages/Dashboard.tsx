import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  Building2,
  Car,
  Clock,
  Heart,
  Plus,
  RefreshCw,
  Settings,
  Zap
} from 'lucide-react';
import {
  createSimulation,
  listSimulations,
  getResources
} from '../api';
import type { Simulation, ResourceData } from '../types';
import './Dashboard.css';

export default function Dashboard() {
  const navigate = useNavigate();
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [resources, setResources] = useState<ResourceData | null>(null);
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [showNewCase, setShowNewCase] = useState(false);

  // New case form state
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

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    setLoading(true);
    try {
      const [sims, res] = await Promise.all([
        listSimulations(),
        getResources()
      ]);
      setSimulations(sims);
      setResources(res);
    } catch (error) {
      console.error('Failed to load data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateSimulation = async () => {
    setCreating(true);
    try {
      const result = await createSimulation({
        simulation_speed: 10,
        mode: 'sequential',
        max_concurrent_cases: 10
      });
      navigate(`/simulation/${result.simulation_id}`);
    } catch (error) {
      console.error('Failed to create simulation:', error);
    } finally {
      setCreating(false);
    }
  };

  const handleCreateCase = async () => {
    setCreating(true);
    try {
      // Create simulation first
      const sim = await createSimulation({
        simulation_speed: 10,
        mode: 'sequential',
        max_concurrent_cases: 10
      });

      // Add case through API
      const { addCase } = await import('../api');
      await addCase(sim.simulation_id, {
        severity: newCase.severity as any,
        emergency_type: newCase.emergency_type,
        location: newCase.location,
        patient: newCase.patient,
        time_window_minutes: newCase.time_window_minutes
      });

      navigate(`/simulation/${sim.simulation_id}`);
    } catch (error) {
      console.error('Failed to create case:', error);
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'running': return 'badge-running';
      case 'paused': return 'badge-paused';
      case 'completed': return 'badge-success';
      default: return 'badge-low';
    }
  };

  return (
    <div className="dashboard">
      {/* Header */}
      <header className="dashboard-header">
        <div className="header-left">
          <div className="logo">
            <Heart className="logo-icon" />
            <span className="logo-text">MiroFish</span>
          </div>
          <span className="subtitle">Emergency Response Simulation</span>
        </div>
        <div className="header-right">
          <button className="btn-icon" onClick={loadData} disabled={loading}>
            <RefreshCw className={loading ? 'animate-spin' : ''} />
          </button>
          <button className="btn-primary" onClick={() => setShowNewCase(true)}>
            <Plus /> New Emergency
          </button>
        </div>
      </header>

      {/* Main Content */}
      <main className="dashboard-main">
        {/* Stats Overview */}
        <section className="stats-grid">
          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--blue-100)', color: 'var(--blue-600)' }}>
              <Activity />
            </div>
            <div className="stat-content">
              <span className="stat-value">{simulations.length}</span>
              <span className="stat-label">Total Simulations</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--green-100)', color: 'var(--green-600)' }}>
              <Building2 />
            </div>
            <div className="stat-content">
              <span className="stat-value">{resources?.hospitals?.length || 0}</span>
              <span className="stat-label">Hospitals</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--orange-100)', color: 'var(--orange-600)' }}>
              <Car />
            </div>
            <div className="stat-content">
              <span className="stat-value">{resources?.ambulances?.length || 0}</span>
              <span className="stat-label">Ambulances</span>
            </div>
          </div>

          <div className="stat-card">
            <div className="stat-icon" style={{ background: 'var(--purple-500)', color: 'white' }}>
              <Zap />
            </div>
            <div className="stat-content">
              <span className="stat-value">{resources?.routes?.length || 0}</span>
              <span className="stat-label">Routes</span>
            </div>
          </div>
        </section>

        {/* Quick Actions */}
        <section className="quick-actions">
          <h2>Quick Actions</h2>
          <div className="actions-grid">
            <button className="action-card" onClick={handleCreateSimulation} disabled={creating}>
              <div className="action-icon">
                <Plus />
              </div>
              <span className="action-title">Create Simulation</span>
              <span className="action-desc">Start a new emergency response simulation</span>
            </button>

            <button className="action-card" onClick={() => setShowNewCase(true)}>
              <div className="action-icon alert">
                <AlertTriangle />
              </div>
              <span className="action-title">Report Emergency</span>
              <span className="action-desc">Submit a new emergency case for simulation</span>
            </button>

            <button className="action-card" onClick={loadData}>
              <div className="action-icon">
                <RefreshCw />
              </div>
              <span className="action-title">Refresh Data</span>
              <span className="action-desc">Update simulation and resource status</span>
            </button>
          </div>
        </section>

        {/* Recent Simulations */}
        <section className="recent-simulations">
          <h2>Recent Simulations</h2>
          {loading ? (
            <div className="loading-state">
              <div className="spinner"></div>
              <span>Loading simulations...</span>
            </div>
          ) : simulations.length === 0 ? (
            <div className="empty-state">
              <Activity size={48} strokeWidth={1.5} />
              <h3>No Simulations Yet</h3>
              <p>Create your first simulation to start simulating emergency response scenarios.</p>
              <button className="btn-primary" onClick={handleCreateSimulation} disabled={creating}>
                <Plus /> Create Simulation
              </button>
            </div>
          ) : (
            <div className="simulations-list">
              {simulations.slice(0, 5).map((sim) => (
                <div
                  key={sim.id}
                  className="simulation-item"
                  onClick={() => navigate(`/simulation/${sim.id}`)}
                >
                  <div className="sim-header">
                    <span className="sim-id font-mono">{sim.id}</span>
                    <span className={`badge ${getStatusBadgeClass(sim.status)}`}>
                      {sim.status}
                    </span>
                  </div>
                  <div className="sim-details">
                    <span className="sim-detail">
                      <Clock size={14} /> {new Date(sim.created_at).toLocaleString()}
                    </span>
                    <span className="sim-detail">
                      <Settings size={14} /> Speed: {sim.config.simulation_speed}x
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>

        {/* Resource Overview */}
        <section className="resources-overview">
          <h2>Resources Available</h2>
          <div className="resources-grid">
            {/* Hospitals */}
            <div className="resource-section">
              <h3><Building2 size={18} /> Hospitals</h3>
              <div className="resource-list">
                {resources?.hospitals?.slice(0, 3).map((h) => (
                  <div key={h.hospital_id} className="resource-item">
                    <span className="resource-name">{h.name}</span>
                    <span className={`badge ${h.level === 'tertiary' ? 'badge-success' : 'badge-low'}`}>
                      {h.level}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Ambulances */}
            <div className="resource-section">
              <h3><Car size={18} /> Ambulances</h3>
              <div className="resource-list">
                {resources?.ambulances?.slice(0, 3).map((a) => (
                  <div key={a.ambulance_id} className="resource-item">
                    <span className="resource-name">{a.name}</span>
                    <span className="resource-status available">Available</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>
      </main>

      {/* New Case Modal */}
      {showNewCase && (
        <div className="modal-overlay" onClick={() => setShowNewCase(false)}>
          <div className="modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>Report New Emergency</h2>
              <button className="btn-icon" onClick={() => setShowNewCase(false)}>
                &times;
              </button>
            </div>
            <div className="modal-body">
              <div className="form-group">
                <label>Severity Level</label>
                <select
                  value={newCase.severity}
                  onChange={(e) => setNewCase({ ...newCase, severity: e.target.value })}
                >
                  <option value="critical">Critical - Immediate life threat</option>
                  <option value="severe">Severe - High urgency</option>
                  <option value="moderate">Moderate - Standard urgency</option>
                  <option value="low">Low - Non-urgent</option>
                </select>
              </div>

              <div className="form-group">
                <label>Emergency Type</label>
                <select
                  value={newCase.emergency_type}
                  onChange={(e) => setNewCase({ ...newCase, emergency_type: e.target.value })}
                >
                  <option value="fetal_distress">Fetal Distress</option>
                  <option value="maternal_hemorrhage">Maternal Hemorrhage</option>
                  <option value="uterine_rupture">Uterine Rupture</option>
                  <option value="cord_prolapse">Cord Prolapse</option>
                  <option value="placental_abruption">Placental Abruption</option>
                  <option value="eclampsia">Eclampsia</option>
                  <option value="shoulder_dystocia">Shoulder Dystocia</option>
                  <option value="premature_labor">Premature Labor</option>
                  <option value="other">Other</option>
                </select>
              </div>

              <div className="form-group">
                <label>Location</label>
                <input
                  type="text"
                  value={newCase.location.address}
                  onChange={(e) => setNewCase({
                    ...newCase,
                    location: { ...newCase.location, address: e.target.value }
                  })}
                  placeholder="Enter address"
                />
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Gestational Age (weeks)</label>
                  <input
                    type="number"
                    value={newCase.patient.gestational_age_weeks}
                    onChange={(e) => setNewCase({
                      ...newCase,
                      patient: { ...newCase.patient, gestational_age_weeks: parseInt(e.target.value) }
                    })}
                    min="20"
                    max="45"
                  />
                </div>
                <div className="form-group">
                  <label>Blood Type</label>
                  <select
                    value={newCase.patient.blood_type}
                    onChange={(e) => setNewCase({
                      ...newCase,
                      patient: { ...newCase.patient, blood_type: e.target.value }
                    })}
                  >
                    <option value="O_positive">O+</option>
                    <option value="O_negative">O-</option>
                    <option value="A_positive">A+</option>
                    <option value="A_negative">A-</option>
                    <option value="B_positive">B+</option>
                    <option value="B_negative">B-</option>
                    <option value="AB_positive">AB+</option>
                    <option value="AB_negative">AB-</option>
                  </select>
                </div>
              </div>

              <div className="form-row">
                <div className="form-group">
                  <label>Time Window (minutes)</label>
                  <input
                    type="number"
                    value={newCase.time_window_minutes}
                    onChange={(e) => setNewCase({
                      ...newCase,
                      time_window_minutes: parseInt(e.target.value)
                    })}
                    min="1"
                    max="120"
                  />
                </div>
              </div>

              <div className="form-group checkbox-group">
                <label>
                  <input
                    type="checkbox"
                    checked={newCase.patient.previous_cesarean}
                    onChange={(e) => setNewCase({
                      ...newCase,
                      patient: { ...newCase.patient, previous_cesarean: e.target.checked }
                    })}
                  />
                  Previous Cesarean Section
                </label>
                <label>
                  <input
                    type="checkbox"
                    checked={newCase.patient.multiple_gestation}
                    onChange={(e) => setNewCase({
                      ...newCase,
                      patient: { ...newCase.patient, multiple_gestation: e.target.checked }
                    })}
                  />
                  Multiple Gestation (Twins/Triplets)
                </label>
              </div>
            </div>
            <div className="modal-footer">
              <button className="btn-secondary" onClick={() => setShowNewCase(false)}>
                Cancel
              </button>
              <button className="btn-primary" onClick={handleCreateCase} disabled={creating}>
                {creating ? (
                  <>
                    <div className="spinner small"></div> Creating...
                  </>
                ) : (
                  <>
                    <Zap /> Create & Run Simulation
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
