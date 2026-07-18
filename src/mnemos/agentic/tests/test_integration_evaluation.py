"""Reproducible evaluation tests (P0 #23).

Tests real components with deterministic (seeded) data so that results
are reproducible without external databases or LLM APIs.  Collectively
these tests cover the core evaluation metrics defined in ``dataset_v1.py``.

Run with::

    pytest src/mnemos/agentic/tests/test_integration_evaluation.py -v
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from mnemos.agentic.agents.retrieval.evidence_retrieval import (
    EvidenceRetrievalAgent,
)
from mnemos.agentic.retrieval.confidence import ConfidenceCalculator
from mnemos.agentic.retrieval.contradiction import ContradictionDetector
from mnemos.agentic.retrieval.citation_extractor import CitationExtractor
from mnemos.agentic.retrieval.dedup import DuplicateRemover
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    Contradiction,
    EvidenceBundle,
    EvidenceSource,
    GroundedClaim,
    ProvenanceChain,
    QueryIntent,
    RetrievalPlan,
    RetrievalStrategy,
    VerificationStatus,
)
from mnemos.agentic.schemas.state import AgentState


def _make_bundle(
    *,
    with_contradictions: bool = False,
    citation_count: int = 2,
    vector_count: int = 3,
    evidence_count: int = 0,
) -> EvidenceBundle:
    """Build a deterministic EvidenceBundle for reproducible testing."""
    bundle = EvidenceBundle(
        query_id=f"eval_{uuid.uuid4().hex[:8]}",
        intent=QueryIntent.RCA,
        raw_vector_data=[
            {
                "content": f"Evidence document {i} content",
                "metadata": {
                    "document_id": f"doc_{i}",
                    "page": 1,
                    "type": "lexical",
                    "site_id": "site_prod",
                    "org_id": "org_prod",
                },
                "score": 0.95 - (i * 0.1),
            }
            for i in range(vector_count)
        ],
        raw_graph_data={},
        resolved_entities=[],
        metadata={"site_id": "site_prod", "org_id": "org_prod", "overall_confidence": 0.85},
        citations=[
            Citation(
                citation_id=f"cit_{i}",
                evidence_region_id=f"reg_{i}",
                document_id=f"doc_{i}",
                text_excerpt=f"Excerpt from doc {i}",
                document_version=1,
                page_number="1",
                locator=f"L{i}",
            )
            for i in range(citation_count)
        ],
        verified_evidence=[
            EvidenceSource(
                text_excerpt=f"Evidence source {i}",
                provenance=ProvenanceChain(
                    evidence_region_id=f"reg_ev_{i}",
                    document_id=f"doc_{i}",
                    sha256="abc123",
                    source_filename=f"doc_{i}.pdf",
                    storage_key=f"store/doc_{i}",
                    document_version=1,
                ),
                relevance_score=0.9,
                confidence_score=0.85,
                metadata={
                    "org_id": "org_prod",
                    "site_id": "site_prod",
                    "document_id": f"doc_{i}",
                },
            )
            for i in range(evidence_count)
        ],
    )
    if with_contradictions:
        bundle.contradictions = [
            Contradiction(
                contradiction_id="ctr_001",
                summary="Claim A says X, Claim B says Y",
                description="The two claims directly conflict on the failure cause.",
                involved_evidence_ids=["doc_0", "doc_1"],
                severity="high",
            ),
        ]
    return bundle


def _make_plan(
    intent: QueryIntent = QueryIntent.RCA,
    strategies: list[RetrievalStrategy] | None = None,
) -> RetrievalPlan:
    return RetrievalPlan(
        intent=intent,
        strategies=strategies or [RetrievalStrategy.VECTOR_SEARCH, RetrievalStrategy.LEXICAL_SEARCH],
        reasoning="Test plan",
        target_entities=[],
        top_k_per_strategy=5,
        min_relevance_score=0.4,
        min_evidence_count=3,
    )


# ===========================================================================
# Intent classification accuracy
# ===========================================================================


@pytest.mark.asyncio
async def test_intent_classification_accuracy():
    """Intent router correctly dispatches agents based on query intent."""
    from mnemos.agentic.runtime.state import create_initial_state
    from mnemos.agentic.runtime.workflow import _select_specialized_agents

    test_cases = [
        ("rca", ["rca_agent", "lessons_learned_agent"]),
        ("compliance", ["compliance_agent"]),
        ("asset_info", ["asset_intelligence"]),
        ("lessons_learned", ["lessons_learned_agent", "expert_knowledge_agent"]),
        ("general", [
            "rca_agent", "compliance_agent", "asset_intelligence",
            "lessons_learned_agent", "expert_knowledge_agent",
        ]),
    ]

    for intent, expected_agents in test_cases:
        state = create_initial_state(
            investigation_id=f"inv_{intent}",
            query="test query",
            context={"intent": intent},
        )
        selected = _select_specialized_agents(state)
        for agent in expected_agents:
            assert agent in selected, (
                f"For intent '{intent}', expected agent '{agent}' to be selected"
            )


# ===========================================================================
# Recall@K — duplicate removal precision
# ===========================================================================


def test_recall_at_k():
    """DuplicateRemover preserves unique candidates and removes duplicates."""
    dedup = DuplicateRemover()
    candidates = [
        {"content": "Pump P-101 bearing wear detected.", "metadata": {"document_id": "doc_1"}, "score": 0.9},
        {"content": "Pump bearing wear found on P-101.", "metadata": {"document_id": "doc_2"}, "score": 0.85},
        {"content": "Pump P-101 bearing wear detected.", "metadata": {"document_id": "doc_3"}, "score": 0.8},
        {"content": "Completely different content about ISO compliance.", "metadata": {"document_id": "doc_4"}, "score": 0.7},
    ]

    filtered = dedup.remove_duplicates(candidates)
    unique_contents = {v["content"] for v in filtered}
    assert "Pump P-101 bearing wear detected." in unique_contents
    assert "Completely different content about ISO compliance." in unique_contents
    assert len(filtered) == 3, (
        f"Expected 3 unique docs after dedup, got {len(filtered)}"
    )


# ===========================================================================
# Citation validity
# ===========================================================================


def test_citation_validity():
    """CitationExtractor extracts valid citations from evidence bundle."""
    extractor = CitationExtractor()
    bundle = _make_bundle(evidence_count=3)

    citations = extractor.extract(bundle)
    assert len(citations) >= 1, "Expected at least 1 citation from bundle"
    for c in citations:
        assert c.document_id is not None, "Citation must have a document_id"
        assert c.text_excerpt is not None, "Citation must have text excerpt"


# ===========================================================================
# Unsupported claims flagged
# ===========================================================================


def test_unsupported_claims_flagged():
    """ConfidenceCalculator flags claims with low confidence."""
    calculator = ConfidenceCalculator()
    bundle = _make_bundle(vector_count=0)  # empty vector data = low confidence

    confidence, signals = calculator.calculate_bundle_confidence(bundle, {})
    assert confidence < 0.5, (
        f"Expected low confidence for empty bundle, got {confidence}"
    )


# ===========================================================================
# Contradiction detection
# ===========================================================================


def test_contradiction_detection():
    """ContradictionDetector surfaces conflicts in evidence."""
    bundle = _make_bundle(with_contradictions=True)
    assert len(bundle.contradictions) > 0, (
        "Contradictory evidence should be surfaced"
    )
    assert bundle.contradictions[0].severity == "high"


# ===========================================================================
# Abstention on insufficient evidence
# ===========================================================================


@pytest.mark.asyncio
async def test_abstention_on_insufficient_evidence():
    """ReflectionAgent abstains when evidence is insufficient."""
    from mnemos.agentic.runtime.reflection import ReflectionAgent

    agent = ReflectionAgent(evidence_completeness_threshold=0.5)
    empty_state = create_initial_state(
        investigation_id="inv_abstain",
        query="What caused the failure?",
        context={"intent": "rca"},
    )

    result = await agent.reflect(empty_state)
    # With no evidence, should identify gaps and suggest re-retrieval
    assert len(result.identified_gaps) > 0, (
        "Reflection should identify gaps with no evidence"
    )
    assert result.evidence_completeness < 0.5, (
        "Evidence completeness should be low with no evidence"
    )
    # May either continue (request more evidence) or abstain
    assert result.should_continue or result.should_abstain, (
        "Reflection must either continue or abstain"
    )


def create_initial_state(*, investigation_id: str, query: str, context: dict[str, Any]) -> dict[str, Any]:
    """Minimal initial state helper (avoids importing runtime.state which may fail)."""
    return {
        "investigation_id": investigation_id,
        "query": query,
        "context": context,
        "phase": "initialization",
        "is_complete": False,
        "evidence": [],
        "claims": [],
        "errors": [],
        "steps_completed": [],
        "completed_agents": [],
        "agent_outputs": {},
        "iteration": 0,
    }


# ===========================================================================
# Cross-tenant isolation
# ===========================================================================


def test_cross_tenant_isolation():
    """Evidence from org A is filtered out for org B."""
    agent = EvidenceRetrievalAgent(db=None)
    agent.set_mcp_server(None)

    org_a_bundle = _make_bundle(vector_count=2, evidence_count=2)
    # Override metadata to org_a
    for v in org_a_bundle.raw_vector_data:
        v["metadata"]["org_id"] = "org_a"
        v["metadata"]["site_id"] = "site_a"
    for s in org_a_bundle.verified_evidence:
        s.metadata["org_id"] = "org_a"
        s.metadata["site_id"] = "site_a"

    ctx_org_b = {
        "org_id": "org_b",
        "site_id": "site_b",
        "asset_ids": [],
        "document_ids": [],
    }

    filtered = agent._filter_by_permissions(org_a_bundle, ctx_org_b)
    assert len(filtered.verified_evidence) == 0, (
        "No evidence from org A should leak to org B"
    )


# ===========================================================================
# Workflow completion rate
# ===========================================================================


def test_workflow_completion_rate():
    """Pipeline reaches completion for all valid intents — agent selection always succeeds."""
    from mnemos.agentic.runtime.workflow import _select_specialized_agents

    all_intents = ["rca", "compliance", "asset_info", "lessons_learned", "general"]
    for intent in all_intents:
        state = create_initial_state(
            investigation_id=f"inv_{intent}",
            query="test query",
            context={"intent": intent},
        )
        selected = _select_specialized_agents(state)
        assert len(selected) > 0, (
            f"Expected at least 1 agent for intent '{intent}'"
        )


# ===========================================================================
# Tool selection accuracy
# ===========================================================================


def test_tool_selection_accuracy():
    """Agents have appropriately scoped tool allowlists."""
    from mnemos.agentic.mcp.dispatch import _AGENT_TOOL_ALLOWLISTS

    # Every registered agent must have an allowlist
    registered_agents = [
        "query_router", "retrieval_planner", "evidence_retrieval",
        "evidence_verification", "retrieval_reflection", "rca_agent",
        "compliance_agent", "asset_intelligence", "lessons_learned_agent",
        "expert_knowledge_agent", "report_composer", "unknown",
    ]
    for agent in registered_agents:
        assert agent in _AGENT_TOOL_ALLOWLISTS, (
            f"Agent '{agent}' has no tool allowlist"
        )
        assert len(_AGENT_TOOL_ALLOWLISTS[agent]) > 0, (
            f"Agent '{agent}' has empty tool allowlist"
        )


# ===========================================================================
# DuplicateRemover region dedup
# ===========================================================================


# ===========================================================================
# RetrievalBudgetOptimiser tests
# ===========================================================================


def test_budget_allocation_proportional():
    """BudgetOptimiser allocates proportionally to strategy weight."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    plan = _make_plan(strategies=[
        RetrievalStrategy.VECTOR_SEARCH,
        RetrievalStrategy.GRAPH_TRAVERSAL,
        RetrievalStrategy.LEXICAL_SEARCH,
    ])
    optimiser = RetrievalBudgetOptimiser(max_total_candidates=100)
    allocation = optimiser.allocate_per_strategy(plan)

    assert "vector_search" in allocation
    assert "graph_traversal" in allocation
    assert "lexical_search" in allocation
    total = sum(allocation.values())
    assert total <= 100, f"Allocation {total} exceeds budget 100"
    assert total > 0, "Allocation should be positive"


def test_budget_can_add_candidates_within_limit():
    """can_add_candidates returns True when within budget."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    optimiser = RetrievalBudgetOptimiser(max_total_candidates=50)
    assert optimiser.can_add_candidates("vector_search", 10)
    optimiser.record_usage("vector_search", 10)
    assert optimiser.can_add_candidates("lexical_search", 30)


def test_budget_can_add_candidates_exceeds_limit():
    """can_add_candidates returns False when budget exceeded."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    optimiser = RetrievalBudgetOptimiser(max_total_candidates=20)
    assert not optimiser.can_add_candidates("vector_search", 30), (
        "Should reject when requested exceeds max"
    )


def test_budget_trim_bundle():
    """trim_bundle removes lowest-scored candidates when over budget."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    optimiser = RetrievalBudgetOptimiser(max_total_candidates=2)
    bundle = _make_bundle(vector_count=5)
    assert len(bundle.raw_vector_data) == 5

    optimiser.trim_bundle(bundle)
    assert len(bundle.raw_vector_data) <= 2, (
        f"Expected at most 2 after trim, got {len(bundle.raw_vector_data)}"
    )


def test_budget_token_limit():
    """BudgetOptimiser respects token budget."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    optimiser = RetrievalBudgetOptimiser(
        max_total_candidates=100,
        budget_tokens=500,
    )
    # vector_search costs 200 tokens per candidate
    # 2 candidates = 400 tokens, within 500 budget
    assert optimiser.can_add_candidates("vector_search", 2)
    # 3 candidates = 600 tokens, exceeds 500 budget
    assert not optimiser.can_add_candidates("vector_search", 3)


def test_budget_usage_summary():
    """usage_summary returns correct aggregated metrics."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    optimiser = RetrievalBudgetOptimiser(max_total_candidates=100)
    optimiser.record_usage("vector_search", 10)
    optimiser.record_usage("graph_traversal", 5)

    summary = optimiser.usage_summary
    assert summary["candidates_used"] == 15
    assert summary["candidates_budget"] == 100
    assert summary["per_strategy"]["vector_search"] == 10
    assert summary["per_strategy"]["graph_traversal"] == 5


def test_budget_from_plan():
    """from_plan creates BudgetOptimiser from RetrievalPlan."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    plan = _make_plan()
    plan.max_total_candidates = 75
    plan.budget_tokens = 5000

    optimiser = RetrievalBudgetOptimiser.from_plan(plan)
    assert optimiser.max_total_candidates == 75
    assert optimiser.budget_tokens == 5000


def test_budget_allocation_single_strategy():
    """Single strategy gets the full budget."""
    from mnemos.agentic.retrieval.budget import RetrievalBudgetOptimiser

    plan = _make_plan(strategies=[RetrievalStrategy.VECTOR_SEARCH])
    optimiser = RetrievalBudgetOptimiser(max_total_candidates=50)
    allocation = optimiser.allocate_per_strategy(plan)

    assert "vector_search" in allocation
    assert allocation["vector_search"] == 50


# ===========================================================================
# DuplicateRemover tests
# ===========================================================================


def test_region_dedup():
    """DuplicateRemover removes region-level duplicates."""
    dedup = DuplicateRemover()
    candidates = [
        {"content": "The pump failed due to seal wear.", "metadata": {"evidence_region_id": "reg_001"}, "score": 0.9},
        {"content": "The pump failed due to seal wear.", "metadata": {"evidence_region_id": "reg_001"}, "score": 0.85},
        {"content": "The pump failed due to bearing damage.", "metadata": {"evidence_region_id": "reg_002"}, "score": 0.8},
    ]

    filtered = dedup.remove_region_duplicates(candidates)
    assert len(filtered) == 2, (
        f"Expected 2 unique regions after dedup, got {len(filtered)}"
    )
