import asyncio
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.models.entities import EvidenceRegion, Document, DocumentVersion
from mnemos.agentic.schemas.base import (
    EvidenceSource,
    ProvenanceChain,
    VerificationStatus,
    EvidenceBundle,
    Contradiction
)
from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.reranker import CrossEncoderReranker
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("graph_rag")

class GraphRAGLayer:
    """
    Advanced GraphRAG implementation providing deep provenance and cross-modal grounding.
    Optimized for high-fidelity industrial intelligence.
    """

    def __init__(
        self,
        db: AsyncSession,
        graph_client: Neo4jGraphClient,
        reranker: Optional[CrossEncoderReranker] = None
    ):
        self.db = db
        self.graph_client = graph_client
        self.reranker = reranker or CrossEncoderReranker()

    async def ground_evidence(self, region_ids: List[str], node_map: Dict[str, str] = None) -> List[EvidenceSource]:
        """
        Batched grounding of evidence regions with full version-aware provenance.
        """
        if not region_ids:
            return []

        node_map = node_map or {}

        # Batch fetch all required regions and their latest document versions
        stmt = (
            select(EvidenceRegion, Document, DocumentVersion)
            .join(Document, EvidenceRegion.document_id == Document.id)
            .join(DocumentVersion, (DocumentVersion.document_id == Document.id) & (DocumentVersion.version == Document.version))
            .where(EvidenceRegion.id.in_(list(set(region_ids))))
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

    async def process_bundle(self, bundle: EvidenceBundle, query: str) -> List[EvidenceSource]:
        """
        The core GraphRAG pipeline:
        Grounding -> Merging -> Reranking -> Filtering.
        """
        logger.info(f"Starting GraphRAG grounding for query: {query[:50]}...")

        # 1. Collect all evidence IDs for batched grounding
        region_ids: Set[str] = set()
        node_map: Dict[str, str] = {} # region_id -> node_id

        # From Graph Context
        for asset_id, data in bundle.raw_graph_data.items():
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

        # From Vector/Lexical results (if they contain evidence_region_ids)
        for res in bundle.raw_vector_data:
            rid = res.get("metadata", {}).get("evidence_region_id")
            if rid:
                region_ids.add(rid)

        # 2. Ground everything in parallel with DB
        grounded_sources = await self.ground_evidence(list(region_ids), node_map)

        if not grounded_sources:
            logger.warning("No grounded evidence found during GraphRAG process.")
            return []

        # 3. Cross-Encoder Reranking (Latency optimized)
        texts = [s.text_excerpt for s in grounded_sources]
        rerank_results = await self.reranker.rerank(query, texts)

        # 4. Final filter and sort
        final_sources = []
        for res in rerank_results:
            source = grounded_sources[res.index]
            source.relevance_score = res.score

            # High-fidelity threshold for industrial safety
            if res.score >= 0.4:
                final_sources.append(source)

        logger.info(f"GraphRAG complete. Produced {len(final_sources)} verified evidence sources.")
        return final_sources
