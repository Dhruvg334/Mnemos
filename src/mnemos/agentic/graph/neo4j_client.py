from typing import Any

from neo4j import AsyncGraphDatabase

from mnemos.agentic.graph.interfaces import (
    BaseGraphClient,
    GraphNode,
    GraphQueryResult,
    GraphRelationship,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("graph_client")

class Neo4jGraphClient(BaseGraphClient):
    """
    Production Neo4j client for industrial knowledge graph traversal.
    """
    def __init__(self, uri: str, user: str, password: str):
        self.driver = AsyncGraphDatabase.driver(uri, auth=(user, password))

    async def close(self):
        await self.driver.close()

    async def query(self, cypher: str, parameters: dict[str, Any] = None) -> list[dict[str, Any]]:
        async with self.driver.session() as session:
            result = await session.run(cypher, parameters or {})
            records = await result.data()
            return records

    async def get_asset_context(self, asset_id: str, depth: int = 2, max_nodes: int = 100) -> GraphQueryResult:
        cypher = """
        MATCH (a:Asset {id: $asset_id})
        CALL apoc.path.subgraphAll(a, {
            maxDepth: $depth,
            limit: $max_nodes,
            relationshipFilter: 'CONTAINS>|HAS_COMPONENT>|PART_OF>|CONNECTED_TO'
        })
        YIELDS nodes, relationships
        RETURN [n in nodes | {id: n.id, label: labels(n)[0], properties: properties(n)}] as nodes,
               [r in relationships | {source_id: id(startNode(r)), target_id: id(endNode(r)), type: type(r), properties: properties(r)}] as rels
        """
        records = await self.query(cypher, {"asset_id": asset_id, "depth": depth, "max_nodes": max_nodes})
        if not records:
            return GraphQueryResult(nodes=[], relationships=[])

        data = records[0]
        return GraphQueryResult(
            nodes=[GraphNode(**n) for n in data["nodes"]],
            relationships=[GraphRelationship(**r) for r in data["rels"]]
        )

    async def find_related_failures(self, asset_id: str) -> list[GraphNode]:
        cypher = """
        MATCH (a:Asset {id: $asset_id})
        MATCH (a)-[:HAS_COMPONENT*0..3]->(comp)-[:EXPERIENCED]->(f:Failure)
        RETURN f.id as id, labels(f)[0] as label, properties(f) as properties
        """
        records = await self.query(cypher, {"asset_id": asset_id})
        return [GraphNode(**r) for r in records]
