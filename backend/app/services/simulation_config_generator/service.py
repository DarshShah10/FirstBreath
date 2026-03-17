"""
SimulationConfigGenerator — intelligently generates simulation parameters using an LLM.

Analyzes simulation requirements, document content, and graph entity information
to automatically produce fine-grained simulation parameter configurations.

Uses a step-by-step generation strategy to avoid failures from generating
overly long content in a single call:
1. Generate time configuration
2. Generate event configuration
3. Generate agent configurations in batches
4. Generate platform configuration
"""

import json
import math
import time
from typing import Any, Callable, Dict, List, Optional

from openai import OpenAI

from ...config import Config
from ...utils.logger import get_logger
from ..zep_entity_reader import EntityNode
from .models import (
    AgentActivityConfig,
    EventConfig,
    PlatformConfig,
    SimulationParameters,
    TimeSimulationConfig,
)
from .prompts import (
    AGENT_CONFIGS_SYSTEM_PROMPT,
    EVENT_CONFIG_SYSTEM_PROMPT,
    TIME_CONFIG_SYSTEM_PROMPT,
    build_agent_configs_batch_prompt,
    build_event_config_prompt,
    build_time_config_prompt,
)
from .utils import fix_truncated_json, generate_agent_config_by_rule, try_fix_config_json

logger = get_logger('mirofish.simulation_config')


class SimulationConfigGenerator:
    """
    Intelligent simulation configuration generator.

    Uses the LLM to analyze simulation requirements, document content, and graph entity
    information, then automatically generates the optimal simulation parameter configuration.

    Uses a step-by-step generation strategy:
    1. Generate time configuration and event configuration (lightweight)
    2. Generate agent configurations in batches (15–20 per batch)
    3. Generate platform configuration
    """

    # Maximum context character count
    MAX_CONTEXT_LENGTH = 50000
    # Number of agents generated per batch
    AGENTS_PER_BATCH = 15

    # Context truncation lengths per step (characters)
    TIME_CONFIG_CONTEXT_LENGTH = 10000    # time configuration
    EVENT_CONFIG_CONTEXT_LENGTH = 8000    # event configuration
    ENTITY_SUMMARY_LENGTH = 300           # entity summary in context
    AGENT_SUMMARY_LENGTH = 300            # entity summary in agent configuration
    ENTITIES_PER_TYPE_DISPLAY = 20        # entities displayed per type

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = api_key or Config.LLM_API_KEY
        self.base_url = base_url or Config.LLM_BASE_URL
        self.model_name = model_name or Config.LLM_MODEL_NAME

        if not self.api_key:
            raise ValueError("LLM_API_KEY is not configured")

        self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_config(
        self,
        simulation_id: str,
        project_id: str,
        graph_id: str,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
        enable_twitter: bool = True,
        enable_reddit: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ) -> SimulationParameters:
        """
        Intelligently generate a complete simulation configuration (step-by-step).

        Args:
            simulation_id: Simulation ID.
            project_id: Project ID.
            graph_id: Graph ID.
            simulation_requirement: Simulation requirement description.
            document_text: Raw document content.
            entities: Filtered entity list.
            enable_twitter: Whether to enable Twitter platform.
            enable_reddit: Whether to enable Reddit platform.
            progress_callback: Progress callback (current_step, total_steps, message).

        Returns:
            SimulationParameters: Complete simulation parameters.
        """
        logger.info(
            f"Starting intelligent simulation config generation: "
            f"simulation_id={simulation_id}, entity_count={len(entities)}"
        )

        num_batches = math.ceil(len(entities) / self.AGENTS_PER_BATCH)
        total_steps = 3 + num_batches  # time config + event config + N agent batches + platform config
        current_step = 0

        def report_progress(step: int, message: str) -> None:
            nonlocal current_step
            current_step = step
            if progress_callback:
                progress_callback(step, total_steps, message)
            logger.info(f"[{step}/{total_steps}] {message}")

        # Build base context
        context = self._build_context(
            simulation_requirement=simulation_requirement,
            document_text=document_text,
            entities=entities,
        )

        reasoning_parts = []

        # Step 1: Generate time configuration
        report_progress(1, "Generating time configuration...")
        num_entities = len(entities)
        time_config_result = self._generate_time_config(context, num_entities)
        time_config = self._parse_time_config(time_config_result, num_entities)
        reasoning_parts.append(f"Time config: {time_config_result.get('reasoning', 'success')}")

        # Step 2: Generate event configuration
        report_progress(2, "Generating event configuration and trending topics...")
        event_config_result = self._generate_event_config(context, simulation_requirement, entities)
        event_config = self._parse_event_config(event_config_result)
        reasoning_parts.append(f"Event config: {event_config_result.get('reasoning', 'success')}")

        # Steps 3–N: Generate agent configurations in batches
        all_agent_configs: List[AgentActivityConfig] = []
        for batch_idx in range(num_batches):
            start_idx = batch_idx * self.AGENTS_PER_BATCH
            end_idx = min(start_idx + self.AGENTS_PER_BATCH, len(entities))
            batch_entities = entities[start_idx:end_idx]

            report_progress(
                3 + batch_idx,
                f"Generating agent configurations ({start_idx + 1}–{end_idx}/{len(entities)})...",
            )

            batch_configs = self._generate_agent_configs_batch(
                context=context,
                entities=batch_entities,
                start_idx=start_idx,
                simulation_requirement=simulation_requirement,
            )
            all_agent_configs.extend(batch_configs)

        reasoning_parts.append(
            f"Agent configs: successfully generated {len(all_agent_configs)} configurations"
        )

        # Assign poster agents to initial posts
        logger.info("Assigning suitable poster agents to initial posts...")
        event_config = self._assign_initial_post_agents(event_config, all_agent_configs)
        assigned_count = len(
            [p for p in event_config.initial_posts if p.get("poster_agent_id") is not None]
        )
        reasoning_parts.append(f"Initial post assignment: {assigned_count} posts assigned a poster")

        # Final step: Generate platform configuration
        report_progress(total_steps, "Generating platform configuration...")
        twitter_config = None
        reddit_config = None

        if enable_twitter:
            twitter_config = PlatformConfig(
                platform="twitter",
                recency_weight=0.4,
                popularity_weight=0.3,
                relevance_weight=0.3,
                viral_threshold=10,
                echo_chamber_strength=0.5,
            )

        if enable_reddit:
            reddit_config = PlatformConfig(
                platform="reddit",
                recency_weight=0.3,
                popularity_weight=0.4,
                relevance_weight=0.3,
                viral_threshold=15,
                echo_chamber_strength=0.6,
            )

        params = SimulationParameters(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=graph_id,
            simulation_requirement=simulation_requirement,
            time_config=time_config,
            agent_configs=all_agent_configs,
            event_config=event_config,
            twitter_config=twitter_config,
            reddit_config=reddit_config,
            llm_model=self.model_name,
            llm_base_url=self.base_url,
            generation_reasoning=" | ".join(reasoning_parts),
        )

        logger.info(
            f"Simulation config generation complete: {len(params.agent_configs)} agent configurations"
        )
        return params

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(
        self,
        simulation_requirement: str,
        document_text: str,
        entities: List[EntityNode],
    ) -> str:
        """Build LLM context, truncated to the maximum allowed length."""
        entity_summary = self._summarize_entities(entities)

        context_parts = [
            f"## Simulation Requirement\n{simulation_requirement}",
            f"\n## Entity Information ({len(entities)} entities)\n{entity_summary}",
        ]

        current_length = sum(len(p) for p in context_parts)
        remaining_length = self.MAX_CONTEXT_LENGTH - current_length - 500  # 500-char buffer

        if remaining_length > 0 and document_text:
            doc_text = document_text[:remaining_length]
            if len(document_text) > remaining_length:
                doc_text += "\n...(document truncated)"
            context_parts.append(f"\n## Raw Document Content\n{doc_text}")

        return "\n".join(context_parts)

    def _summarize_entities(self, entities: List[EntityNode]) -> str:
        """Generate a brief summary of entities grouped by type."""
        lines = []

        by_type: Dict[str, List[EntityNode]] = {}
        for e in entities:
            t = e.get_entity_type() or "Unknown"
            if t not in by_type:
                by_type[t] = []
            by_type[t].append(e)

        for entity_type, type_entities in by_type.items():
            lines.append(f"\n### {entity_type} ({len(type_entities)} entities)")
            display_count = self.ENTITIES_PER_TYPE_DISPLAY
            summary_len = self.ENTITY_SUMMARY_LENGTH
            for e in type_entities[:display_count]:
                preview = (
                    (e.summary[:summary_len] + "...")
                    if len(e.summary) > summary_len
                    else e.summary
                )
                lines.append(f"- {e.name}: {preview}")
            if len(type_entities) > display_count:
                lines.append(f"  ... and {len(type_entities) - display_count} more")

        return "\n".join(lines)

    def _call_llm_with_retry(self, prompt: str, system_prompt: str) -> Dict[str, Any]:
        """Call the LLM with retry logic and JSON repair."""
        max_attempts = 3
        last_error = None

        for attempt in range(max_attempts):
            try:
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt},
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.7 - (attempt * 0.1),  # reduce temperature on each retry
                )

                content = response.choices[0].message.content
                finish_reason = response.choices[0].finish_reason

                if finish_reason == 'length':
                    logger.warning(f"LLM output was truncated (attempt {attempt + 1})")
                    content = fix_truncated_json(content)

                try:
                    return json.loads(content)
                except json.JSONDecodeError as e:
                    logger.warning(f"JSON parse failed (attempt {attempt + 1}): {str(e)[:80]}")
                    fixed = try_fix_config_json(content)
                    if fixed:
                        return fixed
                    last_error = e

            except Exception as e:
                logger.warning(f"LLM call failed (attempt {attempt + 1}): {str(e)[:80]}")
                last_error = e
                time.sleep(2 * (attempt + 1))

        raise last_error or Exception("LLM call failed after all retries")

    def _generate_time_config(self, context: str, num_entities: int) -> Dict[str, Any]:
        """Generate time simulation configuration via LLM."""
        context_truncated = context[:self.TIME_CONFIG_CONTEXT_LENGTH]
        max_agents_allowed = max(1, int(num_entities * 0.9))

        prompt = build_time_config_prompt(context_truncated, num_entities, max_agents_allowed)

        try:
            return self._call_llm_with_retry(prompt, TIME_CONFIG_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"LLM time config generation failed: {e}; using default config")
            return self._get_default_time_config(num_entities)

    def _get_default_time_config(self, num_entities: int) -> Dict[str, Any]:
        """Return default time configuration based on Chinese daily schedule."""
        return {
            "total_simulation_hours": 72,
            "minutes_per_round": 60,  # 1 hour per round to speed up time flow
            "agents_per_hour_min": max(1, num_entities // 15),
            "agents_per_hour_max": max(5, num_entities // 5),
            "peak_hours": [19, 20, 21, 22],
            "off_peak_hours": [0, 1, 2, 3, 4, 5],
            "morning_hours": [6, 7, 8],
            "work_hours": [9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
            "reasoning": "Default Chinese daily schedule configuration (1 hour per round)",
        }

    def _parse_time_config(
        self, result: Dict[str, Any], num_entities: int
    ) -> TimeSimulationConfig:
        """Parse time configuration result and validate agents_per_hour values."""
        agents_per_hour_min = result.get("agents_per_hour_min", max(1, num_entities // 15))
        agents_per_hour_max = result.get("agents_per_hour_max", max(5, num_entities // 5))

        if agents_per_hour_min > num_entities:
            logger.warning(
                f"agents_per_hour_min ({agents_per_hour_min}) exceeds total agent count "
                f"({num_entities}); corrected"
            )
            agents_per_hour_min = max(1, num_entities // 10)

        if agents_per_hour_max > num_entities:
            logger.warning(
                f"agents_per_hour_max ({agents_per_hour_max}) exceeds total agent count "
                f"({num_entities}); corrected"
            )
            agents_per_hour_max = max(agents_per_hour_min + 1, num_entities // 2)

        if agents_per_hour_min >= agents_per_hour_max:
            agents_per_hour_min = max(1, agents_per_hour_max // 2)
            logger.warning(
                f"agents_per_hour_min >= max; corrected to {agents_per_hour_min}"
            )

        return TimeSimulationConfig(
            total_simulation_hours=result.get("total_simulation_hours", 72),
            minutes_per_round=result.get("minutes_per_round", 60),
            agents_per_hour_min=agents_per_hour_min,
            agents_per_hour_max=agents_per_hour_max,
            peak_hours=result.get("peak_hours", [19, 20, 21, 22]),
            off_peak_hours=result.get("off_peak_hours", [0, 1, 2, 3, 4, 5]),
            off_peak_activity_multiplier=0.05,  # almost no activity in early morning
            morning_hours=result.get("morning_hours", [6, 7, 8]),
            morning_activity_multiplier=0.4,
            work_hours=result.get("work_hours", list(range(9, 19))),
            work_activity_multiplier=0.7,
            peak_activity_multiplier=1.5,
        )

    def _generate_event_config(
        self,
        context: str,
        simulation_requirement: str,
        entities: List[EntityNode],
    ) -> Dict[str, Any]:
        """Generate event configuration via LLM."""
        # Build entity type list for LLM reference
        type_examples: Dict[str, list] = {}
        for e in entities:
            etype = e.get_entity_type() or "Unknown"
            if etype not in type_examples:
                type_examples[etype] = []
            if len(type_examples[etype]) < 3:
                type_examples[etype].append(e.name)

        type_info = "\n".join(
            f"- {t}: {', '.join(examples)}" for t, examples in type_examples.items()
        )

        context_truncated = context[:self.EVENT_CONFIG_CONTEXT_LENGTH]
        prompt = build_event_config_prompt(context_truncated, simulation_requirement, type_info)

        try:
            return self._call_llm_with_retry(prompt, EVENT_CONFIG_SYSTEM_PROMPT)
        except Exception as e:
            logger.warning(f"LLM event config generation failed: {e}; using default config")
            return {
                "hot_topics": [],
                "narrative_direction": "",
                "initial_posts": [],
                "reasoning": "Using default configuration",
            }

    def _parse_event_config(self, result: Dict[str, Any]) -> EventConfig:
        """Parse event configuration result."""
        return EventConfig(
            initial_posts=result.get("initial_posts", []),
            scheduled_events=[],
            hot_topics=result.get("hot_topics", []),
            narrative_direction=result.get("narrative_direction", ""),
        )

    def _assign_initial_post_agents(
        self,
        event_config: EventConfig,
        agent_configs: List[AgentActivityConfig],
    ) -> EventConfig:
        """
        Assign suitable poster agents to initial posts.

        Matches each post's poster_type to the most appropriate agent_id.
        """
        if not event_config.initial_posts:
            return event_config

        # Build agent index by entity type
        agents_by_type: Dict[str, List[AgentActivityConfig]] = {}
        for agent in agent_configs:
            etype = agent.entity_type.lower()
            if etype not in agents_by_type:
                agents_by_type[etype] = []
            agents_by_type[etype].append(agent)

        # Type alias map to handle variant LLM output formats
        type_aliases = {
            "official": ["official", "university", "governmentagency", "government"],
            "university": ["university", "official"],
            "mediaoutlet": ["mediaoutlet", "media"],
            "student": ["student", "person"],
            "professor": ["professor", "expert", "teacher"],
            "alumni": ["alumni", "person"],
            "organization": ["organization", "ngo", "company", "group"],
            "person": ["person", "student", "alumni"],
        }

        # Track next agent index per type to avoid reusing the same agent
        used_indices: Dict[str, int] = {}

        updated_posts = []
        for post in event_config.initial_posts:
            poster_type = post.get("poster_type", "").lower()
            content = post.get("content", "")
            matched_agent_id = None

            # 1. Direct match
            if poster_type in agents_by_type:
                agents = agents_by_type[poster_type]
                idx = used_indices.get(poster_type, 0) % len(agents)
                matched_agent_id = agents[idx].agent_id
                used_indices[poster_type] = idx + 1
            else:
                # 2. Alias match
                for alias_key, aliases in type_aliases.items():
                    if poster_type in aliases or alias_key == poster_type:
                        for alias in aliases:
                            if alias in agents_by_type:
                                agents = agents_by_type[alias]
                                idx = used_indices.get(alias, 0) % len(agents)
                                matched_agent_id = agents[idx].agent_id
                                used_indices[alias] = idx + 1
                                break
                    if matched_agent_id is not None:
                        break

            # 3. Fallback: use the most influential agent
            if matched_agent_id is None:
                logger.warning(
                    f"No agent found for type '{poster_type}'; "
                    f"using the highest-influence agent"
                )
                if agent_configs:
                    sorted_agents = sorted(
                        agent_configs, key=lambda a: a.influence_weight, reverse=True
                    )
                    matched_agent_id = sorted_agents[0].agent_id
                else:
                    matched_agent_id = 0

            updated_posts.append({
                "content": content,
                "poster_type": post.get("poster_type", "Unknown"),
                "poster_agent_id": matched_agent_id,
            })

            logger.info(
                f"Initial post assignment: poster_type='{poster_type}' -> agent_id={matched_agent_id}"
            )

        event_config.initial_posts = updated_posts
        return event_config

    def _generate_agent_configs_batch(
        self,
        context: str,
        entities: List[EntityNode],
        start_idx: int,
        simulation_requirement: str,
    ) -> List[AgentActivityConfig]:
        """Generate a batch of agent activity configurations."""
        entity_list = []
        summary_len = self.AGENT_SUMMARY_LENGTH
        for i, e in enumerate(entities):
            entity_list.append({
                "agent_id": start_idx + i,
                "entity_name": e.name,
                "entity_type": e.get_entity_type() or "Unknown",
                "summary": e.summary[:summary_len] if e.summary else "",
            })

        prompt = build_agent_configs_batch_prompt(simulation_requirement, entity_list)

        try:
            result = self._call_llm_with_retry(prompt, AGENT_CONFIGS_SYSTEM_PROMPT)
            llm_configs = {cfg["agent_id"]: cfg for cfg in result.get("agent_configs", [])}
        except Exception as e:
            logger.warning(f"LLM agent config batch generation failed: {e}; using rule-based generation")
            llm_configs = {}

        configs: List[AgentActivityConfig] = []
        for i, entity in enumerate(entities):
            agent_id = start_idx + i
            cfg = llm_configs.get(agent_id, {})

            if not cfg:
                cfg = generate_agent_config_by_rule(entity)

            configs.append(AgentActivityConfig(
                agent_id=agent_id,
                entity_uuid=entity.uuid,
                entity_name=entity.name,
                entity_type=entity.get_entity_type() or "Unknown",
                activity_level=cfg.get("activity_level", 0.5),
                posts_per_hour=cfg.get("posts_per_hour", 0.5),
                comments_per_hour=cfg.get("comments_per_hour", 1.0),
                active_hours=cfg.get("active_hours", list(range(9, 23))),
                response_delay_min=cfg.get("response_delay_min", 5),
                response_delay_max=cfg.get("response_delay_max", 60),
                sentiment_bias=cfg.get("sentiment_bias", 0.0),
                stance=cfg.get("stance", "neutral"),
                influence_weight=cfg.get("influence_weight", 1.0),
            ))

        return configs
