"""Comprehensive tests for ReportComposerAgent and InvestigationPipeline.

Tests the report composition agent (merging, deduplication, confidence
computation, disclaimer generation) and the 11-stage investigation
pipeline structure and backward-compatible workflow factory.

All tests are self-contained: no database, no LLM, no network calls.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from mnemos.agentic.runtime.types import AgentCapability, AgentRole
from mnemos.agentic.schemas.base import (
    ClaimSupportStatus,
    ConfidenceSignal,
    Contradiction,
    EvidenceBundle,
    EvidenceSource,
    GroundedClaim,
    MissingEvidence,
    ProvenanceChain,
    QueryIntent,
    ReasoningDecision,
    ReasoningOutput,
    RecommendedAction,
)
from mnemos.agentic.schemas.specialized import FinalReport

pytestmark = pytest.mark.filterwarnings(
    "ignore:create_investigation_workflow is deprecated:DeprecationWarning"
)

# ======================================================================
# Helpers: realistic mock data builders
# ======================================================================


def _provenance(**overrides: Any) -> ProvenanceChain:
    """Build a minimal but valid ProvenanceChain for testing."""
    defaults: dict[str, Any] = {
        "evidence_region_id": "er_001",
        "document_id": "doc_001",
        "document_version": 1,
        "sha256": "abc123def456",
        "source_filename": "maintenance_report.pdf",
        "storage_key": "s3://bucket/doc_001",
    }
    defaults.update(overrides)
    return ProvenanceChain(**defaults)


def _evidence_source(**overrides: Any) -> EvidenceSource:
    """Build a minimal EvidenceSource for testing."""
    defaults: dict[str, Any] = {
        "text_excerpt": "Pump P-101 failed due to seal degradation.",
        "provenance": _provenance(),
        "relevance_score": 0.9,
        "confidence_score": 0.85,
    }
    defaults.update(overrides)
    return EvidenceSource(**defaults)


def _grounded_claim(
    claim_id: str = "claim_001",
    text: str = "Seal degradation caused pump failure",
    status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    sources: list[EvidenceSource] | None = None,
) -> GroundedClaim:
    """Build a GroundedClaim for testing."""
    return GroundedClaim(
        claim_id=claim_id,
        text=text,
        status=status,
        sources=sources or [_evidence_source()],
    )


def _citation(citation_id: str = "cit_001", **overrides: Any) -> Any:
    """Build a Citation for testing."""
    from mnemos.agentic.schemas.base import Citation

    defaults: dict[str, Any] = {
        "citation_id": citation_id,
        "evidence_region_id": "er_001",
        "document_id": "doc_001",
        "text_excerpt": "Maintenance log entry from 2024-01-15.",
    }
    defaults.update(overrides)
    return Citation(**defaults)


def _contradiction(contradiction_id: str = "contra_001", **overrides: Any) -> Contradiction:
    """Build a Contradiction for testing."""
    defaults: dict[str, Any] = {
        "contradiction_id": contradiction_id,
        "summary": "Conflicting maintenance records",
        "description": "Log says replaced, inspection says original.",
        "involved_evidence_ids": ["ev_001", "ev_002"],
    }
    defaults.update(overrides)
    return Contradiction(**defaults)


def _recommended_action(
    action_id: str = "act_001",
    description: str = "Replace seal on P-101",
    priority: str = "high",
    **overrides: Any,
) -> RecommendedAction:
    """Build a RecommendedAction for testing."""
    defaults: dict[str, Any] = {
        "action_id": action_id,
        "type": "REPAIR",
        "description": description,
        "priority": priority,
        "reasoning": "Seal degraded beyond tolerance.",
    }
    defaults.update(overrides)
    return RecommendedAction(**defaults)


def _missing_evidence(description: str = "Missing vibration data") -> MissingEvidence:
    """Build a MissingEvidence for testing."""
    return MissingEvidence(
        evidence_type="sensor_data",
        description=description,
        suggested_action="Collect vibration readings from P-101",
    )


def _reasoning_output(
    agent_name: str = "rca_agent",
    claims: list[GroundedClaim] | None = None,
    citations: list | None = None,
    contradictions: list[Contradiction] | None = None,
    next_actions: list[RecommendedAction] | None = None,
    missing_evidence: list[MissingEvidence] | None = None,
    confidence_score: float = 0.8,
    decision: ReasoningDecision = ReasoningDecision.SUFFICIENT,
    summary: str = "Root cause analysis completed.",
) -> ReasoningOutput:
    """Build a ReasoningOutput for testing."""
    return ReasoningOutput(
        agent_name=agent_name,
        reasoning_decision=decision,
        claims=claims or [],
        citations=citations or [],
        confidence_score=confidence_score,
        missing_evidence=missing_evidence or [],
        contradictions=contradictions or [],
        next_actions=next_actions or [],
        next_recommended_agents=[],
        reasoning_summary=summary,
    )


def _state(
    query: str = "What caused the P-101 pump failure?",
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a minimal AgentState dict for testing."""
    return {
        "query": query,
        "context": context or {},
    }


# ======================================================================
# ReportComposerAgent fixtures
# ======================================================================


@pytest.fixture
def _patch_deps():
    """Patch all external dependencies required by _BaseReasoningAgent."""
    with (
        patch(
            "mnemos.agentic.agents.reasoning._base.get_llm_service",
            return_value=MagicMock(),
        ),
        patch(
            "mnemos.agentic.agents.reasoning._base.get_prompt_manager",
            return_value=MagicMock(),
        ),
        patch(
            "mnemos.agentic.agents.reasoning._base.MnemosGuardrails",
            return_value=MagicMock(),
        ),
    ):
        yield


@pytest.fixture
def composer(_patch_deps):
    """Instantiate a ReportComposerAgent with mocked dependencies."""
    from mnemos.agentic.agents.reasoning.report_composer import (
        ReportComposerAgent,
    )

    return ReportComposerAgent(db=MagicMock())


# ======================================================================
# ReportComposerAgent tests
# ======================================================================


class TestReportComposerAgentIdentity:
    """Tests for agent name, role, and capabilities."""

    def test_report_composer_name_and_role(self, composer):
        """Agent must expose correct name and COMPOSITION role."""
        assert composer.name == "report_composer"
        assert composer.role == AgentRole.COMPOSITION

    def test_report_composer_capabilities(self, composer):
        """Agent must advertise the report_composition capability."""
        caps = composer._capabilities()
        assert len(caps) == 1
        cap = caps[0]
        assert isinstance(cap, AgentCapability)
        assert cap.name == "report_composition"
        assert "final_report" in cap.output_types
        assert "reasoning_output" in cap.output_types
        assert isinstance(cap.input_types, list)
        assert isinstance(cap.dependencies, list)


class TestReportComposerExecute:
    """Tests for the execute method."""

    @pytest.mark.asyncio
    async def test_report_composer_execute_no_outputs(self, composer):
        """Execute with no reasoning outputs must produce an empty report."""
        state = _state(context={})
        result = await composer.execute(state)

        ctx = result["context"]
        report: FinalReport = ctx["final_report"]
        assert isinstance(report, FinalReport)
        assert len(report.grounded_claims) == 0
        assert len(report.recommended_actions) == 0
        assert len(report.contradictions) == 0
        assert report.confidence_statement == "Insufficient evidence"
        assert "enough verified workspace evidence" in report.summary
        assert report.disclaimer

    @pytest.mark.asyncio
    async def test_report_composer_execute_with_outputs(self, composer):
        """Execute with RCA and compliance outputs must produce a FinalReport."""
        rca_output = _reasoning_output(
            agent_name="rca_agent",
            claims=[_grounded_claim("c1", "Seal failure is root cause")],
            confidence_score=0.85,
        )
        compliance_output = _reasoning_output(
            agent_name="compliance_agent",
            claims=[
                _grounded_claim(
                    "c2",
                    "Inspection SOP v3 was followed",
                    status=ClaimSupportStatus.SUPPORTED,
                ),
            ],
            confidence_score=0.9,
            summary="Compliance verified.",
        )

        state = _state(
            context={"reasoning_outputs": [rca_output, compliance_output]},
        )
        result = await composer.execute(state)
        ctx = result["context"]

        report: FinalReport = ctx["final_report"]
        assert isinstance(report, FinalReport)
        assert len(report.grounded_claims) == 2
        assert report.sections  # keyed by agent_name
        assert "rca_agent" in report.sections
        assert "compliance_agent" in report.sections

        final_output = ctx["reasoning_output"]
        assert final_output.agent_name == "report_composer"


class TestReportComposerMergeClaims:
    """Tests for claim merging and deduplication logic."""

    def test_report_composer_merge_claims_dedup(self, composer):
        """Claims with the same claim_id must be deduplicated."""
        claim_a = _grounded_claim("c1", "Text from agent A")
        claim_b = _grounded_claim("c1", "Text from agent B")
        out_a = _reasoning_output(claims=[claim_a])
        out_b = _reasoning_output(claims=[claim_b])

        merged = composer._merge_claims([out_a, out_b])
        ids = [c.claim_id for c in merged]
        assert ids.count("c1") == 1
        assert len(merged) == 1

    def test_report_composer_merge_claims_preference(self, composer):
        """When duplicate claim_ids exist, SUPPORTED must win over lower tiers."""
        claim_uncertain = _grounded_claim(
            "c1",
            "Maybe seal issue",
            status=ClaimSupportStatus.UNCERTAIN,
        )
        claim_supported = _grounded_claim(
            "c1",
            "Definitely seal issue",
            status=ClaimSupportStatus.SUPPORTED,
        )
        out_uncertain = _reasoning_output(claims=[claim_uncertain])
        out_supported = _reasoning_output(claims=[claim_supported])

        merged = composer._merge_claims([out_uncertain, out_supported])
        assert len(merged) == 1
        assert merged[0].status == ClaimSupportStatus.SUPPORTED
        assert merged[0].text == "Definitely seal issue"

    def test_report_composer_merge_claims_refuted_beats_no_evidence(self, composer):
        """REFUTED status must beat NO_EVIDENCE for the same claim."""
        claim_no_ev = _grounded_claim(
            "c1",
            "Some claim",
            status=ClaimSupportStatus.NO_EVIDENCE,
        )
        claim_refuted = _grounded_claim(
            "c1",
            "Some claim",
            status=ClaimSupportStatus.REFUTED,
        )
        merged = composer._merge_claims(
            [_reasoning_output(claims=[claim_no_ev]), _reasoning_output(claims=[claim_refuted])]
        )
        assert len(merged) == 1
        assert merged[0].status == ClaimSupportStatus.REFUTED


class TestReportComposerMergeCitations:
    """Tests for citation deduplication."""

    def test_report_composer_merge_citations_dedup(self, composer):
        """Citations with the same citation_id must be deduplicated."""
        cit_a = _citation("cit_001", document_id="doc_A")
        cit_b = _citation("cit_001", document_id="doc_A")
        out_a = _reasoning_output(citations=[cit_a])
        out_b = _reasoning_output(citations=[cit_b])

        merged = composer._merge_citations([out_a, out_b])
        assert len(merged) == 1
        assert merged[0].citation_id == "cit_001"

    def test_report_composer_merge_citations_unique_kept(self, composer):
        """Distinct citation_ids must all be kept."""
        cit_1 = _citation("cit_001")
        cit_2 = _citation("cit_002")
        out = _reasoning_output(citations=[cit_1, cit_2])

        merged = composer._merge_citations([out])
        assert len(merged) == 2


class TestReportComposerMergeContradictions:
    """Tests for contradiction merging."""

    def test_report_composer_merge_contradictions(self, composer):
        """All unique contradictions must be kept; duplicates dropped."""
        contra_a = _contradiction("contra_001")
        contra_b = _contradiction("contra_002")
        contra_dup = _contradiction("contra_001")

        out_a = _reasoning_output(contradictions=[contra_a, contra_b])
        out_b = _reasoning_output(contradictions=[contra_dup])

        merged = composer._merge_contradictions([out_a, out_b])
        assert len(merged) == 2
        ids = {c.contradiction_id for c in merged}
        assert ids == {"contra_001", "contra_002"}


class TestReportComposerMergeRecommendations:
    """Tests for recommendation merging, dedup, and priority sorting."""

    def test_report_composer_merge_recommendations_priority(self, composer):
        """Actions must be sorted: critical > high > medium > low."""
        actions = [
            _recommended_action("a1", "Low task", priority="low"),
            _recommended_action("a2", "Critical shutdown", priority="critical"),
            _recommended_action("a3", "Medium inspection", priority="medium"),
            _recommended_action("a4", "High priority repair", priority="high"),
        ]
        out = _reasoning_output(next_actions=actions)

        merged = composer._merge_recommendations([out])
        priorities = [a.priority for a in merged]
        assert priorities == ["critical", "high", "medium", "low"]

    def test_report_composer_merge_recommendations_dedup(self, composer):
        """Actions with identical description text must be deduplicated."""
        action_a = _recommended_action("a1", "Replace seal on P-101", priority="high")
        action_b = _recommended_action("a2", "Replace seal on P-101", priority="critical")
        out_a = _reasoning_output(next_actions=[action_a])
        out_b = _reasoning_output(next_actions=[action_b])

        merged = composer._merge_recommendations([out_a, out_b])
        assert len(merged) == 1
        # First-encountered wins (critical wins here since it was in out_b
        # but the description is the same, so the first one added wins).
        # Actually the first one encountered in iteration order wins.
        assert merged[0].action_id == "a1"

    def test_report_composer_merge_recommendations_dedup_case_insensitive(
        self,
        composer,
    ):
        """Dedup must be case-insensitive after strip+lower."""
        action_a = _recommended_action("a1", "Replace Seal On P-101", priority="high")
        action_b = _recommended_action("a2", " replace seal on p-101 ", priority="low")
        out_a = _reasoning_output(next_actions=[action_a])
        out_b = _reasoning_output(next_actions=[action_b])

        merged = composer._merge_recommendations([out_a, out_b])
        assert len(merged) == 1


class TestReportComposerConfidence:
    """Tests for confidence computation and verbal statements."""

    def test_report_composer_overall_confidence(self, composer):
        """Confidence must be the weighted average of agent scores."""
        out_a = _reasoning_output(confidence_score=0.8)
        out_b = _reasoning_output(confidence_score=0.6)

        state = _state(context={})
        confidence = composer._compute_overall_confidence([out_a, out_b], state)
        assert confidence == pytest.approx(0.7, abs=0.01)

    def test_report_composer_overall_confidence_with_bundle(self, composer):
        """When an evidence_bundle has confidence_signals, blend them in."""
        signal = ConfidenceSignal(
            signal_name="evidence_quality",
            signal_value=0.95,
            weight=2.0,
        )
        bundle = EvidenceBundle(
            query_id="q1",
            intent=QueryIntent.RCA,
            confidence_signals=[signal],
        )
        out_a = _reasoning_output(confidence_score=0.8)
        state = _state(context={"evidence_bundle": bundle})

        confidence = composer._compute_overall_confidence([out_a], state)
        # Expected: 0.85 * 0.8 + 0.15 * 0.95 = 0.68 + 0.1425 = 0.8225
        assert confidence == pytest.approx(0.822, abs=0.01)

    def test_report_composer_overall_confidence_no_outputs(self, composer):
        """No outputs must yield confidence 0.0."""
        state = _state(context={})
        confidence = composer._compute_overall_confidence([], state)
        assert confidence == 0.0

    def test_report_composer_confidence_statement_very_high(self, composer):
        """Confidence > 0.9 must produce 'Very High'."""
        statement = composer._build_confidence_statement(0.95)
        assert statement.startswith("Very High")
        assert "95%" in statement

    def test_report_composer_confidence_statement_low(self, composer):
        """Confidence < 0.3 must produce 'Very Low'."""
        statement = composer._build_confidence_statement(0.2)
        assert statement.startswith("Very Low")

    def test_report_composer_confidence_statement_high(self, composer):
        """Confidence between 0.75 and 0.9 must produce 'High'."""
        statement = composer._build_confidence_statement(0.82)
        assert statement.startswith("High")

    def test_report_composer_confidence_statement_medium(self, composer):
        """Confidence between 0.5 and 0.75 must produce 'Medium'."""
        statement = composer._build_confidence_statement(0.6)
        assert statement.startswith("Medium")

    def test_report_composer_confidence_statement_exact_boundary(self, composer):
        """Boundary value 0.75 exactly must produce 'Medium' (not 'High')."""
        statement = composer._build_confidence_statement(0.75)
        assert statement.startswith("Medium")


class TestReportComposerSections:
    """Tests for the report sections and summary."""

    def test_report_composer_final_report_sections(self, composer):
        """Report sections must be keyed by agent_name with correct fields."""
        out_a = _reasoning_output(
            agent_name="rca_agent",
            confidence_score=0.8,
            summary="RCA summary text.",
            decision=ReasoningDecision.SUFFICIENT,
        )
        out_b = _reasoning_output(
            agent_name="compliance_agent",
            confidence_score=0.9,
            summary="Compliance summary text.",
            decision=ReasoningDecision.SUFFICIENT,
        )
        state = _state(context={"reasoning_outputs": [out_a, out_b]})

        report = composer._synthesize_report([out_a, out_b], state)

        assert "rca_agent" in report.sections
        assert "compliance_agent" in report.sections

        rca_section = report.sections["rca_agent"]
        assert rca_section["summary"] == "RCA summary text."
        assert rca_section["confidence"] == 0.8
        assert rca_section["decision"] == ReasoningDecision.SUFFICIENT
        assert "metadata" in rca_section

    def test_report_composer_title_from_query(self, composer):
        """Title must be derived from the investigation query."""
        state = _state(query="Why did the boiler overheat?")
        title = composer._build_title(state["query"])
        assert title == "Investigation Report: Why did the boiler overheat?"

    def test_report_composer_title_empty_query(self, composer):
        """Empty query must produce default title."""
        assert composer._build_title("") == "Investigation Report"

    def test_report_composer_title_long_query_truncated(self, composer):
        """Query longer than 120 chars must be truncated."""
        long_query = "A" * 150
        title = composer._build_title(long_query)
        assert title.startswith("Investigation Report: AAAAA")
        assert title.endswith("...")
        assert len(title) < len("Investigation Report: ") + 150


class TestReportComposerDisclaimer:
    """Tests for disclaimer generation."""

    def test_report_composer_disclaimer(self, composer):
        """Disclaimer must be present and mention human validation."""
        disclaimer = composer._build_disclaimer(0.8)
        assert "human validation" in disclaimer.lower()
        assert "WARNING" not in disclaimer

    def test_report_composer_disclaimer_low_confidence(self, composer):
        """Low confidence disclaimer must include WARNING."""
        disclaimer = composer._build_disclaimer(0.3)
        assert "WARNING" in disclaimer
        assert "human validation" in disclaimer.lower()


class TestReportComposerEmptyReport:
    """Tests for the empty-report path."""

    def test_report_composer_build_empty_report(self, composer):
        """Empty report must have zero claims/actions and zero confidence."""
        state = _state(query="Test query")
        report = composer._build_empty_report(state)
        assert isinstance(report, FinalReport)
        assert len(report.grounded_claims) == 0
        assert len(report.recommended_actions) == 0
        assert len(report.contradictions) == 0
        assert report.confidence_statement == "Insufficient evidence"
        assert report.title == "Investigation Report: Test query"

    def test_report_composer_build_empty_report_default_query(self, composer):
        """Empty report with no query must use default title."""
        state = _state(query="")
        report = composer._build_empty_report(state)
        assert report.title == "Investigation Report"


class TestReportComposerMissingEvidence:
    """Tests for missing evidence collection."""

    def test_report_composer_collect_missing_evidence_dedup(self, composer):
        """Duplicate missing-evidence descriptions must be deduplicated."""
        me_a = _missing_evidence("Missing vibration data")
        me_b = _missing_evidence("Missing vibration data")
        out_a = _reasoning_output(missing_evidence=[me_a])
        out_b = _reasoning_output(missing_evidence=[me_b])

        result = composer._collect_missing_evidence([out_a, out_b])
        assert len(result) == 1
        assert result[0] == "Missing vibration data"

    def test_report_composer_collect_missing_evidence_unique(self, composer):
        """Distinct descriptions must all be kept."""
        me_a = _missing_evidence("Missing vibration data")
        me_b = _missing_evidence("Missing thermal images")
        out = _reasoning_output(missing_evidence=[me_a, me_b])

        result = composer._collect_missing_evidence([out])
        assert len(result) == 2

    def test_report_composer_collect_missing_evidence_empty(self, composer):
        """No missing evidence must return empty list."""
        out = _reasoning_output(missing_evidence=[])
        result = composer._collect_missing_evidence([out])
        assert result == []


class TestReportComposerSummary:
    """Tests for summary generation."""

    def test_report_composer_build_summary(self, composer):
        """Summary must mention agent count and claim counts."""
        out_a = _reasoning_output(
            agent_name="rca_agent",
            claims=[
                _grounded_claim("c1", "text", ClaimSupportStatus.SUPPORTED),
                _grounded_claim("c2", "text2", ClaimSupportStatus.REFUTED),
            ],
            decision=ReasoningDecision.SUFFICIENT,
            summary="RCA completed.",
        )
        report = composer._synthesize_report([out_a], _state())
        assert "Based on the verified workspace evidence" in report.summary
        assert "text (supported)" in report.summary
        assert "reasoning agent" not in report.summary.lower()
        assert "Rca Agent" not in report.summary


class TestReportComposerStoreFinal:
    """Tests for state storage after composition."""

    @pytest.mark.asyncio
    async def test_report_composer_store_final_with_claims(self, composer):
        """_store_final must populate context with final_report and output."""
        claim = _grounded_claim("c1", "text")
        report = FinalReport(
            title="Test Report",
            summary="Summary",
            sections={},
            grounded_claims=[claim],
            confidence_statement="High confidence (85%)",
        )
        outputs = [_reasoning_output(claims=[claim])]
        state = _state(context={})

        composer._store_final(state, report, outputs)
        ctx = state["context"]
        assert ctx["final_report"] is report
        assert ctx["reasoning_output"].agent_name == "report_composer"
        assert ctx["reasoning_output"].reasoning_decision == ReasoningDecision.SUFFICIENT
        assert ctx["reasoning_output"].metadata["total_claims"] == 1

    @pytest.mark.asyncio
    async def test_report_composer_store_final_no_claims(self, composer):
        """_store_final with no claims must use 0.0 confidence."""
        report = FinalReport(
            title="Empty",
            summary="Nothing",
            sections={},
            confidence_statement="Very Low confidence (0%)",
        )
        state = _state(context={})
        composer._store_final(state, report, [])

        output = state["context"]["reasoning_output"]
        assert output.confidence_score == 0.0
        assert output.claims == []


# ======================================================================
# InvestigationPipeline tests
# ======================================================================


class TestInvestigationPipeline:
    """Tests for InvestigationPipeline structure and stages."""

    def test_pipeline_init(self):
        """Pipeline must be constructible with default parameters."""
        from mnemos.agentic.runtime.workflow import InvestigationPipeline

        pipeline = InvestigationPipeline()
        assert pipeline.max_iterations == 10
        assert pipeline.evidence_confidence_threshold == 0.7
        assert pipeline.auto_checkpoint is True
        assert pipeline.failure_recovery is not None
        assert pipeline.approval_node is not None
        assert pipeline.reflection_agent is not None

    def test_pipeline_init_custom_params(self):
        """Pipeline must accept custom parameters."""
        from mnemos.agentic.runtime.workflow import InvestigationPipeline

        pipeline = InvestigationPipeline(
            max_iterations=5,
            evidence_confidence_threshold=0.8,
            auto_checkpoint=False,
        )
        assert pipeline.max_iterations == 5
        assert pipeline.evidence_confidence_threshold == 0.8
        assert pipeline.auto_checkpoint is False

    def test_pipeline_stages_registered(self):
        """All 11 stages must exist as methods on InvestigationPipeline."""
        from mnemos.agentic.runtime.workflow import InvestigationPipeline

        expected_stages = [
            "_stage_supervisor_init",
            "_stage_query_router",
            "_stage_retrieval_planner",
            "_stage_evidence_retrieval",
            "_stage_evidence_verification",
            "_stage_reflection",
            "_stage_specialized_agents",
            "_stage_report_composer",
            "_stage_human_approval",
            "_stage_final_response",
            "_stage_complete",
        ]
        for stage_name in expected_stages:
            assert hasattr(InvestigationPipeline, stage_name), (
                f"Missing pipeline stage: {stage_name}"
            )
            assert callable(getattr(InvestigationPipeline, stage_name)), (
                f"Pipeline stage {stage_name} is not callable"
            )

    def test_pipeline_has_run_method(self):
        """Pipeline must expose the async run() entry point."""
        from mnemos.agentic.runtime.workflow import InvestigationPipeline

        assert hasattr(InvestigationPipeline, "run")
        assert hasattr(InvestigationPipeline, "run_streaming")

    @pytest.mark.asyncio
    async def test_pipeline_run_produces_result(self):
        """Full pipeline run with no agents must produce a valid result dict."""
        from mnemos.agentic.runtime.workflow import InvestigationPipeline

        pipeline = InvestigationPipeline(auto_checkpoint=False)
        result = await pipeline.run("inv_test_001", "Test query")

        assert isinstance(result, dict)
        assert result["investigation_id"] == "inv_test_001"
        assert "final_response" in result
        assert "final_report" in result
        assert "phase" in result
        assert "event_summary" in result
        assert result["is_complete"] is True


class TestBackwardCompatibility:
    """Tests for the legacy create_investigation_workflow function."""

    def test_create_investigation_workflow(self):
        """Legacy factory function must be importable and callable."""
        from mnemos.agentic.runtime.workflow import create_investigation_workflow

        assert callable(create_investigation_workflow)

    def test_create_investigation_workflow_returns_state_graph(self):
        """Legacy factory must return a StateGraph-like object."""
        from unittest.mock import patch as _patch

        from mnemos.agentic.runtime.registry import AgentRegistry
        from mnemos.agentic.runtime.workflow import create_investigation_workflow

        registry = AgentRegistry()
        agent_functions: dict[str, Any] = {}

        with _patch("mnemos.agentic.runtime.workflow.SupervisorAgent") as MockSupervisor:
            MockSupervisor.return_value = MagicMock()
            MockSupervisor.return_value.decide_next = MagicMock()
            graph = create_investigation_workflow(
                agent_registry=registry,
                agent_functions=agent_functions,
            )

        assert graph is not None
        assert hasattr(graph, "add_node") or hasattr(graph, "compile")

    def test_create_investigation_workflow_accepts_params(self):
        """Legacy factory must accept all documented parameters."""
        from mnemos.agentic.runtime.registry import AgentRegistry
        from mnemos.agentic.runtime.workflow import create_investigation_workflow

        registry = AgentRegistry()

        # Just verify it doesn't raise with all parameters
        with patch("mnemos.agentic.runtime.workflow.SupervisorAgent") as MockSupervisor:
            MockSupervisor.return_value = MagicMock()
            graph = create_investigation_workflow(
                agent_registry=registry,
                agent_functions={},
                max_iterations=5,
                evidence_confidence_threshold=0.8,
                auto_checkpoint_interval=2,
            )
            assert graph is not None


# ======================================================================
# Edge-case and integration-style tests
# ======================================================================


class TestEdgeCases:
    """Edge-case tests for unusual or boundary inputs."""

    def test_merge_claims_empty_outputs(self, composer):
        """Merging claims from no outputs must return empty list."""
        assert composer._merge_claims([]) == []

    def test_merge_citations_empty_outputs(self, composer):
        """Merging citations from no outputs must return empty list."""
        assert composer._merge_citations([]) == []

    def test_merge_contradictions_empty_outputs(self, composer):
        """Merging contradictions from no outputs must return empty list."""
        assert composer._merge_contradictions([]) == []

    def test_merge_recommendations_empty_outputs(self, composer):
        """Merging recommendations from no outputs must return empty list."""
        assert composer._merge_recommendations([]) == []

    def test_collect_missing_evidence_empty_outputs(self, composer):
        """Collecting missing evidence from no outputs must return empty."""
        assert composer._collect_missing_evidence([]) == []

    @pytest.mark.asyncio
    async def test_execute_gathers_from_context_key(self, composer):
        """Execute must read from context['reasoning_outputs'] first."""
        out = _reasoning_output(agent_name="rca_agent")
        state = _state(context={"reasoning_outputs": [out]})
        result = await composer.execute(state)

        report = result["context"]["final_report"]
        assert isinstance(report, FinalReport)
        assert report.sections.get("rca_agent") is not None

    @pytest.mark.asyncio
    async def test_execute_with_single_output(self, composer):
        """Execute with a single reasoning output must still produce a report."""
        out = _reasoning_output(
            agent_name="rca_agent",
            claims=[_grounded_claim("c1", "Single claim")],
            confidence_score=0.75,
        )
        state = _state(context={"reasoning_outputs": [out]})
        result = await composer.execute(state)

        report = result["context"]["final_report"]
        assert len(report.grounded_claims) == 1
        assert "Medium" in report.confidence_statement or "High" in report.confidence_statement

    def test_multiple_outputs_same_claim_different_statuses(self, composer):
        """When multiple agents produce the same claim with different
        statuses, the best-supported version must be selected."""
        c_uncertain = _grounded_claim("c1", "text", status=ClaimSupportStatus.UNCERTAIN)
        c_refuted = _grounded_claim("c1", "text", status=ClaimSupportStatus.REFUTED)
        c_no_ev = _grounded_claim("c1", "text", status=ClaimSupportStatus.NO_EVIDENCE)

        outputs = [
            _reasoning_output(claims=[c_no_ev]),
            _reasoning_output(claims=[c_refuted]),
            _reasoning_output(claims=[c_uncertain]),
        ]
        merged = composer._merge_claims(outputs)
        assert len(merged) == 1
        assert merged[0].status == ClaimSupportStatus.UNCERTAIN

    def test_all_recommendation_priorities(self, composer):
        """Verify the full priority ordering with one action of each level."""
        actions = [
            _recommended_action("a_low", "Low task", priority="low"),
            _recommended_action("a_med", "Med task", priority="medium"),
            _recommended_action("a_high", "High task", priority="high"),
            _recommended_action("a_crit", "Crit task", priority="critical"),
        ]
        merged = composer._merge_recommendations([_reasoning_output(next_actions=actions)])
        priorities = [a.priority for a in merged]
        assert priorities == ["critical", "high", "medium", "low"]

    def test_build_disclaimer_high_confidence_no_warning(self, composer):
        """High confidence must not include WARNING in disclaimer."""
        disclaimer = composer._build_disclaimer(0.9)
        assert "WARNING" not in disclaimer
        assert "human validation" in disclaimer.lower()

    def test_build_confidence_statement_zero(self, composer):
        """Zero confidence must map to 'Very Low'."""
        stmt = composer._build_confidence_statement(0.0)
        assert stmt.startswith("Very Low")
        assert "0%" in stmt

    def test_build_confidence_statement_one(self, composer):
        """Confidence 1.0 must map to 'Very High'."""
        stmt = composer._build_confidence_statement(1.0)
        assert stmt.startswith("Very High")
        assert "100%" in stmt
