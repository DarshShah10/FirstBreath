"""
LLM prompt builders for the simulation configuration generator.
"""

import json
from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# System prompts
# ---------------------------------------------------------------------------

TIME_CONFIG_SYSTEM_PROMPT = (
    "You are a social media simulation expert. "
    "Return pure JSON format. Time configurations must match Chinese daily schedule habits."
)

EVENT_CONFIG_SYSTEM_PROMPT = (
    "You are a public opinion analysis expert. "
    "Return pure JSON format. Note that poster_type must exactly match an available entity type."
)

AGENT_CONFIGS_SYSTEM_PROMPT = (
    "You are a social media behavior analysis expert. "
    "Return pure JSON. Configurations must match Chinese daily schedule habits."
)


# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------

def build_time_config_prompt(
    context: str,
    num_entities: int,
    max_agents_allowed: int,
) -> str:
    """Build the LLM prompt for generating time simulation configuration."""
    return f"""Based on the following simulation requirements, generate a time simulation configuration.

{context}

## Task
Generate a time configuration JSON.

### Basic principles (for reference — adjust flexibly based on the specific event and participant group):
- Users are based in China; the configuration must match Beijing time daily schedule habits.
- 00:00–05:00: almost no activity (activity multiplier 0.05)
- 06:00–08:00: gradually becoming active (activity multiplier 0.4)
- 09:00–18:00: moderate activity during work hours (activity multiplier 0.7)
- 19:00–22:00: peak period (activity multiplier 1.5)
- 23:00 onwards: activity declining (activity multiplier 0.5)
- General pattern: low in the early hours, rising in the morning, moderate during work hours, peak in the evening
- **Important**: The example values below are for reference only. Adjust time slots based on event nature and participant group characteristics:
  - Example: student group peak may be 21:00–23:00; media active all day; official institutions only during work hours
  - Example: breaking news may trigger late-night discussion, so off_peak_hours can be shortened appropriately

### Return JSON format (no markdown)

Example:
{{
    "total_simulation_hours": 72,
    "minutes_per_round": 60,
    "agents_per_hour_min": 5,
    "agents_per_hour_max": 50,
    "peak_hours": [19, 20, 21, 22],
    "off_peak_hours": [0, 1, 2, 3, 4, 5],
    "morning_hours": [6, 7, 8],
    "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
    "reasoning": "Time configuration notes for this event"
}}

Field descriptions:
- total_simulation_hours (int): Total simulation duration, 24–168 hours; shorter for breaking events, longer for sustained topics
- minutes_per_round (int): Duration per round, 30–120 minutes; 60 minutes recommended
- agents_per_hour_min (int): Minimum agents activated per hour (range: 1–{max_agents_allowed})
- agents_per_hour_max (int): Maximum agents activated per hour (range: 1–{max_agents_allowed})
- peak_hours (int array): Peak hours, adjusted for participant group
- off_peak_hours (int array): Off-peak hours, typically late night / early morning
- morning_hours (int array): Morning hours
- work_hours (int array): Work hours
- reasoning (string): Brief explanation of why this configuration was chosen"""


def build_event_config_prompt(
    context: str,
    simulation_requirement: str,
    type_info: str,
) -> str:
    """Build the LLM prompt for generating event configuration."""
    return f"""Based on the following simulation requirements, generate an event configuration.

Simulation requirement: {simulation_requirement}

{context}

## Available entity types and examples
{type_info}

## Task
Generate an event configuration JSON:
- Extract trending topic keywords
- Describe the direction of public opinion development
- Design initial post content; **each post must specify a poster_type (poster entity type)**

**Important**: poster_type must be chosen from the "Available entity types" listed above so that \
initial posts can be assigned to the appropriate agent for publishing.
For example: official statements should be posted by Official/University type, \
news by MediaOutlet, student opinions by Student.

Return JSON format (no markdown):
{{
    "hot_topics": ["keyword1", "keyword2", ...],
    "narrative_direction": "<description of public opinion development direction>",
    "initial_posts": [
        {{"content": "post content", "poster_type": "entity type (must be chosen from available types)"}},
        ...
    ],
    "reasoning": "<brief explanation>"
}}"""


def build_agent_configs_batch_prompt(
    simulation_requirement: str,
    entity_list: List[Dict[str, Any]],
) -> str:
    """Build the LLM prompt for generating a batch of agent activity configurations."""
    return f"""Based on the following information, generate social media activity configurations for each entity.

Simulation requirement: {simulation_requirement}

## Entity list
```json
{json.dumps(entity_list, ensure_ascii=False, indent=2)}
```

## Task
Generate activity configurations for each entity. Notes:
- **Time must match Chinese daily schedule**: almost no activity from 00:00–05:00; most active from 19:00–22:00
- **Official institutions** (University/GovernmentAgency): low activity (0.1–0.3), active during work hours (9–17), slow response (60–240 min), high influence (2.5–3.0)
- **Media** (MediaOutlet): medium activity (0.4–0.6), active all day (8–23), fast response (5–30 min), high influence (2.0–2.5)
- **Individuals** (Student/Person/Alumni): high activity (0.6–0.9), mainly evening (18–23), fast response (1–15 min), low influence (0.8–1.2)
- **Public figures / Experts**: medium activity (0.4–0.6), medium-high influence (1.5–2.0)

Return JSON format (no markdown):
{{
    "agent_configs": [
        {{
            "agent_id": <must match input>,
            "activity_level": <0.0–1.0>,
            "posts_per_hour": <posting frequency>,
            "comments_per_hour": <comment frequency>,
            "active_hours": [<list of active hours, matching Chinese schedule>],
            "response_delay_min": <minimum response delay in minutes>,
            "response_delay_max": <maximum response delay in minutes>,
            "sentiment_bias": <-1.0 to 1.0>,
            "stance": "<supportive/opposing/neutral/observer>",
            "influence_weight": <influence weight>
        }},
        ...
    ]
}}"""
