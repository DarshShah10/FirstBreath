"""
Neo4j Retrieval Tools Service

Wraps Neo4j graph search, node retrieval, edge queries for use by the Report Agent.
This is a Neo4j-based replacement for the ZepToolsService.

Core retrieval tools:
1. search_graph         — Search nodes and edges in the graph
2. get_all_nodes        — Get all nodes in a graph
3. get_all_edges        — Get all edges in a graph
4. get_node_detail      — Get detailed information about a node
5. get_node_edges       — Get edges connected to a node
6. get_entities_by_type — Get entities filtered by type
7. get_graph_statistics — Get statistics about the graph
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from ..config import Config
from ..utils.logger import get_logger
from ..utils.llm_client import LLMClient
from .neo4j_entity_reader import Neo4jEntityReader, EntityNode

logger = get_logger('mirofish.neo4j_tools')


@dataclass
class SearchResult:
    """Search result from graph query."""
    query: str
    nodes: List[Dict[str, Any]]
    edges: List[Dict[str, Any]]
    total_nodes: int
    total_edges: int


@dataclass
class NodeInfo:
    """Node information."""
    uuid: str
    name: str
    labels: List[str]
    summary: str
    attributes: Dict[str, Any]


@dataclass
class EdgeInfo:
    """Edge information."""
    uuid: str
    name: str
    source_uuid: str
    target_uuid: str
    fact: str
    attributes: Dict[str, Any]


class Neo4jToolsService:
    """
    Neo4j Retrieval Tools Service.

    Provides the same interface as ZepToolsService but uses Neo4j underneath.
    """

    def __init__(self):
        self.reader = Neo4jEntityReader()
        self.llm = LLMClient()

    def search_graph(
        self,
        graph_id: str,
        query: str,
        limit: int = 20
    ) -> SearchResult:
        """
        Search the graph for nodes matching the query.

        Args:
            graph_id: The graph ID to search
            query: Search query
            limit: Maximum number of results

        Returns:
            SearchResult with matching nodes and edges
        """
        logger.info(f"Searching graph {graph_id} for: {query}")

        # Search for matching nodes
        nodes = self.reader.search_nodes(graph_id, query)

        # Build node dicts
        node_dicts = []
        for node in nodes[:limit]:
            node_dicts.append({
                "uuid": node.uuid,
                "name": node.name,
                "entity_type": node.entity_type,
                "description": node.description,
                "summary": node.summary,
                "attributes": node.attributes
            })

        return SearchResult(
            query=query,
            nodes=node_dicts,
            edges=[],  # Edge search not implemented yet
            total_nodes=len(node_dicts),
            total_edges=0
        )

    def get_all_nodes(self, graph_id: str) -> List[NodeInfo]:
        """
        Get all nodes in a graph.

        Args:
            graph_id: The graph ID

        Returns:
            List of NodeInfo objects
        """
        nodes = self.reader.get_all_nodes(graph_id)
        return [
            NodeInfo(
                uuid=n.uuid,
                name=n.name,
                labels=[n.entity_type],
                summary=n.summary,
                attributes=n.attributes
            )
            for n in nodes
        ]

    def get_all_edges(self, graph_id: str) -> List[EdgeInfo]:
        """
        Get all edges in a graph.

        Args:
            graph_id: The graph ID

        Returns:
            List of EdgeInfo objects
        """
        # For now, return empty list - edge retrieval would need additional implementation
        return []

    def get_node_detail(
        self,
        graph_id: str,
        node_uuid: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get detailed information about a node.

        Args:
            graph_id: The graph ID
            node_uuid: The node UUID

        Returns:
            Node details or None if not found
        """
        nodes = self.reader.get_all_nodes(graph_id)
        for node in nodes:
            if node.uuid == node_uuid:
                return {
                    "uuid": node.uuid,
                    "name": node.name,
                    "entity_type": node.entity_type,
                    "description": node.description,
                    "summary": node.summary,
                    "attributes": node.attributes
                }
        return None

    def get_node_edges(
        self,
        graph_id: str,
        node_name: str
    ) -> List[Dict[str, Any]]:
        """
        Get edges connected to a node.

        Args:
            graph_id: The graph ID
            node_name: The node name

        Returns:
            List of edge dictionaries
        """
        return self.reader.get_node_edges(graph_id, node_name)

    def get_entities_by_type(
        self,
        graph_id: str,
        entity_type: str
    ) -> List[Dict[str, Any]]:
        """
        Get entities filtered by type.

        Args:
            graph_id: The graph ID
            entity_type: The entity type to filter by

        Returns:
            List of entity dictionaries
        """
        filtered = self.reader.get_entities_by_type(graph_id, entity_type)
        return [
            {
                "uuid": e.uuid,
                "name": e.name,
                "entity_type": e.entity_type,
                "description": e.description,
                "summary": e.summary,
                "attributes": e.attributes
            }
            for e in filtered.entities
        ]

    def get_entity_summary(
        self,
        graph_id: str,
        node_uuid: str
    ) -> str:
        """
        Get a summary of an entity.

        Args:
            graph_id: The graph ID
            node_uuid: The node UUID

        Returns:
            Summary text
        """
        detail = self.get_node_detail(graph_id, node_uuid)
        if detail:
            return detail.get("summary", detail.get("description", ""))
        return ""

    def get_graph_statistics(self, graph_id: str) -> Dict[str, Any]:
        """
        Get statistics about the graph.

        Args:
            graph_id: The graph ID

        Returns:
            Dictionary with graph statistics
        """
        nodes = self.reader.get_all_nodes(graph_id)

        # Count entities by type
        type_counts: Dict[str, int] = {}
        for node in nodes:
            et = node.entity_type
            type_counts[et] = type_counts.get(et, 0) + 1

        return {
            "graph_id": graph_id,
            "total_nodes": len(nodes),
            "total_edges": 0,  # Edge count not implemented yet
            "entity_types": list(type_counts.keys()),
            "entity_type_counts": type_counts
        }

    def get_simulation_context(
        self,
        graph_id: str,
        simulation_id: str = None,
        simulation_requirement: str = None
    ) -> Dict[str, Any]:
        """
        Get simulation context from the graph.

        Args:
            graph_id: The graph ID
            simulation_id: The simulation ID (optional)
            simulation_requirement: The simulation requirement description (optional)

        Returns:
            Context dictionary with graph statistics and related facts
        """
        # Get all nodes as context
        nodes = self.reader.get_all_nodes(graph_id)
        node_summaries = [
            f"{n.name} ({n.entity_type})"
            for n in nodes[:20]  # Limit to first 20
        ]

        # Get graph statistics
        type_counts: Dict[str, int] = {}
        for node in nodes:
            et = node.entity_type
            type_counts[et] = type_counts.get(et, 0) + 1

        # Build context with expected fields for report agent
        context = {
            "graph_id": graph_id,
            "simulation_id": simulation_id or "",
            "simulation_requirement": simulation_requirement or "",
            "node_count": len(nodes),
            "total_entities": len(nodes),
            "total_nodes": len(nodes),
            "total_edges": 0,  # Edge count not implemented yet
            "entity_types": list(type_counts.keys()),
            "graph_statistics": {
                "total_nodes": len(nodes),
                "total_edges": 0,
                "entity_types": list(type_counts.keys()),
                "entity_type_counts": type_counts
            },
            "related_facts": [
                {
                    "entity": n.name,
                    "type": n.entity_type,
                    "description": n.description
                }
                for n in nodes[:10]
            ],
            "summary": f"Graph contains {len(nodes)} entities: " + ", ".join(node_summaries)
        }

        return context


# Alias for backward compatibility
ZepToolsService = Neo4jToolsService
