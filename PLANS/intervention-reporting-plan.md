# Implementation Plan: Actionable Intervention Reporting System

## Requirements Restatement

**Current Problem:**
The intervention report output is too generic and not actionable:
```
=== INTERVENTION REPORT: Case test_case ===
Status: CRITICAL - INTERVENTION REQUIRED
Success Probability: 6%
Priority Interventions (2):
  1. [CRITICAL] Prepare operating room for emergency case
  2. [HIGH] Divert to hospital with available OR
```

**What We Need:**
A comprehensive report that tells the user EXACTLY what to do, WHO does it, and WHEN - like a mission briefing:

```
═══════════════════════════════════════════════════════════════════
OBSTETRIC EMERGENCY RESPONSE - CASE #MAT-2024-001847
═══════════════════════════════════════════════════════════════════

PATIENT CONTEXT
├─ Emergency: MATERNAL HEMORRHAGE (CRITICAL)
├─ Gestational Age: 38 weeks
├─ Location: Sector 12, Noida (Lat: 28.61, Lng: 77.20)
├─ Time Window: 20 MINUTES TO INTERVENTION
└─ Current Time in Simulation: 14.5 minutes elapsed

SITUATION ASSESSMENT
├─ Success Probability: 23% (CRITICAL)
├─ Response Feasibility: ❌ NOT FEASIBLE WITHOUT INTERVENTION
└─ Bottlenecks Active: 3

═══════════════════════════════════════════════════════════════════
IMMEDIATE ACTIONS REQUIRED (EXECUTE NOW)
═══════════════════════════════════════════════════════════════════

ACTION #1: OR CLEARANCE PROTOCOL
───────────────────────────────────────────────────────────────────
Priority: 🔴 CRITICAL
Who: Hospital Administrator / OR Manager
What: Clear OR-2 for emergency C-section
How:
  1. Cancel non-emergency surgery in OR-2 (Dr. Singh's appendix - can wait 2 hours)
  2. Page current surgical team to wrap up within 5 minutes
  3. Alert cleaning staff to prepare OR immediately after
  4. Notify anesthesiologist Dr. Kumar to be on standby
Time to Complete: 8-12 minutes
Time Saved: 15 minutes
Confidence: 85%

ALTERNATIVE: Transfer to City Hospital (See Action #2)

───────────────────────────────────────────────────────────────────
ACTION #2: HOSPITAL DIVERSION
───────────────────────────────────────────────────────────────────
Priority: 🔴 CRITICAL (If OR unavailable)
Who: EMS Dispatch
What: Divert ambulance to City Hospital, Sector 15
Why: OR-2 is occupied, City Hospital has available OR
Route:
  Current: Central Maternity → 12 min ETA
  Diverted: City Hospital → 15 min ETA (+3 min, BUT OR available)
Contacts:
  City Hospital Dispatch: +91-11-2222-4444
  Attending: Dr. Priya Sharma
Blood Bank Status: ✅ 4 units O-negative available
Staff Status: ✅ OBGYN, Anesthesiologist, Neonatologist on duty

───────────────────────────────────────────────────────────────────
ACTION #3: BLOOD BANK MOBILIZATION
───────────────────────────────────────────────────────────────────
Priority: 🟠 HIGH
Who: Blood Bank Coordinator
What: Secure blood products for maternal hemorrhage
Required:
  - 2 units O-negative (crossmatch ready)
  - 2 units fresh frozen plasma
Current Stock: 4 units available ✅
Action: Reserve units, have courier on standby
Estimated Time: 10 minutes to bedside delivery

═══════════════════════════════════════════════════════════════════
RESPONSE CHAIN STATUS
═══════════════════════════════════════════════════════════════════

⏱️ AMBULANCE (AMB-001)
   Status: EN_ROUTE_TO_PATIENT
   Current Location: Sector 10 Chowk (2.3 km from patient)
   ETA to Patient: 4 minutes
   ETA to Hospital: 16 minutes total
   Route Condition: 🟢 Clear (traffic light priority active)

🏥 HOSPITAL (Central Maternity)
   Status: ALERTED
   OR Status: 🔴 OCCUPIED (surgery ends in ~18 min)
   Bed Status: 🟡 70% occupied (3 beds available)
   Staff: 🟢 Dr. Verma (OBGYN) on duty, Dr. Kumar on call

🩸 BLOOD BANK
   Status: 🟡 PARTIALLY READY
   O-negative: 4 units (sufficient for this case)

═══════════════════════════════════════════════════════════════════
BOTTLENECK ANALYSIS
═══════════════════════════════════════════════════════════════════

Bottleneck #1: Operating Room Congestion
├─ Location: Central Maternity Hospital, OR-2
├─ Issue: Currently in use for non-emergency surgery
├─ Delay: 15-18 minutes
├─ Impact: Cannot perform emergency C-section on arrival
└─ Resolution: Clear OR OR divert to City Hospital

Bottleneck #2: Staff Specialization Gap
├─ Issue: Anesthesiologist Dr. Kumar is 20 minutes away
├─ Impact: Delay in anesthesia preparation
└─ Resolution: Call Dr. Kumar NOW to start travel

Bottleneck #3: Blood Crossmatch Pending
├─ Issue: Patient blood type not confirmed
├─ Impact: 10 min delay for crossmatch process
└─ Resolution: Draw blood sample NOW for quick typing

═══════════════════════════════════════════════════════════════════
EXECUTION CHECKLIST (Print and Use)
═══════════════════════════════════════════════════════════════════

[ ] 1. CALL City Hospital NOW: +91-11-2222-4444
      └─ Say: "Emergency maternal hemorrhage, diverting patient"
      └─ Ask: Confirm OR availability and ETA

[ ] 2. RADIO Ambulance AMB-001
      └─ Instruction: "Divert to City Hospital, Sector 15"
      └─ Reason: "Central OR occupied"

[ ] 3. PAGE Dr. Kumar (Anesthesiologist)
      └─ Message: "Maternal hemorrhage, 20 min ETA, prepare spinal kit"

[ ] 4. BLOOD BANK
      └─ Action: Reserve 2 units O-negative, prepare FFP
      └─ Courier on standby for hospital delivery

[ ] 5. ALERT Neonatal Team
      └─ Notify NICU of incoming premature delivery risk
      └─ Prepare radiant warmer and ventilation equipment

═══════════════════════════════════════════════════════════════════
PROJECTED OUTCOMES
═══════════════════════════════════════════════════════════════════

WITH INTERVENTION #1 (OR Clearance):
├─ Success Probability: 23% → 58%
├─ Patient Outcome: Likely positive with C-section
└─ Risk: Moderate - depends on surgery completion timing

WITH INTERVENTION #2 (Hospital Diversion):
├─ Success Probability: 23% → 71%
├─ Patient Outcome: Good - OR guaranteed available
└─ Risk: Low - City Hospital has full team assembled

WITH ALL INTERVENTIONS:
├─ Success Probability: 23% → 85%+
├─ Patient Outcome: Excellent prognosis
└─ Time Saved: ~20 minutes

═══════════════════════════════════════════════════════════════════
Report Generated: 2024-03-19 14:32:05 IST
Simulation Time: 14.5 minutes
Engine: MiroFish v2.0
═══════════════════════════════════════════════════════════════════
```

---

## Implementation Phases

### Phase 1: Enhanced Data Models (foundation)

**Files to modify:**
- `intervention_recommender.py` - Add enhanced dataclasses

**Changes:**
1. Add `ActionStep` dataclass with:
   - `step_number`: int
   - `action`: str (specific instruction)
   - `actor`: str (WHO does this)
   - `method`: str (HOW to do it)
   - `contacts`: List[ContactInfo] (phone numbers, etc.)
   - `estimated_time`: float
   - `dependencies`: List[str] (what must happen first)
   - `checklist_items`: List[str] (tick box items)

2. Add `ResourceAvailability` to track:
   - Current location
   - ETA to relevant point
   - Availability status
   - Contact information

3. Add `InterventionScenario` to compare:
   - "Do nothing" baseline
   - "Intervention A" improvement
   - "Intervention B" alternative
   - Combined interventions

### Phase 2: Rich Bottleneck Detection

**Files to modify:**
- `intervention_recommender.py` - `_identify_bottlenecks()`

**Changes:**
1. Extract real data from simulation state:
   - Actual ambulance locations and ETAs
   - Real hospital OR status with expected availability time
   - Staff on-duty vs on-call with response times
   - Blood bank actual inventory levels

2. Calculate precise delays based on:
   - Distance-based travel times
   - Traffic condition impacts
   - OR queue position
   - Staff arrival times

3. Add bottleneck severity scoring:
   - Critical (blocks intervention entirely)
   - High (significant delay)
   - Medium (manageable delay)
   - Low (minor impact)

### Phase 3: Actionable Recommendation Generator

**Files to modify:**
- `intervention_recommender.py` - `_generate_recommendations()`

**Changes:**
1. Generate specific action steps for each intervention:
   ```
   BEFORE: "Prepare operating room for emergency case"
   AFTER:
     1. "Cancel non-emergency surgery in OR-2"
        - Actor: Hospital Administrator
        - Contact: +91-11-2222-3333
        - Time: 3 minutes
     2. "Alert cleaning staff"
        - Actor: OR Manager
        - Contact: +91-11-2222-3334
        - Time: 2 minutes after surgery ends
     3. "Prepare surgical instruments"
        - Actor: Scrub Nurse
        - Time: 5 minutes
   ```

2. Add alternative scenarios:
   - Primary recommendation
   - Fallback option
   - Worst-case backup

3. Include resource-specific information:
   - Hospital contact numbers
   - Staff on-call lists
   - Alternative facility options

### Phase 4: Comprehensive Report Generator

**Files to modify:**
- `intervention_recommender.py` - `generate_intervention_report()`

**Changes:**
1. Create structured report with sections:
   - Executive Summary (1-paragraph overview)
   - Patient Context (specific details)
   - Situation Assessment (success probability, feasibility)
   - Immediate Actions (numbered with specific steps)
   - Response Chain Status (real-time agent states)
   - Bottleneck Analysis (detailed issue descriptions)
   - Execution Checklist (printable tick-box list)
   - Projected Outcomes (with/without intervention)

2. Support multiple output formats:
   - Terminal-friendly text (current)
   - Structured JSON (for API/UI)
   - Markdown (for documentation)
   - HTML (for dashboard)

### Phase 5: Simulation Engine Integration

**Files to modify:**
- `parallel_simulation_engine.py` - `_build_case_status()`

**Changes:**
1. Enhance `_build_case_status()` to capture:
   - Real ambulance locations (lat/lng)
   - Actual ETAs from road network
   - Hospital OR detailed status
   - Staff on-duty/on-call status
   - Blood bank actual inventory

2. Pass rich context to intervention analyzer

---

## Dependencies

1. **Data availability** - Simulation engine must track detailed state
2. **Resource registry** - Must include contact information
3. **Road network** - Must provide accurate ETAs

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Report too verbose | HIGH | LOW | Add "concise" mode option |
| Missing contact info | MEDIUM | MEDIUM | Add placeholder with "contact unavailable" |
| Performance impact | LOW | MEDIUM | Lazy-generate detailed data only when needed |

---

## Estimated Complexity: MEDIUM-HIGH

- Phase 1 (Models): 2-3 hours
- Phase 2 (Bottleneck Detection): 3-4 hours
- Phase 3 (Recommendation Generator): 4-5 hours
- Phase 4 (Report Generator): 3-4 hours
- Phase 5 (Integration): 2-3 hours
- **Total: 14-19 hours**

---

## Files to Modify

```
backend/app/services/emergency_response/
├── intervention_recommender.py  (main changes)
├── parallel_simulation_engine.py (enhance status)
└── __init__.py                  (export new functions)
```

---

## Success Criteria

1. Report contains WHO, WHAT, HOW, WHEN for each action
2. Includes actual contact numbers where available
3. Shows before/after success probability
4. Provides printable execution checklist
5. Generates alternative scenarios (diversion vs clearance)
