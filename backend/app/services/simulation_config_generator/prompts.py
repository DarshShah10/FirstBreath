"""
LLM prompt builders for the VahanAI Emergency Response simulation configuration generator.
"""

import json
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

TIME_CONFIG_SYSTEM_PROMPT = (
    "You are an emergency logistics simulation expert. "
    "Return pure JSON format. Time configurations represent the 60-minute Golden Hour "
    "of emergency medical response, simulated minute-by-minute. "
    "Respond only in English."
)

EVENT_CONFIG_SYSTEM_PROMPT = (
    "You are an emergency dispatch simulation expert. "
    "Return pure JSON format. Initial events are the distress signal and first dispatch commands. "
    "Note that poster_type must exactly match an available entity type. "
    "Respond only in English."
)

AGENT_CONFIGS_SYSTEM_PROMPT = (
    "You are an emergency response behavior analysis expert. "
    "Return pure JSON. Configurations must reflect real emergency logistics patterns. "
    "Respond only in English."
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_time_config_prompt(
    context: str,
    num_entities: int,
    max_agents_allowed: int,
) -> str:
    """Build the LLM prompt for generating Golden Hour time simulation configuration."""
    return f"""Based on the following emergency scenario, generate a Golden Hour simulation time configuration.

{context}

## Task
Generate a time configuration JSON for a 60-minute emergency response simulation.

### Core Principles:
- This is a minute-by-minute emergency response simulation, NOT a social media simulation.
- The "Golden Hour" is the critical 60-minute window after an emergency where patient survival
  probability drops sharply with every minute of delay.
- total_simulation_hours MUST be set to 1 (= 60 minutes total)
- minutes_per_round should be 5 (each round = 5 simulation minutes, giving 12 rounds total)
- Activity patterns follow emergency surge logic:
  - Minutes 0-10: CRITICAL DISPATCH (all units alerted, ambulances en route) — multiplier 2.0
  - Minutes 11-20: HIGH RESPONSE (ambulances en route, hospital prep begins) — multiplier 1.8
  - Minutes 21-35: PEAK TREATMENT (patient contact, triage, stabilization) — multiplier 1.5
  - Minutes 36-50: MODERATE HANDOFF (transport to hospital, handoff to ER) — multiplier 1.2
  - Minutes 51-60: RESOLUTION (post-handoff debrief, outcome assessment) — multiplier 0.8

### Return JSON format (no markdown)

Example:
{{
    "total_simulation_hours": 1,
    "minutes_per_round": 5,
    "agents_per_hour_min": 3,
    "agents_per_hour_max": {max_agents_allowed},
    "peak_hours": [0],
    "off_peak_hours": [],
    "morning_hours": [],
    "work_hours": [0],
    "reasoning": "Golden Hour: 60-minute emergency response window, 5-minute rounds"
}}

Field descriptions:
- total_simulation_hours (int): MUST be 1 (the Golden Hour = 60 minutes)
- minutes_per_round (int): Duration per round in minutes — use 5 for 12 rounds across the hour
- agents_per_hour_min (int): Minimum units active per round (range: 1–{max_agents_allowed})
- agents_per_hour_max (int): Maximum units active per round (range: 1–{max_agents_allowed})
- peak_hours (int array): [0] — the entire Golden Hour is effectively peak
- off_peak_hours (int array): [] — no off-peak in a life-or-death emergency
- morning_hours (int array): [] — not applicable
- work_hours (int array): [0] — the whole simulation is active
- reasoning (string): Brief note on emergency type and expected response timeline"""


def build_event_config_prompt(
    context: str,
    simulation_requirement: str,
    type_info: str,
) -> str:
    return f"""Based on the following emergency scenario, generate the initial dispatch events.

Emergency scenario: {simulation_requirement}

{context}

## Available unit types and examples
{type_info}

## Task
Generate an initial dispatch event configuration.

**CRITICAL RULE — You MUST include at least one bottleneck signal in initial_posts:**
A bottleneck is a unit that reports being unavailable, delayed, or at capacity at T+0.
This creates a realistic failure condition for the optimizer to analyze.

Examples of bottleneck signals:
- Primary OT occupied: poster_type "OperatingTheater", content reports OT-1 is in active surgery
- Nearest ambulance off-route: poster_type "ALS_Ambulance", content reports crew responding to prior call
- Blood type unavailable: poster_type "BloodBank", content reports O-Neg stock critically low
- Surgeon unavailable: poster_type "Doctor_Surgeon", content reports both on-call surgeons in procedure

**poster_type must match an available unit type exactly.**

Return JSON format (no markdown):
{{
    "hot_topics": ["keyword1", "keyword2", "keyword3"],
    "narrative_direction": "<timeline: Dispatch(T+0) → [BOTTLENECK at T+X: specify unit and failure] → PatientContact(T+Y) → [CONSEQUENCE: delay/escalation] → Resolution(T+60)>",
    "initial_posts": [
        {{"content": "PRIORITY-1 ALERT: [emergency description, location, patient condition]", "poster_type": "Dispatcher"}},
        {{"content": "[Primary ambulance or resource reports a PROBLEM — delayed, occupied, unavailable]", "poster_type": "<unit_type>"}},
        {{"content": "[Secondary unit responds or hospital confirms prep status]", "poster_type": "<unit_type>"}}
    ],
    "reasoning": "<identify the specific bottleneck designed into this scenario and what intervention would fix it>"
}}"""


def build_agent_configs_batch_prompt(
    simulation_requirement: str,
    entity_list: List[Dict[str, Any]],
) -> str:
    """Build the LLM prompt for generating a batch of emergency unit activity configurations."""
    return f"""Based on the following emergency scenario, generate operational configurations for each unit.

Emergency scenario: {simulation_requirement}

## Unit list
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
Generate activity configurations for each unit. Behavioral rules:

- **Dispatchers / Control Room**: Very high activity (0.9), active across all 12 rounds, response delay
  0-2 minutes, very high influence (3.0). They orchestrate the entire response chain.
- **ALS/BLS Ambulances**: High activity (0.8), most active in rounds 1-6 (en route and patient contact),
  response delay 1-5 minutes, medium influence (1.5).
- **Doctors / Surgeons**: Medium activity (0.5), most active in rounds 4-12 (receiving patient and
  operating), response delay 2-10 minutes, very high influence (2.5).
- **Trauma Nurses**: High activity (0.7), active throughout all rounds, fast response 1-3 minutes,
  medium influence (1.2).
- **BloodBank / OperatingTheater**: Low activity (0.3), respond only when requested by dispatch or
  hospital, slow response 5-20 minutes, high influence (2.0) — critical but reactive.
- **Hospitals**: Medium activity (0.4), active from round 3 onwards (prep phase begins), medium
  influence (2.0).

Sentiment bias interpretation:
- Negative (-1.0 to -0.3): Unit is overwhelmed, delayed, or reporting failure conditions
- Neutral (-0.2 to 0.2): Unit is operational, normal response
- Positive (0.3 to 1.0): Unit is performing optimally, ahead of schedule

Stance values: "responding" / "coordinating" / "waiting" / "critical"

Return JSON format (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must match input agent_id>,
            "activity_level": <0.0-1.0>,
            "posts_per_hour": <broadcast frequency per round>,
            "comments_per_hour": <response frequency per round>,
            "active_hours": [0],
            "response_delay_min": <minimum delay in minutes>,
            "response_delay_max": <maximum delay in minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<responding/coordinating/waiting/critical>",
            "influence_weight": <influence weight 0.5-3.0>
        }},
        ...
    ]
}}"""
