"""
LLM prompt builders for the OASIS Agent Profile generator.
"""

import json
from typing import Any, Dict


def get_system_prompt(is_individual: bool) -> str:
    """Return the LLM system prompt for profile generation."""
    return (
        "You are a social media user persona generation expert. "
        "Generate detailed, realistic personas for public opinion simulation, "
        "restoring real-world situations to the greatest extent possible. "
        "You must return valid JSON format; all string values must not contain "
        "unescaped newline characters. Use Chinese."
    )


def build_individual_persona_prompt(
    entity_name: str,
    entity_type: str,
    entity_summary: str,
    entity_attributes: Dict[str, Any],
    context: str,
) -> str:
    """Build the LLM prompt for an individual entity persona."""
    attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
    context_str = context[:3000] if context else "No additional context"

    return f"""Generate a detailed social media user persona for this entity, \
restoring real-world situations to the greatest extent possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Please generate JSON with the following fields:

1. bio: Social media bio, 200 characters
2. persona: Detailed persona description (2000-character plain text), including:
   - Basic information (age, occupation, educational background, location)
   - Background (important experiences, connection to events, social relationships)
   - Personality traits (MBTI type, core personality, emotional expression style)
   - Social media behavior (posting frequency, content preferences, interaction style, language characteristics)
   - Stance and opinions (attitude toward topics, content that might provoke or move them)
   - Unique traits (catchphrases, special experiences, personal hobbies)
   - Personal memory (important part of the persona: describe this individual's connection to the event \
and their existing actions and reactions in the event)
3. age: Age as an integer
4. gender: Gender in English: "male" or "female"
5. mbti: MBTI type (e.g. INTJ, ENFP)
6. country: Country (use Chinese, e.g. "中国")
7. profession: Occupation
8. interested_topics: Array of topics of interest

Important:
- All field values must be strings or numbers; do not use newline characters
- persona must be a continuous prose description
- Use Chinese (except gender which must be English male/female)
- Content must be consistent with the entity information
- age must be a valid integer; gender must be "male" or "female"
"""


def build_group_persona_prompt(
    entity_name: str,
    entity_type: str,
    entity_summary: str,
    entity_attributes: Dict[str, Any],
    context: str,
) -> str:
    """Build the LLM prompt for a group / institutional entity persona."""
    attrs_str = json.dumps(entity_attributes, ensure_ascii=False) if entity_attributes else "None"
    context_str = context[:3000] if context else "No additional context"

    return f"""Generate a detailed social media account profile for this institution/group entity, \
restoring real-world situations to the greatest extent possible.

Entity name: {entity_name}
Entity type: {entity_type}
Entity summary: {entity_summary}
Entity attributes: {attrs_str}

Context information:
{context_str}

Please generate JSON with the following fields:

1. bio: Official account bio, 200 characters, professional and appropriate
2. persona: Detailed account profile description (2000-character plain text), including:
   - Basic institutional information (official name, nature of institution, founding background, main functions)
   - Account positioning (account type, target audience, core function)
   - Communication style (language characteristics, common expressions, taboo topics)
   - Content publication characteristics (content types, posting frequency, active time periods)
   - Stance and attitude (official position on core topics, approach to handling controversy)
   - Special notes (representative group profile, operational habits)
   - Institutional memory (important part of the institutional persona: describe this institution's \
connection to the event and its existing actions and reactions in the event)
3. age: Set to 30 (virtual age for institutional accounts)
4. gender: Set to "other" (institutional accounts use "other" to indicate non-personal)
5. mbti: MBTI type describing account style, e.g. ISTJ for rigorous and conservative
6. country: Country (use Chinese, e.g. "中国")
7. profession: Description of institutional function
8. interested_topics: Array of areas of focus

Important:
- All field values must be strings or numbers; null values are not allowed
- persona must be a continuous prose description without newline characters
- Use Chinese (except gender which must be English "other")
- age must be integer 30; gender must be string "other"
- Institutional account communication must match its identity positioning
"""
