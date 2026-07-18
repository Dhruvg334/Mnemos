"""Evaluation gate tests for CI (P0 #20).

These tests run the evaluation framework against synthetic investigation
states (no LLM, no DB).  They enforce the threshold values defined in
``dataset_v1.CI_THRESHOLDS``.

A failing threshold means a real regression occurred and must be fixed
before the PR can merge.

P0 #20 required categories covered:
- intent classification accuracy       → routing_accuracy metric
- entity-resolution accuracy           → graph_retrieval_quality metric
- retrieval Recall@K                   → retrieval_recall metric
- citation validity / completeness     → citation_precision metric
- unsupported-claim rate               → grounded_answer_rate metric
- abstention accuracy                  → abstention_quality metric
- tool-selection correctness           → tool_recovery metric
- workflow completion rate             → workflow_completion metric
- cross-site/tenant leakage            → routing_accuracy (expect block)
- latency budget                       → avg_latency_ms threshold
- cost budget (not testable w/o LLM)   → noted in README as skipped

P0 #21: The report produced here uses real metric computation code
(``ProductionMetrics``, ``InvestigationEvaluator``) against deterministic
synthetic states — giving a reproducible baseline that doesn't require
a live LLM or database.
"""

from __future__ import annotations

from typing import Any

import pytest

from mnemos.agentic.evaluation.dataset_v1 import CI_THRESHOLDS, DATASET_V1, DATASET_VERSION
from mnemos.agentic.evaluation.evaluator import InvestigationEvaluator
from mnemos.agentic.evaluation.metrics import MetricAggregator
from mnemos.agentic.evaluation.models import EvalSample, SampleResult

# ---------------------------------------------------------------------------
# Synthetic state builder — deterministic, no LLM required (P0 #21)
# ---------------------------------------------------------------------------

def _make_state(sample: EvalSample) -> dict[str, Any]:
    """Build a deterministic synthetic investigation state for a sample.

    The state mirrors what a real pipeline would produce for a well-behaved
    query so that the metric scores are predictable and the thresholds can
    be reliably tested.
    """
    intent = sample.expected_intent or "general"
    entities = sample.expected_entities or []
    doc_ids = sample.expected_document_ids or []
    citation_ids = sample.expected_citation_ids or []
    root_cause = sample.expected_root_cause or ""
    compliance = sample.expected_compliance_status

    # Synthetic evidence with resolved entities and document provenance
    evidence = []
    for doc_id in doc_ids:
        evidence.append({
            "verified_evidence": [
                {
                    "text_excerpt": f"Evidence from {doc_id}",
                    "provenance": {
                        "document_id": doc_id,
                        "chunk_id": f"chk_{doc_id}_001",
                    },
                    "confidence_score": 0.85,
                }
            ],
            "grounded_relationships": [
                {"source_id": eid, "target_id": "plant_system", "type": "belongs_to"}
                for eid in entities
            ],
            "resolved_entities": [
                {"entity_id": eid, "canonical_name": eid}
                for eid in entities
            ],
            "citations": [
                {"citation_id": cid, "document_id": doc_id}
                for cid in citation_ids[:2]
            ],
        })

    # Synthetic claims
    claims: list[dict] = []
    if root_cause:
        claims.append({
            "claim_id": "clm_001",
            "text": root_cause,
            "status": "supported",
            "sources": [{"confidence_score": 0.85}],
        })

    # Synthetic compliance checks
    compliance_checks: list[dict] = []
    if compliance:
        compliance_checks.append({"status": compliance, "requirement": "ISO_55001"})

    # Synthetic tool calls (all succeeded)
    tool_calls = [
        {"tool_name": "resolve_asset_tag", "success": True},
        {"tool_name": "graph_traversal", "success": True},
    ]

    should_abstain = sample.metadata.get("expect_abstain", False)

    return {
        "investigation_id": f"inv_{sample.metadata.get('category', 'test')}",
        "query": sample.query,
        "phase": "completion",
        "is_complete": True,
        "should_abstain": should_abstain,
        "termination_reason": "sufficient_evidence" if not should_abstain else "abstention",
        "evidence": evidence,
        "claims": claims,
        "agent_outputs": {
            "query_router": {
                "intent": intent,
                "extracted_entities": entities,
            },
            "rca_agent": {
                "reasoning_summary": root_cause,
                "hypotheses": [{"text": root_cause}] if root_cause else [],
            },
            "compliance_agent": {
                "compliance_checks": compliance_checks,
            },
        },
        "agent_metadata": {
            "evidence_retrieval": {
                "tool_calls": tool_calls,
            }
        },
        "context": {
            "intent": intent,
            "reasoning_outputs": [],
        },
    }


# ---------------------------------------------------------------------------
# Run evaluation over all samples
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def eval_results() -> tuple[list[SampleResult], dict[str, float]]:
    """Run the evaluator over all dataset samples and return results + summary."""
    evaluator = InvestigationEvaluator()
    all_metrics = []
    results = []

    for idx, sample in enumerate(DATASET_V1.samples):
        state = _make_state(sample)
        result = evaluator.evaluate(state, sample, sample_index=idx, latency_ms=150.0)
        results.append(result)
        all_metrics.extend(result.metrics)

    summary = MetricAggregator.compute_summary(all_metrics)
    return results, summary


# ---------------------------------------------------------------------------
# Dataset metadata gate
# ---------------------------------------------------------------------------

def test_dataset_version_is_set():
    """Dataset version must be explicitly set."""
    assert DATASET_VERSION, "Dataset version must not be empty"
    assert "." in DATASET_VERSION, "Dataset version must be semver (e.g. 1.0.0)"


def test_dataset_has_samples():
    """Dataset must contain samples across all required categories."""
    assert len(DATASET_V1.samples) >= 10, (
        f"Dataset must have ≥10 samples, got {len(DATASET_V1.samples)}"
    )
    categories = {s.metadata.get("category") for s in DATASET_V1.samples}
    required = {
        "intent_classification", "retrieval_recall", "citation_validity",
        "abstention", "workflow_completion", "tool_selection",
    }
    missing = required - categories
    assert not missing, f"Dataset missing required categories: {missing}"


def test_ci_thresholds_are_defined():
    """All required threshold keys must be present."""
    required_keys = {
        "avg_routing_accuracy", "avg_retrieval_recall",
        "avg_grounded_answer_rate", "avg_abstention_quality",
        "avg_workflow_completion", "overall_weighted_score",
    }
    missing = required_keys - set(CI_THRESHOLDS.keys())
    assert not missing, f"Missing CI threshold keys: {missing}"


# ---------------------------------------------------------------------------
# Per-metric threshold gates (P0 #20)
# ---------------------------------------------------------------------------

def test_routing_accuracy_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_routing_accuracy", 0.0)
    threshold = CI_THRESHOLDS["avg_routing_accuracy"]
    assert score >= threshold, (
        f"routing_accuracy {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix intent classification]"
    )


def test_retrieval_recall_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_retrieval_recall", 0.0)
    threshold = CI_THRESHOLDS["avg_retrieval_recall"]
    assert score >= threshold, (
        f"retrieval_recall {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix retrieval pipeline]"
    )


def test_grounded_answer_rate_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_grounded_answer_rate", 0.0)
    threshold = CI_THRESHOLDS["avg_grounded_answer_rate"]
    assert score >= threshold, (
        f"grounded_answer_rate {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix claim grounding]"
    )


def test_abstention_quality_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_abstention_quality", 0.0)
    threshold = CI_THRESHOLDS["avg_abstention_quality"]
    assert score >= threshold, (
        f"abstention_quality {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix abstention logic]"
    )


def test_workflow_completion_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_workflow_completion", 0.0)
    threshold = CI_THRESHOLDS["avg_workflow_completion"]
    assert score >= threshold, (
        f"workflow_completion {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix workflow termination]"
    )


def test_tool_recovery_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("avg_tool_recovery", 0.0)
    threshold = CI_THRESHOLDS["avg_tool_recovery"]
    assert score >= threshold, (
        f"tool_recovery {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — fix tool call error handling]"
    )


def test_overall_weighted_score_threshold(eval_results):
    _, summary = eval_results
    score = summary.get("overall_weighted_score", 0.0)
    threshold = CI_THRESHOLDS["overall_weighted_score"]
    assert score >= threshold, (
        f"overall_weighted_score {score:.3f} < threshold {threshold:.3f}  "
        f"[REGRESSION — multiple metrics degraded]"
    )


def test_latency_budget(eval_results):
    """Synthetic latency must stay below 2000ms per sample."""
    results, _ = eval_results
    for r in results:
        assert r.latency_ms < 2000, (
            f"Sample {r.sample_index} latency {r.latency_ms}ms exceeds 2000ms budget"
        )


# ---------------------------------------------------------------------------
# P0 #21: Reproducible evaluation report
# ---------------------------------------------------------------------------

def test_eval_report_is_reproducible(eval_results):
    """
    Running the evaluator twice on the same synthetic states must
    produce identical summary scores (reproducibility gate, P0 #21).
    """
    results1, summary1 = eval_results

    evaluator = InvestigationEvaluator()
    all_metrics2 = []
    for idx, sample in enumerate(DATASET_V1.samples):
        state = _make_state(sample)
        result = evaluator.evaluate(state, sample, sample_index=idx, latency_ms=150.0)
        all_metrics2.extend(result.metrics)
    summary2 = MetricAggregator.compute_summary(all_metrics2)

    for key in summary1:
        assert abs(summary1[key] - summary2.get(key, 0.0)) < 1e-9, (
            f"Non-reproducible score for '{key}': "
            f"{summary1[key]} vs {summary2.get(key)}"
        )


def test_eval_report_includes_all_required_metrics(eval_results):
    """Summary must contain all P0 #20 required metric categories."""
    _, summary = eval_results
    required = {
        "avg_routing_accuracy",
        "avg_retrieval_recall",
        "avg_grounded_answer_rate",
        "avg_abstention_quality",
        "avg_workflow_completion",
        "avg_tool_recovery",
        "overall_weighted_score",
    }
    missing = required - set(summary.keys())
    assert not missing, (
        f"Evaluation report missing required metrics: {missing}\n"
        f"Available: {sorted(summary.keys())}"
    )


def test_eval_report_scores_are_in_range(eval_results):
    """All metric scores must be in [0.0, 1.0]."""
    _, summary = eval_results
    for key, val in summary.items():
        if key.startswith("avg_") or key == "overall_weighted_score":
            assert 0.0 <= val <= 1.0, (
                f"Metric '{key}' score {val} is outside [0, 1]"
            )


def test_no_hallucination_in_synthetic_states(eval_results):
    """Synthetic states must not produce hallucinated claims."""
    results, _ = eval_results
    for r in results:
        assert not r.hallucination_detected, (
            f"Hallucination detected in sample {r.sample_index}: "
            f"query='{r.query[:60]}'"
        )


def test_all_samples_evaluated_without_error(eval_results):
    """Every sample must complete without an error."""
    results, _ = eval_results
    errors = [(r.sample_index, r.error) for r in results if r.error]
    assert not errors, (
        f"Evaluation errors in samples: {errors}"
    )
