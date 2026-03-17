"""
Utility functions for the simulation configuration generator.

Covers: JSON repair and rule-based agent configuration generation.
"""

import json
import re
from typing import Any, Dict, Optional

from ..zep_entity_reader import EntityNode


# ---------------------------------------------------------------------------
# JSON repair utilities
# ---------------------------------------------------------------------------

def fix_truncated_json(content: str) -> str:
    """Repair JSON that was truncated by a token limit."""
    content = content.strip()

    # Count unclosed brackets
    open_braces = content.count('{') - content.count('}')
    open_brackets = content.count('[') - content.count(']')

    # Close any unclosed string literal
    if content and content[-1] not in '",}]':
        content += '"'

    # Close brackets
    content += ']' * open_brackets
    content += '}' * open_braces

    return content


def try_fix_config_json(content: str) -> Optional[Dict[str, Any]]:
    """Attempt to repair a malformed configuration JSON string."""
    content = fix_truncated_json(content)

    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        json_str = json_match.group()

        # Remove embedded newlines inside string values
        def fix_string(match: re.Match) -> str:
            s = match.group(0)
            s = s.replace('\n', ' ').replace('\r', ' ')
            s = re.sub(r'\s+', ' ', s)
            return s

        json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string, json_str)

        try:
            return json.loads(json_str)
        except Exception:
            # Aggressive repair: strip control characters
            try:
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                return json.loads(json_str)
            except Exception:
                pass

    return None


# ---------------------------------------------------------------------------
# Rule-based agent configuration (fallback)
# ---------------------------------------------------------------------------

def generate_agent_config_by_rule(entity: EntityNode) -> Dict[str, Any]:
    """
    Generate a single agent configuration using rules (fallback when LLM is unavailable).

    Activity patterns are based on Chinese daily schedule habits (Beijing time).
    """
    entity_type = (entity.get_entity_type() or "Unknown").lower()

    if entity_type in ["university", "governmentagency", "ngo"]:
        # Official institutions: active during work hours, low frequency, high influence
        return {
            "activity_level": 0.2,
            "posts_per_hour": 0.1,
            "comments_per_hour": 0.05,
            "active_hours": list(range(9, 18)),   # 09:00–17:59
            "response_delay_min": 60,
            "response_delay_max": 240,
            "sentiment_bias": 0.0,
            "stance": "neutral",
            "influence_weight": 3.0,
        }

    elif entity_type in ["mediaoutlet"]:
        # Media: active all day, medium frequency, high influence
        return {
            "activity_level": 0.5,
            "posts_per_hour": 0.8,
            "comments_per_hour": 0.3,
            "active_hours": list(range(7, 24)),   # 07:00–23:59
            "response_delay_min": 5,
            "response_delay_max": 30,
            "sentiment_bias": 0.0,
            "stance": "observer",
            "influence_weight": 2.5,
        }

    elif entity_type in ["professor", "expert", "official"]:
        # Experts / professors: active during work hours and evening, medium frequency
        return {
            "activity_level": 0.4,
            "posts_per_hour": 0.3,
            "comments_per_hour": 0.5,
            "active_hours": list(range(8, 22)),   # 08:00–21:59
            "response_delay_min": 15,
            "response_delay_max": 90,
            "sentiment_bias": 0.0,
            "stance": "neutral",
            "influence_weight": 2.0,
        }

    elif entity_type in ["student"]:
        # Students: primarily evening, high frequency
        return {
            "activity_level": 0.8,
            "posts_per_hour": 0.6,
            "comments_per_hour": 1.5,
            "active_hours": [8, 9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # morning + evening
            "response_delay_min": 1,
            "response_delay_max": 15,
            "sentiment_bias": 0.0,
            "stance": "neutral",
            "influence_weight": 0.8,
        }

    elif entity_type in ["alumni"]:
        # Alumni: primarily evening
        return {
            "activity_level": 0.6,
            "posts_per_hour": 0.4,
            "comments_per_hour": 0.8,
            "active_hours": [12, 13, 19, 20, 21, 22, 23],  # lunch break + evening
            "response_delay_min": 5,
            "response_delay_max": 30,
            "sentiment_bias": 0.0,
            "stance": "neutral",
            "influence_weight": 1.0,
        }

    else:
        # Default: evening peak
        return {
            "activity_level": 0.7,
            "posts_per_hour": 0.5,
            "comments_per_hour": 1.2,
            "active_hours": [9, 10, 11, 12, 13, 18, 19, 20, 21, 22, 23],  # daytime + evening
            "response_delay_min": 2,
            "response_delay_max": 20,
            "sentiment_bias": 0.0,
            "stance": "neutral",
            "influence_weight": 1.0,
        }
