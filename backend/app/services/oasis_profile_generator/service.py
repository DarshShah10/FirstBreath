"""
OasisProfileGenerator — converts Zep graph entities into OASIS Agent Profiles.

Improvements over the original implementation:
1. Calls Zep retrieval to enrich entity context before generation.
2. Produces highly detailed personas via LLM prompts.
3. Distinguishes individual entities from abstract group entities.
"""

import json
import random
import time
from threading import Lock
from typing import Any, Callable, Dict, List, Optional
import concurrent.futures

from openai import OpenAI
from zep_cloud.client import Zep

from ...config import Config
from ...utils.logger import get_logger
from ..zep_entity_reader import EntityNode
from .constants import UNIT_TYPES, BASE_LOCATIONS
from .models import OasisAgentProfile
from .prompts import build_group_persona_prompt, build_individual_persona_prompt, get_system_prompt
from .utils import (
    build_entity_context,
    fix_truncated_json,
    generate_profile_rule_based,
    generate_username,
    is_individual_entity,
    normalize_gender,
    print_generated_profile,
    try_fix_json,
)

logger = get_logger('mirofish.oasis_profile')


class OasisProfileGenerator:
    """
    OASIS Profile Generator.

    Converts Zep graph entities into Agent Profiles required for OASIS simulation.

    Key features:
    1. Calls Zep graph retrieval to obtain richer context.
    2. Generates highly detailed operational dossiers (callsign, specialty, location, equipment, availability).
    3. Distinguishes individual response units from facility/institution entities.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        zep_api_key: Optional[str] = None,
        graph_id: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        # Zep client for context enrichment
        self.zep_api_key = zep_api_key or Config.ZEP_API_KEY
        self.zep_client: Optional[Zep] = None
        self.graph_id = graph_id

        if self.zep_api_key:
            try:
                self.zep_client = Zep(api_key=self.zep_api_key)
            except Exception as e:
                logger.warning(f"Zep client initialization failed: {e}")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_graph_id(self, graph_id: str) -> None:
        """Set the graph ID used for Zep retrieval."""
        self.graph_id = graph_id

    def generate_profile_from_entity(
        self,
        entity: EntityNode,
        user_id: int,
        use_llm: bool = True,
    ) -> OasisAgentProfile:
        """
        Generate an OASIS Agent Profile from a Zep entity.

        Args:
            entity: Zep entity node.
            user_id: User ID for OASIS.
            use_llm: Whether to use the LLM to generate a detailed persona.

        Returns:
            OasisAgentProfile instance.
        """
        entity_type = entity.get_entity_type() or "Entity"
        name = entity.name
        user_name = generate_username(name)

        context = build_entity_context(entity, self.zep_client, self.graph_id)

        if use_llm:
            profile_data = self._generate_profile_with_llm(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
                context=context,
            )
        else:
            profile_data = generate_profile_rule_based(
                entity_name=name,
                entity_type=entity_type,
                entity_summary=entity.summary,
                entity_attributes=entity.attributes,
            )

        return OasisAgentProfile(
            user_id=user_id,
            user_name=user_name,
            name=name,
            bio=profile_data.get("bio", f"{entity_type}: {name}"),
            persona=profile_data.get(
                "persona", entity.summary or f"A {entity_type} named {name}."
            ),
            karma=profile_data.get("karma", random.randint(500, 5000)),
            friend_count=profile_data.get("friend_count", random.randint(50, 500)),
            follower_count=profile_data.get("follower_count", random.randint(100, 1000)),
            statuses_count=profile_data.get("statuses_count", random.randint(100, 2000)),
            age=profile_data.get("age"),
            gender=profile_data.get("gender"),
            mbti=profile_data.get("mbti"),
            country=profile_data.get("country"),
            profession=profile_data.get("profession"),
            interested_topics=profile_data.get("interested_topics", []),
            source_entity_uuid=entity.uuid,
            source_entity_type=entity_type,
        )

    def generate_profiles_from_entities(
        self,
        entities: List[EntityNode],
        use_llm: bool = True,
        progress_callback: Optional[Callable] = None,
        graph_id: Optional[str] = None,
        parallel_count: int = 5,
        realtime_output_path: Optional[str] = None,
        output_platform: str = "reddit",
    ) -> List[OasisAgentProfile]:
        """
        Batch-generate Agent Profiles from a list of entities (parallel execution).

        Args:
            entities: List of entity nodes.
            use_llm: Whether to use the LLM for detailed persona generation.
            progress_callback: Optional progress callback (current, total, message).
            graph_id: Graph ID for Zep context enrichment.
            parallel_count: Number of concurrent workers (default 5).
            realtime_output_path: If provided, write results incrementally to this file.
            output_platform: Output format — "reddit" (JSON) or "twitter" (CSV).

        Returns:
            List of OasisAgentProfile instances in the same order as `entities`.
        """
        if graph_id:
            self.graph_id = graph_id

        total = len(entities)
        profiles: List[Optional[OasisAgentProfile]] = [None] * total
        completed_count = [0]
        lock = Lock()

        def save_profiles_realtime() -> None:
            """Incrementally persist already-generated profiles to disk."""
            if not realtime_output_path:
                return

            with lock:
                existing_profiles = [p for p in profiles if p is not None]
                if not existing_profiles:
                    return

                try:
                    if output_platform == "reddit":
                        profiles_data = [p.to_reddit_format() for p in existing_profiles]
                        with open(realtime_output_path, 'w', encoding='utf-8') as f:
                            json.dump(profiles_data, f, ensure_ascii=False, indent=2)
                    else:
                        import csv
                        profiles_data = [p.to_twitter_format() for p in existing_profiles]
                        if profiles_data:
                            fieldnames = list(profiles_data[0].keys())
                            with open(realtime_output_path, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.DictWriter(f, fieldnames=fieldnames)
                                writer.writeheader()
                                writer.writerows(profiles_data)
                except Exception as e:
                    logger.warning(f"Real-time profile save failed: {e}")

        def generate_single_profile(idx: int, entity: EntityNode):
            """Worker function for a single profile generation task."""
            entity_type = entity.get_entity_type() or "Entity"

            try:
                profile = self.generate_profile_from_entity(
                    entity=entity,
                    user_id=idx,
                    use_llm=use_llm,
                )
                print_generated_profile(entity.name, entity_type, profile)
                return idx, profile, None

            except Exception as e:
                logger.error(f"Failed to generate persona for entity {entity.name}: {str(e)}")
                fallback_profile = OasisAgentProfile(
                    user_id=idx,
                    user_name=generate_username(entity.name),
                    name=entity.name,
                    bio=f"{entity_type}: {entity.name}",
                    persona=entity.summary or "An emergency response unit participating in the Golden Hour.",
                    source_entity_uuid=entity.uuid,
                    source_entity_type=entity_type,
                )
                return idx, fallback_profile, str(e)

        logger.info(
            f"Starting parallel generation of {total} agent personas "
            f"(parallel workers: {parallel_count})..."
        )
        logger.info(f"{'='*60}")
        logger.info(f"Starting agent persona generation — {total} entities, {parallel_count} workers")
        logger.info(f"{'='*60}")

        with concurrent.futures.ThreadPoolExecutor(max_workers=parallel_count) as executor:
            future_to_entity = {
                executor.submit(generate_single_profile, idx, entity): (idx, entity)
                for idx, entity in enumerate(entities)
            }

            for future in concurrent.futures.as_completed(future_to_entity):
                idx, entity = future_to_entity[future]
                entity_type = entity.get_entity_type() or "Entity"

                try:
                    result_idx, profile, error = future.result()
                    profiles[result_idx] = profile

                    with lock:
                        completed_count[0] += 1
                        current = completed_count[0]

                    save_profiles_realtime()

                    if progress_callback:
                        progress_callback(
                            current,
                            total,
                            f"Completed {current}/{total}: {entity.name} ({entity_type})",
                        )

                    if error:
                        logger.warning(
                            f"[{current}/{total}] {entity.name} using fallback persona: {error}"
                        )
                    else:
                        logger.info(
                            f"[{current}/{total}] Successfully generated persona: "
                            f"{entity.name} ({entity_type})"
                        )

                except Exception as e:
                    logger.error(f"Exception while processing entity {entity.name}: {str(e)}")
                    with lock:
                        completed_count[0] += 1
                    profiles[idx] = OasisAgentProfile(
                        user_id=idx,
                        user_name=generate_username(entity.name),
                        name=entity.name,
                        bio=f"{entity_type}: {entity.name}",
                        persona=entity.summary or "An emergency response unit participating in the Golden Hour.",
                        source_entity_uuid=entity.uuid,
                        source_entity_type=entity_type,
                    )
                    save_profiles_realtime()

        logger.info(f"{'='*60}")
        logger.info(f"Persona generation complete! Generated {len([p for p in profiles if p])} agents")
        logger.info(f"{'='*60}")

        return profiles

    def save_profiles(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit",
    ) -> None:
        """
        Save profiles to a file in the correct platform format.

        OASIS platform format requirements:
        - Twitter: CSV format
        - Reddit: JSON format

        Args:
            profiles: List of OasisAgentProfile instances.
            file_path: Destination file path.
            platform: Platform type — "reddit" or "twitter".
        """
        if platform == "twitter":
            self._save_twitter_csv(profiles, file_path)
        else:
            self._save_reddit_json(profiles, file_path)

    # Backward-compatible alias
    def save_profiles_to_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
        platform: str = "reddit",
    ) -> None:
        """[Deprecated] Use save_profiles() instead."""
        logger.warning("save_profiles_to_json is deprecated; use save_profiles instead")
        self.save_profiles(profiles, file_path, platform)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _generate_profile_with_llm(
        self,
        entity_name: str,
        entity_type: str,
        entity_summary: str,
        entity_attributes: Dict[str, Any],
        context: str,
    ) -> Dict[str, Any]:
        """
        Generate a detailed persona using the LLM.

        Distinguishes between individual entities (concrete persona) and
        group/institutional entities (representative account persona).
        """
        is_individual = is_individual_entity(entity_type)

        if is_individual:
            prompt = build_individual_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )
        else:
            prompt = build_group_persona_prompt(
                entity_name, entity_type, entity_summary, entity_attributes, context
            )

        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": get_system_prompt(is_individual)},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),  # reduce temperature on each retry
                )

                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason

                if finish_reason == 'length':
                    logger.warning(
                        f"LLM output was truncated (attempt {attempt + 1}), attempting repair..."
                    )
                    content = fix_truncated_json(content)

                try:
                    result = json.loads(content)

                    # Ensure required fields are populated
                    if "bio" not in result or not result["bio"]:
                        result["bio"] = (
                            entity_summary[:200]
                            if entity_summary
                            else f"{entity_type}: {entity_name}"
                        )
                    if "persona" not in result or not result["persona"]:
                        result["persona"] = entity_summary or f"{entity_name} is a {entity_type}."

                    return result

                except json.JSONDecodeError as je:
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {str(je)[:80]}")

                    result = try_fix_json(content, entity_name, entity_type, entity_summary)
                    if result.get("_fixed"):
                        del result["_fixed"]
                        return result

                    last_error = je

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {str(e)[:80]}")
                last_error = e
                time.sleep(1 * (attempt + 1))  # exponential back-off

        logger.warning(
            f"LLM persona generation failed after {max_attempts} attempts: {last_error}; "
            f"falling back to rule-based generation"
        )
        return generate_profile_rule_based(entity_name, entity_type, entity_summary, entity_attributes)

    def _save_twitter_csv(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
    ) -> None:
        """
        Save Twitter profiles as CSV (OASIS official format).

        OASIS Twitter CSV fields:
        - user_id: User ID (sequential, starting from 0 based on CSV row order)
        - name: User's real name
        - username: System username
        - user_char: Full persona description (injected into LLM system prompt to guide agent behavior)
        - description: Short public bio (shown on user profile page)

        user_char vs description:
        - user_char: Used internally by LLM system prompt; determines how the agent thinks and acts.
        - description: Externally visible; shown to other users.
        """
        import csv

        # Ensure the file has a .csv extension
        if not file_path.endswith('.csv'):
            file_path = file_path.replace('.json', '.csv')

        with open(file_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['user_id', 'name', 'username', 'user_char', 'description'])

            for idx, profile in enumerate(profiles):
                # user_char: full persona (bio + persona) for LLM system prompt
                user_char = profile.bio
                if profile.persona and profile.persona != profile.bio:
                    user_char = f"{profile.bio} {profile.persona}"
                user_char = user_char.replace('\n', ' ').replace('\r', ' ')

                # description: short bio for external display
                description = profile.bio.replace('\n', ' ').replace('\r', ' ')

                writer.writerow([
                    idx,               # user_id: sequential from 0
                    profile.name,      # name: real name
                    profile.user_name, # username
                    user_char,         # user_char: full persona (internal LLM use)
                    description,       # description: short bio (external display)
                ])

        logger.info(
            f"Saved {len(profiles)} Twitter profiles to {file_path} (OASIS CSV format)"
        )

    def _save_reddit_json(
        self,
        profiles: List[OasisAgentProfile],
        file_path: str,
    ) -> None:
        """
        Save Reddit profiles as JSON format.

        Uses the same format as to_reddit_format(), ensuring OASIS can read them correctly.
        The user_id field is critical — it must match poster_agent_id in initial_posts
        for agent_graph.get_agent() to resolve correctly.

        Required fields:
        - user_id: integer, used to match initial_posts poster_agent_id
        - username: username string
        - name: display name
        - bio: short bio
        - persona: detailed persona
        - age: integer
        - gender: "male", "female", or "other"
        - mbti: MBTI type string
        - country: country string
        """
        data = []
        for idx, profile in enumerate(profiles):
            item = {
                "user_id": profile.user_id if profile.user_id is not None else idx,
                "username": profile.user_name,
                "name": profile.name,
                "bio": profile.bio[:150] if profile.bio else f"{profile.name}",
                "persona": profile.persona or f"{profile.name} is an emergency response unit in the Golden Hour simulation.",
                "karma": profile.karma if profile.karma else 1000,
                "created_at": profile.created_at,
                # OASIS required fields — all must have defaults
                "age": profile.age if profile.age else 30,
                "gender": normalize_gender(profile.gender),
                "mbti": profile.mbti if profile.mbti else "ISTJ",
                "country": profile.country if profile.country else "City Emergency Services",
            }

            if profile.profession:
                item["profession"] = profile.profession
            if profile.interested_topics:
                item["interested_topics"] = profile.interested_topics

            data.append(item)

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(
            f"Saved {len(profiles)} Reddit profiles to {file_path} "
            f"(JSON format with user_id field)"
        )
