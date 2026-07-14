import re
from typing import TypeVar

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.deps import get_graph_client, get_llm_service, get_prompt_manager
from mnemos.agentic.retrieval.engine import HybridRetrievalEngine
from mnemos.agentic.retrieval.graph_rag import GraphRAGLayer
from mnemos.agentic.retrieval.identity_resolver import AssetIdentityResolver
from mnemos.agentic.schemas.base import (
    AgentResponse,
    QueryIntent,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.schemas.specialized import (
    AssetPassport,
    FinalReport,
    RCACaseReport,
)
from mnemos.agentic.schemas.state import AgentState
from mnemos.agentic.utils.guardrails import GuardrailViolation, MnemosGuardrails
from mnemos.agentic.utils.logging import StructuredLogger

logger = StructuredLogger("nodes")
T = TypeVar("T", bound=BaseModel)

class BaseNode:
    """
    Optimized base node with structured logging and safety guardrails.
    """
    def __init__(self, db: AsyncSession):
        self.db = db
        self.prompt_manager = get_prompt_manager()
        self.llm = get_llm_service()
        self.guardrails = MnemosGuardrails()

    async def __call__(self, state: AgentState) -> AgentState:
        node_name = self.__class__.__name__
        logger.info(f"Node Start: {node_name}")
        try:
            if node_name == "QueryRouterNode":
                self.guardrails.detect_injection(state["query"])

            updated_state = await self.execute(state)
            updated_state["steps_completed"].append(node_name)
            return updated_state
        except GuardrailViolation as e:
            logger.warning(f"Guardrail violation in {node_name}: {str(e)}")
            state["errors"].append(f"SAFETY_VIOLATION: {str(e)}")
            return state
        except Exception as e:
            logger.error(f"Execution failed in {node_name}: {str(e)}", exc_info=True)
            state["errors"].append(f"INTERNAL_ERROR: {node_name}: {str(e)}")
            return state

    async def execute(self, state: AgentState) -> AgentState:
        raise NotImplementedError

class QueryRouterNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        query = state["query"].lower()
        intent = QueryIntent.GENERAL
        if any(w in query for w in ["rca", "root cause", "failure", "incident"]):
            intent = QueryIntent.RCA
        elif any(w in query for w in ["compliance", "regulation", "audit", "standard"]):
            intent = QueryIntent.COMPLIANCE
        elif any(w in query for w in ["asset", "tag", "specs", "drawing"]):
            intent = QueryIntent.ASSET_INFO
        elif any(w in query for w in ["lesson", "recurrence", "learned"]):
            intent = QueryIntent.LESSONS_LEARNED

        state["intent"] = intent
        return state

class EntityResolverNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        resolver = AssetIdentityResolver(self.db)
        tag_pattern = r'\b[0-9]{0,3}[A-Z]{1,3}-[0-9]{1,4}[A-Z]?\b'
        mentions = re.findall(tag_pattern, state["query"].upper())

        resolved = []
        for mention in set(mentions):
            results = await resolver.resolve(mention, state["context"].get("site_id"))
            resolved.extend(results)

        state["resolved_entities"] = resolved
        return state

class RetrievalPlannerNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        intent = state["intent"]
        strategies = [RetrievalStrategy.VECTOR_SEARCH, RetrievalStrategy.LEXICAL_SEARCH]

        if intent in [QueryIntent.ASSET_INFO, QueryIntent.RCA, QueryIntent.LESSONS_LEARNED]:
            strategies.extend([RetrievalStrategy.GRAPH_TRAVERSAL, RetrievalStrategy.SQL_QUERY])

        if intent == QueryIntent.COMPLIANCE:
            strategies.extend([RetrievalStrategy.METADATA_FILTER, RetrievalStrategy.SQL_QUERY])

        state["retrieval_plan"] = RetrievalPlan(
            intent=intent,
            strategies=list(set(strategies)),
            target_entities=[e.entity_id for e in state["resolved_entities"]],
            reasoning=f"Optimized strategy for {intent}"
        )
        return state

class EvidenceRetrievalNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        graph_client = await get_graph_client()
        engine = HybridRetrievalEngine(self.db, graph_client)

        bundle = await engine.execute_plan(
            state["context"].get("query_id"),
            state["query"],
            state["retrieval_plan"],
            state["context"]
        )
        state["evidence_bundle"] = bundle
        return state

class EvidenceVerificationNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        graph_client = await get_graph_client()
        rag_layer = GraphRAGLayer(self.db, graph_client)

        verified_evidence = await rag_layer.process_bundle(state["evidence_bundle"], state["query"])
        state["evidence_bundle"].verified_evidence = verified_evidence

        # Enforce security boundaries
        self.guardrails.check_permissions(state["context"], verified_evidence)
        return state

class AssetAgentNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        evidence = state["evidence_bundle"].verified_evidence
        if not evidence:
            return state

        prompt = self.prompt_manager.get_prompt("asset_intelligence", query=state["query"], evidence=evidence)
        passport = await self.llm.call_structured(prompt, AssetPassport)
        state["context"]["asset_passport"] = passport.model_dump()
        return state

class RCAAgentNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        evidence = state["evidence_bundle"].verified_evidence
        if not evidence:
            return state

        prompt = self.prompt_manager.get_prompt("rca_analysis", query=state["query"], evidence=evidence)
        report = await self.llm.call_structured(prompt, RCACaseReport)

        # Safety check: Verify claims in RCA against evidence
        self.guardrails.verify_grounding(report.hypotheses)

        state["context"]["rca_report"] = report.model_dump()
        state["claims"].extend(report.hypotheses)
        return state

class ResponseComposerNode(BaseNode):
    async def execute(self, state: AgentState) -> AgentState:
        bundle = state["evidence_bundle"]
        ctx = state["context"]

        # Aggregate Graph Paths
        graph_paths = []
        if bundle.raw_graph_data:
            for _, data in bundle.raw_graph_data.items():
                for rel in data.get("relationships", []):
                    graph_paths.append([rel["source_id"], rel["type"], rel["target_id"]])

        # Synthesize final report sections
        prompt = self.prompt_manager.get_prompt(
            "report_composer",
            query=state["query"],
            intent=state["intent"],
            asset_intelligence=ctx.get("asset_passport"),
            rca_analysis=ctx.get("rca_report"),
            compliance_package=ctx.get("compliance_package"),
            lessons_learned=ctx.get("lessons_learned")
        )

        final_report = await self.llm.call_structured(prompt, FinalReport)

        state["final_response"] = AgentResponse(
            answer=final_report.summary,
            confidence_score=0.95,
            claims=final_report.grounded_claims,
            missing_evidence=final_report.missing_evidence or [],
            contradictions=final_report.contradictions or [],
            recommended_actions=final_report.recommended_actions or [],
            graph_paths=graph_paths,
            metadata={"trace_id": ctx.get("trace_id")}
        )
        return state
