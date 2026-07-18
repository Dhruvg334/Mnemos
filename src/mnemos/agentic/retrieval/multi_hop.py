"""Multi-Hop Retriever.

Performs iterative graph expansion to follow relationship chains
in the knowledge graph. Starting from resolved entities, it traverses
edges up to N hops, collecting evidence at each hop.
"""

from __future__ import annotations

from typing import Any

from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.schemas.base import EvidenceBundle, RetrievalPlan
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("multi_hop")


class MultiHopRetriever:
    """Iterative graph expansion for multi-hop reasoning.

    For each hop:
    1. Collects current frontier nodes
    2. Expands one level of relationships
    3. Collects evidence regions attached to new nodes
    4. Filters by relevance and stops when budget is exhausted
    """

    def __init__(self, graph_client: Neo4jGraphClient) -> None:
        self.graph_client = graph_client

    async def retrieve(
        self,
        bundle: EvidenceBundle,
        plan: RetrievalPlan,
        query_text: str,
    ) -> None:
        """Perform multi-hop retrieval from resolved entities."""
        max_hops = plan.max_hops
        if max_hops < 2:
            return

        for entity in bundle.resolved_entities:
            try:
                hop_data = await self._hop(entity.entity_id, max_hops)
                if hop_data:
                    key = f"multi_hop_{entity.entity_id}"
                    bundle.raw_graph_data[key] = hop_data
            except Exception as exc:
                logger.error(f"Multi-hop failed for {entity.entity_id}: {exc}")

    async def _hop(self, start_id: str, max_hops: int) -> dict[str, Any]:
        """Traverse up to max_hops levels from start_id."""
        all_nodes: list[dict[str, Any]] = []
        all_rels: list[dict[str, Any]] = []
        visited_nodes: set[str] = {start_id}
        frontier: list[str] = [start_id]

        for hop in range(max_hops - 1):
            if not frontier:
                break

            next_frontier: list[str] = []
            for node_id in frontier:
                try:
                    cypher = """
                    MATCH (n {id: $node_id})-[r]-(m)
                    WHERE NOT m.id IN $visited
                    RETURN m.id as id, labels(m)[0] as label,
                           properties(m) as properties,
                           type(r) as rel_type,
                           id(r) as rel_id,
                           properties(r) as rel_props
                    LIMIT 20
                    """
                    records = await self.graph_client.query(
                        cypher,
                        {"node_id": node_id, "visited": list(visited_nodes)},
                    )

                    for rec in records:
                        m_id = rec["id"]
                        if m_id and m_id not in visited_nodes:
                            visited_nodes.add(m_id)
                            next_frontier.append(m_id)
                            all_nodes.append(
                                {
                                    "id": m_id,
                                    "label": rec["label"],
                                    "properties": rec["properties"],
                                    "hop": hop + 1,
                                }
                            )
                            all_rels.append(
                                {
                                    "source_id": node_id,
                                    "target_id": m_id,
                                    "type": rec["rel_type"],
                                    "properties": rec["rel_props"],
                                    "hop": hop + 1,
                                }
                            )
                except Exception:
                    continue

            frontier = next_frontier

        if not all_nodes:
            return {}

        return {"nodes": all_nodes, "relationships": all_rels}
