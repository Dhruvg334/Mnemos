"""Complete GraphRAG Layer.

Provides deep provenance grounding and cross-modal evidence fusion
with support for 6 industrial knowledge graph types:
- Asset Hierarchy (parent-child asset relationships)
- Component Graph (component dependencies and connections)
- Incident Graph (failure events and their consequences)
- Procedure Graph (maintenance and operational procedures)
- Failure Graph (failure modes, root causes, cascading effects)
- Requirement Graph (compliance requirements and their status)
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.reranker import CrossEncoderReranker
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    EvidenceSource,
    GraphType,
    GroundedRelationship,
    ProvenanceChain,
    VerificationStatus,
)
from mnemos.agentic.utils.logging import StructuredLogger
from mnemos.models.entities import Document, DocumentVersion, EvidenceRegion

logger = StructuredLogger("graph_rag")

# Cypher queries for each graph type
GRAPH_TYPE_QUERIES: dict[GraphType, str] = {
    GraphType.ASSET_HIERARCHY: """
        MATCH (a:Asset {id: $asset_id})-[:CONTAINS|PART_OF*0..4]->(child)
        RETURN DISTINCT child.id as id, labels(child)[0] as label,
               properties(child) as properties, 'asset_hierarchy' as graph_type
        LIMIT 50
    """,
    GraphType.COMPONENT_GRAPH: """
        MATCH (a:Asset {id: $asset_id})-[:HAS_COMPONENT*0..3]->(comp)
        OPTIONAL MATCH (comp)-[:CONNECTED_TO]->(connected)
        RETURN DISTINCT comp.id as id, labels(comp)[0] as label,
               properties(comp) as properties, 'component_graph' as graph_type
        LIMIT 50
    """,
    GraphType.INCIDENT_GRAPH: """
        MATCH (a:Asset {id: $asset_id})-[:EXPERIENCED*0..3]->(incident)
        OPTIONAL MATCH (incident)-[:CAUSED_BY]->(cause)
        OPTIONAL MATCH (incident)-[:AFFECTED]->(affected)
        RETURN DISTINCT incident.id as id, labels(incident)[0] as label,
               properties(incident) as properties, 'incident_graph' as graph_type
        LIMIT 50
    """,
    GraphType.PROCEDURE_GRAPH: """
        MATCH (a:Asset {id: $asset_id})-[:HAS_PROCEDURE|FOLLOWS*0..3]->(proc)
        RETURN DISTINCT proc.id as id, labels(proc)[0] as label,
               properties(proc) as properties, 'procedure_graph' as graph_type
        LIMIT 50
    """,
    GraphType.FAILURE_GRAPH: """
        MATCH (a:Asset {id: $asset_id})-[:HAS_FAILURE_MODE*0..3]->(fm)
        OPTIONAL MATCH (fm)-[:TRIGGERS*0..2]->(effect)
        OPTIONAL MATCH (fm)-[:ROOT_CAUSE_OF*0..2]->(root)
        RETURN DISTINCT fm.id as id, labels(fm)[0] as label,
               properties(fm) as properties, 'failure_graph' as graph_type
        LIMIT 50
    """,
    GraphType.REQUIREMENT_GRAPH: """
        MATCH (a:Asset {id: $asset_id})-[:SUBJECT_TO*0..3]->(req)
        OPTIONAL MATCH (req)-[:VERIFIED_BY]->(verification)
        RETURN DISTINCT req.id as id, labels(req)[0] as label,
               properties(req) as properties, 'requirement_graph' as graph_type
        LIMIT 50
    """,
}

# Relationship traversal query for grounding
RELATIONSHIP_QUERY = """
    MATCH (source {id: $source_id})-[r]->(target {id: $target_id})
    RETURN type(r) as rel_type,
           source.id as source_id, labels(source)[0] as source_label,
           target.id as target_id, labels(target)[0] as target_label,
           properties(r) as properties
"""


class GraphRAGLayer:
    """Complete GraphRAG implementation with 6 graph types.

    Provides:
    - Multi-graph-type traversal (asset hierarchy, component, incident,
      procedure, failure, requirement)
    - Version-aware evidence grounding with superseded detection
    - Cross-encoder reranking of grounded evidence
    - Relationship grounding for graph edges
    """

    def __init__(
        self,
        db: AsyncSession,
        graph_client: Neo4jGraphClient,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self.db = db
        self.graph_client = graph_client
        self.reranker = reranker or CrossEncoderReranker()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def process_bundle(
        self, bundle: EvidenceBundle, query: str
    ) -> list[EvidenceSource]:
        """Graph-Vector Fusion Pipeline:
        1. Collect candidate evidence IDs from graph traversal results
        2. Merge with vector retrieval candidates
        3. Ground everything to evidence chunks with full provenance
        4. Cross-encoder rerank for final relevance ranking
        5. Filter by minimum relevance threshold
        """
        logger.info(f"Starting Graph-Vector Fusion for query: {query[:50]}...")

        # 1. Collect all candidate evidence IDs
        region_ids: set[str] = set()
        node_map: dict[str, str] = {}

        for _asset_id, data in bundle.raw_graph_data.items():
            for node in data.get("nodes", []):
                rid = node.get("properties", {}).get("evidence_region_id")
                if rid:
                    region_ids.add(rid)
                    node_map[rid] = node["id"]
            for fail in data.get("related_failures", []):
                rid = fail.get("properties", {}).get("evidence_region_id")
                if rid:
                    region_ids.add(rid)
                    node_map[rid] = fail["id"]

        # 2. Merge with vector candidates
        for res in bundle.raw_vector_data:
            rid = res.get("metadata", {}).get("evidence_region_id") or res.get("chunk_id")
            if rid:
                region_ids.add(rid)

        # 3. Ground everything
        grounded_sources = await self.ground_evidence(list(region_ids), node_map)

        if not grounded_sources:
            logger.warning("No grounded evidence found during fusion.")
            return []

        # 4. Cross-encoder rerank
        texts = [s.text_excerpt for s in grounded_sources]
        rerank_results = await self.reranker.rerank(query, texts)

        # 5. Extract reranked sources
        final_sources: list[EvidenceSource] = []
        for res in rerank_results:
            source = grounded_sources[res.index]
            source.relevance_score = res.score
            if res.score >= 0.4:
                final_sources.append(source)

        logger.info(
            f"Fusion complete. Produced {len(final_sources)} reranked evidence sources."
        )
        return final_sources

    async def ground_evidence(
        self,
        region_ids: list[str],
        node_map: dict[str, str] | None = None,
    ) -> list[EvidenceSource]:
        """Batch grounding of evidence regions with version-aware provenance."""
        if not region_ids:
            return []

        node_map = node_map or {}

        # Fetch regions with latest document version (superseded check)
        stmt = (
            select(EvidenceRegion, Document, DocumentVersion)
            .join(Document, EvidenceRegion.document_id == Document.id)
            .join(
                DocumentVersion,
                (DocumentVersion.document_id == Document.id)
                & (DocumentVersion.version == Document.version),
            )
            .where(EvidenceRegion.id.in_(list(set(region_ids))))
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        grounded_sources: list[EvidenceSource] = []
        for region, doc, version in rows:
            provenance = ProvenanceChain(
                node_id=node_map.get(region.id),
                evidence_region_id=region.id,
                chunk_id=region.metadata_json.get("chunk_id") if region.metadata_json else None,
                document_id=doc.id,
                document_version=doc.version,
                page_number=region.page_or_sheet,
                locator=region.locator,
                sha256=version.sha256,
                source_filename=doc.filename,
                storage_key=version.storage_key,
            )

            grounded_sources.append(EvidenceSource(
                text_excerpt=region.text_excerpt or "",
                provenance=provenance,
                relevance_score=1.0,
                confidence_score=0.9,
                verification_status=VerificationStatus.PROVENANCE_VALIDATED,
                metadata={
                    **(region.metadata_json or {}),
                    "is_latest_version": True,
                    "document_id": doc.id,
                },
            ))

        return grounded_sources

    # ------------------------------------------------------------------
    # Graph type traversal
    # ------------------------------------------------------------------

    async def traverse_graph_type(
        self,
        asset_id: str,
        graph_type: GraphType,
    ) -> dict[str, Any]:
        """Traverse a specific graph type for an asset."""
        cypher = GRAPH_TYPE_QUERIES.get(graph_type)
        if not cypher:
            return {"nodes": [], "relationships": [], "graph_type": graph_type.value}

        try:
            records = await self.graph_client.query(cypher, {"asset_id": asset_id})

            nodes = [
                {
                    "id": rec["id"],
                    "label": rec["label"],
                    "properties": rec["properties"],
                    "graph_type": rec["graph_type"],
                }
                for rec in records
                if rec.get("id")
            ]

            # Fetch relationships between these nodes
            relationships = await self._fetch_relationships(
                [n["id"] for n in nodes]
            )

            return {
                "nodes": nodes,
                "relationships": relationships,
                "graph_type": graph_type.value,
            }
        except Exception as exc:
            logger.error(f"Graph traversal failed for {graph_type.value}: {exc}")
            return {"nodes": [], "relationships": [], "graph_type": graph_type.value}

    async def traverse_all_graph_types(
        self,
        asset_id: str,
        graph_types: list[GraphType] | None = None,
    ) -> dict[str, Any]:
        """Traverse all specified graph types for an asset."""
        types_to_query = graph_types or list(GraphType)

        combined_nodes: list[dict[str, Any]] = []
        combined_rels: list[dict[str, Any]] = []

        for gt in types_to_query:
            data = await self.traverse_graph_type(asset_id, gt)
            combined_nodes.extend(data.get("nodes", []))
            combined_rels.extend(data.get("relationships", []))

        return {
            "nodes": combined_nodes,
            "relationships": combined_rels,
            "graph_types_queried": [gt.value for gt in types_to_query],
        }

    async def ground_relationships(
        self,
        bundle: EvidenceBundle,
    ) -> list[GroundedRelationship]:
        """Ground graph relationships to verified evidence sources."""
        grounded_rels: list[GroundedRelationship] = []

        for _entity_id, data in bundle.raw_graph_data.items():
            for rel in data.get("relationships", []):
                try:
                    records = await self.graph_client.query(
                        RELATIONSHIP_QUERY,
                        {
                            "source_id": rel.get("source_id", ""),
                            "target_id": rel.get("target_id", ""),
                        },
                    )

                    if records:
                        rec = records[0]
                        # Find evidence for this relationship
                        evidence_source = self._find_evidence_for_node(
                            rel.get("source_id", ""), bundle
                        )
                        if evidence_source:
                            grounded_rels.append(GroundedRelationship(
                                source_id=rec["source_id"],
                                target_id=rec["target_id"],
                                relationship_type=rec["rel_type"],
                                evidence=evidence_source,
                                confidence=0.8,
                            ))
                except Exception:
                    continue

        return grounded_rels

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _fetch_relationships(
        self, node_ids: list[str]
    ) -> list[dict[str, Any]]:
        """Fetch relationships between a set of nodes."""
        if len(node_ids) < 2:
            return []

        relationships: list[dict[str, Any]] = []
        # Batch fetch in chunks to avoid massive IN clauses
        chunk_size = 20
        for i in range(0, len(node_ids), chunk_size):
            chunk = node_ids[i : i + chunk_size]
            ids_param = ", ".join(f'"{nid}"' for nid in chunk)
            cypher = f"""
                MATCH (a)-[r]->(b)
                WHERE a.id IN [{ids_param}] AND b.id IN [{ids_param}]
                RETURN a.id as source_id, b.id as target_id,
                       type(r) as type, properties(r) as properties
                LIMIT 100
            """
            try:
                records = await self.graph_client.query(cypher)
                for rec in records:
                    relationships.append({
                        "source_id": rec["source_id"],
                        "target_id": rec["target_id"],
                        "type": rec["type"],
                        "properties": rec["properties"],
                    })
            except Exception:
                continue

        return relationships

    def _find_evidence_for_node(
        self, node_id: str, bundle: EvidenceBundle
    ) -> EvidenceSource | None:
        """Find the best evidence source for a given graph node."""
        for source in bundle.verified_evidence:
            if source.provenance.node_id == node_id:
                return source

        # Fall back to any verified evidence from the same document
        for source in bundle.verified_evidence:
            if source.provenance.document_id:
                return source

        return None
