"""Citation Extractor.

Extracts structured citations from verified evidence, linking each
piece of evidence back to its source document with full provenance.
"""

from __future__ import annotations

from mnemos.agentic.schemas.base import (
    Citation,
    EvidenceBundle,
    EvidenceSource,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("citation_extractor")


class CitationExtractor:
    """Extracts structured citations from verified evidence.

    For each verified EvidenceSource, creates a Citation with:
    - Full document provenance (id, version, sha256)
    - Page/locator information
    - Retrieval source tracking
    - Relevance and confidence scores
    """

    def extract(self, bundle: EvidenceBundle) -> list[Citation]:
        """Extract citations from all verified evidence in the bundle."""
        citations: list[Citation] = []
        seen_provenances: set[str] = set()

        for idx, source in enumerate(bundle.verified_evidence):
            prov = source.provenance
            dedup_key = f"{prov.document_id}:{prov.evidence_region_id}:{prov.document_version}"

            if dedup_key in seen_provenances:
                continue
            seen_provenances.add(dedup_key)

            retrieval_sources = self._determine_retrieval_sources(
                source, bundle
            )

            citation = Citation(
                citation_id=f"cit_{bundle.query_id}_{idx:04d}",
                evidence_region_id=prov.evidence_region_id,
                document_id=prov.document_id,
                document_version=prov.document_version,
                chunk_id=prov.chunk_id,
                page_number=prov.page_number,
                locator=prov.locator,
                text_excerpt=source.text_excerpt[:500],
                retrieval_sources=retrieval_sources,
                relevance_score=source.relevance_score,
                confidence_score=source.confidence_score,
                is_latest_version=prov.document_version == self._get_max_version(
                    prov.document_id, bundle
                ),
            )
            citations.append(citation)

        logger.info(
            f"Extracted {len(citations)} citations from "
            f"{len(bundle.verified_evidence)} verified sources"
        )
        return citations

    def _determine_retrieval_sources(
        self,
        source: EvidenceSource,
        bundle: EvidenceBundle,
    ) -> list[str]:
        """Determine which retrieval strategies contributed this evidence."""
        sources: list[str] = []
        region_id = source.provenance.evidence_region_id

        # Check if region came from graph
        for _entity_id, data in bundle.raw_graph_data.items():
            for node in data.get("nodes", []):
                props = node.get("properties", {})
                if props.get("evidence_region_id") == region_id:
                    sources.append("graph")
                    break

        # Check if region came from vector
        for vec in bundle.raw_vector_data:
            meta = vec.get("metadata", {})
            if meta.get("evidence_region_id") == region_id:
                sources.append("vector")
                break

        # Check if region came from lexical
        for vec in bundle.raw_vector_data:
            meta = vec.get("metadata", {})
            if meta.get("type") == "lexical" and meta.get("evidence_region_id") == region_id:
                if "lexical" not in sources:
                    sources.append("lexical")
                break

        if not sources:
            sources.append("unknown")

        return sources

    @staticmethod
    def _get_max_version(document_id: str, bundle: EvidenceBundle) -> int:
        """Get the maximum version seen for a document across all evidence."""
        max_version = 1
        for source in bundle.verified_evidence:
            if source.provenance.document_id == document_id:
                max_version = max(max_version, source.provenance.document_version)
        return max_version
