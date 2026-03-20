"""
LLM prompt builders for VahanAI Emergency Response Dispatch Simulation.

Core concept: When a distress signal arrives, simulate the response chain
to identify where it will break, then output specific interventions to fix it.
"""

import json
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

UNIT_CONFIG_SYSTEM_PROMPT = (
    "You are an emergency dispatch analysis expert. "
    "Return pure JSON. Analyze units based on their current status, location, and dependencies. "
    "Respond only in English."
)

DISPATCH_SYSTEM_PROMPT = (
    "You are the VahanAI Optimizer. Your job is NOT to describe what happened — "
    "your job is to tell operators EXACTLY what to do to save the patient. "
    "Return pure JSON. Respond only in English."
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_unit_config_prompt(
    simulation_requirement: str,
    entity_list: List[Dict[str, Any]],
) -> str:
    """Build prompt for analyzing available units."""
    return f"""Analyze emergency response units for: {simulation_requirement}

## Available Units
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
For each unit, determine:
1. Is it available RIGHT NOW?
2. How far is it from the emergency?
3. What does it provide (ambulance, surgery, blood, etc.)?
4. What does it need (OT, blood, specialist)?
5. How critical is it? (1.0 = single point of failure, 0.5 = can substitute)

Return JSON format:
{{
    "units": [
        {{
            "agent_id": <id>,
            "entity_name": "<name>",
            "entity_type": "<ambulance/doctor/hospital/ot/blood_bank/dispatcher>",
            "is_available": true/false,
            "distance_km": <distance>,
            "response_time_min": <estimated response time>,
            "provides": ["<service1>", "<service2>"],
            "requires": ["<needed_service>"],
            "criticality": <0.5-1.0>
        }}
    ]
}}"""


def build_dispatch_prompt(
    distress_signal: Dict[str, Any],
    available_units: List[Dict[str, Any]],
    city_condition: Dict[str, Any],
) -> str:
    """Build prompt for dispatch analysis and intervention recommendation."""

    traffic_info = ""
    if city_condition.get("traffic_level") != "normal":
        traffic_info = f"\\n⚠️ TRAFFIC: {city_condition.get('traffic_level')}"
        if city_condition.get("blocked_routes"):
            traffic_info += f"\\nBlocked routes: {', '.join(city_condition.get('blocked_routes', []))}"

    if city_condition.get("is_festival"):
        traffic_info += f"\\n🎪 FESTIVAL: {city_condition.get('festival_name')} — expect delays"

    return f"""## DISTRESS SIGNAL
Type: {distress_signal.get('signal_type', 'B')} (B=108 call, A=FirstBreath, C=nurse flag)
Severity: {distress_signal.get('severity', 8)}/10
Time Window: {distress_signal.get('time_window_min', 20)} minutes
Location: {distress_signal.get('location', 'Unknown')}
Condition: {distress_signal.get('patient_condition', 'Unknown')}
Needs: {"Ambulance" if distress_signal.get('needs_ambulance') else ""}, {"Blood (" + distress_signal.get('blood_type', '') + ")" if distress_signal.get('needs_blood') else ""}, {"OT" if distress_signal.get('needs_ot') else ""}, {distress_signal.get('needs_specialist', '') if distress_signal.get('needs_specialist') else ''}

{traffic_info}

## AVAILABLE UNITS
```json
{json.dumps(available_units, ensure_ascii=False, indent=2)}
```

## TASK
Answer these 3 questions:

1. **SUCCESS PROBABILITY** — Will current resources reach in time? (0-100%)

2. **BOTTLENECK** — Where will it fail?
   - dispatch: No ambulance available
   - en_route: Ambulance delayed by traffic
   - handoff: Hospital not ready
   - ot_prep: Operating theater occupied
   - blood: Required blood type unavailable

3. **INTERVENTION** — What ONE action would change the outcome?
   Be SPECIFIC. Not "improve coordination" — say "Reroute AMB-07 via Route-B, saves 8 min"
   Not "alert hospital" — say "Pre-alert OT-2 now, pages Dr. Sharma at T+5"

Return JSON:
{{
    "success_probability": <0-100>,
    "bottleneck": "<dispatch/en_route/handoff/ot_prep/blood>",
    "bottleneck_unit": "<specific unit or 'multiple'>",
    "intervention": {{
        "action": "<EXACT action to take>",
        "trigger": "now/T+<X>/if_<condition>",
        "time_saved_min": <minutes>,
        "survival_impact": "High/Medium/Low"
    }}
}}"""
