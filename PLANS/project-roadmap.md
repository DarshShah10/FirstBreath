# MiroFish Project Roadmap: Moving Forward

## Current Status (March 2026)

### ✅ Completed Phases
| Phase | Status | Components |
|-------|--------|------------|
| Phase 1: Core Infrastructure | ✅ COMPLETE | ResourceRegistry, BaseAgent, Config loading |
| Phase 2: Agent Implementation | ✅ COMPLETE | AmbulanceAgent, HospitalAgent, DispatchAgent, CityConditionAgent |
| Phase 3: Full Simulation Loop | ✅ COMPLETE | StaffAgent, BloodBankAgent, RoadNetworkAgent, CaseQueue, InterventionRecommender |
| Actionable Intervention System | ✅ COMPLETE | Mission-briefing style reports with WHO/HOW/WHEN |

### ⚠️ Critical Issues (Needs Immediate Fix)

1. **Ambulance ETA Calculation Bug** - Shows 5672 minutes instead of ~18 minutes
2. **No Test Coverage** - Zero unit tests exist
3. **Technical Debt** - Magic numbers, duplicate Route classes

### 📋 Remaining Work

---

## Detailed Implementation Plan

### Phase A: Critical Bug Fixes (High Priority)

#### A1: Fix Ambulance ETA Calculation Bug
**Problem**: Ambulance agent ETA calculation returns 5672 minutes instead of ~18 minutes
**Location**: `ambulance_agent.py` - `_calculate_eta_to_destination()` method

**Steps**:
1. Debug the ETA calculation in `AmbulanceAgent._calculate_eta_to_destination()`
2. Trace through the route calculation logic
3. Fix distance/speed calculation
4. Add unit tests

**Files**: `ambulance_agent.py`
**Effort**: 2-3 hours

---

#### A2: Add Unit Test Infrastructure
**Problem**: No tests exist for agent systems

**Steps**:
1. Set up pytest configuration
2. Create test fixtures for agents
3. Write tests for:
   - AmbulanceAgent state machine
   - HospitalAgent state machine
   - CaseQueue priority calculation
   - InterventionRecommender logic
4. Achieve 70%+ coverage target

**Files**: `tests/` directory
**Effort**: 8-12 hours

---

### Phase B: API Layer (REST + Streaming)

#### B1: REST API Endpoints
**Purpose**: Expose simulation via HTTP API

**Endpoints**:
```
POST   /api/v1/simulations              # Create new simulation
GET    /api/v1/simulations/{id}        # Get simulation status
POST   /api/v1/simulations/{id}/cases # Add emergency case
GET    /api/v1/simulations/{id}/report # Get intervention report
POST   /api/v1/simulations/{id}/run    # Run simulation
DELETE /api/v1/simulations/{id}        # Stop simulation
```

**Steps**:
1. Create FastAPI application structure
2. Implement simulation lifecycle endpoints
3. Add request/response models
4. Integrate with ParallelSimulationEngine
5. Add authentication

**Files**: `backend/app/api/` new directory
**Effort**: 12-16 hours

---

#### B2: WebSocket Real-Time Streaming
**Purpose**: Live simulation updates for dashboard

**Events**:
```
simulation.step      # Every simulation step
agent.state_change  # Agent state transitions
case.update        # Case status changes
intervention.required  # Bottleneck detected
simulation.complete # Simulation finished
```

**Steps**:
1. Add WebSocket endpoint
2. Integrate EventStream from simulation engine
3. Implement client subscription management
4. Add reconnection handling
5. Create streaming protocol

**Files**: `backend/app/api/websocket.py`
**Effort**: 8-10 hours

---

### Phase C: Frontend Dashboard

#### C1: Simulation Dashboard
**Purpose**: Visualize simulation state in real-time

**Features**:
- Map view with ambulance/hospital positions
- Real-time agent status panel
- Timeline of events
- Live intervention alerts
- Case management interface

**Steps**:
1. Create Vue/React dashboard structure
2. Implement WebSocket client
3. Build map visualization
4. Create status panels
5. Add intervention alert system

**Files**: `frontend/src/views/Dashboard.vue`
**Effort**: 20-25 hours

---

#### C2: Report Viewer
**Purpose**: Display actionable intervention reports

**Features**:
- Formatted report display
- Print-friendly checklist
- Action tracking
- Scenario comparison
- Export options (PDF, JSON)

**Steps**:
1. Create report viewer component
2. Implement print stylesheet
3. Add export functionality
4. Build scenario comparison view

**Files**: `frontend/src/components/ReportViewer.vue`
**Effort**: 10-12 hours

---

### Phase D: FirstBreath Integration

#### D1: CTG Signal Interface
**Purpose**: Connect CTG (Cardiotocography) detection to simulation

**Interface**:
```python
class CTGSignalReceiver:
    def on_distress_detected(
        self,
        patient_id: str,
        ctg_data: Dict,
        severity: EmergencySeverity,
        location: Location
    ) -> str:  # Returns case_id
```

**Steps**:
1. Design CTG signal receiver interface
2. Implement message queue consumer
3. Create DistressSignal from CTG data
4. Add validation and enrichment
5. Integrate with case queue

**Files**: `backend/app/services/firstbreath_adapter.py`
**Effort**: 8-10 hours

---

#### D2: Real-Time CTG Streaming (Optional)
**Purpose**: Stream CTG data during transport

**Steps**:
1. Add CTG data storage
2. Implement streaming endpoint
3. Create visualization component
4. Add alerting thresholds

**Effort**: 12-15 hours (if implemented)

---

### Phase E: Technical Debt & Polish

#### E1: Refactor Magic Numbers
**Problem**: Hardcoded constants scattered throughout code

**Constants to Extract**:
```python
# ambulance_agent.py
AMBULANCE_SPEED_KMH = 40
ARRIVAL_THRESHOLD_KM = 0.1
MAX_REROUTES = 3

# hospital_agent.py
STAFF_ALERT_TIME = 2.0
OT_PREP_TIME = 10.0
BLOOD_PREP_TIME = 5.0

# intervention_recommender.py
CRITICAL_THRESHOLD = 10
URGENT_THRESHOLD = 20
```

**Files**: Multiple
**Effort**: 4-6 hours

---

#### E2: Unify Route Classes
**Problem**: Two different Route classes (TransportRoute vs Route)

**Steps**:
1. Audit both Route implementations
2. Design unified interface
3. Migrate to single Route class
4. Update all consumers

**Files**: `response_resource.py`, `road_network_agent.py`
**Effort**: 6-8 hours

---

#### E3: Blood Type Normalization
**Problem**: Case sensitivity in blood type matching (a_positive vs A+)

**Steps**:
1. Create BloodType enum with normalization
2. Update BloodBankAgent
3. Add blood type conversion utilities

**Effort**: 2-3 hours

---

### Phase F: Advanced Features (Future)

#### F1: Historical Analysis
- Store simulation results
- Trend analysis
- Bottleneck frequency reports
- Resource optimization suggestions

#### F2: Machine Learning Prediction
- Predict bottlenecks before they occur
- Optimize resource allocation
- Anomaly detection in response times

#### F3: Multi-Region Support
- Regional case queue pools
- Cross-region resource sharing
- Federated simulation

---

## Implementation Priority & Timeline

### Immediate (This Week)
| Task | Priority | Effort | Dependencies |
|------|----------|--------|--------------|
| Fix ETA Bug | 🔴 CRITICAL | 2-3h | None |
| Add Test Infrastructure | 🔴 CRITICAL | 4-6h | None |
| Unit Tests for Agents | 🔴 CRITICAL | 6-8h | Tests infra |

### Short-Term (2-3 Weeks)
| Task | Priority | Effort | Dependencies |
|------|----------|--------|--------------|
| REST API | 🟠 HIGH | 12-16h | None |
| WebSocket Streaming | 🟠 HIGH | 8-10h | REST API |
| Dashboard Map | 🟠 HIGH | 10-12h | WebSocket |
| Report Viewer | 🟠 HIGH | 8-10h | REST API |

### Medium-Term (1-2 Months)
| Task | Priority | Effort | Dependencies |
|------|----------|--------|--------------|
| FirstBreath Adapter | 🟡 MEDIUM | 8-10h | REST API |
| CTG Streaming | 🟡 MEDIUM | 12-15h | FirstBreath |
| Technical Debt | 🟡 MEDIUM | 12-17h | None |

### Long-Term (Future)
| Task | Priority | Effort | Dependencies |
|------|----------|--------|--------------|
| Historical Analysis | ⚪ LOW | 20h | REST API |
| ML Prediction | ⚪ LOW | 40h | Historical |
| Multi-Region | ⚪ LOW | 30h | Complex |

---

## Recommended Next Steps

### Option 1: Fix Bugs First (Recommended)
1. Fix Ambulance ETA bug
2. Add test infrastructure
3. Write unit tests for core agents
4. Then proceed to API

### Option 2: API First
1. Build REST API
2. Build WebSocket streaming
3. Fix bugs in parallel
4. Add tests

### Option 3: Full Stack
1. Build API layer
2. Build frontend dashboard
3. Fix bugs
4. Add tests

---

## Resource Requirements

| Resource | Requirement |
|----------|-------------|
| Backend Developer | 1 (current) |
| Frontend Developer | 1 (future) |
| Test Coverage Goal | 70%+ |
| Documentation | Auto-generated |

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| ETA bug more complex | MEDIUM | HIGH | Allocate 2x time, debug thoroughly |
| WebSocket scalability | LOW | MEDIUM | Use message batching |
| FirstBreath API changes | HIGH | MEDIUM | Design adapter pattern |
| Test coverage goal | MEDIUM | MEDIUM | Prioritize critical paths |

---

## Success Metrics

- ✅ All agents have unit tests
- ✅ API responds < 200ms for standard operations
- ✅ WebSocket latency < 500ms
- ✅ 70%+ test coverage
- ✅ Zero critical bugs in production
- ✅ FirstBreath integration functional

---

## Questions for Clarification

1. **Frontend Preference**: Vue.js (existing) or React?
2. **Database**: SQLite for now, PostgreSQL later?
3. **Deployment Target**: Local, Docker, Cloud?
4. **FirstBreath Integration**: Do you have the API spec?
5. **Priority Order**: Which phase matters most?

---

**Estimated Total Effort** (excluding future phases):
- Immediate + Short-Term: 70-90 hours
- Medium-Term: 20-27 hours
- **Total: 90-117 hours**
