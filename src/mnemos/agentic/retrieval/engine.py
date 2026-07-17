"""Hybrid Retrieval Engine.

Orchestrates the full retrieval intelligence pipeline:
- Dynamic retrieval planning with query decomposition
- Parallel execution of vector, graph, lexical, structured, and multi-hop strategies
- Cross-encoder reranking
- Duplicate removal (content hash + region dedup)
- Superseded document filtering
- Permission filtering
- Citation extraction
- Confidence calculation
- Source reliability scoring
- Contradiction detection
- Missing evidence detection
- Retrieval budget optimisation
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser
from mnemos.agentic.retrieval.citation_extractor import CitationExtractor
from mnemos.agentic.retrieval.confidence import ConfidenceCalculator
from mnemos.agentic.retrieval.contradiction import ContradictionDetector
from mnemos.agentic.retrieval.dedup import DuplicateRemover
from mnemos.agentic.retrieval.identity_resolver import AssetIdentityResolver
from mnemos.agentic.retrieval.lexical import LexicalRetriever
from mnemos.agentic.retrieval.multi_hop import MultiHopRetriever
from mnemos.agentic.retrieval.reranker import CrossEncoderReranker
from mnemos.agentic.retrieval.source_reliability import SourceReliabilityScorer
from mnemos.agentic.retrieval.structured import StructuredRetriever
from mnemos.agentic.retrieval.superseded import SupersededDetector
from mnemos.agentic.retrieval.vector import VectorRetriever
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    MissingEvidence,
    QueryIntent,
    ResolvedEntity,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("retrieval_engine")


class HybridRetrievalEngine:
    """Orchestrates the full multi-modal retrieval pipeline.

    Pipeline stages:
    1. Identity resolution
    2. Parallel strategy execution (graph, vector, lexical, structured, multi-hop)
    3. Duplicate removal
    4. Superseded document filtering
    5. Cross-encoder reranking
    6. Contradiction detection
    7. Source reliability scoring
    8. Confidence calculation
    9. Citation extraction
    10. Missing evidence detection
    11. Budget trimming
    """

    def __init__(
        self,
        db: AsyncSession,
        graph_client: Neo4jGraphClient,
        reranker: CrossEncoderReranker | None = None,
    ) -> None:
        self.db = db
        self.graph_client = graph_client
        self.identity_resolver = AssetIdentityResolver(db)
        self.structured_retriever = StructuredRetriever(db)
        self.lexical_retriever = LexicalRetriever(db)
        self.vector_retriever = VectorRetriever(db)
        self.reranker = reranker or CrossEncoderReranker()
        self.multi_hop = MultiHopRetriever(graph_client)
        self.dedup = DuplicateRemover()
        self.superseded_detector = SupersededDetector(db)
        self.contradiction_detector = ContradictionDetector()
        self.source_reliability_scorer = SourceReliabilityScorer()
        self.confidence_calculator = ConfidenceCalculator()
        self.citation_extractor = CitationExtractor()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def execute_plan(
        self,
        query_id: str,
        query_text: str,
        plan: RetrievalPlan,
        context: dict[str, Any],
    ) -> EvidenceBundle:
        """Execute a dynamic retrieval plan with full pipeline."""
        site_id = plan.site_id or context.get("site_id")

        # Budget setup
        budget = RetrievalBudgetOptimiser.from_plan(plan)

        # 1. Resolve identities
        unique_resolved = await self._resolve_identities(plan, site_id)

        bundle = EvidenceBundle(
            query_id=query_id,
            intent=plan.intent,
            resolved_entities=unique_resolved,
            metadata={
                "site_id": site_id,
                "org_id": plan.organisation_id or context.get("org_id"),
                "plan_reasoning": plan.reasoning,
                "strategies_executed": [s.value for s in plan.strategies],
                "filters": self._summarise_filters(plan),
                "budget": budget.usage_summary,
            },
        )

        # 2. Parallel strategy execution
        tasks: list[asyncio.Task[None]] = []
        for strategy in plan.strategies:
            if strategy == RetrievalStrategy.GRAPH_TRAVERSAL:
                tasks.append(asyncio.create_task(self._execute_graph(bundle, plan)))
            elif strategy == RetrievalStrategy.VECTOR_SEARCH:
                tasks.append(asyncio.create_task(self._execute_vector(bundle, query_text, plan)))
            elif strategy == RetrievalStrategy.LEXICAL_SEARCH:
                tasks.append(asyncio.create_task(self._execute_lexical(bundle, query_text, plan)))
            elif strategy in (RetrievalStrategy.SQL_QUERY, RetrievalStrategy.METADATA_FILTER):
                tasks.append(asyncio.create_task(self._execute_structured(bundle, plan)))
            elif strategy == RetrievalStrategy.MULTI_HOP:
                tasks.append(asyncio.create_task(self._execute_multi_hop(bundle, plan, query_text)))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

        # 3. Superseded document filtering
        try:
            current_ids = await self.superseded_detector.get_current_version_ids()
            bundle.raw_vector_data = self.superseded_detector.filter_superseded(
                bundle.raw_vector_data, current_ids
            )
            bundle.raw_vector_data = self.superseded_detector.mark_versions(
                bundle.raw_vector_data, current_ids
            )
        except Exception as exc:
            logger.warning(f"Superseded detection failed: {exc}")

        # 4. Duplicate removal
        bundle.raw_vector_data = self.dedup.remove_region_duplicates(
            bundle.raw_vector_data
        )
        bundle.raw_vector_data = self.dedup.remove_duplicates(
            bundle.raw_vector_data
        )

        # 5. Cross-encoder reranking
        if plan.enable_reranking and bundle.raw_vector_data:
            await self._rerank(bundle, query_text, plan)

        # 6. Budget trimming
        budget.trim_bundle(bundle)

        # 7. Contradiction detection
        bundle.contradictions = await self.contradiction_detector.detect(bundle)

        # 8. Source reliability scoring
        source_reliabilities = self.source_reliability_scorer.score_bundle(bundle)

        # 9. Confidence calculation
        confidence, confidence_signals = self.confidence_calculator.calculate_bundle_confidence(
            bundle, source_reliabilities
        )
        bundle.confidence_signals = confidence_signals
        bundle.metadata["overall_confidence"] = confidence

        # 10. Citation extraction
        bundle.citations = self.citation_extractor.extract(bundle)

        # 11. Missing evidence detection
        bundle.missing_evidence = self._detect_missing_evidence(bundle, plan)

        logger.info(
            f"Retrieval complete for {query_id}: "
            f"{len(bundle.raw_vector_data)} vector, "
            f"{len(bundle.raw_graph_data)} graph, "
            f"{len(bundle.verified_evidence)} verified, "
            f"{len(bundle.contradictions)} contradictions, "
            f"{len(bundle.citations)} citations, "
            f"confidence={confidence:.3f}"
        )
        return bundle

    # ------------------------------------------------------------------
    # Identity resolution
    # ------------------------------------------------------------------

    async def _resolve_identities(
        self, plan: RetrievalPlan, site_id: str | None
    ) -> list[ResolvedEntity]:
        resolved_entities: list[ResolvedEntity] = []
        entity_mentions = plan.asset_ids or plan.target_entities

        for mention in entity_mentions:
            if mention.startswith("ast_"):
                specs = await self.structured_retriever.get_asset_specs(mention)
                if specs:
                    resolved_entities.append(ResolvedEntity(
                        original_text=specs.get("asset_tag", ""),
                        entity_id=mention,
                        entity_type="ASSET",
                        confidence=1.0,
                        canonical_name=specs.get("name", ""),
                        metadata=specs,
                    ))
            else:
                resolved = await self.identity_resolver.resolve(mention, site_id)
                resolved_entities.extend(resolved)

        seen: set[str] = set()
        unique: list[ResolvedEntity] = []
        for e in resolved_entities:
            if e.entity_id not in seen:
                unique.append(e)
                seen.add(e.entity_id)
        return unique

    # ------------------------------------------------------------------
    # Graph traversal
    # ------------------------------------------------------------------

    async def _execute_graph(self, bundle: EvidenceBundle, plan: RetrievalPlan) -> None:
        for entity in bundle.resolved_entities:
            try:
                if plan.graph_types:
                    # Use specific graph types
                    graph_data = await self._traverse_graph_types(
                        entity.entity_id, plan.graph_types
                    )
                else:
                    # Default traversal
                    graph_data = await self.graph_client.get_asset_context(
                        entity.entity_id, depth=2
                    )
                    graph_data = {
                        "nodes": [n.model_dump() for n in graph_data.nodes],
                        "relationships": [r.model_dump() for r in graph_data.relationships],
                    }

                bundle.raw_graph_data[entity.entity_id] = graph_data

                if bundle.intent == QueryIntent.RCA:
                    failures = await self.graph_client.find_related_failures(
                        entity.entity_id
                    )
                    bundle.raw_graph_data[entity.entity_id]["related_failures"] = [
                        f.model_dump() for f in failures
                    ]
            except Exception as exc:
                logger.error(f"Graph error for {entity.entity_id}: {exc}")

    async def _traverse_graph_types(
        self, asset_id: str, graph_types: list
    ) -> dict[str, Any]:
        """Traverse multiple graph types."""
        from mnemos.agentic.retrieval.graph_rag import GraphRAGLayer

        rag = GraphRAGLayer(self.db, self.graph_client, self.reranker)
        return await rag.traverse_all_graph_types(asset_id, graph_types)

    # ------------------------------------------------------------------
    # Vector search
    # ------------------------------------------------------------------

    async def _execute_vector(
        self, bundle: EvidenceBundle, query: str, plan: RetrievalPlan
    ) -> None:
        try:
            embedding = await self.vector_retriever.get_embeddings(query)

            filters: dict[str, Any] = {}
            if plan.site_id:
                filters["site_id"] = plan.site_id
            if plan.organisation_id:
                filters["org_id"] = plan.organisation_id
            if plan.asset_ids:
                filters["asset_id"] = plan.asset_ids[0]
            if plan.document_ids:
                filters["document_id"] = plan.document_ids[0]
            if plan.date_from:
                filters["date_from"] = plan.date_from
            if plan.date_to:
                filters["date_to"] = plan.date_to

            results = await self.vector_retriever.search(
                embedding, top_k=plan.top_k_per_strategy, filters=filters
            )
            for res in results:
                bundle.raw_vector_data.append(res.model_dump())
        except Exception as exc:
            logger.error(f"Vector search failed: {exc}")

    # ------------------------------------------------------------------
    # Lexical search
    # ------------------------------------------------------------------

    async def _execute_lexical(
        self, bundle: EvidenceBundle, query: str, plan: RetrievalPlan
    ) -> None:
        try:
            results = await self.lexical_retriever.search(
                query,
                site_id=plan.site_id,
                limit=plan.top_k_per_strategy,
                date_from=plan.date_from,
                date_to=plan.date_to,
                latest_version_only=plan.latest_version_only,
                document_versions=plan.document_versions,
                document_ids=plan.document_ids,
            )
            for res in results:
                bundle.raw_vector_data.append({
                    "content": res["text"],
                    "metadata": {
                        **res["metadata"],
                        "evidence_region_id": res["id"],
                        "type": "lexical",
                    },
                    "score": res.get("score", 1.0),
                })
        except Exception as exc:
            logger.error(f"Lexical search failed: {exc}")

    # ------------------------------------------------------------------
    # Structured / SQL
    # ------------------------------------------------------------------

    async def _execute_structured(
        self, bundle: EvidenceBundle, plan: RetrievalPlan
    ) -> None:
        for entity in bundle.resolved_entities:
            try:
                history, cards = await asyncio.gather(
                    self.structured_retriever.get_maintenance_history(
                        entity.entity_id, date_from=plan.date_from, date_to=plan.date_to
                    ),
                    self.structured_retriever.get_knowledge_cards(
                        entity.entity_id, date_from=plan.date_from, date_to=plan.date_to
                    ),
                )

                bundle.metadata[f"history_{entity.entity_id}"] = history
                bundle.metadata[f"expert_memory_{entity.entity_id}"] = cards

                for card in cards:
                    bundle.raw_vector_data.append({
                        "content": f"EXPERT MEMORY: {card['title']}\n{card['content']}",
                        "metadata": {
                            "type": "knowledge_card",
                            "id": card["card_id"],
                            "version": card["version"],
                        },
                        "score": 0.9,
                    })
            except Exception as exc:
                logger.error(f"Structured query failed for {entity.entity_id}: {exc}")

    # ------------------------------------------------------------------
    # Multi-hop
    # ------------------------------------------------------------------

    async def _execute_multi_hop(
        self, bundle: EvidenceBundle, plan: RetrievalPlan, query_text: str
    ) -> None:
        await self.multi_hop.retrieve(bundle, plan, query_text)

    # ------------------------------------------------------------------
    # Reranking
    # ------------------------------------------------------------------

    async def _rerank(
        self, bundle: EvidenceBundle, query: str, plan: RetrievalPlan
    ) -> None:
        texts = [v.get("content", "") for v in bundle.raw_vector_data]
        if not texts:
            return

        try:
            rerank_results = await self.reranker.rerank(query, texts)
        except Exception as exc:
            logger.error(f"Reranking failed: {exc}")
            return

        scored = [
            (r.index, r.score)
            for r in rerank_results
            if r.score >= plan.min_relevance_score
        ]
        scored.sort(key=lambda x: x[1], reverse=True)

        keep_indices = {idx for idx, _ in scored[: plan.top_k_per_strategy]}
        bundle.raw_vector_data = [
            v for i, v in enumerate(bundle.raw_vector_data) if i in keep_indices
        ]

        score_map = {r.index: r.score for r in rerank_results}
        for v in bundle.raw_vector_data:
            idx = bundle.raw_vector_data.index(v)
            v["rerank_score"] = score_map.get(idx, v.get("score", 0.0))

    # ------------------------------------------------------------------
    # Missing evidence detection
    # ------------------------------------------------------------------

    def _detect_missing_evidence(
        self, bundle: EvidenceBundle, plan: RetrievalPlan
    ) -> list[MissingEvidence]:
        """Detect expected but missing evidence types."""
        missing: list[MissingEvidence] = []

        # Check if we got graph data when graph traversal was requested
        if RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies:
            if not bundle.raw_graph_data:
                missing.append(MissingEvidence(
                    evidence_type="graph_traversal",
                    description="No graph traversal results returned",
                    suggested_action="Check graph connectivity or expand search scope",
                    priority="high",
                ))

        # Check if we got vector results when vector search was requested
        if RetrievalStrategy.VECTOR_SEARCH in plan.strategies:
            vector_results = [
                v for v in bundle.raw_vector_data
                if v.get("metadata", {}).get("type") != "knowledge_card"
            ]
            if not vector_results:
                missing.append(MissingEvidence(
                    evidence_type="vector_search",
                    description="No vector search results returned",
                    suggested_action="Check embedding generation or expand query terms",
                    priority="high",
                ))

        # Check if entity resolution failed when entities were expected
        if plan.target_entities and not bundle.resolved_entities:
            missing.append(MissingEvidence(
                evidence_type="entity_resolution",
                description=f"Failed to resolve {len(plan.target_entities)} entity mentions",
                suggested_action="Check entity names or provide alternative identifiers",
                priority="high",
            ))

        # Check if compliance docs are missing for compliance intent
        if plan.intent == QueryIntent.COMPLIANCE:
            has_compliance = any(
                v.get("metadata", {}).get("type") == "compliance"
                for v in bundle.raw_vector_data
            )
            if not has_compliance:
                missing.append(MissingEvidence(
                    evidence_type="compliance_document",
                    description="No compliance-specific evidence found",
                    suggested_action="Check compliance document index or expand date range",
                    priority="medium",
                ))

        # Check if RCA-specific evidence is missing
        if plan.intent == QueryIntent.RCA:
            has_incident = any(
                "incident" in v.get("content", "").lower() or "failure" in v.get("content", "").lower()
                for v in bundle.raw_vector_data
            )
            if not has_incident:
                missing.append(MissingEvidence(
                    evidence_type="incident_history",
                    description="No incident or failure history found",
                    suggested_action="Check incident database or expand time range",
                    priority="medium",
                ))

        return missing

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _summarise_filters(plan: RetrievalPlan) -> dict[str, Any]:
        filters: dict[str, Any] = {}
        if plan.site_id:
            filters["site_id"] = plan.site_id
        if plan.organisation_id:
            filters["org_id"] = plan.organisation_id
        if plan.date_from:
            filters["date_from"] = plan.date_from
        if plan.date_to:
            filters["date_to"] = plan.date_to
        if not plan.latest_version_only:
            filters["include_historical_versions"] = True
        if plan.document_ids:
            filters["document_count"] = len(plan.document_ids)
        if plan.graph_types:
            filters["graph_types"] = [gt.value for gt in plan.graph_types]
        if plan.decomposition_enabled:
            filters["decomposition_enabled"] = True
        if plan.sub_queries:
            filters["sub_query_count"] = len(plan.sub_queries)
        return filters
