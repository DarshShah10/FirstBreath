"""
Neo4j Entity Reader
Reads entity information from Neo4j graph database
"""

from dataclasses import dataclass
from typing import List, Optional, Dict, Any

from neo4j import GraphDatabase

from ..config import Config


@dataclass
class EntityNode:
    """Entity node"""
    uuid: str
    name: str
    entity_type: str
    description: str = ""
    summary: str = ""
    attributes: Dict[str, Any] = None
    related_edges: List[Dict[str, Any]] = None
    related_nodes: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.attributes is None:
            self.attributes = {}
        if self.related_edges is None:
            self.related_edges = []
        if self.related_nodes is None:
            self.related_nodes = []

    def get_entity_type(self) -> str:
        """Backward compatibility method"""
        return self.entity_type

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "uuid": self.uuid,
            "name": self.name,
            "entity_type": self.entity_type,
            "description": self.description,
            "summary": self.summary,
            "attributes": self.attributes,
            "related_edges": self.related_edges,
            "related_nodes": self.related_nodes,
        }


@dataclass
class FilteredEntities:
    """Filtered entities"""
    entities: List[EntityNode]
    query: str = ""
    entity_types: set = None
    total_count: int = 0
    filtered_count: int = 0

    def __post_init__(self):
        if self.entity_types is None:
            self.entity_types = set()
        if self.total_count == 0:
            self.total_count = len(self.entities)
        if self.filtered_count == 0:
            self.filtered_count = len(self.entities)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entities": [e.to_dict() if hasattr(e, 'to_dict') else e for e in self.entities],
            "entity_types": list(self.entity_types),
            "total_count": self.total_count,
            "filtered_count": self.filtered_count,
        }


class Neo4jEntityReader:
    """
    Reads entities from Neo4j graph database
    """

    def __init__(self, uri: str = None, username: str = None, password: str = None):
        self.uri = uri or Config.NEO4J_URI
        self.username = username or Config.NEO4J_USERNAME
        self.password = password or Config.NEO4J_PASSWORD
        self.database = Config.NEO4J_DATABASE

        self.driver = GraphDatabase.driver(
            self.uri,
            auth=(self.username, self.password)
        )

    def close(self):
        """Close connection"""
        if self.driver:
            self.driver.close()

    def get_all_nodes(self, graph_id: str, entity_type: str = None) -> List[EntityNode]:
        """
        Get all entity nodes

        Args:
            graph_id: Graph ID
            entity_type: Entity type filter

        Returns:
            List of entity nodes
        """
        with self.driver.session(database=self.database) as session:
            if entity_type:
                query = """
                    MATCH (n:Entity {graph_id: $graph_id})
                    WHERE n.type = $entity_type
                    RETURN n.uuid AS uuid, n.name AS name, n.type AS entity_type,
                           n.description AS description, n.summary AS summary,
                           n.attributes AS attributes
                """
                result = session.run(query, graph_id=graph_id, entity_type=entity_type)
            else:
                query = """
                    MATCH (n:Entity {graph_id: $graph_id})
                    RETURN n.uuid AS uuid, n.name AS name, n.type AS entity_type,
                           n.description AS description, n.summary AS summary,
                           n.attributes AS attributes
                """
                result = session.run(query, graph_id=graph_id)

            nodes = []
            for record in result:
                nodes.append(EntityNode(
                    uuid=record["uuid"] or "",
                    name=record["name"] or "",
                    entity_type=record["entity_type"] or "Entity",
                    description=record.get("description") or "",
                    summary=record.get("summary") or "",
                    attributes=dict(record.get("attributes") or {})
                ))
            return nodes

    def get_node_by_name(self, graph_id: str, name: str) -> Optional[EntityNode]:
        """Get entity by name"""
        with self.driver.session(database=self.database) as session:
            query = """
                MATCH (n:Entity {graph_id: $graph_id, name: $name})
                RETURN n.uuid AS uuid, n.name AS name, n.type AS entity_type,
                       n.description AS description, n.summary AS summary,
                       n.attributes AS attributes
            """
            result = session.run(query, graph_id=graph_id, name=name)
            record = result.single()

            if record:
                return EntityNode(
                    uuid=record["uuid"] or "",
                    name=record["name"] or "",
                    entity_type=record["entity_type"] or "Entity",
                    description=record.get("description") or "",
                    summary=record.get("summary") or "",
                    attributes=dict(record.get("attributes") or {})
                )
            return None

    def get_node_edges(self, graph_id: str, node_name: str) -> List[Dict]:
        """Get all relations of an entity"""
        with self.driver.session(database=self.database) as session:
            query = """
                MATCH (n:Entity {graph_id: $graph_id, name: $node_name})-[r]-(m)
                RETURN type(r) AS relation_type,
                       startNode(r).name AS source_name,
                       endNode(r).name AS target_name,
                       r.description AS description
            """
            result = session.run(query, graph_id=graph_id, node_name=node_name)

            edges = []
            for record in result:
                edges.append({
                    "type": record["relation_type"],
                    "source": record["source_name"],
                    "target": record["target_name"],
                    "description": record.get("description") or ""
                })
            return edges

    def search_nodes(self, graph_id: str, keyword: str) -> List[EntityNode]:
        """Search entities"""
        with self.driver.session(database=self.database) as session:
            query = """
                MATCH (n:Entity {graph_id: $graph_id})
                WHERE toLower(n.name) CONTAINS toLower($keyword)
                   OR toLower(n.description) CONTAINS toLower($keyword)
                RETURN n.uuid AS uuid, n.name AS name, n.type AS entity_type,
                       n.description AS description, n.summary AS summary,
                       n.attributes AS attributes
                LIMIT 50
            """
            result = session.run(query, graph_id=graph_id, keyword=keyword)

            nodes = []
            for record in result:
                nodes.append(EntityNode(
                    uuid=record["uuid"] or "",
                    name=record["name"] or "",
                    entity_type=record["entity_type"] or "Entity",
                    description=record.get("description") or "",
                    summary=record.get("summary") or "",
                    attributes=dict(record.get("attributes") or {})
                ))
            return nodes

    def get_entities_by_type(self, graph_id: str, entity_type: str) -> FilteredEntities:
        """按类型获取实体"""
        entities = self.get_all_nodes(graph_id, entity_type)
        return FilteredEntities(
            entities=entities,
            query=f"type:{entity_type}"
        )

    def filter_defined_entities(
        self,
        graph_id: str,
        defined_entity_types: Optional[List[str]] = None,
        enrich_with_edges: bool = True
    ) -> FilteredEntities:
        """
        Filter graph nodes, returning only nodes with custom types.

        Args:
            graph_id: Graph ID
            defined_entity_types: Optional whitelist of entity types
            enrich_with_edges: Whether to populate edge information

        Returns:
            FilteredEntities containing matching entities and statistics
        """
        import uuid as uuid_module

        # Get all nodes
        all_nodes = self.get_all_nodes(graph_id)
        total_count = len(all_nodes)

        # Filter nodes
        filtered_entities = []
        entity_types_found = set()

        for node in all_nodes:
            # Skip nodes without custom types
            if node.entity_type in ["Entity", "Node", ""]:
                continue

            # If whitelist provided, check for match
            if defined_entity_types:
                if node.entity_type not in defined_entity_types:
                    continue

            entity_types_found.add(node.entity_type)

            # If edge info needed, get it
            if enrich_with_edges:
                node.related_edges = self.get_node_edges(graph_id, node.name)

            filtered_entities.append(node)

        return FilteredEntities(
            entities=filtered_entities,
            query=""
        )

    def get_entity_with_context(
        self,
        graph_id: str,
        entity_uuid: str
    ) -> Optional[EntityNode]:
        """Get complete context for a single entity"""
        # Find by name
        all_nodes = self.get_all_nodes(graph_id)
        for node in all_nodes:
            if node.uuid == entity_uuid:
                node.related_edges = self.get_node_edges(graph_id, node.name)
                return node
        return None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
