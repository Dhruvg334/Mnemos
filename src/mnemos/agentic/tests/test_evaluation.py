"""Comprehensive tests for the Mnemos AI evaluation framework.

Covers ProductionMetrics (10 metrics), MetricAggregator, InvestigationEvaluator,
EvalReporter, and model creation/serialisation.  All tests are self-contained —
no external services, databases, or LLM calls are required.
"""

from __future__ import annotations

import json
import math

import pytest

from mnemos.agentic.evaluation.evaluator import InvestigationEvaluator
from mnemos.agentic.evaluation.metrics import MetricAggregator, ProductionMetrics
from mnemos.agentic.evaluation.models import (
    BenchmarkReport,
    ComparisonReport,
    EvalDataset,
    EvalPipelineType,
    EvalSample,
    MetricResult,
    SampleResult,
)
from mnemos.agentic.evaluation.reporter import EvalReporter
from mnemos.agentic.schemas.base import (
    Citation,
    ClaimSupportStatus,
    ComplianceCheckResult,
    EvidenceSource,
    GroundedClaim,
    ProvenanceChain,
)


# ── helpers ──────────────────────────────────────────────────────────


def _make_provenance(document_id: str = "doc-1") -> ProvenanceChain:
    return ProvenanceChain(
        evidence_region_id="er-1",
        document_id=document_id,
        document_version=1,
        sha256="a" * 64,
        source_filename="test.pdf",
        storage_key="s3://bucket/test.pdf",
    )


def _make_evidence_source(document_id: str = "doc-1", text: str = "excerpt") -> EvidenceSource:
    return EvidenceSource(
        text_excerpt=text,
        provenance=_make_provenance(document_id),
        relevance_score=0.9,
        confidence_score=0.8,
    )


def _make_citation(citation_id: str, document_id: str = "doc-1") -> Citation:
    return Citation(
        citation_id=citation_id,
        evidence_region_id=f"er-{citation_id}",
        document_id=document_id,
        text_excerpt=f"text for {citation_id}",
    )


def _make_grounded_claim(
    claim_id: str,
    status: ClaimSupportStatus = ClaimSupportStatus.SUPPORTED,
    with_sources: bool = True,
) -> GroundedClaim:
    return GroundedClaim(
        claim_id=claim_id,
        text=f"claim {claim_id}",
        status=status,
        sources=[_make_evidence_source()] if with_sources else [],
    )


def _make_benchmark_report(
    name: str = "test-benchmark",
    pipeline: EvalPipelineType = EvalPipelineType.MNEMOS_GRAPH_RAG,
    metrics: dict[str, float] | None = None,
) -> BenchmarkReport:
    return BenchmarkReport(
        benchmark_name=name,
        pipeline_type=pipeline,
        dataset_name="test-dataset",
        summary_metrics=metrics or {"routing_accuracy": 0.9, "retrieval_recall": 0.8},
        sample_results=[],
        total_duration_ms=1000.0,
        avg_latency_ms=50.0,
        success_count=10,
        failure_count=0,
    )


# =====================================================================
# ProductionMetrics — Routing Accuracy (tests 1–4)
# =====================================================================


class TestRoutingAccuracy:
    """Tests for ProductionMetrics.routing_accuracy."""

    def test_routing_accuracy_identical(self) -> None:
        """Both predicted and expected intent are the same → 1.0."""
        result = ProductionMetrics.routing_accuracy("rca", "rca")
        assert result.score == 1.0
        assert result.name == "routing_accuracy"

    def test_routing_accuracy_different(self) -> None:
        """Predicted intent differs from expected → 0.0."""
        result = ProductionMetrics.routing_accuracy("rca", "compliance")
        assert result.score == 0.0

    def test_routing_accuracy_partial(self) -> None:
        """Case-insensitive and whitespace-trimmed comparison."""
        result = ProductionMetrics.routing_accuracy("  RCA  ", "rca")
        assert result.score == 1.0

    def test_routing_accuracy_empty(self) -> None:
        """Both inputs are None → 1.0 (no expected intent)."""
        result = ProductionMetrics.routing_accuracy(None, None)
        assert result.score == 1.0

    def test_routing_accuracy_predicted_none(self) -> None:
        """Predicted is None but expected is set → 0.0."""
        result = ProductionMetrics.routing_accuracy(None, "rca")
        assert result.score == 0.0

    def test_routing_accuracy_expected_none(self) -> None:
        """Expected is None → 1.0 regardless of prediction."""
        result = ProductionMetrics.routing_accuracy("rca", None)
        assert result.score == 1.0


# =====================================================================
# ProductionMetrics — Retrieval Recall (tests 5–8)
# =====================================================================


class TestRetrievalRecall:
    """Tests for ProductionMetrics.retrieval_recall."""

    def test_retrieval_recall_perfect(self) -> None:
        """All expected documents are in the retrieved set → 1.0."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=["d1", "d2", "d3"],
            expected_doc_ids=["d1", "d2", "d3"],
        )
        assert result.score == 1.0

    def test_retrieval_recall_none_found(self) -> None:
        """No expected documents retrieved → 0.0."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=["d4", "d5"],
            expected_doc_ids=["d1", "d2"],
        )
        assert result.score == 0.0

    def test_retrieval_recall_partial(self) -> None:
        """2 of 4 expected docs found → 0.5."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=["d1", "d2", "x"],
            expected_doc_ids=["d1", "d2", "d3", "d4"],
        )
        assert math.isclose(result.score, 0.5)

    def test_retrieval_recall_empty_expected(self) -> None:
        """No expected docs → 1.0 (not applicable)."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=["d1"],
            expected_doc_ids=[],
        )
        assert result.score == 1.0

    def test_retrieval_recall_duplicates_collapsed(self) -> None:
        """Duplicate retrieved IDs are collapsed into a set."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=["d1", "d1", "d1"],
            expected_doc_ids=["d1", "d2"],
        )
        assert math.isclose(result.score, 0.5)

    def test_retrieval_recall_empty_retrieved(self) -> None:
        """Empty retrieved list with expected docs → 0.0."""
        result = ProductionMetrics.retrieval_recall(
            retrieved_doc_ids=[],
            expected_doc_ids=["d1"],
        )
        assert result.score == 0.0


# =====================================================================
# ProductionMetrics — Graph Retrieval Quality (tests 9–10)
# =====================================================================


class TestGraphRetrievalQuality:
    """Tests for ProductionMetrics.graph_retrieval_quality."""

    def test_graph_retrieval_quality_all_found(self) -> None:
        """All expected entities in graph nodes → 1.0."""
        result = ProductionMetrics.graph_retrieval_quality(
            graph_nodes=["e1", "e2", "e3"],
            expected_entities=["e1", "e2", "e3"],
        )
        assert result.score == 1.0

    def test_graph_retrieval_quality_none_found(self) -> None:
        """No expected entities in graph nodes → 0.0."""
        result = ProductionMetrics.graph_retrieval_quality(
            graph_nodes=["e4", "e5"],
            expected_entities=["e1", "e2"],
        )
        assert result.score == 0.0

    def test_graph_retrieval_quality_partial(self) -> None:
        """1 of 3 expected entities found → ~0.333."""
        result = ProductionMetrics.graph_retrieval_quality(
            graph_nodes=["e1"],
            expected_entities=["e1", "e2", "e3"],
        )
        assert math.isclose(result.score, 1 / 3)

    def test_graph_retrieval_quality_empty_expected(self) -> None:
        """No expected entities → 1.0 (not applicable)."""
        result = ProductionMetrics.graph_retrieval_quality(
            graph_nodes=["e1"],
            expected_entities=[],
        )
        assert result.score == 1.0


# =====================================================================
# ProductionMetrics — Citation Precision (tests 11–14)
# =====================================================================


class TestCitationPrecision:
    """Tests for ProductionMetrics.citation_precision."""

    def test_citation_precision_perfect(self) -> None:
        """All cited IDs are in the expected set → 1.0."""
        citations = [_make_citation("c1"), _make_citation("c2")]
        result = ProductionMetrics.citation_precision(citations, ["c1", "c2"])
        assert result.score == 1.0

    def test_citation_precision_mixed(self) -> None:
        """2 of 3 cited IDs are expected → 2/3."""
        citations = [_make_citation("c1"), _make_citation("c2"), _make_citation("spurious")]
        result = ProductionMetrics.citation_precision(citations, ["c1", "c2"])
        assert math.isclose(result.score, 2 / 3)

    def test_citation_precision_empty(self) -> None:
        """No citations produced → 0.0."""
        result = ProductionMetrics.citation_precision([], ["c1"])
        assert result.score == 0.0

    def test_citation_precision_no_expected(self) -> None:
        """No expected IDs → 1.0 (not applicable)."""
        citations = [_make_citation("c1")]
        result = ProductionMetrics.citation_precision(citations, [])
        assert result.score == 1.0

    def test_citation_precision_all_spurious(self) -> None:
        """All cited IDs are spurious → 0.0."""
        citations = [_make_citation("x"), _make_citation("y")]
        result = ProductionMetrics.citation_precision(citations, ["c1", "c2"])
        assert result.score == 0.0


# =====================================================================
# ProductionMetrics — Grounded Answer Rate (tests 15–16)
# =====================================================================


class TestGroundedAnswerRate:
    """Tests for ProductionMetrics.grounded_answer_rate."""

    def test_grounded_answer_rate_all_grounded(self) -> None:
        """All SUPPORTED claims have evidence sources → 1.0."""
        claims = [
            _make_grounded_claim("c1", ClaimSupportStatus.SUPPORTED, with_sources=True),
            _make_grounded_claim("c2", ClaimSupportStatus.SUPPORTED, with_sources=True),
        ]
        result = ProductionMetrics.grounded_answer_rate(claims)
        assert result.score == 1.0

    def test_grounded_answer_rate_none_grounded(self) -> None:
        """SUPPORTED claims with no evidence sources → 0.0."""
        claims = [
            _make_grounded_claim("c1", ClaimSupportStatus.SUPPORTED, with_sources=False),
            _make_grounded_claim("c2", ClaimSupportStatus.SUPPORTED, with_sources=False),
        ]
        result = ProductionMetrics.grounded_answer_rate(claims)
        assert result.score == 0.0

    def test_grounded_answer_rate_no_supported(self) -> None:
        """No SUPPORTED claims → 1.0 (defaults to 1.0)."""
        claims = [
            _make_grounded_claim("c1", ClaimSupportStatus.REFUTED, with_sources=False),
        ]
        result = ProductionMetrics.grounded_answer_rate(claims)
        assert result.score == 1.0

    def test_grounded_answer_rate_empty(self) -> None:
        """No claims at all → 1.0 (nothing to evaluate)."""
        result = ProductionMetrics.grounded_answer_rate([])
        assert result.score == 1.0

    def test_grounded_answer_rate_mixed(self) -> None:
        """1 of 2 SUPPORTED claims grounded → 0.5."""
        claims = [
            _make_grounded_claim("c1", ClaimSupportStatus.SUPPORTED, with_sources=True),
            _make_grounded_claim("c2", ClaimSupportStatus.SUPPORTED, with_sources=False),
        ]
        result = ProductionMetrics.grounded_answer_rate(claims)
        assert math.isclose(result.score, 0.5)


# =====================================================================
# ProductionMetrics — Abstention Quality (tests 17–18)
# =====================================================================


class TestAbstentionQuality:
    """Tests for ProductionMetrics.abstention_quality."""

    def test_abstention_quality_correct_abstain(self) -> None:
        """Abstained when ground truth unavailable → 1.0."""
        result = ProductionMetrics.abstention_quality(
            abstained=True, ground_truth_available=False,
        )
        assert result.score == 1.0

    def test_abstention_quality_incorrect_abstain(self) -> None:
        """Abstained when ground truth available → 0.0."""
        result = ProductionMetrics.abstention_quality(
            abstained=True, ground_truth_available=True,
        )
        assert result.score == 0.0

    def test_abstention_quality_correct_non_abstain(self) -> None:
        """Answered when ground truth available → 1.0."""
        result = ProductionMetrics.abstention_quality(
            abstained=False, ground_truth_available=True,
        )
        assert result.score == 1.0

    def test_abstention_quality_no_gt_no_abstain(self) -> None:
        """Answered without ground truth → 0.25."""
        result = ProductionMetrics.abstention_quality(
            abstained=False, ground_truth_available=False,
        )
        assert result.score == 0.25


# =====================================================================
# ProductionMetrics — Tool Recovery (tests 19–20)
# =====================================================================


class TestToolRecovery:
    """Tests for ProductionMetrics.tool_recovery."""

    def test_tool_recovery_all_recovered(self) -> None:
        """All tool calls succeeded (no final failures) → 1.0."""
        calls = [{"tool_name": "a"}, {"tool_name": "b"}]
        result = ProductionMetrics.tool_recovery(tool_calls=calls, failed_tool_calls=[])
        assert result.score == 1.0

    def test_tool_recovery_none_recovered(self) -> None:
        """All tool calls failed → 0.0."""
        calls = [{"tool_name": "a"}, {"tool_name": "b"}]
        result = ProductionMetrics.tool_recovery(
            tool_calls=calls, failed_tool_calls=calls,
        )
        assert result.score == 0.0

    def test_tool_recovery_empty(self) -> None:
        """No tool calls → 1.0 (not applicable)."""
        result = ProductionMetrics.tool_recovery(tool_calls=[], failed_tool_calls=[])
        assert result.score == 1.0

    def test_tool_recovery_partial(self) -> None:
        """1 of 3 failed after retry → 2/3 recovery."""
        calls = [{"tool_name": "a"}, {"tool_name": "b"}, {"tool_name": "c"}]
        failed = [{"tool_name": "c"}]
        result = ProductionMetrics.tool_recovery(tool_calls=calls, failed_tool_calls=failed)
        assert math.isclose(result.score, 2 / 3)


# =====================================================================
# ProductionMetrics — Workflow Completion (tests 21–22)
# =====================================================================


class TestWorkflowCompletion:
    """Tests for ProductionMetrics.workflow_completion."""

    def test_workflow_completion_success(self) -> None:
        """Workflow completed and expected complete → 1.0."""
        result = ProductionMetrics.workflow_completion(
            is_complete=True, termination_reason=None, expected_complete=True,
        )
        assert result.score == 1.0

    def test_workflow_completion_failure(self) -> None:
        """Workflow incomplete but expected complete → 0.0."""
        result = ProductionMetrics.workflow_completion(
            is_complete=False, termination_reason="timeout", expected_complete=True,
        )
        assert result.score == 0.0

    def test_workflow_completion_expected_incomplete(self) -> None:
        """Workflow incomplete and expected incomplete → 1.0."""
        result = ProductionMetrics.workflow_completion(
            is_complete=False, termination_reason="early_exit", expected_complete=False,
        )
        assert result.score == 1.0

    def test_workflow_completion_unexpected_complete(self) -> None:
        """Workflow completed but expected incomplete → 0.0."""
        result = ProductionMetrics.workflow_completion(
            is_complete=True, termination_reason=None, expected_complete=False,
        )
        assert result.score == 0.0


# =====================================================================
# ProductionMetrics — RCA Quality (tests 23–24)
# =====================================================================


class TestRcaQuality:
    """Tests for ProductionMetrics.rca_quality."""

    def test_rca_quality_perfect(self) -> None:
        """Exact match (same tokens) → score near 1.0."""
        text = "the root cause is a bearing failure"
        result = ProductionMetrics.rca_quality(rca_output=text, expected_root_cause=text)
        assert result.score == 1.0

    def test_rca_quality_no_match(self) -> None:
        """Completely disjoint tokens → 0.0."""
        result = ProductionMetrics.rca_quality(
            rca_output="alpha bravo charlie",
            expected_root_cause="delta echo foxtrot",
        )
        assert result.score == 0.0

    def test_rca_quality_empty_output(self) -> None:
        """Empty RCA output → 0.0."""
        result = ProductionMetrics.rca_quality(rca_output="", expected_root_cause="some cause")
        assert result.score == 0.0

    def test_rca_quality_empty_expected(self) -> None:
        """Empty expected root cause → 1.0 (not applicable)."""
        result = ProductionMetrics.rca_quality(rca_output="some text", expected_root_cause="")
        assert result.score == 1.0

    def test_rca_quality_partial_overlap(self) -> None:
        """Partial token overlap → Jaccard score between 0 and 1."""
        result = ProductionMetrics.rca_quality(
            rca_output="the pump failed due to vibration",
            expected_root_cause="the pump failed due to overheating",
        )
        assert 0.0 < result.score < 1.0


# =====================================================================
# ProductionMetrics — Compliance Quality (tests 25–26)
# =====================================================================


class TestComplianceQuality:
    """Tests for ProductionMetrics.compliance_quality."""

    def test_compliance_quality_all_pass(self) -> None:
        """All checks pass with expected 'pass' → 1.0."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="revision", status="pass"),
            ComplianceCheckResult(check_id="c2", check_type="date", status="pass"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance="pass")
        assert result.score == 1.0

    def test_compliance_quality_mixed(self) -> None:
        """2 pass, 1 fail with expected 'pass' → 2/3."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="revision", status="pass"),
            ComplianceCheckResult(check_id="c2", check_type="date", status="pass"),
            ComplianceCheckResult(check_id="c3", check_type="workflow", status="fail"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance="pass")
        assert math.isclose(result.score, 2 / 3)

    def test_compliance_quality_empty(self) -> None:
        """No compliance checks → 0.0."""
        result = ProductionMetrics.compliance_quality([], expected_compliance="pass")
        assert result.score == 0.0

    def test_compliance_quality_expected_fail(self) -> None:
        """All checks fail with expected 'fail' → 1.0."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="revision", status="fail"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance="fail")
        assert result.score == 1.0

    def test_compliance_quality_no_expected_status(self) -> None:
        """No expected status; checks are internally consistent (all pass) → 1.0."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="revision", status="pass"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance=None)
        assert result.score == 1.0

    def test_compliance_quality_no_expected_mixed(self) -> None:
        """No expected status; mix of pass/fail/warn → documented/total."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="a", status="pass"),
            ComplianceCheckResult(check_id="c2", check_type="b", status="fail"),
            ComplianceCheckResult(check_id="c3", check_type="c", status="warning"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance=None)
        assert math.isclose(result.score, 1.0)

    def test_compliance_quality_with_not_applicable(self) -> None:
        """Checks include not_applicable status → only pass/fail/warn counted."""
        checks = [
            ComplianceCheckResult(check_id="c1", check_type="a", status="pass"),
            ComplianceCheckResult(check_id="c2", check_type="b", status="not_applicable"),
        ]
        result = ProductionMetrics.compliance_quality(checks, expected_compliance=None)
        assert math.isclose(result.score, 0.5)


# =====================================================================
# MetricAggregator (tests 27–29)
# =====================================================================


class TestMetricAggregator:
    """Tests for MetricAggregator static methods."""

    def test_weighted_average(self) -> None:
        """Simple weighted average of two metrics."""
        m1 = MetricResult(name="a", score=1.0, weight=2.0)
        m2 = MetricResult(name="b", score=0.0, weight=1.0)
        avg = MetricAggregator.weighted_average([m1, m2])
        assert math.isclose(avg, 2 / 3)

    def test_weighted_average_empty(self) -> None:
        """Empty metric list → 0.0."""
        assert MetricAggregator.weighted_average([]) == 0.0

    def test_weighted_average_zero_weights(self) -> None:
        """All weights zero → 0.0 (avoids division by zero)."""
        m1 = MetricResult(name="a", score=1.0, weight=0.0)
        assert MetricAggregator.weighted_average([m1]) == 0.0

    def test_aggregate_by_name(self) -> None:
        """Multiple results with same name are averaged together."""
        m1 = MetricResult(name="routing_accuracy", score=1.0, weight=1.0)
        m2 = MetricResult(name="routing_accuracy", score=0.0, weight=1.0)
        m3 = MetricResult(name="retrieval_recall", score=0.8, weight=1.0)
        agg = MetricAggregator.aggregate_by_name([m1, m2, m3])
        assert math.isclose(agg["routing_accuracy"], 0.5)
        assert math.isclose(agg["retrieval_recall"], 0.8)

    def test_compute_summary(self) -> None:
        """Summary dict contains avg_ per-metric keys and overall_weighted_score."""
        m1 = MetricResult(name="routing_accuracy", score=1.0)
        m2 = MetricResult(name="retrieval_recall", score=0.8)
        summary = MetricAggregator.compute_summary([m1, m2])
        assert "avg_routing_accuracy" in summary
        assert "avg_retrieval_recall" in summary
        assert "overall_weighted_score" in summary
        assert math.isclose(summary["avg_routing_accuracy"], 1.0)
        assert math.isclose(summary["avg_retrieval_recall"], 0.8)
        assert math.isclose(summary["overall_weighted_score"], 0.9)

    def test_compute_summary_empty(self) -> None:
        """Summary with no metrics → only overall_weighted_score = 0.0."""
        summary = MetricAggregator.compute_summary([])
        assert summary == {"overall_weighted_score": 0.0}


# =====================================================================
# InvestigationEvaluator (tests 30–31)
# =====================================================================


class TestInvestigationEvaluator:
    """Tests for InvestigationEvaluator.evaluate with various state shapes."""

    def test_evaluate_with_full_state(self) -> None:
        """Complete state with all data populated produces valid SampleResult."""
        sample = EvalSample(
            query="Why did the pump fail?",
            expected_intent="rca",
            expected_entities=["e1", "e2"],
            expected_document_ids=["doc-1", "doc-2"],
            expected_citation_ids=["cit-1"],
            expected_root_cause="bearing failure due to vibration",
            expected_compliance_status="pass",
        )

        state = {
            "phase": type("P", (), {"value": "analysis"})(),
            "is_complete": True,
            "should_abstain": False,
            "agent_outputs": {
                "query_router": {"intent": "rca"},
                "response_composer": {"answer": "The pump failed due to bearing wear."},
                "rca_agent": {"reasoning_summary": "bearing failure due to vibration"},
                "compliance_agent": {
                    "compliance_checks": [
                        ComplianceCheckResult(check_id="c1", check_type="revision", status="pass"),
                    ],
                },
            },
            "evidence": [
                {
                    "verified_evidence": [
                        {
                            "text_excerpt": "excerpt text",
                            "provenance": {"document_id": "doc-1"},
                        },
                        {
                            "text_excerpt": "another excerpt",
                            "provenance": {"document_id": "doc-2"},
                        },
                    ],
                    "grounded_relationships": [
                        {"source_id": "e1", "target_id": "e2", "relationship_type": "causes"},
                    ],
                    "resolved_entities": [
                        {"entity_id": "e1"},
                        {"entity_id": "e2"},
                    ],
                    "citations": [
                        _make_citation("cit-1", "doc-1"),
                    ],
                },
            ],
            "claims": [
                {
                    "claim_id": "cl-1",
                    "text": "bearing failure",
                    "status": "supported",
                    "sources": [_make_evidence_source("doc-1")],
                },
            ],
            "agent_metadata": {
                "retriever": {
                    "tool_calls": [
                        {"tool_name": "graph_query", "success": True},
                        {"tool_name": "vector_search", "success": True},
                    ],
                },
            },
        }

        evaluator = InvestigationEvaluator()
        result = evaluator.evaluate(state, sample, sample_index=0, latency_ms=123.4)

        assert isinstance(result, SampleResult)
        assert result.query == "Why did the pump fail?"
        assert result.latency_ms == 123.4
        assert len(result.metrics) == 10
        assert result.claim_count == 1
        assert result.grounded_claim_count == 1
        assert not result.hallucination_detected
        assert result.phase == "analysis"

        metric_names = {m.name for m in result.metrics}
        assert metric_names == {
            "routing_accuracy",
            "retrieval_recall",
            "graph_retrieval_quality",
            "citation_precision",
            "grounded_answer_rate",
            "abstention_quality",
            "tool_recovery",
            "workflow_completion",
            "rca_quality",
            "compliance_quality",
        }

    def test_evaluate_with_minimal_state(self) -> None:
        """Minimal state with just a query produces valid defaults."""
        sample = EvalSample(query="What is the asset status?")
        state = {}

        evaluator = InvestigationEvaluator()
        result = evaluator.evaluate(state, sample)

        assert result.query == "What is the asset status?"
        assert result.answer == ""
        assert len(result.metrics) == 10
        assert result.claim_count == 0
        assert result.retrieved_document_ids == []

    def test_evaluate_batch_length_mismatch(self) -> None:
        """Batch evaluation with mismatched lengths raises ValueError."""
        evaluator = InvestigationEvaluator()
        samples = [EvalSample(query="q1"), EvalSample(query="q2")]
        states: list[dict] = [{"phase": None}]

        with pytest.raises(ValueError, match="must have equal length"):
            evaluator.evaluate_batch(samples, states)

    def test_evaluate_batch_latencies_mismatch(self) -> None:
        """Batch evaluation with mismatched latencies raises ValueError."""
        evaluator = InvestigationEvaluator()
        samples = [EvalSample(query="q1")]
        states: list[dict] = [{}]

        with pytest.raises(ValueError, match="must match samples"):
            evaluator.evaluate_batch(samples, states, latencies_ms=[1.0, 2.0])

    def test_evaluate_batch_success(self) -> None:
        """Batch evaluation of two samples returns two results."""
        evaluator = InvestigationEvaluator()
        samples = [EvalSample(query="q1"), EvalSample(query="q2")]
        states: list[dict] = [{}, {}]

        results = evaluator.evaluate_batch(samples, states, latencies_ms=[10.0, 20.0])
        assert len(results) == 2
        assert results[0].query == "q1"
        assert results[1].query == "q2"
        assert results[0].latency_ms == 10.0
        assert results[1].latency_ms == 20.0


# =====================================================================
# EvalReporter (tests 32–34)
# =====================================================================


class TestEvalReporter:
    """Tests for EvalReporter output formats."""

    def test_to_json(self) -> None:
        """to_json returns valid JSON that round-trips correctly."""
        report = _make_benchmark_report()
        json_str = EvalReporter.to_json(report)
        parsed = json.loads(json_str)
        assert parsed["benchmark_name"] == "test-benchmark"
        assert "summary_metrics" in parsed

    def test_to_json_comparison(self) -> None:
        """to_json works for ComparisonReport too."""
        primary = _make_benchmark_report(name="primary", metrics={"acc": 0.95})
        secondary = _make_benchmark_report(name="secondary", metrics={"acc": 0.80})
        comparison = EvalReporter.compare(primary, secondary)
        json_str = EvalReporter.to_json(comparison)
        parsed = json.loads(json_str)
        assert "deltas" in parsed

    def test_to_markdown(self) -> None:
        """to_markdown produces markdown with key sections."""
        report = _make_benchmark_report()
        md = EvalReporter.to_markdown(report)
        assert "# Benchmark Report:" in md
        assert "## Summary Metrics" in md
        assert "## Sample Results" in md
        assert "| Metric | Value |" in md
        assert "test-benchmark" in md

    def test_to_markdown_with_sample_results(self) -> None:
        """Markdown includes per-sample metric tables."""
        report = _make_benchmark_report()
        report.sample_results = [
            SampleResult(
                sample_index=0,
                query="test query",
                answer="test answer",
                latency_ms=42.0,
                metrics=[MetricResult(name="routing_accuracy", score=1.0)],
            ),
        ]
        md = EvalReporter.to_markdown(report)
        assert "Sample 1 [PASS]" in md
        assert "test query" in md
        assert "routing_accuracy" in md

    def test_compare_reports(self) -> None:
        """compare computes percentage deltas between two reports."""
        primary = _make_benchmark_report(
            name="new-system",
            metrics={"accuracy": 0.95, "recall": 0.80},
        )
        secondary = _make_benchmark_report(
            name="baseline",
            metrics={"accuracy": 0.80, "recall": 0.80},
        )
        comparison = EvalReporter.compare(primary, secondary)

        assert isinstance(comparison, ComparisonReport)
        assert comparison.name == "new-system vs baseline"
        assert math.isclose(comparison.deltas["accuracy"], 18.75, rel_tol=1e-9)
        assert comparison.deltas["recall"] == 0.0

    def test_compare_reports_from_zero(self) -> None:
        """Delta is 100% when baseline value is zero but primary is non-zero."""
        primary = _make_benchmark_report(name="p", metrics={"x": 0.5})
        secondary = _make_benchmark_report(name="s", metrics={"x": 0.0})
        comparison = EvalReporter.compare(primary, secondary)
        assert comparison.deltas["x"] == 100.0

    def test_compare_reports_both_zero(self) -> None:
        """Delta is 0% when both values are zero."""
        primary = _make_benchmark_report(name="p", metrics={"x": 0.0})
        secondary = _make_benchmark_report(name="s", metrics={"x": 0.0})
        comparison = EvalReporter.compare(primary, secondary)
        assert comparison.deltas["x"] == 0.0

    def test_comparison_to_markdown(self) -> None:
        """comparison_to_markdown produces a markdown string with delta table."""
        primary = _make_benchmark_report(name="p", metrics={"acc": 0.9})
        secondary = _make_benchmark_report(name="s", metrics={"acc": 0.8})
        comparison = EvalReporter.compare(primary, secondary)
        md = EvalReporter.comparison_to_markdown(comparison)
        assert "# Comparison Report:" in md
        assert "Metric Deltas" in md
        assert "acc" in md
        assert "Average lift" in md

    def test_to_dict(self) -> None:
        """to_dict returns a plain dictionary."""
        report = _make_benchmark_report()
        d = EvalReporter.to_dict(report)
        assert isinstance(d, dict)
        assert d["benchmark_name"] == "test-benchmark"


# =====================================================================
# Models (tests 35–38)
# =====================================================================


class TestModels:
    """Tests for evaluation model creation and validation."""

    def test_eval_sample_creation(self) -> None:
        """EvalSample can be created with all fields."""
        sample = EvalSample(
            query="test query",
            ground_truth="ground truth answer",
            expected_intent="rca",
            expected_entities=["e1", "e2"],
            expected_document_ids=["d1"],
            expected_citation_ids=["c1"],
            expected_root_cause="root cause",
            expected_compliance_status="pass",
            ground_truth_available=True,
            metadata={"difficulty": "easy"},
        )
        assert sample.query == "test query"
        assert sample.ground_truth == "ground truth answer"
        assert len(sample.expected_entities) == 2
        assert sample.ground_truth_available is True

    def test_eval_sample_defaults(self) -> None:
        """EvalSample defaults are sensible."""
        sample = EvalSample(query="q")
        assert sample.ground_truth is None
        assert sample.expected_intent is None
        assert sample.expected_entities == []
        assert sample.expected_document_ids == []
        assert sample.expected_citation_ids == []
        assert sample.ground_truth_available is True
        assert sample.metadata == {}

    def test_eval_dataset_creation(self) -> None:
        """EvalDataset holds a list of samples."""
        samples = [EvalSample(query=f"q{i}") for i in range(5)]
        dataset = EvalDataset(
            name="unit-test",
            description="A small dataset for unit tests.",
            samples=samples,
        )
        assert dataset.name == "unit-test"
        assert len(dataset.samples) == 5

    def test_benchmark_report_creation(self) -> None:
        """BenchmarkReport can be created with all fields."""
        report = BenchmarkReport(
            benchmark_name="test",
            pipeline_type=EvalPipelineType.MNEMOS_GRAPH_RAG,
            dataset_name="d1",
            summary_metrics={"accuracy": 0.95},
            sample_results=[],
            total_duration_ms=500.0,
            avg_latency_ms=50.0,
            success_count=10,
            failure_count=0,
        )
        assert report.benchmark_name == "test"
        assert report.pipeline_type == EvalPipelineType.MNEMOS_GRAPH_RAG
        assert len(report.benchmark_id) == 16

    def test_benchmark_report_auto_fields(self) -> None:
        """BenchmarkReport auto-generates benchmark_id and timestamp."""
        report = BenchmarkReport(
            benchmark_name="auto",
            pipeline_type=EvalPipelineType.BASELINE_VECTOR_RAG,
            dataset_name="d",
        )
        assert len(report.benchmark_id) == 16
        assert report.timestamp is not None
        assert report.success_count == 0
        assert report.failure_count == 0

    def test_metric_result_weight(self) -> None:
        """MetricResult respects weight field."""
        m = MetricResult(name="test", score=0.8, weight=2.5)
        assert m.weight == 2.5
        assert m.score == 0.8

    def test_metric_result_score_bounds(self) -> None:
        """MetricResult score must be in [0, 1]."""
        MetricResult(name="ok", score=0.0)
        MetricResult(name="ok", score=1.0)
        with pytest.raises(Exception):
            MetricResult(name="bad", score=1.5)
        with pytest.raises(Exception):
            MetricResult(name="bad", score=-0.1)

    def test_sample_result_creation(self) -> None:
        """SampleResult can be created with all fields."""
        sr = SampleResult(
            sample_index=0,
            query="q",
            answer="a",
            latency_ms=100.0,
            metrics=[MetricResult(name="m", score=1.0)],
            claim_count=3,
            grounded_claim_count=2,
            hallucination_detected=True,
            phase="complete",
        )
        assert sr.claim_count == 3
        assert sr.hallucination_detected is True

    def test_comparison_report_creation(self) -> None:
        """ComparisonReport stores both reports and deltas."""
        primary = _make_benchmark_report(name="p")
        secondary = _make_benchmark_report(name="s")
        cr = ComparisonReport(
            name="p vs s",
            report_primary=primary,
            report_secondary=secondary,
            deltas={"acc": 10.0},
        )
        assert cr.deltas["acc"] == 10.0
        assert cr.report_primary.benchmark_name == "p"

    def test_eval_pipeline_type_enum(self) -> None:
        """EvalPipelineType has the expected variants."""
        assert EvalPipelineType.MNEMOS_GRAPH_RAG == "mnemos_graph_rag"
        assert EvalPipelineType.BASELINE_VECTOR_RAG == "baseline_vector_rag"

    def test_evaluation_run_creation(self) -> None:
        """EvaluationRun holds multiple benchmark reports."""
        from mnemos.agentic.evaluation.models import EvaluationRun

        run = EvaluationRun(
            dataset_name="test",
            benchmarks=[_make_benchmark_report("b1"), _make_benchmark_report("b2")],
            total_duration_ms=2000.0,
        )
        assert len(run.benchmarks) == 2
        assert len(run.run_id) == 16
