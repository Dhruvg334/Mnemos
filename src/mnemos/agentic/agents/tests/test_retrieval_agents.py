"""Architecture-level tests for the retrieval intelligence agents.

Tests verify:
- Agent instantiation and registration metadata
- State mutation (each agent produces expected state keys)
- The as_function() adapter works with the runtime workflow
- Dependency ordering is declared correctly
- Error handling (missing state, guardrail violations, LLM failures)
- All agents follow the CollaborativeAgent protocol
- Planner LLM-driven + fallback logic
- RetrievalReflection sufficiency assessment
- Full pipeline integration
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from mnemos.agentic.agents.interfaces import CollaborativeAgent
from mnemos.agentic.agents.retrieval import (
    EvidenceRetrievalAgent,
    EvidenceVerificationAgent,
    QueryRouterAgent,
    RetrievalPlannerAgent,
    RetrievalReflectionAgent,
)
from mnemos.agentic.agents.retrieval._base import _BaseRetrievalAgent
from mnemos.agentic.agents.retrieval.planner import PlannerLLMOutput
from mnemos.agentic.agents.retrieval.query_router import QueryClassification
from mnemos.agentic.runtime.types import (
    AgentRegistration,
    AgentRole,
)
from mnemos.agentic.schemas.base import (
    EvidenceBundle,
    EvidenceSource,
    ProvenanceChain,
    QueryIntent,
    RetrievalPlan,
    RetrievalStrategy,
)
from mnemos.agentic.schemas.state import AgentState

# ======================================================================
# Fixtures
# ======================================================================


@pytest.fixture
def mock_db() -> MagicMock:
    db = MagicMock(spec=AsyncSession)
    db.get = AsyncMock()
    db.execute = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    return db


def _initial_state(query: str = "What is the pressure limit for P-101?") -> AgentState:
    return {
        "query": query,
        "context": {
            "query_id": "qry_test_001",
            "site_id": "site_alpha",
            "org_id": "org_mnemos",
            "user_id": "usr_001",
        },
        "intent": None,
        "resolved_entities": [],
        "retrieval_plan": None,
        "evidence_bundle": None,
        "messages": [],
        "claims": [],
        "final_response": None,
        "steps_completed": [],
        "errors": [],
    }


def _make_verified_source(
    text: str = "Pressure limit is 40 bar",
    confidence: float = 0.9,
    relevance: float = 0.95,
) -> EvidenceSource:
    return EvidenceSource(
        text_excerpt=text,
        provenance=ProvenanceChain(
            evidence_region_id="evr_1",
            document_id="doc_1",
            document_version=1,
            sha256="abc",
            source_filename="manual.pdf",
            storage_key="s3://key",
        ),
        relevance_score=relevance,
        confidence_score=confidence,
    )


# ======================================================================
# Protocol conformance
# ======================================================================


class TestProtocolConformance:
    ALL_AGENTS = [
        QueryRouterAgent,
        RetrievalPlannerAgent,
        EvidenceRetrievalAgent,
        EvidenceVerificationAgent,
        RetrievalReflectionAgent,
    ]

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_is_collaborative_agent(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        assert isinstance(agent, CollaborativeAgent)
        assert isinstance(agent, _BaseRetrievalAgent)

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_has_registration(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        reg = agent.to_registration()
        assert isinstance(reg, AgentRegistration)
        assert reg.name
        assert reg.role in [r.value for r in AgentRole]
        assert isinstance(reg.capabilities, list)

    @pytest.mark.parametrize("cls", ALL_AGENTS)
    def test_has_name_and_role(self, cls: type, mock_db: MagicMock) -> None:
        agent = cls(mock_db)
        assert isinstance(agent.name, str) and len(agent.name) > 0
        assert isinstance(agent.role, AgentRole)


# ======================================================================
# QueryRouterAgent
# ======================================================================


class TestQueryRouterAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = QueryRouterAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "query_router"
        assert reg.role == AgentRole.RETRIEVAL
        assert reg.capabilities[0].name == "query_classification"

    def test_no_dependencies(self, mock_db: MagicMock) -> None:
        assert QueryRouterAgent(mock_db).required_dependencies == []

    @pytest.mark.asyncio
    async def test_classifies_intent(self, mock_db: MagicMock) -> None:
        agent = QueryRouterAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(
            return_value=QueryClassification(
                intent=QueryIntent.ASSET_INFO,
                entities=["P-101"],
                confidence=0.92,
            )
        )

        result = await agent.run(_initial_state())
        assert result["context"]["intent"] == QueryIntent.ASSET_INFO
        assert result["context"]["extracted_entities"] == ["P-101"]
        assert "query_router" in result["steps_completed"]

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_db: MagicMock) -> None:
        agent = QueryRouterAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(side_effect=RuntimeError("timeout"))
        result = await agent.run(_initial_state())
        assert len(result["errors"]) == 1
        assert "query_router" in result["errors"][0]


# ======================================================================
# RetrievalPlannerAgent
# ======================================================================


class TestRetrievalPlannerAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = RetrievalPlannerAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "retrieval_planner"
        assert reg.role == AgentRole.RETRIEVAL
        assert reg.capabilities[0].name == "retrieval_planning"

    def test_depends_on_query_router(self, mock_db: MagicMock) -> None:
        assert "query_router" in RetrievalPlannerAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_llm_plan_used_when_available(self, mock_db: MagicMock) -> None:
        agent = RetrievalPlannerAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(
            return_value=PlannerLLMOutput(
                strategies=[
                    RetrievalStrategy.GRAPH_TRAVERSAL,
                    RetrievalStrategy.VECTOR_SEARCH,
                ],
                asset_ids=["ast_001"],
                date_from="2024-01-01",
                latest_version_only=False,
                top_k_per_strategy=8,
                min_relevance_score=0.5,
                min_evidence_count=4,
                min_average_confidence=0.7,
                reasoning="RCA query needs historical graph traversal",
            )
        )

        state = _initial_state()
        state["context"]["intent"] = QueryIntent.RCA

        result = await agent.run(state)
        plan: RetrievalPlan = result["context"]["retrieval_plan"]

        assert plan.intent == QueryIntent.RCA
        assert RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies
        assert RetrievalStrategy.VECTOR_SEARCH in plan.strategies
        assert plan.asset_ids == ["ast_001"]
        assert plan.date_from == "2024-01-01"
        assert plan.latest_version_only is False
        assert plan.top_k_per_strategy == 8
        assert plan.min_relevance_score == 0.5
        assert plan.min_evidence_count == 4
        assert plan.min_average_confidence == 0.7

    @pytest.mark.asyncio
    async def test_fallback_to_defaults_on_llm_failure(self, mock_db: MagicMock) -> None:
        agent = RetrievalPlannerAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(side_effect=RuntimeError("LLM down"))

        state = _initial_state()
        state["context"]["intent"] = QueryIntent.ASSET_INFO

        result = await agent.run(state)
        plan: RetrievalPlan = result["context"]["retrieval_plan"]

        assert plan.intent == QueryIntent.ASSET_INFO
        assert RetrievalStrategy.METADATA_FILTER in plan.strategies
        assert RetrievalStrategy.GRAPH_TRAVERSAL in plan.strategies
        assert "asset_info" in plan.reasoning

    @pytest.mark.asyncio
    async def test_defaults_to_general_for_unknown_intent(self, mock_db: MagicMock) -> None:
        agent = RetrievalPlannerAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(side_effect=RuntimeError("fail"))

        state = _initial_state()
        state["context"]["intent"] = "unknown_intent"

        result = await agent.run(state)
        plan: RetrievalPlan = result["context"]["retrieval_plan"]
        assert plan.intent == QueryIntent.GENERAL

    @pytest.mark.asyncio
    async def test_populates_asset_ids_from_resolved_entities(self, mock_db: MagicMock) -> None:
        agent = RetrievalPlannerAgent(mock_db)
        agent.llm = MagicMock()
        agent.llm.call_structured = AsyncMock(side_effect=RuntimeError("fail"))

        state = _initial_state()
        state["context"]["intent"] = QueryIntent.ASSET_INFO
        state["context"]["resolved_entities"] = [
            {"entity_id": "ast_001", "canonical_name": "Pump"},
        ]

        result = await agent.run(state)
        plan: RetrievalPlan = result["context"]["retrieval_plan"]
        assert "ast_001" in plan.asset_ids


# ======================================================================
# EvidenceRetrievalAgent
# ======================================================================


class TestEvidenceRetrievalAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = EvidenceRetrievalAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "evidence_retrieval"
        assert reg.role == AgentRole.RETRIEVAL
        assert reg.capabilities[0].name == "evidence_gathering"

    def test_depends_on_retrieval_planner(self, mock_db: MagicMock) -> None:
        assert "retrieval_planner" in EvidenceRetrievalAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_executes_plan(self, mock_db: MagicMock) -> None:
        agent = EvidenceRetrievalAgent(mock_db)

        plan = RetrievalPlan(
            intent=QueryIntent.ASSET_INFO,
            strategies=[RetrievalStrategy.VECTOR_SEARCH],
            target_entities=[],
            reasoning="test",
        )
        bundle = EvidenceBundle(
            query_id="qry_test_001",
            intent=QueryIntent.ASSET_INFO,
            raw_vector_data=[{"content": "Pressure limit 40 bar", "metadata": {}, "score": 0.9}],
            raw_graph_data={},
            resolved_entities=[],
        )

        mock_engine = MagicMock()
        mock_engine.execute_plan = AsyncMock(return_value=bundle)

        state = _initial_state()
        state["context"]["retrieval_plan"] = plan

        with patch(
            "mnemos.agentic.agents.retrieval.evidence_retrieval.HybridRetrievalEngine",
            return_value=mock_engine,
        ):
            with patch(
                "mnemos.agentic.agents.retrieval.evidence_retrieval.get_graph_client",
                new_callable=AsyncMock,
            ):
                result = await agent.run(state)

        assert isinstance(result["context"]["evidence_bundle"], EvidenceBundle)
        assert len(result["evidence"]) == 1
        assert result["evidence"][0]["source"] == "vector"

    @pytest.mark.asyncio
    async def test_skips_without_plan(self, mock_db: MagicMock) -> None:
        result = await EvidenceRetrievalAgent(mock_db).run(_initial_state())
        assert "evidence_bundle" not in result.get("context", {})


# ======================================================================
# EvidenceVerificationAgent
# ======================================================================


class TestEvidenceVerificationAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = EvidenceVerificationAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "evidence_verification"
        assert reg.role == AgentRole.VERIFICATION

    def test_depends_on_evidence_retrieval(self, mock_db: MagicMock) -> None:
        assert "evidence_retrieval" in EvidenceVerificationAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_verifies_evidence(self, mock_db: MagicMock) -> None:
        agent = EvidenceVerificationAgent(mock_db)

        bundle = EvidenceBundle(
            query_id="qry_test_001",
            intent=QueryIntent.ASSET_INFO,
            raw_vector_data=[{"content": "test", "metadata": {}, "score": 0.8}],
            raw_graph_data={},
        )
        mock_rag = MagicMock()
        mock_rag.process_bundle = AsyncMock(return_value=[_make_verified_source()])

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle

        with patch(
            "mnemos.agentic.agents.retrieval.evidence_verification.GraphRAGLayer",
            return_value=mock_rag,
        ):
            with patch(
                "mnemos.agentic.agents.retrieval.evidence_verification.get_graph_client",
                new_callable=AsyncMock,
            ):
                result = await agent.run(state)

        assert len(result["context"]["evidence_bundle"].verified_evidence) == 1
        verified_items = [e for e in result["evidence"] if e["source"] == "verified"]
        assert len(verified_items) == 1

    @pytest.mark.asyncio
    async def test_error_handling(self, mock_db: MagicMock) -> None:
        agent = EvidenceVerificationAgent(mock_db)
        bundle = EvidenceBundle(query_id="q1", intent=QueryIntent.GENERAL)
        mock_rag = MagicMock()
        mock_rag.process_bundle = AsyncMock(side_effect=RuntimeError("Graph fail"))

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle

        with patch(
            "mnemos.agentic.agents.retrieval.evidence_verification.GraphRAGLayer",
            return_value=mock_rag,
        ):
            with patch(
                "mnemos.agentic.agents.retrieval.evidence_verification.get_graph_client",
                new_callable=AsyncMock,
            ):
                result = await agent.run(state)

        assert len(result["errors"]) == 1
        assert "evidence_verification" in result["errors"][0]


# ======================================================================
# RetrievalReflectionAgent
# ======================================================================


class TestRetrievalReflectionAgent:
    def test_registration_metadata(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)
        reg = agent.to_registration()
        assert reg.name == "retrieval_reflection"
        assert reg.role == AgentRole.VERIFICATION
        assert reg.capabilities[0].name == "retrieval_reflection"

    def test_depends_on_evidence_verification(self, mock_db: MagicMock) -> None:
        assert "evidence_verification" in RetrievalReflectionAgent(mock_db).required_dependencies

    @pytest.mark.asyncio
    async def test_sufficient_evidence(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)

        plan = RetrievalPlan(
            intent=QueryIntent.ASSET_INFO,
            strategies=[RetrievalStrategy.VECTOR_SEARCH],
            reasoning="test",
            min_evidence_count=2,
            min_average_confidence=0.6,
        )
        bundle = EvidenceBundle(
            query_id="q1",
            intent=QueryIntent.ASSET_INFO,
            verified_evidence=[
                _make_verified_source(confidence=0.9, relevance=0.95),
                _make_verified_source(text="Max temp 200C", confidence=0.85, relevance=0.8),
                _make_verified_source(
                    text="Last inspected 2024-01", confidence=0.8, relevance=0.75
                ),
            ],
            raw_vector_data=[{"content": "a"}, {"content": "b"}],
            raw_graph_data={"ast_001": {"nodes": [], "relationships": []}},
            resolved_entities=[],
        )

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle
        state["context"]["retrieval_plan"] = plan

        result = await agent.run(state)

        assert result["context"]["retrieval_sufficient"] is True
        assert result["context"]["retrieval_gaps"] == []
        assessment = result["context"]["retrieval_assessment"]
        assert assessment["verified_count"] == 3
        assert assessment["sufficient"] is True

    @pytest.mark.asyncio
    async def test_insufficient_evidence_triggers_replan(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)

        plan = RetrievalPlan(
            intent=QueryIntent.RCA,
            strategies=[RetrievalStrategy.VECTOR_SEARCH, RetrievalStrategy.GRAPH_TRAVERSAL],
            reasoning="test",
            min_evidence_count=5,
            min_average_confidence=0.7,
        )
        bundle = EvidenceBundle(
            query_id="q1",
            intent=QueryIntent.RCA,
            verified_evidence=[
                _make_verified_source(confidence=0.5, relevance=0.4),
            ],
            raw_vector_data=[],
            raw_graph_data={},
            resolved_entities=[],
        )

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle
        state["context"]["retrieval_plan"] = plan

        result = await agent.run(state)

        assert result["context"]["retrieval_sufficient"] is False
        assert len(result["context"]["retrieval_gaps"]) > 0
        # Replan request should be appended
        replan_requests = result.get("replan_requests", [])
        assert len(replan_requests) == 1
        assert "Insufficient" in replan_requests[0].reason

    @pytest.mark.asyncio
    async def test_skips_without_bundle(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)
        state = _initial_state()

        result = await agent.run(state)

        assert result["context"]["retrieval_sufficient"] is False
        assert "No evidence bundle" in result["context"]["retrieval_gaps"][0]

    @pytest.mark.asyncio
    async def test_identifies_entity_resolution_failure(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)

        plan = RetrievalPlan(
            intent=QueryIntent.ASSET_INFO,
            strategies=[RetrievalStrategy.GRAPH_TRAVERSAL],
            target_entities=["P-101"],
            reasoning="test",
            min_evidence_count=3,
            min_average_confidence=0.6,
        )
        bundle = EvidenceBundle(
            query_id="q1",
            intent=QueryIntent.ASSET_INFO,
            verified_evidence=[],
            raw_vector_data=[],
            raw_graph_data={},
            resolved_entities=[],
        )

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle
        state["context"]["retrieval_plan"] = plan

        result = await agent.run(state)

        gaps = result["context"]["retrieval_gaps"]
        assert any("Entity resolution failed" in g for g in gaps)

    @pytest.mark.asyncio
    async def test_identifies_low_source_diversity(self, mock_db: MagicMock) -> None:
        agent = RetrievalReflectionAgent(mock_db)

        plan = RetrievalPlan(
            intent=QueryIntent.ASSET_INFO,
            strategies=[
                RetrievalStrategy.VECTOR_SEARCH,
                RetrievalStrategy.GRAPH_TRAVERSAL,
                RetrievalStrategy.LEXICAL_SEARCH,
            ],
            reasoning="test",
            min_evidence_count=2,
            min_average_confidence=0.5,
        )
        bundle = EvidenceBundle(
            query_id="q1",
            intent=QueryIntent.ASSET_INFO,
            verified_evidence=[
                _make_verified_source(confidence=0.8, relevance=0.8),
                _make_verified_source(confidence=0.7, relevance=0.7),
            ],
            raw_vector_data=[{"content": "a", "metadata": {}}],
            raw_graph_data={},
            resolved_entities=[],
        )

        state = _initial_state()
        state["context"]["evidence_bundle"] = bundle
        state["context"]["retrieval_plan"] = plan

        result = await agent.run(state)

        gaps = result["context"]["retrieval_gaps"]
        assert any("source diversity" in g.lower() for g in gaps)


# ======================================================================
# Pipeline integration
# ======================================================================


class TestPipelineIntegration:
    """Verify the 5 agents can run sequentially as the supervisor dispatches them."""

    @pytest.mark.asyncio
    async def test_full_pipeline_mocked(self, mock_db: MagicMock) -> None:
        # -- 1. QueryRouter --
        router = QueryRouterAgent(mock_db)
        router.llm = MagicMock()
        router.llm.call_structured = AsyncMock(
            return_value=QueryClassification(
                intent=QueryIntent.ASSET_INFO,
                entities=["P-101"],
                confidence=0.92,
            )
        )
        state = await router.run(_initial_state())
        assert state["context"]["intent"] == QueryIntent.ASSET_INFO

        # -- 2. RetrievalPlanner (LLM fallback) --
        planner = RetrievalPlannerAgent(mock_db)
        planner.llm = MagicMock()
        planner.llm.call_structured = AsyncMock(side_effect=RuntimeError("fail"))
        state = await planner.run(state)
        plan = state["context"]["retrieval_plan"]
        assert isinstance(plan, RetrievalPlan)
        assert RetrievalStrategy.METADATA_FILTER in plan.strategies

        # -- 3. EvidenceRetrieval --
        retriever = EvidenceRetrievalAgent(mock_db)
        bundle = EvidenceBundle(
            query_id="qry_test_001",
            intent=QueryIntent.ASSET_INFO,
            raw_vector_data=[
                {"content": "P-101 pressure limit 40 bar", "metadata": {}, "score": 0.95},
            ],
            raw_graph_data={
                "ast_001": {
                    "nodes": [{"id": "n1"}, {"id": "n2"}, {"id": "n3"}],
                    "relationships": [{"type": "HAS_COMPONENT"}],
                }
            },
            resolved_entities=[],
        )
        mock_engine = MagicMock()
        mock_engine.execute_plan = AsyncMock(return_value=bundle)
        with patch(
            "mnemos.agentic.agents.retrieval.evidence_retrieval.HybridRetrievalEngine",
            return_value=mock_engine,
        ):
            with patch(
                "mnemos.agentic.agents.retrieval.evidence_retrieval.get_graph_client",
                new_callable=AsyncMock,
            ):
                state = await retriever.run(state)
        assert state["context"]["evidence_bundle"] is not None

        # -- 4. EvidenceVerification --
        verifier = EvidenceVerificationAgent(mock_db)
        mock_rag = MagicMock()
        mock_rag.process_bundle = AsyncMock(
            return_value=[
                _make_verified_source(),
                _make_verified_source(text="Max operating temp 200C", confidence=0.85),
                _make_verified_source(text="Last inspected Jan 2024", confidence=0.8),
            ]
        )
        with patch(
            "mnemos.agentic.agents.retrieval.evidence_verification.GraphRAGLayer",
            return_value=mock_rag,
        ):
            with patch(
                "mnemos.agentic.agents.retrieval.evidence_verification.get_graph_client",
                new_callable=AsyncMock,
            ):
                state = await verifier.run(state)
        assert len(state["context"]["evidence_bundle"].verified_evidence) == 3

        # -- 5. RetrievalReflection --
        reflection = RetrievalReflectionAgent(mock_db)
        state = await reflection.run(state)
        assert state["context"]["retrieval_sufficient"] is True
        assert "retrieval_reflection" in state["steps_completed"]

    @pytest.mark.asyncio
    async def test_dependency_chain_declared(self, mock_db: MagicMock) -> None:
        router = QueryRouterAgent(mock_db)
        planner = RetrievalPlannerAgent(mock_db)
        retriever = EvidenceRetrievalAgent(mock_db)
        verifier = EvidenceVerificationAgent(mock_db)
        reflection = RetrievalReflectionAgent(mock_db)

        assert router.required_dependencies == []
        assert planner.required_dependencies == ["query_router"]
        assert retriever.required_dependencies == ["retrieval_planner"]
        assert verifier.required_dependencies == ["evidence_retrieval"]
        assert reflection.required_dependencies == ["evidence_verification"]


# ======================================================================
# RetrievalPlan schema
# ======================================================================


class TestRetrievalPlanSchema:
    def test_new_filter_fields(self) -> None:
        plan = RetrievalPlan(
            intent=QueryIntent.RCA,
            strategies=[RetrievalStrategy.GRAPH_TRAVERSAL],
            reasoning="test",
            asset_ids=["ast_001"],
            document_ids=["doc_001"],
            date_from="2024-01-01",
            date_to="2024-12-31",
            latest_version_only=False,
            document_versions=[1, 2],
            site_id="site_alpha",
            organisation_id="org_mnemos",
            top_k_per_strategy=8,
            min_relevance_score=0.5,
            enable_reranking=True,
            min_evidence_count=5,
            min_average_confidence=0.7,
        )

        assert plan.asset_ids == ["ast_001"]
        assert plan.document_ids == ["doc_001"]
        assert plan.date_from == "2024-01-01"
        assert plan.date_to == "2024-12-31"
        assert plan.latest_version_only is False
        assert plan.document_versions == [1, 2]
        assert plan.site_id == "site_alpha"
        assert plan.organisation_id == "org_mnemos"
        assert plan.top_k_per_strategy == 8
        assert plan.min_relevance_score == 0.5
        assert plan.enable_reranking is True
        assert plan.min_evidence_count == 5
        assert plan.min_average_confidence == 0.7

    def test_defaults(self) -> None:
        plan = RetrievalPlan(
            intent=QueryIntent.GENERAL,
            strategies=[],
            reasoning="test",
        )
        assert plan.asset_ids == []
        assert plan.document_ids == []
        assert plan.date_from is None
        assert plan.date_to is None
        assert plan.latest_version_only is True
        assert plan.document_versions is None
        assert plan.top_k_per_strategy == 10
        assert plan.min_relevance_score == 0.4
        assert plan.enable_reranking is True
        assert plan.min_evidence_count == 3
        assert plan.min_average_confidence == 0.6
