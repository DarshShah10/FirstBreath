"""Graph search and node/edge retrieval mixin for ZepToolsService."""

from typing import Dict, Any, List, Optional

from ...utils.logger import get_logger
from ...utils.zep_paging import fetch_all_nodes, fetch_all_edges

from .base import ZepToolsBase
from .models import NodeInfo, EdgeInfo, SearchResult

logger = get_logger('mirofish.zep_tools')


class SearchMixin(ZepToolsBase):
    """
    Graph search and entity retrieval methods.

    Provides semantic search, local keyword-matching fallback, and all
    node/edge retrieval helpers.
    """

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Semantic graph search.

        Uses hybrid search (semantic + BM25) to find relevant information in the graph.
        Falls back to local keyword matching if the Zep Cloud search API is unavailable.

        Args:
            graph_id: Graph ID (Standalone Graph).
            query: Search query string.
            limit: Maximum number of results to return.
            scope: Search scope — "edges" or "nodes".

        Returns:
            SearchResult
        """
        logger.info(f"Graph search: graph_id={graph_id}, query={query[:50]}...")

        # Attempt Zep Cloud Search API
        try:
            search_results = self._call_with_retry(
                func=lambda: self.client.graph.search(
                    graph_id=graph_id,
                    query=query,
                    limit=limit,
                    scope=scope,
                    reranker="cross_encoder"
                ),
                operation_name=f"graph_search(graph={graph_id})"
            )

            facts = []
            edges = []
            nodes = []

            # Parse edge search results
            if hasattr(search_results, 'edges') and search_results.edges:
                for edge in search_results.edges:
                    if hasattr(edge, 'fact') and edge.fact:
                        facts.append(edge.fact)
                    edges.append({
                        "uuid": getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', ''),
                        "name": getattr(edge, 'name', ''),
                        "fact": getattr(edge, 'fact', ''),
                        "source_node_uuid": getattr(edge, 'source_node_uuid', ''),
                        "target_node_uuid": getattr(edge, 'target_node_uuid', ''),
                    })

            # Parse node search results
            if hasattr(search_results, 'nodes') and search_results.nodes:
                for node in search_results.nodes:
                    nodes.append({
                        "uuid": getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                        "name": getattr(node, 'name', ''),
                        "labels": getattr(node, 'labels', []),
                        "summary": getattr(node, 'summary', ''),
                    })
                    # Node summaries also count as facts
                    if hasattr(node, 'summary') and node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Search complete: found {len(facts)} relevant facts")

            return SearchResult(
                facts=facts,
                edges=edges,
                nodes=nodes,
                query=query,
                total_count=len(facts)
            )

        except Exception as e:
            logger.warning(f"Zep Search API failed, falling back to local search: {str(e)}")
            # Fallback: local keyword matching
            return self._local_search(graph_id, query, limit, scope)

    def _local_search(
        self,
        graph_id: str,
        query: str,
        limit: int = 10,
        scope: str = "edges"
    ) -> SearchResult:
        """
        Local keyword-matching search (fallback when Zep Search API is unavailable).

        Fetches all edges/nodes and performs local keyword matching.

        Args:
            graph_id: Graph ID.
            query: Search query string.
            limit: Maximum number of results to return.
            scope: Search scope.

        Returns:
            SearchResult
        """
        logger.info(f"Using local search: query={query[:30]}...")

        facts = []
        edges_result = []
        nodes_result = []

        # Tokenise query (simple whitespace split)
        query_lower = query.lower()
        keywords = [w.strip() for w in query_lower.replace(',', ' ').replace('，', ' ').split() if len(w.strip()) > 1]

        def match_score(text: str) -> int:
            """Compute a relevance score between text and the query."""
            if not text:
                return 0
            text_lower = text.lower()
            # Full query match
            if query_lower in text_lower:
                return 100
            # Keyword match
            score = 0
            for keyword in keywords:
                if keyword in text_lower:
                    score += 10
            return score

        try:
            if scope in ["edges", "both"]:
                # Fetch and score all edges
                all_edges = self.get_all_edges(graph_id)
                scored_edges = []
                for edge in all_edges:
                    score = match_score(edge.fact) + match_score(edge.name)
                    if score > 0:
                        scored_edges.append((score, edge))

                # Sort by score descending
                scored_edges.sort(key=lambda x: x[0], reverse=True)

                for score, edge in scored_edges[:limit]:
                    if edge.fact:
                        facts.append(edge.fact)
                    edges_result.append({
                        "uuid": edge.uuid,
                        "name": edge.name,
                        "fact": edge.fact,
                        "source_node_uuid": edge.source_node_uuid,
                        "target_node_uuid": edge.target_node_uuid,
                    })

            if scope in ["nodes", "both"]:
                # Fetch and score all nodes
                all_nodes = self.get_all_nodes(graph_id)
                scored_nodes = []
                for node in all_nodes:
                    score = match_score(node.name) + match_score(node.summary)
                    if score > 0:
                        scored_nodes.append((score, node))

                scored_nodes.sort(key=lambda x: x[0], reverse=True)

                for score, node in scored_nodes[:limit]:
                    nodes_result.append({
                        "uuid": node.uuid,
                        "name": node.name,
                        "labels": node.labels,
                        "summary": node.summary,
                    })
                    if node.summary:
                        facts.append(f"[{node.name}]: {node.summary}")

            logger.info(f"Local search complete: found {len(facts)} relevant facts")

        except Exception as e:
            logger.error(f"Local search failed: {str(e)}")

        return SearchResult(
            facts=facts,
            edges=edges_result,
            nodes=nodes_result,
            query=query,
            total_count=len(facts)
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Retrieve all nodes from a graph (paginated).

        Args:
            graph_id: Graph ID.

        Returns:
            List of NodeInfo objects.
        """
        logger.info(f"Fetching all nodes for graph {graph_id}...")

        nodes = fetch_all_nodes(self.client, graph_id)

        result = []
        for node in nodes:
            node_uuid = getattr(node, 'uuid_', None) or getattr(node, 'uuid', None) or ""
            result.append(NodeInfo(
                uuid=str(node_uuid) if node_uuid else "",
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            ))

        logger.info(f"Retrieved {len(result)} nodes")
        return result

    def get_all_edges(self, graph_id: str, include_temporal: bool = True) -> List[EdgeInfo]:
        """
        Retrieve all edges from a graph (paginated, with temporal metadata).

        Args:
            graph_id: Graph ID.
            include_temporal: Whether to populate temporal fields
                              (created_at, valid_at, invalid_at, expired_at). Default True.

        Returns:
            List of EdgeInfo objects.
        """
        logger.info(f"Fetching all edges for graph {graph_id}...")

        edges = fetch_all_edges(self.client, graph_id)

        result = []
        for edge in edges:
            edge_uuid = getattr(edge, 'uuid_', None) or getattr(edge, 'uuid', None) or ""
            edge_info = EdgeInfo(
                uuid=str(edge_uuid) if edge_uuid else "",
                name=edge.name or "",
                fact=edge.fact or "",
                source_node_uuid=edge.source_node_uuid or "",
                target_node_uuid=edge.target_node_uuid or ""
            )

            # Populate temporal metadata
            if include_temporal:
                edge_info.created_at = getattr(edge, 'created_at', None)
                edge_info.valid_at = getattr(edge, 'valid_at', None)
                edge_info.invalid_at = getattr(edge, 'invalid_at', None)
                edge_info.expired_at = getattr(edge, 'expired_at', None)

            result.append(edge_info)

        logger.info(f"Retrieved {len(result)} edges")
        return result

    def get_node_detail(self, node_uuid: str) -> Optional[NodeInfo]:
        """
        Retrieve detailed information for a single node.

        Args:
            node_uuid: Node UUID.

        Returns:
            NodeInfo, or None if the node could not be retrieved.
        """
        logger.info(f"Fetching node detail: {node_uuid[:8]}...")

        try:
            node = self._call_with_retry(
                func=lambda: self.client.graph.node.get(uuid_=node_uuid),
                operation_name=f"get_node_detail(uuid={node_uuid[:8]}...)"
            )

            if not node:
                return None

            return NodeInfo(
                uuid=getattr(node, 'uuid_', None) or getattr(node, 'uuid', ''),
                name=node.name or "",
                labels=node.labels or [],
                summary=node.summary or "",
                attributes=node.attributes or {}
            )
        except Exception as e:
            logger.error(f"Failed to retrieve node detail: {str(e)}")
            return None

    def get_node_edges(self, graph_id: str, node_uuid: str) -> List[EdgeInfo]:
        """
        Retrieve all edges connected to a specific node.

        Fetches all graph edges and filters to those involving the target node.

        Args:
            graph_id: Graph ID.
            node_uuid: Node UUID.

        Returns:
            List of EdgeInfo objects.
        """
        logger.info(f"Fetching edges for node {node_uuid[:8]}...")

        try:
            # Fetch all graph edges and filter by node UUID
            all_edges = self.get_all_edges(graph_id)

            result = []
            for edge in all_edges:
                # Keep edges where the node is either source or target
                if edge.source_node_uuid == node_uuid or edge.target_node_uuid == node_uuid:
                    result.append(edge)

            logger.info(f"Found {len(result)} edges connected to node")
            return result

        except Exception as e:
            logger.warning(f"Failed to retrieve node edges: {str(e)}")
            return []

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str
    ) -> List[NodeInfo]:
        """
        Retrieve all entities of a specific type.

        Args:
            graph_id: Graph ID.
            entity_type: Entity type label (e.g. Student, PublicFigure).

        Returns:
            List of matching NodeInfo objects.
        """
        logger.info(f"Fetching entities of type {entity_type}...")

        all_nodes = self.get_all_nodes(graph_id)

        filtered = []
        for node in all_nodes:
            # Keep nodes whose labels include the requested type
            if entity_type in node.labels:
                filtered.append(node)

        logger.info(f"Found {len(filtered)} entities of type {entity_type}")
        return filtered

    def get_entity_summary(
        self,
        graph_id: str,
        entity_name: str
    ) -> Dict[str, Any]:
        """
        Retrieve a relationship summary for a named entity.

        Searches for all information related to the entity and compiles a summary.

        Args:
            graph_id: Graph ID.
            entity_name: Entity name.

        Returns:
            Dictionary containing the entity info, related facts, and related edges.
        """
        logger.info(f"Fetching relationship summary for entity {entity_name}...")

        # Search for information related to this entity
        search_result = self.search_graph(
            graph_id=graph_id,
            query=entity_name,
            limit=20
        )

        # Locate the entity node in the full node list
        all_nodes = self.get_all_nodes(graph_id)
        entity_node = None
        for node in all_nodes:
            if node.name.lower() == entity_name.lower():
                entity_node = node
                break

        related_edges = []
        if entity_node:
            related_edges = self.get_node_edges(graph_id, entity_node.uuid)

        return {
            "entity_name": entity_name,
            "entity_info": entity_node.to_dict() if entity_node else None,
            "related_facts": search_result.facts,
            "related_edges": [e.to_dict() for e in related_edges],
            "total_relations": len(related_edges)
        }

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Retrieve aggregate statistics for a graph.

        Args:
            graph_id: Graph ID.

        Returns:
            Dictionary containing node/edge counts and type distributions.
        """
        logger.info(f"Fetching statistics for graph {graph_id}...")

        nodes = self.get_all_nodes(graph_id)
        edges = self.get_all_edges(graph_id)

        # Count entity type distribution
        entity_types = {}
        for node in nodes:
            for label in node.labels:
                if label not in ["Entity", "Node"]:
                    entity_types[label] = entity_types.get(label, 0) + 1

        # Count relationship type distribution
        relation_types = {}
        for edge in edges:
            relation_types[edge.name] = relation_types.get(edge.name, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "entity_types": entity_types,
            "relation_types": relation_types
        }

    def get_simulation_context(
        self,
        graph_id: str,
        simulation_requirement: str,
        limit: int = 30
    ) -> Dict[str, Any]:
        """
        Retrieve context information relevant to a simulation requirement.

        Performs a comprehensive search across all information related to the requirement.

        Args:
            graph_id: Graph ID.
            simulation_requirement: Natural-language description of the simulation requirement.
            limit: Maximum number of items per category.

        Returns:
            Dictionary containing related facts, graph statistics, and entity list.
        """
        logger.info(f"Fetching simulation context: {simulation_requirement[:50]}...")

        # Search for information related to the simulation requirement
        search_result = self.search_graph(
            graph_id=graph_id,
            query=simulation_requirement,
            limit=limit
        )

        # Fetch graph statistics
        stats = self.get_graph_statistics(graph_id)

        # Fetch all entity nodes
        all_nodes = self.get_all_nodes(graph_id)

        # Keep only nodes with a specific entity type (non-generic Entity nodes)
        entities = []
        for node in all_nodes:
            custom_labels = [l for l in node.labels if l not in ["Entity", "Node"]]
            if custom_labels:
                entities.append({
                    "name": node.name,
                    "type": custom_labels[0],
                    "summary": node.summary
                })

        return {
            "simulation_requirement": simulation_requirement,
            "related_facts": search_result.facts,
            "graph_statistics": stats,
            "entities": entities[:limit],  # Cap the list
            "total_entities": len(entities)
        }
