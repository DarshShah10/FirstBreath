"""
Report Agent service.

Implements ReACT (Reasoning + Acting) pattern for simulation report generation:
1. Planning phase: analyze the simulation requirement and plan the report outline
2. Generation phase: generate content section by section, each section may call tools
3. Assembly phase: assemble the final complete report
"""

import json
import re
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime

from ...config import Config
from ...utils.llm_client import LLMClient
from ...utils.logger import get_logger
from ..neo4j_tools_service import (
    Neo4jToolsService as ZepToolsService,
)
from .models import Report, ReportSection, ReportOutline, ReportStatus
from .loggers import ReportLogger, ReportConsoleLogger
from .manager import ReportManager
from .prompts import (
    TOOL_DESC_INSIGHT_FORGE,
    TOOL_DESC_PANORAMA_SEARCH,
    TOOL_DESC_QUICK_SEARCH,
    TOOL_DESC_INTERVIEW_AGENTS,
    PLAN_SYSTEM_PROMPT,
    PLAN_USER_PROMPT_TEMPLATE,
    SECTION_SYSTEM_PROMPT_TEMPLATE,
    SECTION_USER_PROMPT_TEMPLATE,
    REACT_OBSERVATION_TEMPLATE,
    REACT_INSUFFICIENT_TOOLS_MSG,
    REACT_INSUFFICIENT_TOOLS_MSG_ALT,
    REACT_TOOL_LIMIT_MSG,
    REACT_UNUSED_TOOLS_HINT,
    REACT_FORCE_FINAL_MSG,
    CHAT_SYSTEM_PROMPT_TEMPLATE,
    CHAT_OBSERVATION_SUFFIX,
)

logger = get_logger('mirofish.report_agent')


class ReportAgent:
    """
    Report Agent — simulation report generation agent.

    Uses ReACT (Reasoning + Acting) pattern:
    1. Planning phase: analyze simulation requirement, plan report outline
    2. Generation phase: generate content section by section, each section may call tools multiple times
    3. Reflection phase: check content completeness and accuracy
    """

    # Maximum tool calls per section
    MAX_TOOL_CALLS_PER_SECTION = 5

    # Maximum reflection rounds
    MAX_REFLECTION_ROUNDS = 3

    # Maximum tool calls per chat turn
    MAX_TOOL_CALLS_PER_CHAT = 2

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        simulation_requirement: str,
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None
    ):
        """
        Initialize Report Agent.

        Args:
            graph_id: Graph ID.
            simulation_id: Simulation ID.
            simulation_requirement: Simulation requirement description.
            llm_client: LLM client (optional).
            zep_tools: Zep tools service (optional).
        """
        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.simulation_requirement = simulation_requirement

        self.llm = llm_client or LLMClient()
        self.zep_tools = zep_tools or ZepToolsService()

        self.tools = self._define_tools()

        # Initialized in generate_report
        self.report_logger: Optional[ReportLogger] = None
        self.console_logger: Optional[ReportConsoleLogger] = None

        logger.info(f"ReportAgent initialized: graph_id={graph_id}, simulation_id={simulation_id}")

    def _define_tools(self) -> Dict[str, Dict[str, Any]]:
        """Define available tools."""
        return {
            "insight_forge": {
                "name": "insight_forge",
                "description": TOOL_DESC_INSIGHT_FORGE,
                "parameters": {
                    "query": "The question or topic you want to analyze in depth",
                    "report_context": "Context of the current report section (optional, helps generate more precise sub-questions)"
                }
            },
            "panorama_search": {
                "name": "panorama_search",
                "description": TOOL_DESC_PANORAMA_SEARCH,
                "parameters": {
                    "query": "Search query for relevance ranking",
                    "include_expired": "Whether to include expired/historical content (default True)"
                }
            },
            "quick_search": {
                "name": "quick_search",
                "description": TOOL_DESC_QUICK_SEARCH,
                "parameters": {
                    "query": "Search query string",
                    "limit": "Number of results to return (optional, default 10)"
                }
            },
            "interview_agents": {
                "name": "interview_agents",
                "description": TOOL_DESC_INTERVIEW_AGENTS,
                "parameters": {
                    "interview_topic": "Interview topic or requirement (e.g. 'understand student views on dormitory formaldehyde incident')",
                    "max_agents": "Maximum number of agents to interview (optional, default 5, max 10)"
                }
            }
        }

    def _execute_tool(self, tool_name: str, parameters: Dict[str, Any], report_context: str = "") -> str:
        """
        Execute a tool call.

        Args:
            tool_name: Tool name.
            parameters: Tool parameters.
            report_context: Report context (used by InsightForge).

        Returns:
            Tool execution result as text.
        """
        logger.info(f"Executing tool: {tool_name}, parameters: {parameters}")

        try:
            if tool_name == "insight_forge":
                query = parameters.get("query", "")
                ctx = parameters.get("report_context", "") or report_context
                result = self.zep_tools.insight_forge(
                    graph_id=self.graph_id,
                    query=query,
                    simulation_requirement=self.simulation_requirement,
                    report_context=ctx
                )
                return result.to_text()

            elif tool_name == "panorama_search":
                query = parameters.get("query", "")
                include_expired = parameters.get("include_expired", True)
                if isinstance(include_expired, str):
                    include_expired = include_expired.lower() in ['true', '1', 'yes']
                result = self.zep_tools.panorama_search(
                    graph_id=self.graph_id,
                    query=query,
                    include_expired=include_expired
                )
                return result.to_text()

            elif tool_name == "quick_search":
                query = parameters.get("query", "")
                limit = parameters.get("limit", 10)
                if isinstance(limit, str):
                    limit = int(limit)
                result = self.zep_tools.quick_search(
                    graph_id=self.graph_id,
                    query=query,
                    limit=limit
                )
                return result.to_text()

            elif tool_name == "interview_agents":
                interview_topic = parameters.get("interview_topic", parameters.get("query", ""))
                max_agents = parameters.get("max_agents", 5)
                if isinstance(max_agents, str):
                    max_agents = int(max_agents)
                max_agents = min(max_agents, 10)
                result = self.zep_tools.interview_agents(
                    simulation_id=self.simulation_id,
                    interview_requirement=interview_topic,
                    simulation_requirement=self.simulation_requirement,
                    max_agents=max_agents
                )
                return result.to_text()

            # ── Backward-compatible legacy tools (redirect internally) ──

            elif tool_name == "search_graph":
                logger.info("search_graph redirected to quick_search")
                return self._execute_tool("quick_search", parameters, report_context)

            elif tool_name == "get_graph_statistics":
                result = self.zep_tools.get_graph_statistics(self.graph_id)
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_entity_summary":
                entity_name = parameters.get("entity_name", "")
                result = self.zep_tools.get_entity_summary(
                    graph_id=self.graph_id,
                    entity_name=entity_name
                )
                return json.dumps(result, ensure_ascii=False, indent=2)

            elif tool_name == "get_simulation_context":
                logger.info("get_simulation_context redirected to insight_forge")
                query = parameters.get("query", self.simulation_requirement)
                return self._execute_tool("insight_forge", {"query": query}, report_context)

            elif tool_name == "get_entities_by_type":
                entity_type = parameters.get("entity_type", "")
                nodes = self.zep_tools.get_entities_by_type(
                    graph_id=self.graph_id,
                    entity_type=entity_type
                )
                result = [n.to_dict() for n in nodes]
                return json.dumps(result, ensure_ascii=False, indent=2)

            else:
                return f"Unknown tool: {tool_name}. Please use one of: insight_forge, panorama_search, quick_search"

        except Exception as e:
            logger.error(f"Tool execution failed: {tool_name}, error: {str(e)}")
            return f"Tool execution failed: {str(e)}"

    # Valid tool names used for bare-JSON fallback parsing validation
    VALID_TOOL_NAMES = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

    def _parse_tool_calls(self, response: str) -> List[Dict[str, Any]]:
        """
        Parse tool calls from LLM response.

        Supported formats (in priority order):
        1. <tool_call>{"name": "tool_name", "parameters": {...}}</tool_call>
        2. Bare JSON (the entire response or a single line is a tool call JSON)
        """
        tool_calls = []

        # Format 1: XML-style (standard format)
        xml_pattern = r'<tool_call>\s*(\{.*?\})\s*</tool_call>'
        for match in re.finditer(xml_pattern, response, re.DOTALL):
            try:
                call_data = json.loads(match.group(1))
                tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        if tool_calls:
            return tool_calls

        # Format 2: fallback — LLM outputs bare JSON (no <tool_call> tags)
        # Only tried when format 1 did not match, to avoid false positives in body text
        stripped = response.strip()
        if stripped.startswith('{') and stripped.endswith('}'):
            try:
                call_data = json.loads(stripped)
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
                    return tool_calls
            except json.JSONDecodeError:
                pass

        # Response may have thought text + bare JSON — try extracting last JSON object
        json_pattern = r'(\{"(?:name|tool)"\s*:.*?\})\s*$'
        match = re.search(json_pattern, stripped, re.DOTALL)
        if match:
            try:
                call_data = json.loads(match.group(1))
                if self._is_valid_tool_call(call_data):
                    tool_calls.append(call_data)
            except json.JSONDecodeError:
                pass

        return tool_calls

    def _is_valid_tool_call(self, data: dict) -> bool:
        """Validate that a parsed JSON object is a valid tool call."""
        # Support both {"name": ..., "parameters": ...} and {"tool": ..., "params": ...}
        tool_name = data.get("name") or data.get("tool")
        if tool_name and tool_name in self.VALID_TOOL_NAMES:
            if "tool" in data:
                data["name"] = data.pop("tool")
            if "params" in data and "parameters" not in data:
                data["parameters"] = data.pop("params")
            return True
        return False

    def _get_tools_description(self) -> str:
        """Generate tool description text."""
        desc_parts = ["Available tools:"]
        for name, tool in self.tools.items():
            params_desc = ", ".join([f"{k}: {v}" for k, v in tool["parameters"].items()])
            desc_parts.append(f"- {name}: {tool['description']}")
            if params_desc:
                desc_parts.append(f"  Parameters: {params_desc}")
        return "\n".join(desc_parts)

    def plan_outline(
        self,
        progress_callback: Optional[Callable] = None
    ) -> ReportOutline:
        """
        Plan the report outline.

        Uses the LLM to analyze the simulation requirement and plan the report structure.

        Args:
            progress_callback: Progress callback function.

        Returns:
            ReportOutline: Report outline.
        """
        logger.info("Starting report outline planning...")

        if progress_callback:
            progress_callback("planning", 0, "Analyzing simulation requirement...")

        context = self.zep_tools.get_simulation_context(
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement
        )

        if progress_callback:
            progress_callback("planning", 30, "Generating report outline...")

        system_prompt = PLAN_SYSTEM_PROMPT
        user_prompt = PLAN_USER_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            total_nodes=context.get('graph_statistics', {}).get('total_nodes', 0),
            total_edges=context.get('graph_statistics', {}).get('total_edges', 0),
            entity_types=list(context.get('graph_statistics', {}).get('entity_types', {}).keys()),
            total_entities=context.get('total_entities', 0),
            related_facts_json=json.dumps(context.get('related_facts', [])[:10], ensure_ascii=False, indent=2),
        )

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            if progress_callback:
                progress_callback("planning", 80, "Parsing outline structure...")

            sections = []
            for section_data in response.get("sections", []):
                sections.append(ReportSection(
                    title=section_data.get("title", ""),
                    content=""
                ))

            outline = ReportOutline(
                title=response.get("title", "Simulation Analysis Report"),
                summary=response.get("summary", ""),
                sections=sections
            )

            if progress_callback:
                progress_callback("planning", 100, "Outline planning complete")

            logger.info(f"Outline planning complete: {len(sections)} sections")
            return outline

        except Exception as e:
            logger.error(f"Outline planning failed: {str(e)}")
            # Fallback outline with 3 sections
            return ReportOutline(
                title="Future Prediction Report",
                summary="Future trends and risk analysis based on simulation predictions",
                sections=[
                    ReportSection(title="Prediction Scenario and Core Findings"),
                    ReportSection(title="Population Behavior Prediction Analysis"),
                    ReportSection(title="Trend Outlook and Risk Warnings")
                ]
            )

    def _generate_section_react(
        self,
        section: ReportSection,
        outline: ReportOutline,
        previous_sections: List[str],
        progress_callback: Optional[Callable] = None,
        section_index: int = 0
    ) -> str:
        """
        Generate a single section using the ReACT pattern.

        ReACT loop:
        1. Thought — determine what information is needed
        2. Action — call a tool to retrieve information
        3. Observation — analyze tool results
        4. Repeat until sufficient information or iteration limit reached
        5. Final Answer — generate section content

        Args:
            section: Section to generate.
            outline: Full outline.
            previous_sections: Content of previous sections (for coherence).
            progress_callback: Progress callback.
            section_index: Section index (for logging).

        Returns:
            Section content in Markdown format.
        """
        logger.info(f"ReACT generating section: {section.title}")

        if self.report_logger:
            self.report_logger.log_section_start(section.title, section_index)

        system_prompt = SECTION_SYSTEM_PROMPT_TEMPLATE.format(
            report_title=outline.title,
            report_summary=outline.summary,
            simulation_requirement=self.simulation_requirement,
            section_title=section.title,
            tools_description=self._get_tools_description(),
        )

        # Build user prompt — each completed section truncated to 4000 chars
        if previous_sections:
            previous_parts = []
            for sec in previous_sections:
                truncated = sec[:4000] + "..." if len(sec) > 4000 else sec
                previous_parts.append(truncated)
            previous_content = "\n\n---\n\n".join(previous_parts)
        else:
            previous_content = "(This is the first section)"

        user_prompt = SECTION_USER_PROMPT_TEMPLATE.format(
            previous_content=previous_content,
            section_title=section.title,
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        tool_calls_count = 0
        max_iterations = 5
        min_tool_calls = 3
        conflict_retries = 0
        used_tools = set()
        all_tools = {"insight_forge", "panorama_search", "quick_search", "interview_agents"}

        report_context = f"Section title: {section.title}\nSimulation requirement: {self.simulation_requirement}"

        for iteration in range(max_iterations):
            if progress_callback:
                progress_callback(
                    "generating",
                    int((iteration / max_iterations) * 100),
                    f"Deep retrieval and writing ({tool_calls_count}/{self.MAX_TOOL_CALLS_PER_SECTION})"
                )

            response = self.llm.chat(
                messages=messages,
                temperature=0.5,
                max_tokens=4096
            )

            if response is None:
                logger.warning(f"Section {section.title} iteration {iteration + 1}: LLM returned None")
                if iteration < max_iterations - 1:
                    messages.append({"role": "assistant", "content": "(empty response)"})
                    messages.append({"role": "user", "content": "Please continue generating content."})
                    continue
                break

            logger.debug(f"LLM response: {response[:200]}...")

            tool_calls = self._parse_tool_calls(response)
            has_tool_calls = bool(tool_calls)
            has_final_answer = "Final Answer:" in response

            # ── Conflict handling: LLM output both tool call and Final Answer ──
            if has_tool_calls and has_final_answer:
                conflict_retries += 1
                logger.warning(
                    f"Section {section.title} iteration {iteration + 1}: "
                    f"LLM output both tool call and Final Answer (conflict #{conflict_retries})"
                )

                if conflict_retries <= 2:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": (
                            "[Format Error] You included both a tool call and Final Answer in one reply — this is not allowed.\n"
                            "Each reply must do ONLY ONE of the following:\n"
                            "- Call one tool (output one <tool_call> block, no Final Answer)\n"
                            "- Output final content (start with 'Final Answer:', no <tool_call>)\n"
                            "Please reply again doing only one thing."
                        ),
                    })
                    continue
                else:
                    # Third conflict: degrade by truncating to the first tool call
                    logger.warning(
                        f"Section {section.title}: {conflict_retries} consecutive conflicts, "
                        "degrading to truncated first tool call"
                    )
                    first_tool_end = response.find('</tool_call>')
                    if first_tool_end != -1:
                        response = response[:first_tool_end + len('</tool_call>')]
                        tool_calls = self._parse_tool_calls(response)
                        has_tool_calls = bool(tool_calls)
                    has_final_answer = False
                    conflict_retries = 0

            # Log LLM response
            if self.report_logger:
                self.report_logger.log_llm_response(
                    section_title=section.title,
                    section_index=section_index,
                    response=response,
                    iteration=iteration + 1,
                    has_tool_calls=has_tool_calls,
                    has_final_answer=has_final_answer
                )

            # ── Case 1: LLM output Final Answer ──
            if has_final_answer:
                if tool_calls_count < min_tool_calls:
                    messages.append({"role": "assistant", "content": response})
                    unused_tools = all_tools - used_tools
                    unused_hint = f"(These tools have not been used yet, recommended to try: {', '.join(unused_tools)})" if unused_tools else ""
                    messages.append({
                        "role": "user",
                        "content": REACT_INSUFFICIENT_TOOLS_MSG.format(
                            tool_calls_count=tool_calls_count,
                            min_tool_calls=min_tool_calls,
                            unused_hint=unused_hint,
                        ),
                    })
                    continue

                final_answer = response.split("Final Answer:")[-1].strip()
                logger.info(f"Section {section.title} complete (tool calls: {tool_calls_count})")

                if self.report_logger:
                    self.report_logger.log_section_content(
                        section_title=section.title,
                        section_index=section_index,
                        content=final_answer,
                        tool_calls_count=tool_calls_count
                    )
                return final_answer

            # ── Case 2: LLM attempted a tool call ──
            if has_tool_calls:
                if tool_calls_count >= self.MAX_TOOL_CALLS_PER_SECTION:
                    messages.append({"role": "assistant", "content": response})
                    messages.append({
                        "role": "user",
                        "content": REACT_TOOL_LIMIT_MSG.format(
                            tool_calls_count=tool_calls_count,
                            max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        ),
                    })
                    continue

                # Only execute the first tool call
                call = tool_calls[0]
                if len(tool_calls) > 1:
                    logger.info(f"LLM attempted {len(tool_calls)} tool calls, executing only the first: {call['name']}")

                if self.report_logger:
                    self.report_logger.log_tool_call(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        parameters=call.get("parameters", {}),
                        iteration=iteration + 1
                    )

                result = self._execute_tool(
                    call["name"],
                    call.get("parameters", {}),
                    report_context=report_context
                )

                if self.report_logger:
                    self.report_logger.log_tool_result(
                        section_title=section.title,
                        section_index=section_index,
                        tool_name=call["name"],
                        result=result,
                        iteration=iteration + 1
                    )

                tool_calls_count += 1
                used_tools.add(call['name'])

                unused_tools = all_tools - used_tools
                unused_hint = ""
                if unused_tools and tool_calls_count < self.MAX_TOOL_CALLS_PER_SECTION:
                    unused_hint = REACT_UNUSED_TOOLS_HINT.format(unused_list="、".join(unused_tools))

                messages.append({"role": "assistant", "content": response})
                messages.append({
                    "role": "user",
                    "content": REACT_OBSERVATION_TEMPLATE.format(
                        tool_name=call["name"],
                        result=result,
                        tool_calls_count=tool_calls_count,
                        max_tool_calls=self.MAX_TOOL_CALLS_PER_SECTION,
                        used_tools_str=", ".join(used_tools),
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # ── Case 3: neither tool call nor Final Answer ──
            messages.append({"role": "assistant", "content": response})

            if tool_calls_count < min_tool_calls:
                unused_tools = all_tools - used_tools
                unused_hint = f"(These tools have not been used yet, recommended to try: {', '.join(unused_tools)})" if unused_tools else ""

                messages.append({
                    "role": "user",
                    "content": REACT_INSUFFICIENT_TOOLS_MSG_ALT.format(
                        tool_calls_count=tool_calls_count,
                        min_tool_calls=min_tool_calls,
                        unused_hint=unused_hint,
                    ),
                })
                continue

            # Sufficient tool calls — LLM output content without "Final Answer:" prefix
            # Accept it directly as the final answer
            logger.info(
                f"Section {section.title}: no 'Final Answer:' prefix detected, "
                f"accepting LLM output as final content (tool calls: {tool_calls_count})"
            )
            final_answer = response.strip()

            if self.report_logger:
                self.report_logger.log_section_content(
                    section_title=section.title,
                    section_index=section_index,
                    content=final_answer,
                    tool_calls_count=tool_calls_count
                )
            return final_answer

        # Maximum iterations reached — force content generation
        logger.warning(f"Section {section.title} reached max iterations, forcing generation")
        messages.append({"role": "user", "content": REACT_FORCE_FINAL_MSG})

        response = self.llm.chat(
            messages=messages,
            temperature=0.5,
            max_tokens=4096
        )

        if response is None:
            logger.error(f"Section {section.title}: forced final LLM returned None, using error placeholder")
            final_answer = "(Section generation failed: LLM returned empty response, please retry)"
        elif "Final Answer:" in response:
            final_answer = response.split("Final Answer:")[-1].strip()
        else:
            final_answer = response

        if self.report_logger:
            self.report_logger.log_section_content(
                section_title=section.title,
                section_index=section_index,
                content=final_answer,
                tool_calls_count=tool_calls_count
            )

        return final_answer

    def generate_report(
        self,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        report_id: Optional[str] = None
    ) -> Report:
        """
        Generate a complete report (section-by-section streaming output).

        Each section is saved immediately after generation.
        File structure:
        reports/{report_id}/
            meta.json       - report metadata
            outline.json    - report outline
            progress.json   - generation progress
            section_01.md   - section 1
            section_02.md   - section 2
            ...
            full_report.md  - complete report

        Args:
            progress_callback: Progress callback (stage, progress, message).
            report_id: Report ID (auto-generated if not provided).

        Returns:
            Report: Complete report.
        """
        import uuid

        if not report_id:
            report_id = f"report_{uuid.uuid4().hex[:12]}"
        start_time = datetime.now()

        report = Report(
            report_id=report_id,
            simulation_id=self.simulation_id,
            graph_id=self.graph_id,
            simulation_requirement=self.simulation_requirement,
            status=ReportStatus.PENDING,
            created_at=datetime.now().isoformat()
        )

        completed_section_titles = []

        try:
            ReportManager._ensure_report_folder(report_id)

            self.report_logger = ReportLogger(report_id)
            self.report_logger.log_start(
                simulation_id=self.simulation_id,
                graph_id=self.graph_id,
                simulation_requirement=self.simulation_requirement
            )

            self.console_logger = ReportConsoleLogger(report_id)

            ReportManager.update_progress(
                report_id, "pending", 0, "Initializing report...",
                completed_sections=[]
            )
            ReportManager.save_report(report)

            # Phase 1: plan outline
            report.status = ReportStatus.PLANNING
            ReportManager.update_progress(
                report_id, "planning", 5, "Starting report outline planning...",
                completed_sections=[]
            )

            self.report_logger.log_planning_start()

            if progress_callback:
                progress_callback("planning", 0, "Starting report outline planning...")

            outline = self.plan_outline(
                progress_callback=lambda stage, prog, msg:
                    progress_callback(stage, prog // 5, msg) if progress_callback else None
            )
            report.outline = outline

            self.report_logger.log_planning_complete(outline.to_dict())

            ReportManager.save_outline(report_id, outline)
            ReportManager.update_progress(
                report_id, "planning", 15, f"Outline planning complete, {len(outline.sections)} sections",
                completed_sections=[]
            )
            ReportManager.save_report(report)

            logger.info(f"Outline saved: {report_id}/outline.json")

            # Phase 2: generate sections
            report.status = ReportStatus.GENERATING

            total_sections = len(outline.sections)
            generated_sections = []

            for i, section in enumerate(outline.sections):
                section_num = i + 1
                base_progress = 20 + int((i / total_sections) * 70)

                ReportManager.update_progress(
                    report_id, "generating", base_progress,
                    f"Generating section: {section.title} ({section_num}/{total_sections})",
                    current_section=section.title,
                    completed_sections=completed_section_titles
                )

                if progress_callback:
                    progress_callback(
                        "generating",
                        base_progress,
                        f"Generating section: {section.title} ({section_num}/{total_sections})"
                    )

                section_content = self._generate_section_react(
                    section=section,
                    outline=outline,
                    previous_sections=generated_sections,
                    progress_callback=lambda stage, prog, msg:
                        progress_callback(
                            stage,
                            base_progress + int(prog * 0.7 / total_sections),
                            msg
                        ) if progress_callback else None,
                    section_index=section_num
                )

                section.content = section_content
                generated_sections.append(f"## {section.title}\n\n{section_content}")

                ReportManager.save_section(report_id, section_num, section)
                completed_section_titles.append(section.title)

                full_section_content = f"## {section.title}\n\n{section_content}"

                if self.report_logger:
                    self.report_logger.log_section_full_complete(
                        section_title=section.title,
                        section_index=section_num,
                        full_content=full_section_content.strip()
                    )

                logger.info(f"Section saved: {report_id}/section_{section_num:02d}.md")

                ReportManager.update_progress(
                    report_id, "generating",
                    base_progress + int(70 / total_sections),
                    f"Section {section.title} complete",
                    current_section=None,
                    completed_sections=completed_section_titles
                )

            # Phase 3: assemble full report
            if progress_callback:
                progress_callback("generating", 95, "Assembling complete report...")

            ReportManager.update_progress(
                report_id, "generating", 95, "Assembling complete report...",
                completed_sections=completed_section_titles
            )

            report.markdown_content = ReportManager.assemble_full_report(report_id, outline)
            report.status = ReportStatus.COMPLETED
            report.completed_at = datetime.now().isoformat()

            total_time_seconds = (datetime.now() - start_time).total_seconds()

            if self.report_logger:
                self.report_logger.log_report_complete(
                    total_sections=total_sections,
                    total_time_seconds=total_time_seconds
                )

            ReportManager.save_report(report)
            ReportManager.update_progress(
                report_id, "completed", 100, "Report generation complete",
                completed_sections=completed_section_titles
            )

            if progress_callback:
                progress_callback("completed", 100, "Report generation complete")

            logger.info(f"Report generation complete: {report_id}")

            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

        except Exception as e:
            logger.error(f"Report generation failed: {str(e)}")
            report.status = ReportStatus.FAILED
            report.error = str(e)

            if self.report_logger:
                self.report_logger.log_error(str(e), "failed")

            try:
                ReportManager.save_report(report)
                ReportManager.update_progress(
                    report_id, "failed", -1, f"Report generation failed: {str(e)}",
                    completed_sections=completed_section_titles
                )
            except Exception:
                pass

            if self.console_logger:
                self.console_logger.close()
                self.console_logger = None

            return report

    def chat(
        self,
        message: str,
        chat_history: List[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Chat with Report Agent.

        The agent can autonomously call retrieval tools to answer questions.

        Args:
            message: User message.
            chat_history: Conversation history.

        Returns:
            {
                "response": "Agent reply",
                "tool_calls": [list of tools called],
                "sources": [information sources]
            }
        """
        logger.info(f"Report Agent chat: {message[:50]}...")

        chat_history = chat_history or []

        # Retrieve generated report content
        report_content = ""
        try:
            report = ReportManager.get_report_by_simulation(self.simulation_id)
            if report and report.markdown_content:
                report_content = report.markdown_content[:15000]
                if len(report.markdown_content) > 15000:
                    report_content += "\n\n... [report content truncated] ..."
        except Exception as e:
            logger.warning(f"Failed to retrieve report content: {e}")

        system_prompt = CHAT_SYSTEM_PROMPT_TEMPLATE.format(
            simulation_requirement=self.simulation_requirement,
            report_content=report_content if report_content else "(no report available)",
            tools_description=self._get_tools_description(),
        )

        messages = [{"role": "system", "content": system_prompt}]

        for h in chat_history[-10:]:
            messages.append(h)

        messages.append({
            "role": "user",
            "content": message
        })

        tool_calls_made = []
        max_iterations = 2

        for iteration in range(max_iterations):
            response = self.llm.chat(
                messages=messages,
                temperature=0.5
            )

            tool_calls = self._parse_tool_calls(response)

            if not tool_calls:
                clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', response, flags=re.DOTALL)
                clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)

                return {
                    "response": clean_response.strip(),
                    "tool_calls": tool_calls_made,
                    "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
                }

            tool_results = []
            for call in tool_calls[:1]:
                if len(tool_calls_made) >= self.MAX_TOOL_CALLS_PER_CHAT:
                    break
                result = self._execute_tool(call["name"], call.get("parameters", {}))
                tool_results.append({
                    "tool": call["name"],
                    "result": result[:1500]
                })
                tool_calls_made.append(call)

            messages.append({"role": "assistant", "content": response})
            observation = "\n".join([f"[{r['tool']} result]\n{r['result']}" for r in tool_results])
            messages.append({
                "role": "user",
                "content": observation + CHAT_OBSERVATION_SUFFIX
            })

        # Max iterations reached — get final response
        final_response = self.llm.chat(
            messages=messages,
            temperature=0.5
        )

        clean_response = re.sub(r'<tool_call>.*?</tool_call>', '', final_response, flags=re.DOTALL)
        clean_response = re.sub(r'\[TOOL_CALL\].*?\)', '', clean_response)

        return {
            "response": clean_response.strip(),
            "tool_calls": tool_calls_made,
            "sources": [tc.get("parameters", {}).get("query", "") for tc in tool_calls_made]
        }
