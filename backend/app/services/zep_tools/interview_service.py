"""Agent interview mixin for ZepToolsService."""

import json
import re
from typing import Dict, Any, List, Optional

from ...utils.logger import get_logger

# Allowed characters for simulation IDs used in filesystem paths
_SAFE_ID_RE = re.compile(r'^[a-zA-Z0-9_-]{1,128}$')

from .base import ZepToolsBase
from .models import AgentInterview, InterviewResult
from .prompts import (
    INTERVIEW_PROMPT_PREFIX,
    SELECT_AGENTS_SYSTEM_PROMPT,
    GENERATE_QUESTIONS_SYSTEM_PROMPT,
    SUMMARIZE_INTERVIEWS_SYSTEM_PROMPT,
)

logger = get_logger('mirofish.zep_tools')


class InterviewMixin(ZepToolsBase):
    """
    Agent interview methods.

    Provides the full interview pipeline:
    - Load agent profiles from simulation files
    - Select the best agents via LLM
    - Generate interview questions via LLM
    - Call the OASIS batch interview API
    - Parse responses and build the interview report
    - Generate a consolidated summary via LLM
    """

    def interview_agents(
        self,
        simulation_id: str,
        interview_requirement: str,
        simulation_requirement: str = "",
        max_agents: int = 5,
        custom_questions: List[str] = None
    ) -> InterviewResult:
        """
        InterviewAgents — Deep Interview.

        Calls the real OASIS interview API to interview agents currently running
        in the simulation:
        1. Reads agent profile files to discover all simulation agents.
        2. Uses an LLM to analyse the interview requirement and select the most
           relevant agents.
        3. Uses an LLM to generate interview questions.
        4. Calls /api/simulation/interview/batch for real interviews
           (both platforms simultaneously).
        5. Consolidates all interview responses into an interview report.

        NOTE: Requires the simulation environment to be running (OASIS env active).

        Use cases:
        - Understanding event perspectives from different role viewpoints.
        - Collecting multi-party opinions.
        - Obtaining real agent responses (not LLM-simulated).

        Args:
            simulation_id: Simulation ID (used to locate profile files and call the API).
            interview_requirement: Interview requirement description (unstructured).
            simulation_requirement: Simulation background context (optional).
            max_agents: Maximum number of agents to interview.
            custom_questions: Custom interview questions (optional; auto-generated if omitted).

        Returns:
            InterviewResult
        """
        from ..simulation_runner import SimulationRunner

        logger.info(f"InterviewAgents deep interview (real API): {interview_requirement[:50]}...")

        result = InterviewResult(
            interview_topic=interview_requirement,
            interview_questions=custom_questions or []
        )

        # Step 1: Load agent profile files
        profiles = self._load_agent_profiles(simulation_id)

        if not profiles:
            logger.warning(f"No agent profile files found for simulation {simulation_id}")
            result.summary = "No agent profile files found for this simulation"
            return result

        result.total_agents = len(profiles)
        logger.info(f"Loaded {len(profiles)} agent profiles")

        # Step 2: Use LLM to select agents for interview (returns agent_id list)
        selected_agents, selected_indices, selection_reasoning = self._select_agents_for_interview(
            profiles=profiles,
            interview_requirement=interview_requirement,
            simulation_requirement=simulation_requirement,
            max_agents=max_agents
        )

        result.selected_agents = selected_agents
        result.selection_reasoning = selection_reasoning
        logger.info(f"Selected {len(selected_agents)} agents for interview: {selected_indices}")

        # Step 3: Generate interview questions if none were provided
        if not result.interview_questions:
            result.interview_questions = self._generate_interview_questions(
                interview_requirement=interview_requirement,
                simulation_requirement=simulation_requirement,
                selected_agents=selected_agents
            )
            logger.info(f"Generated {len(result.interview_questions)} interview questions")

        # Combine all questions into a single interview prompt
        combined_prompt = "\n".join([f"{i+1}. {q}" for i, q in enumerate(result.interview_questions)])

        # Prepend format instructions to constrain agent response format
        optimized_prompt = f"{INTERVIEW_PROMPT_PREFIX}{combined_prompt}"

        # Step 4: Call the real interview API (no platform specified → both platforms)
        try:
            # Build batch interview request (no platform → dual-platform interview)
            interviews_request = []
            for agent_idx in selected_indices:
                interviews_request.append({
                    "agent_id": agent_idx,
                    "prompt": optimized_prompt
                    # No platform specified — API interviews both twitter and reddit
                })

            logger.info(f"Calling batch interview API (dual-platform): {len(interviews_request)} agents")

            # Call SimulationRunner batch interview (no platform → dual-platform)
            api_result = SimulationRunner.interview_agents_batch(
                simulation_id=simulation_id,
                interviews=interviews_request,
                platform=None,  # No platform — dual-platform interview
                timeout=180.0   # Dual-platform needs a longer timeout
            )

            logger.info(
                f"Interview API returned: {api_result.get('interviews_count', 0)} results, "
                f"success={api_result.get('success')}"
            )

            # Check whether the API call succeeded
            if not api_result.get("success", False):
                error_msg = api_result.get("error", "unknown error")
                logger.warning(f"Interview API returned failure: {error_msg}")
                result.summary = f"Interview API call failed: {error_msg}. Please verify the OASIS simulation environment is running."
                return result

            # Step 5: Parse API response and build AgentInterview objects
            # Dual-platform response format: {"twitter_0": {...}, "reddit_0": {...}, ...}
            api_data = api_result.get("result", {})
            results_dict = api_data.get("results", {}) if isinstance(api_data, dict) else {}

            for i, agent_idx in enumerate(selected_indices):
                agent = selected_agents[i]
                agent_name = agent.get("realname", agent.get("username", f"Agent_{agent_idx}"))
                agent_role = agent.get("profession", "Unknown")
                agent_bio = agent.get("bio", "")

                # Retrieve interview responses from both platforms
                twitter_result = results_dict.get(f"twitter_{agent_idx}", {})
                reddit_result = results_dict.get(f"reddit_{agent_idx}", {})

                twitter_response = twitter_result.get("response", "")
                reddit_response = reddit_result.get("response", "")

                # Strip any tool-call JSON wrappers from responses
                twitter_response = self._clean_tool_call_response(twitter_response)
                reddit_response = self._clean_tool_call_response(reddit_response)

                # Always output dual-platform labels
                twitter_text = twitter_response if twitter_response else "(no response from this platform)"
                reddit_text = reddit_response if reddit_response else "(no response from this platform)"
                response_text = f"[Twitter Response]\n{twitter_text}\n\n[Reddit Response]\n{reddit_text}"

                # Extract key quotes from both platform responses
                import re
                combined_responses = f"{twitter_response} {reddit_response}"

                # Clean response text: strip headers, numbering, Markdown artefacts
                clean_text = re.sub(r'#{1,6}\s+', '', combined_responses)
                clean_text = re.sub(r'\{[^}]*tool_name[^}]*\}', '', clean_text)
                clean_text = re.sub(r'[*_`|>~\-]{2,}', '', clean_text)
                clean_text = re.sub(r'问题\d+[：:]\s*', '', clean_text)
                clean_text = re.sub(r'【[^】]+】', '', clean_text)

                # Strategy 1 (primary): extract complete, meaningful sentences
                sentences = re.split(r'[。！？]', clean_text)
                meaningful = [
                    s.strip() for s in sentences
                    if 20 <= len(s.strip()) <= 150
                    and not re.match(r'^[\s\W，,；;：:、]+', s.strip())
                    and not s.strip().startswith(('{', '问题'))
                ]
                meaningful.sort(key=len, reverse=True)
                key_quotes = [s + "。" for s in meaningful[:3]]

                # Strategy 2 (fallback): correctly paired Chinese quotation marks 「」
                if not key_quotes:
                    paired = re.findall(r'\u201c([^\u201c\u201d]{15,100})\u201d', clean_text)
                    paired += re.findall(r'\u300c([^\u300c\u300d]{15,100})\u300d', clean_text)
                    key_quotes = [q for q in paired if not re.match(r'^[，,；;：:、]', q)][:3]

                interview = AgentInterview(
                    agent_name=agent_name,
                    agent_role=agent_role,
                    agent_bio=agent_bio[:1000],  # Expand bio length cap
                    question=combined_prompt,
                    response=response_text,
                    key_quotes=key_quotes[:5]
                )
                result.interviews.append(interview)

            result.interviewed_count = len(result.interviews)

        except ValueError as e:
            # Simulation environment is not running
            logger.warning(f"Interview API call failed (environment not running?): {e}")
            result.summary = f"Interview failed: {str(e)}. The simulation environment may have stopped — ensure the OASIS environment is running."
            return result
        except Exception as e:
            logger.error(f"Interview API call raised an exception: {e}")
            import traceback
            logger.error(traceback.format_exc())
            result.summary = f"An error occurred during the interview: {str(e)}"
            return result

        # Step 6: Generate interview summary
        if result.interviews:
            result.summary = self._generate_interview_summary(
                interviews=result.interviews,
                interview_requirement=interview_requirement
            )

        logger.info(f"InterviewAgents complete: interviewed {result.interviewed_count} agents (dual-platform)")
        return result

    @staticmethod
    def _clean_tool_call_response(response: str) -> str:
        """Strip JSON tool-call wrappers from an agent response and return the actual text."""
        if not response or not response.strip().startswith('{'):
            return response
        text = response.strip()
        if 'tool_name' not in text[:80]:
            return response
        import re as _re
        try:
            data = json.loads(text)
            if isinstance(data, dict) and 'arguments' in data:
                for key in ('content', 'text', 'body', 'message', 'reply'):
                    if key in data['arguments']:
                        return str(data['arguments'][key])
        except (json.JSONDecodeError, KeyError, TypeError):
            match = _re.search(r'"content"\s*:\s*"((?:[^"\\]|\\.)*)"', text)
            if match:
                return match.group(1).replace('\\n', '\n').replace('\\"', '"')
        return response

    def _load_agent_profiles(self, simulation_id: str) -> List[Dict[str, Any]]:
        """Load agent profile files for the given simulation."""
        import os
        import csv

        # Validate simulation_id to prevent path traversal
        if not _SAFE_ID_RE.match(simulation_id):
            raise ValueError(f"Invalid simulation_id: {simulation_id!r}")

        # Build and normalise the profile directory path
        uploads_root = os.path.normpath(os.path.join(os.path.dirname(__file__), '../../../uploads'))
        sim_dir = os.path.normpath(os.path.join(uploads_root, 'simulations', simulation_id))

        # Boundary check — ensure we stay inside the uploads directory
        if not sim_dir.startswith(uploads_root + os.sep):
            raise ValueError(f"Resolved path escapes uploads root for simulation_id: {simulation_id!r}")

        profiles = []

        # Prefer Reddit JSON format
        reddit_profile_path = os.path.join(sim_dir, "reddit_profiles.json")
        if os.path.exists(reddit_profile_path):
            try:
                with open(reddit_profile_path, 'r', encoding='utf-8') as f:
                    profiles = json.load(f)
                logger.info(f"Loaded {len(profiles)} profiles from reddit_profiles.json")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read reddit_profiles.json: {e}")

        # Fall back to Twitter CSV format
        twitter_profile_path = os.path.join(sim_dir, "twitter_profiles.csv")
        if os.path.exists(twitter_profile_path):
            try:
                with open(twitter_profile_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Normalise CSV format to the unified profile schema
                        profiles.append({
                            "realname": row.get("name", ""),
                            "username": row.get("username", ""),
                            "bio": row.get("description", ""),
                            "persona": row.get("user_char", ""),
                            "profession": "Unknown"
                        })
                logger.info(f"Loaded {len(profiles)} profiles from twitter_profiles.csv")
                return profiles
            except Exception as e:
                logger.warning(f"Failed to read twitter_profiles.csv: {e}")

        return profiles

    def _select_agents_for_interview(
        self,
        profiles: List[Dict[str, Any]],
        interview_requirement: str,
        simulation_requirement: str,
        max_agents: int
    ) -> tuple:
        """
        Use an LLM to select the most suitable agents for an interview.

        Returns:
            tuple: (selected_agents, selected_indices, reasoning)
                - selected_agents: Full profile dicts for the chosen agents.
                - selected_indices: Integer indices of the chosen agents (used for API calls).
                - reasoning: Explanation of the selection.
        """
        # Build a compact summary list for the LLM
        agent_summaries = []
        for i, profile in enumerate(profiles):
            summary = {
                "index": i,
                "name": profile.get("realname", profile.get("username", f"Agent_{i}")),
                "profession": profile.get("profession", "Unknown"),
                "bio": profile.get("bio", "")[:200],
                "interested_topics": profile.get("interested_topics", [])
            }
            agent_summaries.append(summary)

        user_prompt = f"""Interview requirement:
{interview_requirement}

Simulation background:
{simulation_requirement if simulation_requirement else "not provided"}

Available agent list ({len(agent_summaries)} agents total):
{json.dumps(agent_summaries, ensure_ascii=False, indent=2)}

Please select up to {max_agents} agents most suitable for this interview and explain your selection rationale."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": SELECT_AGENTS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            selected_indices = response.get("selected_indices", [])[:max_agents]
            reasoning = response.get("reasoning", "Automatically selected based on relevance")

            # Resolve full profiles for the selected indices
            selected_agents = []
            valid_indices = []
            for idx in selected_indices:
                if 0 <= idx < len(profiles):
                    selected_agents.append(profiles[idx])
                    valid_indices.append(idx)

            return selected_agents, valid_indices, reasoning

        except Exception as e:
            logger.warning(f"LLM agent selection failed, using default selection: {e}")
            # Fallback: select the first N agents
            selected = profiles[:max_agents]
            indices = list(range(min(max_agents, len(profiles))))
            return selected, indices, "Using default selection strategy"

    def _generate_interview_questions(
        self,
        interview_requirement: str,
        simulation_requirement: str,
        selected_agents: List[Dict[str, Any]]
    ) -> List[str]:
        """Use an LLM to generate interview questions."""
        agent_roles = [a.get("profession", "Unknown") for a in selected_agents]

        user_prompt = f"""Interview requirement: {interview_requirement}

Simulation background: {simulation_requirement if simulation_requirement else "not provided"}

Interviewee roles: {', '.join(agent_roles)}

Please generate 3–5 interview questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": GENERATE_QUESTIONS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5
            )

            return response.get("questions", [f"What are your thoughts on: {interview_requirement}?"])

        except Exception as e:
            logger.warning(f"Interview question generation failed: {e}")
            return [
                f"What is your perspective on: {interview_requirement}?",
                "How has this affected you or the group you represent?",
                "What do you think should be done to address or improve this situation?"
            ]

    def _generate_interview_summary(
        self,
        interviews: List[AgentInterview],
        interview_requirement: str
    ) -> str:
        """Generate a consolidated summary of all interview responses."""
        if not interviews:
            return "No interviews were completed"

        # Collect all interview content
        interview_texts = []
        for interview in interviews:
            interview_texts.append(f"[{interview.agent_name} ({interview.agent_role})]\n{interview.response[:500]}")

        user_prompt = f"""Interview topic: {interview_requirement}

Interview content:
{"".join(interview_texts)}

Please generate an interview summary."""

        try:
            summary = self.llm.chat(
                messages=[
                    {"role": "system", "content": SUMMARIZE_INTERVIEWS_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=800
            )
            return summary

        except Exception as e:
            logger.warning(f"Interview summary generation failed: {e}")
            # Fallback: simple concatenation
            return f"Interviewed {len(interviews)} respondents, including: " + ", ".join([i.agent_name for i in interviews])
