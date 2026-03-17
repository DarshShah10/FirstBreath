"""
Utility functions for the OASIS Agent Profile generator.

Covers: username generation, entity type detection, Zep graph search,
entity context building, JSON repair, rule-based profile generation,
console output, and gender normalization.
"""

import concurrent.futures
import json
import random
import re
import time
from typing import Any, Dict, List, Optional

from ....utils.logger import get_logger
from ..zep_entity_reader import EntityNode
from .constants import (
    COUNTRIES,
    GROUP_ENTITY_TYPES,
    INDIVIDUAL_ENTITY_TYPES,
    MBTI_TYPES,
)

logger = get_logger('mirofish.oasis_profile')


# ---------------------------------------------------------------------------
# Username helpers
# ---------------------------------------------------------------------------

def generate_username(name: str) -> str:
    """Generate a unique username from an entity name."""
    # Remove special characters and convert to lowercase
    username = name.lower().replace(" ", "_")
    username = ''.join(c for c in username if c.isalnum() or c == '_')

    # Append a random suffix to avoid collisions
    suffix = random.randint(100, 999)
    return f"{username}_{suffix}"


# ---------------------------------------------------------------------------
# Entity type detection
# ---------------------------------------------------------------------------

def is_individual_entity(entity_type: str) -> bool:
    """Return True if the entity type represents an individual person."""
    return entity_type.lower() in INDIVIDUAL_ENTITY_TYPES


def is_group_entity(entity_type: str) -> bool:
    """Return True if the entity type represents a group or institution."""
    return entity_type.lower() in GROUP_ENTITY_TYPES


# ---------------------------------------------------------------------------
# Zep graph search
# ---------------------------------------------------------------------------

def search_zep_for_entity(
    entity: EntityNode,
    zep_client: Any,
    graph_id: Optional[str],
) -> Dict[str, Any]:
    """
    Use Zep graph hybrid search to retrieve rich information about an entity.

    Zep has no built-in hybrid search endpoint, so edges and nodes are
    searched separately in parallel and results are merged.

    Args:
        entity: Entity node object.
        zep_client: Initialized Zep client (or None).
        graph_id: Graph ID required for search.

    Returns:
        Dict with keys 'facts', 'node_summaries', and 'context'.
    """
    if not zep_client:
        return {"facts": [], "node_summaries": [], "context": ""}

    entity_name = entity.name
    results: Dict[str, Any] = {"facts": [], "node_summaries": [], "context": ""}

    if not graph_id:
        logger.debug("Skipping Zep retrieval: graph_id not set")
        return results

    comprehensive_query = (
        f"All information, activities, events, relationships and background regarding {entity_name}"
    )

    def search_edges() -> Any:
        """Search edges (facts/relationships) with retry logic."""
        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            try:
                return zep_client.graph.search(
                    query=comprehensive_query,
                    graph_id=graph_id,
                    limit=30,
                    scope="edges",
                    reranker="rrf",
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Zep edge search attempt {attempt + 1} failed: {str(e)[:80]}, retrying..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.debug(
                        f"Zep edge search failed after {max_retries} attempts: {e}"
                    )
        return None

    def search_nodes() -> Any:
        """Search nodes (entity summaries) with retry logic."""
        max_retries = 3
        delay = 2.0
        for attempt in range(max_retries):
            try:
                return zep_client.graph.search(
                    query=comprehensive_query,
                    graph_id=graph_id,
                    limit=20,
                    scope="nodes",
                    reranker="rrf",
                )
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.debug(
                        f"Zep node search attempt {attempt + 1} failed: {str(e)[:80]}, retrying..."
                    )
                    time.sleep(delay)
                    delay *= 2
                else:
                    logger.debug(
                        f"Zep node search failed after {max_retries} attempts: {e}"
                    )
        return None

    try:
        # Run edge and node searches in parallel
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            edge_future = executor.submit(search_edges)
            node_future = executor.submit(search_nodes)

            edge_result = edge_future.result(timeout=30)
            node_result = node_future.result(timeout=30)

        # Process edge search results
        all_facts: set = set()
        if edge_result and hasattr(edge_result, 'edges') and edge_result.edges:
            for edge in edge_result.edges:
                if hasattr(edge, 'fact') and edge.fact:
                    all_facts.add(edge.fact)
        results["facts"] = list(all_facts)

        # Process node search results
        all_summaries: set = set()
        if node_result and hasattr(node_result, 'nodes') and node_result.nodes:
            for node in node_result.nodes:
                if hasattr(node, 'summary') and node.summary:
                    all_summaries.add(node.summary)
                if hasattr(node, 'name') and node.name and node.name != entity_name:
                    all_summaries.add(f"Related entity: {node.name}")
        results["node_summaries"] = list(all_summaries)

        # Build combined context
        context_parts = []
        if results["facts"]:
            context_parts.append(
                "Factual information:\n" + "\n".join(f"- {f}" for f in results["facts"][:20])
            )
        if results["node_summaries"]:
            context_parts.append(
                "Related entities:\n" + "\n".join(f"- {s}" for s in results["node_summaries"][:10])
            )
        results["context"] = "\n\n".join(context_parts)

        logger.info(
            f"Zep hybrid retrieval complete: {entity_name}, "
            f"retrieved {len(results['facts'])} facts, "
            f"{len(results['node_summaries'])} related nodes"
        )

    except concurrent.futures.TimeoutError:
        logger.warning(f"Zep retrieval timed out ({entity_name})")
    except Exception as e:
        logger.warning(f"Zep retrieval failed ({entity_name}): {e}")

    return results


# ---------------------------------------------------------------------------
# Entity context builder
# ---------------------------------------------------------------------------

def build_entity_context(
    entity: EntityNode,
    zep_client: Any,
    graph_id: Optional[str],
) -> str:
    """
    Build a comprehensive context string for an entity.

    Combines:
    1. Entity attribute information
    2. Related edge information (facts)
    3. Related node details
    4. Zep hybrid-search enrichment
    """
    context_parts = []

    # 1. Entity attributes
    if entity.attributes:
        attrs = []
        for key, value in entity.attributes.items():
            if value and str(value).strip():
                attrs.append(f"- {key}: {value}")
        if attrs:
            context_parts.append("### Entity Attributes\n" + "\n".join(attrs))

    # 2. Related edges (facts / relationships)
    existing_facts: set = set()
    if entity.related_edges:
        relationships = []
        for edge in entity.related_edges:
            fact = edge.get("fact", "")
            edge_name = edge.get("edge_name", "")
            direction = edge.get("direction", "")

            if fact:
                relationships.append(f"- {fact}")
                existing_facts.add(fact)
            elif edge_name:
                if direction == "outgoing":
                    relationships.append(f"- {entity.name} --[{edge_name}]--> (related entity)")
                else:
                    relationships.append(f"- (related entity) --[{edge_name}]--> {entity.name}")

        if relationships:
            context_parts.append(
                "### Related Facts and Relationships\n" + "\n".join(relationships)
            )

    # 3. Related node details
    if entity.related_nodes:
        related_info = []
        for node in entity.related_nodes:
            node_name = node.get("name", "")
            node_labels = node.get("labels", [])
            node_summary = node.get("summary", "")

            # Filter out default labels
            custom_labels = [l for l in node_labels if l not in ["Entity", "Node"]]
            label_str = f" ({', '.join(custom_labels)})" if custom_labels else ""

            if node_summary:
                related_info.append(f"- **{node_name}**{label_str}: {node_summary}")
            else:
                related_info.append(f"- **{node_name}**{label_str}")

        if related_info:
            context_parts.append(
                "### Related Entity Information\n" + "\n".join(related_info)
            )

    # 4. Zep hybrid search enrichment
    zep_results = search_zep_for_entity(entity, zep_client, graph_id)

    if zep_results.get("facts"):
        new_facts = [f for f in zep_results["facts"] if f not in existing_facts]
        if new_facts:
            context_parts.append(
                "### Facts Retrieved from Zep\n"
                + "\n".join(f"- {f}" for f in new_facts[:15])
            )

    if zep_results.get("node_summaries"):
        context_parts.append(
            "### Related Nodes Retrieved from Zep\n"
            + "\n".join(f"- {s}" for s in zep_results["node_summaries"][:10])
        )

    return "\n\n".join(context_parts)


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


def try_fix_json(
    content: str,
    entity_name: str,
    entity_type: str,
    entity_summary: str = "",
) -> Dict[str, Any]:
    """Attempt to repair malformed JSON and return a usable dict."""
    # 1. Try fixing truncation first
    content = fix_truncated_json(content)

    # 2. Extract the outermost JSON object
    json_match = re.search(r'\{[\s\S]*\}', content)
    if json_match:
        json_str = json_match.group()

        # 3. Fix actual newlines embedded inside string values
        def fix_string_newlines(match: re.Match) -> str:
            s = match.group(0)
            s = s.replace('\n', ' ').replace('\r', ' ')
            s = re.sub(r'\s+', ' ', s)
            return s

        json_str = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', fix_string_newlines, json_str)

        # 4. First parse attempt
        try:
            result = json.loads(json_str)
            result["_fixed"] = True
            return result
        except json.JSONDecodeError:
            # 5. Aggressive repair: strip control characters
            try:
                json_str = re.sub(r'[\x00-\x1f\x7f-\x9f]', ' ', json_str)
                json_str = re.sub(r'\s+', ' ', json_str)
                result = json.loads(json_str)
                result["_fixed"] = True
                return result
            except Exception:
                pass

    # 6. Extract partial information from the broken string
    bio_match = re.search(r'"bio"\s*:\s*"([^"]*)"', content)
    persona_match = re.search(r'"persona"\s*:\s*"([^"]*)', content)  # may be truncated

    bio = (
        bio_match.group(1)
        if bio_match
        else (entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}")
    )
    persona = (
        persona_match.group(1)
        if persona_match
        else (entity_summary or f"{entity_name} is a {entity_type}.")
    )

    if bio_match or persona_match:
        logger.info("Extracted partial information from malformed JSON")
        return {"bio": bio, "persona": persona, "_fixed": True}

    # 7. Total failure — return minimal structure
    logger.warning("JSON repair failed; returning minimal structure")
    return {
        "bio": entity_summary[:200] if entity_summary else f"{entity_type}: {entity_name}",
        "persona": entity_summary or f"{entity_name} is a {entity_type}.",
    }


# ---------------------------------------------------------------------------
# Rule-based profile generation (fallback)
# ---------------------------------------------------------------------------

def generate_profile_rule_based(
    entity_name: str,
    entity_type: str,
    entity_summary: str,
    entity_attributes: Dict[str, Any],
) -> Dict[str, Any]:
    """Generate a basic persona using rules (fallback when LLM is unavailable)."""
    entity_type_lower = entity_type.lower()

    if entity_type_lower in ["student", "alumni"]:
        return {
            "bio": f"{entity_type} with interests in academics and social issues.",
            "persona": (
                f"{entity_name} is a {entity_type.lower()} who is actively engaged in academic "
                f"and social discussions. They enjoy sharing perspectives and connecting with peers."
            ),
            "age": random.randint(18, 30),
            "gender": random.choice(["male", "female"]),
            "mbti": random.choice(MBTI_TYPES),
            "country": random.choice(COUNTRIES),
            "profession": "Student",
            "interested_topics": ["Education", "Social Issues", "Technology"],
        }

    elif entity_type_lower in ["publicfigure", "expert", "faculty"]:
        return {
            "bio": "Expert and thought leader in their field.",
            "persona": (
                f"{entity_name} is a recognized {entity_type.lower()} who shares insights and "
                f"opinions on important matters. They are known for their expertise and influence "
                f"in public discourse."
            ),
            "age": random.randint(35, 60),
            "gender": random.choice(["male", "female"]),
            "mbti": random.choice(["ENTJ", "INTJ", "ENTP", "INTP"]),
            "country": random.choice(COUNTRIES),
            "profession": entity_attributes.get("occupation", "Expert"),
            "interested_topics": ["Politics", "Economics", "Culture & Society"],
        }

    elif entity_type_lower in ["mediaoutlet", "socialmediaplatform"]:
        return {
            "bio": f"Official account for {entity_name}. News and updates.",
            "persona": (
                f"{entity_name} is a media entity that reports news and facilitates public "
                f"discourse. The account shares timely updates and engages with the audience "
                f"on current events."
            ),
            "age": 30,       # virtual age for institutional accounts
            "gender": "other",  # institutional accounts use "other"
            "mbti": "ISTJ",  # institutional style: rigorous and conservative
            "country": "中国",
            "profession": "Media",
            "interested_topics": ["General News", "Current Events", "Public Affairs"],
        }

    elif entity_type_lower in ["university", "governmentagency", "ngo", "organization"]:
        return {
            "bio": f"Official account of {entity_name}.",
            "persona": (
                f"{entity_name} is an institutional entity that communicates official positions, "
                f"announcements, and engages with stakeholders on relevant matters."
            ),
            "age": 30,       # virtual age for institutional accounts
            "gender": "other",  # institutional accounts use "other"
            "mbti": "ISTJ",  # institutional style: rigorous and conservative
            "country": "中国",
            "profession": entity_type,
            "interested_topics": ["Public Policy", "Community", "Official Announcements"],
        }

    else:
        # Default persona
        return {
            "bio": entity_summary[:150] if entity_summary else f"{entity_type}: {entity_name}",
            "persona": (
                entity_summary
                or f"{entity_name} is a {entity_type.lower()} participating in social discussions."
            ),
            "age": random.randint(25, 50),
            "gender": random.choice(["male", "female"]),
            "mbti": random.choice(MBTI_TYPES),
            "country": random.choice(COUNTRIES),
            "profession": entity_type,
            "interested_topics": ["General", "Social Issues"],
        }


# ---------------------------------------------------------------------------
# Console output
# ---------------------------------------------------------------------------

def print_generated_profile(entity_name: str, entity_type: str, profile: Any) -> None:
    """Print a generated persona to the console (full content, no truncation)."""
    separator = "-" * 70
    topics_str = ', '.join(profile.interested_topics) if profile.interested_topics else 'None'

    output_lines = [
        f"\n{separator}",
        f"[Generated] {entity_name} ({entity_type})",
        f"{separator}",
        f"Username: {profile.user_name}",
        "",
        "[Bio]",
        f"{profile.bio}",
        "",
        "[Detailed Persona]",
        f"{profile.persona}",
        "",
        "[Basic Attributes]",
        f"Age: {profile.age} | Gender: {profile.gender} | MBTI: {profile.mbti}",
        f"Profession: {profile.profession} | Country: {profile.country}",
        f"Topics of Interest: {topics_str}",
        separator,
    ]

    logger.info("\n".join(output_lines))


# ---------------------------------------------------------------------------
# Gender normalization
# ---------------------------------------------------------------------------

def normalize_gender(gender: Optional[str]) -> str:
    """
    Normalize the gender field to OASIS-required English format.

    OASIS accepts: male, female, other
    """
    if not gender:
        return "other"

    gender_lower = gender.lower().strip()

    gender_map = {
        "男": "male",
        "女": "female",
        "机构": "other",
        "其他": "other",
        "male": "male",
        "female": "female",
        "other": "other",
    }

    return gender_map.get(gender_lower, "other")
