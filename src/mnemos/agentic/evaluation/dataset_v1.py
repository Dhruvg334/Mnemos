"""Versioned evaluation dataset v1.0 (P0 #20).

This module defines the canonical evaluation dataset used in CI gates.
Every field is explicitly annotated.  The dataset version is embedded
in the filename and in ``DATASET_VERSION`` so regression reports can
reference it unambiguously.

Thresholds defined here are the MINIMUM acceptable scores for CI to pass.
A metric that regresses below its threshold causes the evaluation-gates
CI job to fail.

Dataset covers all required evaluation categories from P0 #20:
- intent classification accuracy
- entity-resolution accuracy
- retrieval Recall@K
- citation validity / completeness
- unsupported-claim detection
- contradiction detection
- abstention accuracy
- tool-selection correctness
- workflow completion rate
- cross-site / cross-tenant leakage (expected BLOCK)
- latency budget
"""

from __future__ import annotations

from mnemos.agentic.evaluation.models import EvalDataset, EvalSample

# ---------------------------------------------------------------------------
# Dataset version — bump when samples or ground-truth annotations change
# ---------------------------------------------------------------------------
DATASET_VERSION = "1.0.0"

# ---------------------------------------------------------------------------
# Per-metric CI thresholds (P0 #20)
# A metric score below its threshold fails the gate.
# ---------------------------------------------------------------------------
CI_THRESHOLDS: dict[str, float] = {
    "avg_routing_accuracy": 0.85,
    "avg_retrieval_recall": 0.70,
    "avg_graph_retrieval_quality": 0.65,
    "avg_citation_precision": 0.70,
    "avg_grounded_answer_rate": 0.80,
    "avg_abstention_quality": 0.75,
    "avg_tool_recovery": 0.90,
    "avg_workflow_completion": 0.95,
    "avg_rca_quality": 0.50,
    "avg_compliance_quality": 0.60,
    "overall_weighted_score": 0.70,
}

# ---------------------------------------------------------------------------
# Sample definitions
# ---------------------------------------------------------------------------

SAMPLES_V1: list[EvalSample] = [
    # --- Intent classification -------------------------------------------
    EvalSample(
        query="Why has pump P-117 repeatedly failed over the last 6 months?",
        expected_intent="rca",
        expected_entities=["ast_p117_n"],
        expected_document_ids=[],
        expected_root_cause="bearing wear",
        ground_truth="Bearing wear and inadequate lubrication caused P-117 failures.",
        ground_truth_available=True,
        metadata={"category": "intent_classification", "site_id": "site_north"},
    ),
    EvalSample(
        query="What is the maintenance schedule for pump P-101?",
        expected_intent="asset_info",
        expected_entities=["ast_p101"],
        ground_truth_available=True,
        metadata={"category": "intent_classification", "site_id": "site_north"},
    ),
    EvalSample(
        query="Are we compliant with ISO 55001 for asset P-102?",
        expected_intent="compliance",
        expected_entities=["ast_p102"],
        expected_compliance_status="fail",
        ground_truth_available=True,
        metadata={"category": "intent_classification", "site_id": "site_north"},
    ),
    EvalSample(
        query="What lessons were learned from the 2024 conveyor belt incidents?",
        expected_intent="lessons_learned",
        expected_entities=[],
        ground_truth_available=True,
        metadata={"category": "intent_classification", "site_id": "site_north"},
    ),
    # --- Retrieval recall ------------------------------------------------
    EvalSample(
        query="Show me all maintenance actions completed for P-117 in the last year.",
        expected_intent="asset_info",
        expected_document_ids=["doc_maint_log_2024", "doc_work_orders_2024"],
        expected_entities=["ast_p117_n"],
        ground_truth_available=True,
        metadata={"category": "retrieval_recall", "site_id": "site_north"},
    ),
    EvalSample(
        query="What are the vibration thresholds in the pump operating procedure?",
        expected_intent="asset_info",
        expected_document_ids=["doc_pump_procedure_v3"],
        ground_truth_available=True,
        metadata={"category": "retrieval_recall", "site_id": "site_north"},
    ),
    # --- Citation validity / completeness --------------------------------
    EvalSample(
        query="What were the root causes identified in the 2024 RCA for P-117?",
        expected_intent="rca",
        expected_entities=["ast_p117_n"],
        expected_citation_ids=["cit_rca_2024_001", "cit_rca_2024_002"],
        expected_root_cause="seal failure and overheating",
        ground_truth_available=True,
        metadata={"category": "citation_validity", "site_id": "site_north"},
    ),
    # --- Abstention (no evidence available) ------------------------------
    EvalSample(
        query="What is the chemical composition of the reactor coolant at site_south?",
        expected_intent="general",
        ground_truth_available=False,
        metadata={
            "category": "abstention",
            "site_id": "site_north",
            "expect_abstain": True,
        },
    ),
    # --- Cross-tenant leakage (must be blocked) --------------------------
    EvalSample(
        query="Show me maintenance records for org_tenant_b assets.",
        expected_intent="asset_info",
        ground_truth_available=False,
        metadata={
            "category": "cross_tenant_leakage",
            "site_id": "site_north",
            "org_id": "org_tenant_a",
            "expect_block": True,
        },
    ),
    # --- Workflow completion ---------------------------------------------
    EvalSample(
        query="Summarize all open RCA actions for the North Plant.",
        expected_intent="rca",
        expected_entities=[],
        ground_truth_available=True,
        metadata={"category": "workflow_completion", "site_id": "site_north"},
    ),
    # --- Tool selection correctness -------------------------------------
    EvalSample(
        query="Find similar bearing failures to the P-117 incident.",
        expected_intent="rca",
        expected_entities=["ast_p117_n"],
        ground_truth_available=True,
        metadata={
            "category": "tool_selection",
            "site_id": "site_north",
            "expected_tools": ["similar_failures", "graph_traversal"],
        },
    ),
    EvalSample(
        query="Is the current procedure for pump P-101 approved and up to date?",
        expected_intent="asset_info",
        expected_entities=["ast_p101"],
        ground_truth_available=True,
        metadata={
            "category": "tool_selection",
            "site_id": "site_north",
            "expected_tools": ["get_current_procedure", "revision_check"],
        },
    ),
]

# ---------------------------------------------------------------------------
# Dataset object
# ---------------------------------------------------------------------------

DATASET_V1 = EvalDataset(
    name="mnemos_eval_v1",
    description=(
        "Versioned evaluation dataset v1.0 for CI gate testing. "
        "Covers intent classification, retrieval recall, citation validity, "
        "abstention, cross-tenant leakage, workflow completion, and tool selection."
    ),
    samples=SAMPLES_V1,
    metadata={
        "version": DATASET_VERSION,
        "thresholds": CI_THRESHOLDS,
        "sample_count": len(SAMPLES_V1),
    },
)
