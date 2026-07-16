import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.reranker import CrossEncoderReranker
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    EvidenceSource,
    ProvenanceChain,
    VerificationStatus,
)
from mnemos.agentic.utils.logging import StructuredLogger
from mnemos.models.entities import Document, DocumentVersion, EvidenceRegion

logger = StructuredLogger("graph_rag")

class GraphRAGLayer:
    """
    Advanced GraphRAG implementation providing deep provenance and cross-modal grounding.
    Implements Graph-Vector Fusion where graph traversal provides retrieval guidance.
    """

    def __init__(
        self,
        db: AsyncSession,
        graph_client: Neo4jGraphClient,
        reranker: CrossEncoderReranker | None = None
    ):
        self.db = db
        self.graph_client = graph_client
        self.reranker = reranker or CrossEncoderReranker()

    async def ground_evidence(self, region_ids: list[str], node_map: dict[str, str] = None) -> list[EvidenceSource]:
        """
        Batched grounding of evidence regions with full version-aware provenance.
        Ensures only the latest document version is retrieved (superseded check).
        """
        if not region_ids:
            return []

        node_map = node_map or {}

        # Batch fetch all required regions and their latest document versions
        # This join on Document.version == DocumentVersion.version automatically
        # filters out superseded document revisions.
        stmt = (
            select(EvidenceRegion, Document, DocumentVersion)
            .join(Document, EvidenceRegion.document_id == Document.id)
            .join(DocumentVersion, (DocumentVersion.document_id == Document.id) & (DocumentVersion.version == DocumentVersion.version))
            .where(EvidenceRegion.id.in_(list(set(region_ids))))
            .where(Document.version == DocumentVersion.version)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        grounded_sources = []
        for region, doc, version in rows:
            provenance = ProvenanceChain(
                node_id=node_map.get(region.id),
                evidence_region_id=region.id,
                chunk_id=region.metadata_json.get("chunk_id"),
                document_id=doc.id,
                document_version=doc.version,
                page_number=region.page_or_sheet,
                locator=region.locator,
                sha256=version.sha256,
                source_filename=doc.filename,
                storage_key=version.storage_key
            )

            grounded_sources.append(EvidenceSource(
                text_excerpt=region.text_excerpt or "",
                provenance=provenance,
                relevance_score=1.0,
                confidence_score=doc.metadata.get("confidence", 0.9) if hasattr(doc, 'metadata') and doc.metadata else 0.9,
                verification_status=VerificationStatus.PROVENANCE_VALIDATED,
                metadata=region.metadata_json
            ))

        return grounded_sources

    async def process_bundle(self, bundle: EvidenceBundle, query: str) -> list[EvidenceSource]:
        """
        Graph-Vector Fusion Pipeline:
        1. Graph Traversal -> Candidate Evidence IDs
        2. Vector Retrieval -> Candidate Chunk IDs
        3. Merge and Deduplicate Candidates
        4. Ground Candidates to Evidence Chunks
        5. Cross-Encoder Rerank (Final ranking uses chunks)
        """
        logger.info(f"Starting Graph-Vector Fusion for query: {query[:50]}...")

        # 1. Collect all candidate evidence IDs for batched grounding
        region_ids: set[str] = set()
        node_map: dict[str, str] = {} # region_id -> node_id

        # From Graph Guidance (Traversal results)
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

        # 2. Merge with Vector Retrieval candidates
        for res in bundle.raw_vector_data:
            # We accept both chunk_id (from vector) and evidence_region_id (from lexical/metadata)
            # This is the point where graph-guided candidates and vector candidates are fused
            rid = res.get("metadata", {}).get("evidence_region_id") or res.get("chunk_id")
            if rid:
                region_ids.add(rid)

        # 3. Ground everything in parallel (ID -> Chunk mapping)
        grounded_sources = await self.ground_evidence(list(region_ids), node_map)

        if not grounded_sources:
            logger.warning("No grounded evidence found during fusion.")
            return []

        # 4. Final ranking must use evidence chunks via Cross-Encoder reranking
        # This replaces vector/graph scores with actual grounded relevance
        texts = [s.text_excerpt for s in grounded_sources]
        rerank_results = await self.reranker.rerank(query, texts)

        # 5. Extract reranked sources
        final_sources = []
        for res in rerank_results:
            source = grounded_sources[res.index]
            source.relevance_score = res.score
            # Confidence filtering
            if res.score >= 0.4:
                final_sources.append(source)

        logger.info(f"Fusion complete. Produced {len(final_sources)} reranked evidence sources.")
        return final_sources
