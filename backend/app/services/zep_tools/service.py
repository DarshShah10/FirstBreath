"""
Zep Retrieval Tools Service

Wraps graph search, node retrieval, edge queries, and agent interview
capabilities for use by the Report Agent.

Core retrieval tools:
1. insight_forge      — Deep insight retrieval: decomposes the query into sub-queries
                        and performs multi-dimensional retrieval.
2. panorama_search    — Breadth search: retrieves the full picture including expired content.
3. quick_search       — Simple search: fast, lightweight retrieval.
4. interview_agents   — Deep interview: interviews running simulation agents via the real API.
"""

from .insights_service import InsightsMixin
from .interview_service import InterviewMixin


class ZepToolsService(InsightsMixin, InterviewMixin):
    """
    Zep Retrieval Tools Service.

    Combines all retrieval capabilities via mixin inheritance:
    - InsightsMixin  → insight_forge, panorama_search, quick_search, _generate_sub_queries
    - SearchMixin    → search_graph, get_all_nodes, get_all_edges, get_node_detail,
                       get_node_edges, get_entities_by_type, get_entity_summary,
                       get_graph_statistics, get_simulation_context
    - InterviewMixin → interview_agents and all interview helpers
    - ZepToolsBase   → __init__, llm property, _call_with_retry

    MRO: ZepToolsService → InsightsMixin → SearchMixin → InterviewMixin → ZepToolsBase
    """
