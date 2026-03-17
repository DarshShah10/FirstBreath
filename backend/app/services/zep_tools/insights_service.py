"""Deep insight retrieval and panorama search mixin for ZepToolsService."""

from typing import List

from ...utils.logger import get_logger

from .search_service import SearchMixin
from .models import NodeInfo, InsightForgeResult, PanoramaResult, SearchResult
from .prompts import DECOMPOSE_QUERY_SYSTEM_PROMPT

logger = get_logger('mirofish.zep_tools')


class InsightsMixin(SearchMixin):
    """
    Deep insight retrieval and breadth search methods.

    Builds on SearchMixin to provide:
    - insight_forge  — multi-dimensional deep retrieval with LLM sub-query decomposition
    - panorama_search — full breadth search including expired/historical content
    - quick_search   — fast single-call search
    """

    def insight_forge(
        self,
        graph_id: str,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_sub_queries: int = 5
    ) -> InsightForgeResult:
        """
        InsightForge — Deep Insight Retrieval.

        The most powerful hybrid retrieval function. Automatically decomposes the query
        and performs multi-dimensional retrieval:
        1. Uses an LLM to decompose the query into sub-questions.
        2. Performs semantic search for each sub-question.
        3. Extracts relevant entity UUIDs and fetches their details.
        4. Traces relationship chains.
        5. Consolidates all results into a deep insight report.

        Args:
            graph_id: Graph ID.
            query: User question.
            simulation_requirement: Simulation requirement description.
            report_context: Report context (optional; improves sub-query generation).
            max_sub_queries: Maximum number of sub-questions to generate.

        Returns:
            InsightForgeResult
        """
        logger.info(f"InsightForge deep insight retrieval: {query[:50]}...")

        result = InsightForgeResult(
            query=query,
            simulation_requirement=simulation_requirement,
            sub_queries=[]
        )

        # Step 1: Generate sub-queries via LLM
        sub_queries = self._generate_sub_queries(
            query=query,
            simulation_requirement=simulation_requirement,
            report_context=report_context,
            max_queries=max_sub_queries
        )
        result.sub_queries = sub_queries
        logger.info(f"Generated {len(sub_queries)} sub-queries")

        # Step 2: Semantic search for each sub-query
        all_facts = []
        all_edges = []
        seen_facts = set()

        for sub_query in sub_queries:
            search_result = self.search_graph(
                graph_id=graph_id,
                query=sub_query,
                limit=15,
                scope="edges"
            )

            for fact in search_result.facts:
                if fact not in seen_facts:
                    all_facts.append(fact)
                    seen_facts.add(fact)

            all_edges.extend(search_result.edges)

        # Also search on the original query
        main_search = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=20,
            scope="edges"
        )
        for fact in main_search.facts:
            if fact not in seen_facts:
                all_facts.append(fact)
                seen_facts.add(fact)

        result.semantic_facts = all_facts
        result.total_facts = len(all_facts)

        # Step 3: Extract entity UUIDs from edges — fetch only those entities (not all nodes)
        entity_uuids = set()
        for edge_data in all_edges:
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                if source_uuid:
                    entity_uuids.add(source_uuid)
                if target_uuid:
                    entity_uuids.add(target_uuid)

        # Fetch details for all relevant entities (no count cap — full output)
        entity_insights = []
        node_map = {}  # Used for relationship chain construction

        for uuid in list(entity_uuids):  # Process all entities without truncation
            if not uuid:
                continue
            try:
                # Fetch each relevant node individually
                node = self.get_node_detail(uuid)
                if node:
                    node_map[uuid] = node
                    entity_type = next((l for l in node.labels if l not in ["Entity", "Node"]), "Entity")

                    # Collect all facts that mention this entity (no truncation)
                    related_facts = [
                        f for f in all_facts
                        if node.name.lower() in f.lower()
                    ]

                    entity_insights.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "type": entity_type,
                        "summary": node.summary,
                        "related_facts": related_facts  # Full output, untruncated
                    })
            except Exception as e:
                logger.debug(f"Failed to fetch node {uuid}: {e}")
                continue

        result.entity_insights = entity_insights
        result.total_entities = len(entity_insights)

        # Step 4: Build all relationship chains (no count cap)
        relationship_chains = []
        for edge_data in all_edges:  # Process all edges without truncation
            if isinstance(edge_data, dict):
                source_uuid = edge_data.get('source_node_uuid', '')
                target_uuid = edge_data.get('target_node_uuid', '')
                relation_name = edge_data.get('name', '')

                source_name = node_map.get(source_uuid, NodeInfo('', '', [], '', {})).name or source_uuid[:8]
                target_name = node_map.get(target_uuid, NodeInfo('', '', [], '', {})).name or target_uuid[:8]

                chain = f"{source_name} --[{relation_name}]--> {target_name}"
                if chain not in relationship_chains:
                    relationship_chains.append(chain)

        result.relationship_chains = relationship_chains
        result.total_relationships = len(relationship_chains)

        logger.info(
            f"InsightForge complete: {result.total_facts} facts, "
            f"{result.total_entities} entities, {result.total_relationships} relationships"
        )
        return result

    def _generate_sub_queries(
        self,
        query: str,
        simulation_requirement: str,
        report_context: str = "",
        max_queries: int = 5
    ) -> List[str]:
        """
        Use an LLM to decompose a complex query into independently searchable sub-questions.
        """
        user_prompt = f"""Simulation background:
{simulation_requirement}

{f"Report context: {report_context[:500]}" if report_context else ""}

Please decompose the following question into {max_queries} sub-questions:
{query}

Return a JSON list of sub-questions."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": DECOMPOSE_QUERY_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3
            )

            sub_queries = response.get("sub_queries", [])
            # Ensure the result is a list of strings
            return [str(sq) for sq in sub_queries[:max_queries]]

        except Exception as e:
            logger.warning(f"Sub-query generation failed: {str(e)}, using default sub-queries")
            # Fallback: return variants of the original query
            return [
                query,
                f"Key participants involved in: {query}",
                f"Causes and impacts of: {query}",
                f"How did this develop: {query}"
            ][:max_queries]

    def panorama_search(
        self,
        graph_id: str,
        query: str,
        include_expired: bool = True,
        limit: int = 50
    ) -> PanoramaResult:
        """
        PanoramaSearch — Breadth Search.

        Retrieves the full picture including all related content and
        historical/expired information:
        1. Fetches all relevant nodes.
        2. Fetches all edges (including expired/invalidated ones).
        3. Classifies facts as currently active or historical.

        Suitable for scenarios that require understanding the full event picture
        or tracing how something evolved over time.

        Args:
            graph_id: Graph ID.
            query: Search query (used for relevance sorting).
            include_expired: Whether to include expired content. Default True.
            limit: Maximum number of results per category.

        Returns:
            PanoramaResult
        """
        logger.info(f"PanoramaSearch breadth search: {query[:50]}...")

        result = PanoramaResult(query=query)

        # Fetch all nodes
        all_nodes = self.get_all_nodes(graph_id)
        node_map = {n.uuid: n for n in all_nodes}
        result.all_nodes = all_nodes
        result.total_nodes = len(all_nodes)

        # Fetch all edges (with temporal metadata)
        all_edges = self.get_all_edges(graph_id, include_temporal=True)
        result.all_edges = all_edges
        result.total_edges = len(all_edges)

        # Classify facts as active or historical
        active_facts = []
        historical_facts = []

        for edge in all_edges:
            if not edge.fact:
                continue

            # Annotate fact with entity names
            source_name = node_map.get(edge.source_node_uuid, NodeInfo('', '', [], '', {})).name or edge.source_node_uuid[:8]
            target_name = node_map.get(edge.target_node_uuid, NodeInfo('', '', [], '', {})).name or edge.target_node_uuid[:8]

            # Determine if the fact is historical/expired
            is_historical = edge.is_expired or edge.is_invalid

            if is_historical:
                # Historical/expired fact — append time range markers
                valid_at = edge.valid_at or "unknown"
                invalid_at = edge.invalid_at or edge.expired_at or "unknown"
                fact_with_time = f"[{valid_at} - {invalid_at}] {edge.fact}"
                historical_facts.append(fact_with_time)
            else:
                # Currently active fact
                active_facts.append(edge.fact)

        # Sort by relevance to the query
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def relevance_score(fact: str) -> int:
            fact_lower = fact.lower()
            score = 0
            if query_lower in fact_lower:
                score += 100
            for kw in keywords:
                if kw in fact_lower:
                    score += 10
            return score

        # Sort and cap results
        active_facts.sort(key=relevance_score, reverse=True)
        historical_facts.sort(key=relevance_score, reverse=True)

        result.active_facts = active_facts[:limit]
        result.historical_facts = historical_facts[:limit] if include_expired else []
        result.active_count = len(active_facts)
        result.historical_count = len(historical_facts)

        logger.info(f"PanoramaSearch complete: {result.active_count} active, {result.historical_count} historical")
        return result

    def quick_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10
    ) -> SearchResult:
        """
        QuickSearch — Simple Search.

        Lightweight, fast retrieval:
        1. Calls the Zep semantic search directly.
        2. Returns the most relevant results.
        3. Suitable for straightforward, direct retrieval needs.

        Args:
            graph_id: Graph ID.
            query: Search query.
            limit: Maximum number of results to return.

        Returns:
            SearchResult
        """
        logger.info(f"QuickSearch simple search: {query[:50]}...")

        # Delegate directly to the existing search_graph method
        result = self.search_graph(
            graph_id=graph_id,
            query=query,
            limit=limit,
            scope="edges"
        )

        logger.info(f"QuickSearch complete: {result.total_count} results")
        return result
