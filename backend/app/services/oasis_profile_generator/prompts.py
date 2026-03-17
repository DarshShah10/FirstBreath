"""
LLM prompt builders for the VahanAI Emergency Response Unit Profile generator.
"""

import json
from typing import Any, Dict


def get_system_prompt(is_individual: bool) -> str:
    """Return the LLM system prompt for emergency unit profile generation."""
    return (
        "You are an emergency logistics unit profile generation expert. "
        "Generate detailed, realistic operational profiles for emergency response simulation. "
        "You must return valid JSON format; all string values must not contain "
        "unescaped newline characters. Respond only in English."
    )


def build_individual_persona_prompt(
    entity_name: str,
    entity_type: str,
    entity_summary: str,
    entity_attributes: Dict[str, Any],
    context: str,
) -> str:
    """Build the LLM prompt for an individual emergency response unit (Ambulance, Doctor, Nurse, Dispatcher)."""
    attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
    context_str = context[:3000] if context else "No additional context"

    return f"""Generate a detailed emergency response unit operational profile.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Generate JSON with these exact fields:

1. bio: Unit callsign and current status summary, 200 characters max.
   Example: "AMB-07 | ALS Unit | Apollo North Base | Status: Available | Defibrillator, O2, IV Kit"
2. persona: Detailed operational dossier, 2000-character plain text, including:
   - Unit identity (callsign, unit type: ALS_Ambulance / BLS_Ambulance / Doctor_Surgeon / Trauma_Nurse / Dispatcher)
   - Base location and coverage zone (which city sectors or hospitals this unit covers)
   - Response speed profile (average response time in minutes, typical route constraints)
   - Specialty and equipment (medical specialty, equipment loadout, procedures capable of)
   - Availability pattern (shift hours, peak availability windows, current operational status)
   - Communication style (how this unit broadcasts status: terse radio vs. detailed hospital comms)
   - Known bottlenecks (traffic corridors to avoid, equipment limitations, capacity constraints)
   - Operational memory (this unit's involvement in the current emergency: what they know and have done)
3. age: Response time in minutes as integer (e.g. 8 for a unit 8 minutes away)
4. gender: Availability status — must be exactly "male" (available), "female" (en_route), or "other" (busy)
5. mbti: Unit type code — one of: "ALS_Ambulance", "BLS_Ambulance", "Doctor_Surgeon", "Trauma_Nurse",
   "Dispatcher", "BloodBank", "OperatingTheater", "Hospital"
6. country: Base location (e.g. "Apollo Hospital North Wing", "City Control Room Sector 4")
7. profession: Medical specialty or operational role
   (e.g. "Cardiac Surgeon", "Trauma Response Coordinator", "Advanced Life Support Paramedic")
8. interested_topics: Equipment and capabilities list
   (e.g. ["Defibrillator", "Advanced_Airway", "Blood_O_Neg_4_units", "Spinal_Board"])

Important:
- age must be a valid integer (response time in minutes, 1-60)
- gender must be exactly "male" (available), "female" (en_route), or "other" (busy)
- mbti must be one of the listed unit type codes
- persona must be continuous prose without newline characters
- All content must reflect realistic emergency logistics
- Respond only in English
"""


def build_group_persona_prompt(
    entity_name: str,
    entity_type: str,
    entity_summary: str,
    entity_attributes: Dict[str, Any],
    context: str,
) -> str:
    """Build the LLM prompt for a facility entity (Hospital, BloodBank, OperatingTheater, DispatchCenter)."""
    attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
    context_str = context[:3000] if context else "No additional context"

    return f"""Generate a detailed emergency facility operational profile for this institution.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Generate JSON with these exact fields:

1. bio: Facility callsign and current capacity status, 200 characters max.
   Example: "City General Hospital | L1 Trauma | OT: 2 free | ICU: 3 beds | Blood A+: 8 units"
2. persona: Detailed facility operational profile, 2000-character plain text, including:
   - Facility identity (name, type: Hospital / BloodBank / OperatingTheater / DispatchCenter)
   - Capacity status (beds available, OTs free, blood inventory by type, ICU availability)
   - Staff on duty (doctors present, nurses on shift, anesthesiologists available)
   - Communication protocol (how this facility broadcasts availability and who to contact)
   - Current patient load (how busy the facility is right now in the simulation)
   - Known constraints (equipment under maintenance, staff shortages, surge conditions)
   - Facility memory (this facility's role in the current emergency scenario)
3. age: Set to 0 (facility, not an individual)
4. gender: Set to "male" if available capacity, "other" if at capacity or unavailable
5. mbti: Set to one of: "Hospital", "BloodBank", "OperatingTheater", "DispatchCenter"
6. country: Physical location or sector (e.g. "Sector 12 Main Campus", "North District Hub")
7. profession: Facility type and level (e.g. "Level-1 Trauma Center", "Regional Blood Bank")
8. interested_topics: Current inventory and capacity list
   (e.g. ["ICU_Beds_3", "OT_Free_2", "Blood_A_Pos_8_units", "Ventilators_2"])

Important:
- age must be integer 0
- gender must be "male" (available) or "other" (at capacity / unavailable)
- mbti must be one of the listed facility type codes
- All values must reflect the current emergency simulation state
- Respond only in English
"""
