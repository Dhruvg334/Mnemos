import asyncio
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.graph.neo4j_client import Neo4jGraphClient
from mnemos.agentic.retrieval.identity_resolver import AssetIdentityResolver
from mnemos.agentic.retrieval.lexical import LexicalRetriever
from mnemos.agentic.retrieval.reranker import CrossEncoderReranker
from mnemos.agentic.retrieval.structured import StructuredRetriever
from mnemos.agentic.retrieval.vector import VectorRetriever
from mnemos.agentic.schemas.base import (
    Contradiction,
    EvidenceBundle,
    QueryIntent,
    ResolvedEntity,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("retrieval_engine")


class HybridRetrievalEngine:
    """
    Optimized retrieval engine for industrial intelligence.
    Orchestrates multiple search modalities in parallel, including Expert Memory.
    """

    def __init__(
        self,
        db: AsyncSession,
        graph_client: Neo4jGraphClient,
        reranker: CrossEncoderReranker | None = None,
    ):
        self.db = db
        self.graph_client = graph_client
        self.identity_resolver = AssetIdentityResolver(db)
        self.structured_retriever = StructuredRetriever(db)
        self.lexical_retriever = LexicalRetriever(db)
        self.vector_retriever = VectorRetriever(db)
        self.reranker = reranker or CrossEncoderReranker()

    async def execute_plan(
        self, query_id: str, query_text: str, plan: RetrievalPlan, context: dict[str, Any]
    ) -> EvidenceBundle:
        """
        Executes a dynamic retrieval plan with maximum parallelism.
        """
        site_id = context.get("site_id")

        # 1. Resolve Identities (Sequential requirement for downstream graph/sql)
        unique_resolved = await self._resolve_identities(plan, site_id)

        bundle = EvidenceBundle(
            query_id=query_id,
            intent=plan.intent,
            resolved_entities=unique_resolved,
            metadata={
                "site_id": site_id,
                "org_id": context.get("org_id"),
                "plan_reasoning": plan.reasoning,
            },
        )

        # 2. Parallel Strategy Execution
        tasks = []
        for strategy in plan.strategies:
            if strategy == RetrievalStrategy.GRAPH_TRAVERSAL:
                tasks.append(self._execute_graph_traversal(bundle))
            elif strategy == RetrievalStrategy.VECTOR_SEARCH:
                tasks.append(self._execute_vector_search(bundle, query_text, site_id))
            elif strategy == RetrievalStrategy.LEXICAL_SEARCH:
                tasks.append(self._execute_lexical_search(bundle, query_text, site_id))
            elif strategy == RetrievalStrategy.SQL_QUERY:
                tasks.append(self._execute_structured_queries(bundle, site_id))

        if tasks:
            await asyncio.gather(*tasks)

        # 3. Post-Retrieval Verification
        bundle.contradictions = await self._detect_contradictions(bundle)

        logger.info(f"Retrieval complete for {query_id}. Gathered {len(bundle.raw_vector_data)} candidates.")
        return bundle

    async def _resolve_identities(self, plan: RetrievalPlan, site_id: str | None) -> list[ResolvedEntity]:
        resolved_entities = []
        for entity_mention in plan.target_entities:
            if entity_mention.startswith("ast_"):
                specs = await self.structured_retriever.get_asset_specs(entity_mention)
                if specs:
                    resolved_entities.append(ResolvedEntity(
                        original_text=specs.get("asset_tag", ""),
                        entity_id=entity_mention,
                        entity_type="ASSET",
                        confidence=1.0,
                        canonical_name=specs.get("name", ""),
                        metadata=specs
                    ))
            else:
                resolved = await self.identity_resolver.resolve(entity_mention, site_id)
                resolved_entities.extend(resolved)

        seen_ids = set()
        unique = []
        for e in resolved_entities:
            if e.entity_id not in seen_ids:
                unique.append(e)
                seen_ids.add(e.entity_id)
        return unique

    async def _execute_graph_traversal(self, bundle: EvidenceBundle):
        for entity in bundle.resolved_entities:
            try:
                graph_data = await self.graph_client.get_asset_context(entity.entity_id, depth=2)
                bundle.raw_graph_data[entity.entity_id] = {
                    "nodes": [n.model_dump() for n in graph_data.nodes],
                    "relationships": [r.model_dump() for r in graph_data.relationships],
                }
                if bundle.intent == QueryIntent.RCA:
                    failures = await self.graph_client.find_related_failures(entity.entity_id)
                    bundle.raw_graph_data[entity.entity_id]["related_failures"] = [f.model_dump() for f in failures]
            except Exception as e:
                logger.error(f"Graph error for {entity.entity_id}: {e}")

    async def _execute_vector_search(self, bundle: EvidenceBundle, query: str, site_id: str | None):
        try:
            embedding = await self.vector_retriever.get_embeddings(query)
            
            filters = {}
            if site_id:
                filters["site_id"] = site_id
            if bundle.context.get("tenant_id"):
                filters["tenant_id"] = bundle.context.get("tenant_id")
            if bundle.resolved_entities:
                # We can filter by the most confident asset if one exists
                # Or pass multiple if supported. Let's just pass the top entity
                filters["asset_id"] = bundle.resolved_entities[0].entity_id
                
            results = await self.vector_retriever.search(embedding, top_k=10, filters=filters)
            for res in results:
                bundle.raw_vector_data.append(res.model_dump())
        except Exception as e:
            logger.error(f"Vector search failed: {e}")

    async def _execute_lexical_search(self, bundle: EvidenceBundle, query: str, site_id: str | None):
        results = await self.lexical_retriever.search(query, site_id=site_id)
        for res in results:
            bundle.raw_vector_data.append({
                "content": res["text"],
                "metadata": {**res["metadata"], "evidence_region_id": res["id"]},
                "score": 1.0
            })

    async def _execute_structured_queries(self, bundle: EvidenceBundle, site_id: str | None):
        for entity in bundle.resolved_entities:
            # Parallelize History and Expert Memory (Knowledge Cards)
            history_task = self.structured_retriever.get_maintenance_history(entity.entity_id)
            cards_task = self.structured_retriever.get_knowledge_cards(entity.entity_id)

            history, cards = await asyncio.gather(history_task, cards_task)

            bundle.metadata[f"history_{entity.entity_id}"] = history
            bundle.metadata[f"expert_memory_{entity.entity_id}"] = cards

            # Add Knowledge Cards to candidates for reranking if they have enough text
            for card in cards:
                bundle.raw_vector_data.append({
                    "content": f"EXPERT MEMORY: {card['title']}\n{card['content']}",
                    "metadata": {"type": "knowledge_card", "id": card["card_id"], "version": card["version"]},
                    "score": 0.9 # High initial relevance for expert knowledge
                })

    async def _detect_contradictions(self, bundle: EvidenceBundle) -> list[Contradiction]:
        return []
